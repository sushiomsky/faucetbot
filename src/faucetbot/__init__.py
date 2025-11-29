"""
FaucetBot - DuckDice faucet roll automation bot

This bot automates the process of:
1. Claiming faucets for various cryptocurrencies (via browser automation)
2. Checking which cryptocurrencies have faucet balances
3. Rolling the faucet balance with configured win odds
4. Cashing out faucet balance to main balance when above threshold
5. Optionally withdrawing from main balance to external wallet

Note: Faucet claiming requires browser automation (Playwright) due to
Cloudflare protection on the DuckDice faucet API endpoints.
"""

from .api import DuckDiceAPI, DuckDiceConfig
from .bot import FaucetBot, ClaimResult

# Browser-based faucet claiming (optional dependency)
try:
    from .browser import BrowserFaucetClaimer, BrowserConfig, FaucetClaimResult
    __all__ = [
        "DuckDiceAPI", "DuckDiceConfig", "FaucetBot", "ClaimResult",
        "BrowserFaucetClaimer", "BrowserConfig", "FaucetClaimResult",
    ]
except ImportError:
    # Playwright not installed
    __all__ = ["DuckDiceAPI", "DuckDiceConfig", "FaucetBot", "ClaimResult"]

__version__ = "0.1.0"
