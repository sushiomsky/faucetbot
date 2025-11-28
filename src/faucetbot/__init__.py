"""
FaucetBot - DuckDice faucet roll automation bot

This bot automates the process of:
1. Claiming faucets for various cryptocurrencies
2. Checking which cryptocurrencies have faucet balances
3. Rolling the faucet balance with configured win odds
4. Cashing out faucet balance to main balance when above threshold
5. Optionally withdrawing from main balance to external wallet
"""

from .api import DuckDiceAPI, DuckDiceConfig
from .bot import FaucetBot, ClaimResult

__version__ = "0.1.0"
__all__ = ["DuckDiceAPI", "DuckDiceConfig", "FaucetBot", "ClaimResult"]
