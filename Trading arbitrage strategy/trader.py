"""The trader class"""
from TraderBetty.managers.portfolio import PortfolioManager


class Trader():
    def __init__(self, portfolio_manager):
        self.PM = portfolio_manager
        self.exchanges = self.PM.exchanges

