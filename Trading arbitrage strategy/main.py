#!/usr/bin/env python3
"""
Main executable
"""

import os
import sys
import time

from TraderBetty.managers import config, handlers, data, portfolio


here = os.path.abspath("TraderBetty/TraderBetty")
root = os.path.dirname(here)
CONF = os.path.join(root, "config.ini")
KEYS = os.path.join(root, "keys.json")

# TODO: include possibility to input api and config path
connection_conf = config.ConnectionConfigLoader
full_conf = config.FullConfigLoader

CH = handlers.ConnectionHandler(CONF, connection_conf, KEYS)


def main(sleeptime=10):
    PM = portfolio.PortfolioManager(CH, CONF, full_conf)
    try:
        while True:
            pass
            time.sleep(sleeptime)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    status = main()
    sys.exit(status)
