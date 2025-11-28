"""
FaucetBot - DuckDice faucet roll automation bot

This bot automates the process of:
1. Checking which cryptocurrencies have faucet balances
2. Rolling the faucet balance with configured win odds
3. Cashing out faucet balance to main balance when above threshold
4. Optionally withdrawing from main balance to external wallet
"""

from .api import DuckDiceAPI, DuckDiceConfig
from .bot import FaucetBot

__version__ = "0.1.0"
__all__ = ["DuckDiceAPI", "DuckDiceConfig", "FaucetBot"]
