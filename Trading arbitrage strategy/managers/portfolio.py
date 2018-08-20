"""Provides the portfolio manager class"""
import os
import json
from json.decoder import JSONDecodeError
import time
import datetime as dt
import calendar
import itertools

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl

from ccxt import errors
from forex_python.converter import CurrencyRates

from TraderBetty.managers.data import DataManager


class PortfolioManager(DataManager):
    def __init__(self, CH, config_path, config_loader):
        super().__init__(config_path, config_loader)
        self.c = CurrencyRates()
        self.exchanges = CH.exchanges
        self.wallets = CH.wallets

        self.updates = {ex: {} for ex in self.exchanges}

    # -------------------------------------------------------------------------
    # Interactions with the wallets
    # -------------------------------------------------------------------------
    def get_wallet_balance(self, wallet):
        w = self.wallets[wallet]
        wallet_balance = w.check_balance()
        wallet_dict = {}
        for coin in wallet_balance:
            bal = sum(list(wallet_balance[coin].values()))
            if coin == "IOTA":
                bal = bal / 1000000
            wallet_dict[coin] = bal
        balance = pd.Series(wallet_dict, index=self.balances.index)
        self.update_balance(wallet, balance)
        return wallet_dict

    # -------------------------------------------------------------------------
    # Account data collection methods
    # -------------------------------------------------------------------------
    def get_ex_balance(self, exchange, hide_zero=True, update=True):
        ex = self.exchanges[exchange]
        balance = ex.fetch_balance()["total"]
        if hide_zero:
            balance = {
                key: value for key, value in balance.items() if value > 0
            }
        if update:
            self.update_balance(exchange, balance)
            self.updates[ex.id]["balance"] = dt.datetime.today()
        return balance

    def get_trades(self, exchange, since=None, store=True):
        ex = self.exchanges[exchange]
        try:
            trades = ex.fetch_my_trades(since=since)
        except errors.ExchangeError:
            delay = ex.rateLimit if ex.id != "bitfinex" else ex.rateLimit + 2000
            delay = int(delay / 1000)
            trades = []
            symbols = []
            # Careful here, it only gets trades where balance is > 0
            coins = [c for c in self.balances.index.tolist() if
                     self.balances.loc[c, ex.id] > 0]
            for coin in coins:
                coin_symbols = [s for s in ex.symbols if coin in s]
                symbols += coin_symbols
            for symbol in list(set(symbols)):
                symbol_trades = ex.fetch_my_trades(symbol, since=since)
                trades += symbol_trades
                time.sleep(delay)
        tradesdf = pd.read_json(json.dumps(trades))
        # Add additional columns
        tradesdf["exchange"] = ex.name
        tradesdf["date"] = tradesdf["datetime"].apply(lambda d: d.date())
        self.updates[ex.id]["trades"] = dt.datetime.today()
        self.update_trades(exchange, tradesdf)
        return tradesdf

    def get_all_trades(self):
        # This whole method is probably unnecessary
        # There are duplicates in Binance and Bitfinex why?
        for exchange in self.exchanges:
            extr_path = "%s/trades_%s.csv" % (self.DATA_PATH, exchange)
            if os.path.isfile(extr_path):
                extrades = self.extrades[exchange]
            else:
                extrades = self.get_trades(exchange)
            self.update_trades(exchange, extrades)
        return self.trades

    # -------------------------------------------------------------------------
    # Price data collection methods
    # -------------------------------------------------------------------------
    def get_last_price(self, exchange, symbol, verbose=True):
        ex = self.exchanges[exchange]
        if not ex.has["fetchTicker"]:
            print("%s doesn't support fetch_ticker()" % ex.name)
            return None
        if symbol not in ex.symbols:
            if verbose:
                print("%s is not available on %s." % (symbol, ex.name))
            return None
        lp = ex.fetch_ticker(symbol)["last"]
        self.update_ex_price(exchange, symbol, lp)
        return lp

    def get_last_prices(self, exchanges=None):
        if not exchanges:
            exchanges = [ex for ex in self.exchanges]
        for exchange in exchanges:
            ex = self.exchanges[exchange]
            delay = (ex.rateLimit / 1000)
            tickers = ex.fetch_tickers() if ex.has["fetchTickers"] else None
            lpdf = self.exprices[exchange]
            bases = lpdf.index.tolist()
            quotes = list(lpdf.columns)
            symbols = [
                base + "/" + quote for base, quote in
                itertools.product(bases, quotes) if base != quote]
            symbols = filter(lambda s: s in ex.symbols, symbols)
            for symbol in symbols:
                if tickers:
                    lp = tickers.get(symbol, None)
                    lp = lp["last"] if lp else None
                    # There could be a problem here if called for a symbol that's not in my coins
                    self.update_ex_price(exchange, symbol, lp)
                else:
                    self.get_last_price(exchange, symbol, verbose=False)
                    time.sleep(delay)

    def get_all_ex_lp(self, symbol, exchanges=None):
        prices = {}
        if not exchanges:
            exchanges = [ex for ex in self.exchanges]
        for exchange in exchanges:
            lp = self.get_last_price(exchange, symbol, verbose=False)
            if lp:
                prices[exchange] = lp
        prices = sorted(prices.items(), key=lambda x: x[1], reverse=True)
        return prices

    def get_best_price(self, symbol, exchanges=None):
        prices = self.get_all_ex_lp(symbol, exchanges=exchanges)
        if not prices:
            print("%s is not tradeable on any of the exchanges." % symbol)
            return None
        bestex = prices[0][0]
        bestprice = prices[0][1]
        return bestex, bestprice

    def get_order_book(self, exchange, symbol):
        ex = self.exchanges[exchange]
        if not ex.has["fetchOrderBook"]:
            print("{:s} doesn't support fetch_order_book().")
            return None
        ob = ex.fetch_order_book(symbol)
        if not ob["datetime"]:
            ob["datetime"] = dt.datetime.now()
        if not ob["timestamp"]:
            ob["timestamp"] = calendar.timegm(dt.datetime.now().timetuple())
        obdf = pd.DataFrame(ob)
        self.update_order_book(exchange, symbol, obdf)
        return obdf

    def get_ohlcv(self, exchange, symbol, freq="1d", since=None):
        ex = self.exchanges[exchange]
        if not ex.has["fetchOHLCV"]:
            print("{:s} doesn't support fetch_ohlcv().".format(ex))
            return None
        ohlcv = ex.fetch_ohlcv(symbol, freq, since=since)
        ohlcvdf = pd.DataFrame(
            ohlcv,
            columns=["timestamp", "open", "high", "low", "close", "volume"])
        ohlcvdf["datetime"] = ohlcvdf["timestamp"].apply(
            lambda d: dt.datetime.fromtimestamp(int(d / 1000)))
        self.update_ohlcv(exchange, symbol, freq, ohlcvdf)
        return ohlcvdf

    # -------------------------------------------------------------------------
    # Price calculation methods
    # -------------------------------------------------------------------------
    def is_convertible_to(self, base):
        quotes = ["EUR", "USD", "USDT", "BTC", "ETH"]
        all_symbols = []
        for ex in self.exchanges:
            all_symbols += self.exchanges[ex].symbols
        all_symbols = set(all_symbols)
        conv_dict = {quote: base + "/" + quote in all_symbols for quote in quotes}
        return conv_dict

    def convert_coin(self, base, quote="BTC", amount=1):
        if base == quote:
            return None
        price = self.get_best_price(base + "/" + quote)
        price = price[1] if price else 0
        value = amount * price
        return value

    def advanced_convert(self, base, quote, secondary_quote="BTC", amount=1):
        if base == quote:
            return None
        price = self.get_best_price(base + "/" + quote)
        if price:
            price = price[1]
            value = amount * price
        else:
            secval = self.convert_coin(base, quote=secondary_quote,
                                       amount=amount)
            value = self.convert_coin(secondary_quote, quote=quote, amount=secval)
        return value

    def get_ttl_btcvalue(self):
        ttls = self.balances["total"]
        btcttls = []
        for coin in ttls.index.tolist():
            bal = ttls[coin]
            btcbal = 0
            if bal > 0:
                btcbal = self.convert_coin(coin, amount=bal)
            btcttls.append(btcbal)
        btcttls = pd.Series(btcttls, index=ttls.index)
        self.update_balance("btc_value", btcttls)
        return btcttls

    def get_fiatvalue(self, coin, fiat="USD"):
        ttls = self.balances["total"]
        bal = ttls[coin]
        conv_dict = self.is_convertible_to(coin)
        if conv_dict[fiat]:
            fiatbal = self.convert_coin(coin, fiat, amount=bal)
        elif conv_dict["USDT"]:
            usdtbal = self.convert_coin(coin, "USDT", amount=bal)
            fiatbal = self.convert_coin("USDT", "USD", amount=usdtbal)
        elif conv_dict["BTC"]:
            btcbal = self.convert_coin(coin, "BTC", amount=bal)
            fiatbal = self.convert_coin("BTC", "USD", amount=btcbal)
        else:
            print("{:s} cannot be converted to {:s}.".format(coin, fiat))
            fiatbal = None
        return fiatbal

    def get_ttl_eurvalue(self):
        ttls = self.balances["total"]
        eurttls = []
        for coin in ttls.index.tolist():
            bal = ttls[coin]
            eurbal = 0
            if bal > 0:
                eurbal = self.get_fiatvalue(coin, fiat="EUR")
            eurttls.append(eurbal)
        eurttls = pd.Series(eurttls, index=ttls.index)
        self.update_balance("eur_value", eurttls)
        return eurttls

    def get_prtf_value(self, quote="EUR", update=False):
        if update:
            pass
        if quote == "EUR":
            total = self.balances["eur_value"].sum()
            return total

    # -------------------------------------------------------------------------
    # Plotting methods
    # -------------------------------------------------------------------------
    def make_pie_chart(self, labels, sizes, title=None, edgecolor="k"):
        # Set style parameters
        if not edgecolor:
            mpl.rcParams['patch.force_edgecolor'] = False
        else:
            mpl.rcParams['patch.force_edgecolor'] = True
            mpl.rcParams['patch.edgecolor'] = edgecolor

        # Make figure
        fig1, ax1 = plt.subplots()
        ax1.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=90)
        ax1.axis("equal")
        if title:
            ax1.set_title(title)
        plt.show()
