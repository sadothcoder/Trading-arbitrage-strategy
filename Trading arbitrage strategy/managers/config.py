"""Base classes for handlers."""
import abc
import os
from configparser import ConfigParser


class ConfigLoaderAbstract(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def __init__(self, config_file, exchanges, wallets, coins):
        self.exchanges = exchanges if exchanges else None
        self.wallets = wallets if wallets else None
        self.coins = coins if coins else None

        # Check if the path is to valid file
        if not os.path.isfile(config_file):
            raise FileNotFoundError
        # Read in the config file
        config = ConfigParser()
        config.read(config_file)

        self.config_file = config
        if self.config_file:
            self._load_config()

    @abc.abstractmethod
    def _load_config(self):
        pass


class ExchangeLoader(ConfigLoaderAbstract):
    def __init__(self, config, exchanges=None):
        super().__init__(config, exchanges=exchanges, wallets=None, coins=None)

    def _load_config(self):
        try:
            self.exchanges = self.config_file.get("main", "exchanges").split(",")
        except KeyError:
            if self.exchanges is None:
                print("No exchanges predefined.")


class WalletLoader(ConfigLoaderAbstract):
    def __init__(self, config, wallets=None):
        super().__init__(config, exchanges=None, wallets=wallets, coins=None)

    def _load_config(self):
        try:
            self.wallets = self.config_file.get("main", "wallets").split(",")
        except KeyError:
            if self.wallets is None:
                print("No wallets predefined.")


class CoinLoader(ConfigLoaderAbstract):
    def __init__(self, config, coins=None):
        super().__init__(config, exchanges=None, wallets=None, coins=coins)

    def _load_config(self):
        try:
            self.coins = self.config_file.get("main", "coins").split(",")
        except KeyError:
            if self.coins is None:
                print("No coins predefined.")


class ConfigLoader(object):
    def __init__(self, config, exchange_loader, wallet_loader, coin_loader):
        self.config_file = config
        self.exchanges = exchange_loader(config).exchanges if exchange_loader else None
        self.wallets = wallet_loader(config).wallets if wallet_loader else None
        self.coins = coin_loader(config).coins if coin_loader else None


class ConnectionConfigLoader(ConfigLoader):
    def __init__(self, config):
        super().__init__(config, ExchangeLoader, WalletLoader, None)


class FullConfigLoader(ConfigLoader):
    def __init__(self, config):
        super().__init__(config, ExchangeLoader, WalletLoader, CoinLoader)
