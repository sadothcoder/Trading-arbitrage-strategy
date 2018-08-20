"""Implementation of the etherscan.io API"""
import os
import json
from configparser import ConfigParser
import requests
import pandas as pd
from bs4 import BeautifulSoup

# base url for own scrape
BASE_URL = "https://api.etherscan.io/api"
MODULE = "account"
API_KEY = "2T34JM3AT6MUHK26WPMCQ17XEBGMTWQUXU"
PATH = "data"


class Scanner:
    def __init__(self, configfile):
        self.session = requests.Session()

        self.config = ConfigParser()

        if not os.path.isfile(configfile):
            raise ValueError

        self.config.read(configfile)
        self.config_addresses = self.config.get('ether_wallet', 'addresses').split(',')

    def check_balance(self):
        addresses = self.config_addresses
        if not addresses:
            print("No valid addresses found. Aborting!")
            return None
        if len(addresses) > 1:
            action = "multibalance"
            addresses = ",".join(addresses)
        else:
            action = "balance"
            addresses = addresses[0]
        url = BASE_URL + (
            "?module={0:s}&action={1:s}&address={2:s}&tag=latest&apikey={3:s}".
                format(MODULE, action, addresses, API_KEY)
        )
        r = self.session.get(url)
        content = r.content.decode('utf-8', 'ignore')
        balances = json.loads(content)
        return balances
