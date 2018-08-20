"""Sets up the connection to the exchange and wallet APIs."""
import os
import json
from json.decoder import JSONDecodeError
import pandas as pd

import ccxt

from TraderBetty.managers import wallets


class Handler(object):
    def __init__(self, config, config_loader):
        self.config_loader = config_loader(config)


class ConnectionHandler(Handler):
    def __init__(self, config_path, config_loader, key_file):
        super().__init__(config_path, config_loader)
        # Check if the path is to a valid file
        if not os.path.isfile(key_file):
            raise ValueError

        self.exchanges = self.config_loader.exchanges
        self.wallets = self.config_loader.wallets

        # Initiate exchanges
        self.exchanges = {exchange: None for exchange in self.exchanges}
        self._load_exchanges(key_file)
        self._initiate_all_markets()

        self.wallets = {wallet: None for wallet in self.wallets}
        self.load_wallets()

    # -------------------------------------------------------------------------
    # Setup functions
    # -------------------------------------------------------------------------
    def _load_exchanges(self, key_file):
        # Load the api keys from keys file
        with open(key_file) as file:
            keys = json.load(file)
        for exchange in self.exchanges:
            exchange_config = {}
            exchange_config.update(keys[exchange])
            self.exchanges[exchange] = getattr(ccxt, exchange)(exchange_config)

    def _initiate_all_markets(self, reload=False):
        """

        :param reload:
        :return:
        """
        for exchange in self.exchanges:
            try:
                self.exchanges[exchange].load_markets(reload=reload)
            except JSONDecodeError:
                print("Exchange %s seems to be unavailable at the moment" %
                      exchange.name)

    def load_wallets(self):
        config = self.config_loader.config_file
        # TODO: implement wallet address tracking for other coins
        for wallet in self.wallets:
            if wallet == "iota_wallet":
                self.wallets[wallet] = wallets.IotaWallet(config)


class DataHandler(Handler):
    def __init__(self, config_path, config_loader):
        super().__init__(config_path, config_loader)
        self.DATA_PATH = "data"
        self.BALANCE_PATH = self.DATA_PATH + "/balances.csv"
        self.TRADES_PATH = self.DATA_PATH + "/trades.csv"
        self.ORDERBOOK_PATH = self.DATA_PATH + "/order_books"
        self.OHLCV_PATH = self.DATA_PATH + "/ohlcv"
        self.coins = self.config_loader.coins
        self.exchanges = self.config_loader.exchanges
        self.wallets = self.config_loader.wallets
        self.extrades_paths = [self.DATA_PATH + "/trades_%s.csv" %
                               exchange for exchange in self.exchanges]

        if not os.path.isfile(self.BALANCE_PATH):
            balances = pd.DataFrame(
                index=self.coins,
                columns=list(self.exchanges) +
                        ["total", "btc_value", "eur_value"])
            self.store_csv(balances, self.BALANCE_PATH)
        if not os.path.isfile(self.TRADES_PATH):
            trades = pd.DataFrame(columns=[
                "exchange", "id", "date", "datetime", "timestamp"])
            self.store_csv(trades, self.TRADES_PATH, index=False)
        for exchange in self.exchanges:
            extrades_path = self.DATA_PATH + "/trades_%s.csv" % exchange
            if not os.path.isfile(extrades_path):
                extrades = pd.DataFrame(columns=[
                    "exchange", "id", "date", "datetime", "timestamp"])
                self.store_csv(extrades, extrades_path, index=False)
            exprice_path = self.DATA_PATH + "/prices_%s.csv" % exchange
            if not os.path.isfile(exprice_path):
                exprices = pd.DataFrame(index=self.coins, columns=self.coins)
                self.store_csv(exprices, exprice_path)

        self.balances = self._load_balances()
        self.trades = self._load_trades()

        self.extrades = {exchange: self._load_ex_trades(exchange) for
                         exchange in self.exchanges}
        self.exprices = {exchange: self._load_ex_prices(exchange) for
                         exchange in self.exchanges}

        all_order_books = [f for f in os.listdir(self.ORDERBOOK_PATH) if
                         os.path.isfile(self.ORDERBOOK_PATH + "/" + f)]
        self.order_books = {ex: {} for ex in self.exchanges}
        for ex in self.order_books:
            ex_files = [f for f in all_order_books if ex in f]
            symbols = [
                "/".join([s.split("_")[-2], s.split("_")[-1].split(".")[0]])
                for s in ex_files]
            ex_books = [pd.read_csv(
                self.ORDERBOOK_PATH + "/" + f,
                sep=";", parse_dates=True, index_col=["datetime"]
            ) for f in ex_files]
            self.order_books[ex] = {s: ob for s, ob in zip(symbols, ex_books)}

        all_ohlcvs = [f for f in os.listdir(self.OHLCV_PATH) if
                      os.path.isfile(self.OHLCV_PATH + "/" + f)]
        self.ohlcvs = {ex: {} for ex in self.exchanges}
        for ex in self.ohlcvs:
            ex_files = [f for f in all_ohlcvs if ex in f]
            symbols = ["/".join([s.split("_")[-3],
                                 s.split("_")[-2] +
                                 s.split("_")[-1].split(".")[0]]) for
                       s in ex_files]
            ex_ohlcvs = [pd.read_csv(
                self.OHLCV_PATH + "/" + f,
                sep=";", parse_dates=True, index_col=["datetime"]
            ) for f in ex_files]
            self.ohlcvs[ex] = {s: ohlcv for s, ohlcv in zip(symbols, ex_ohlcvs)}

    def _load_balances(self):
        try:
            balances = pd.read_csv(self.BALANCE_PATH, sep=";", index_col=0)
            return balances
        except FileNotFoundError:
            print("Balance file was not found.")

    def _load_trades(self):
        try:
            trades = pd.read_csv(self.TRADES_PATH,
                                 sep=";",
                                 parse_dates=["date", "datetime", "timestamp"],
                                 index_col=["exchange", "id"])
            return trades
        except FileNotFoundError:
            print("Trade file was not found.")

    def _load_ex_trades(self, exchange):
        try:
            trades = pd.read_csv("%s/trades_%s.csv" % (self.DATA_PATH, exchange),
                                 sep=";",
                                 parse_dates=["date", "datetime", "timestamp"],
                                 index_col=["exchange", "id"])
            return trades
        except FileNotFoundError:
            print("Trades for %s were not found." % exchange)

    def _load_ex_prices(self, exchange):
        try:
            prices = pd.read_csv("%s/prices_%s.csv" % (self.DATA_PATH, exchange),
                                 sep=";", index_col=0)
            return prices
        except FileNotFoundError:
            print("Prices for %s were not found." % exchange)

    def store_csv(self, df, path, index=True):
        df.to_csv(path, sep=";", index=index)
