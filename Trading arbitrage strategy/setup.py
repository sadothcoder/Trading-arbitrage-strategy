
from setuptools import setup, find_packages


VERSION = "0.0.1"


setup(name="TraderBetty", version=VERSION, author="iuvbio",
      author_email="",
      url="https://github.com/iuvbio/traderbetty.git",
      test_suite="", tests_require=[],
      packages=find_packages(exclude=["data", "docs", "tests*"]),
      install_requires=["ccxt", "pandas"],
      description="Cryptocurrency portfolio manager and arbitrage trader",
      license="MIT",  classifiers=["Development Status :: 4 - Beta",
                                   "Intended Audience :: Developers"],
      )
