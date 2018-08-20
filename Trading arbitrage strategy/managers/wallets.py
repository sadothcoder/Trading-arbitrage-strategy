"""Iota wallet classes"""
#!/usr/bin/env python3

import os
from configparser import ConfigParser
from iota import Iota, Address, BadApiResponse, Hash


class IotaWallet(object):
    def __init__(self, config_path):
        self.config = ConfigParser()

        if not os.path.isfile(config_path):
            raise ValueError

        self.config.read(config_path)
        self.config_addresses = self.config.get('iota_wallet', 'addresses').split(',')

    def check_balance(self):
        iota_dict = {}
        addresses = []

        for input_address in self.config_addresses:
            if len(input_address) != Hash.LEN:
                print('Address %s is not %d characters. Skipping.' % (
                    input_address, Hash.LEN))
                print('Make sure it does not include the checksum.')
                continue

            addy = Address(input_address)
            addresses.append(addy)

        if len(addresses) == 0:
            print('No valid addresses found, exiting.')
        else:
            config_uri = self.config.get('iota_wallet', 'uri')
            api = Iota(config_uri)
            response = None

            try:
                print('Connecting to tangle via {uri}.'.format(uri=config_uri))
                response = api.get_balances(addresses)
            except ConnectionError as e:
                print('{uri} is not responding.'.format(uri=config_uri))
                print(e)
            except BadApiResponse as e:
                print('{uri} is not responding properly.'.format(uri=config_uri))
                print(e)

            if response:
                iota_dict = {"IOTA": {address: response['balances'][i] for i, address in enumerate(addresses)}}

        return iota_dict
