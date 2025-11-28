"""
DuckDice API client for faucet bot operations.

Provides API methods for:
- Getting user info and balances (including faucet balances)
- Playing dice with faucet balance
- Faucet cashout to main balance
- Withdrawals from main balance
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests


@dataclass
class DuckDiceConfig:
    """Configuration for DuckDice API client."""
    api_key: str
    base_url: str = "https://duckdice.io/api"
    timeout: int = 30
    request_delay_ms: int = 1000


class DuckDiceAPI:
    """DuckDice API client with methods for faucet bot operations."""

    def __init__(self, config: DuckDiceConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "User-Agent": "FaucetBot/1.0.0",
                "Accept": "*/*",
                "Cache-Control": "no-cache",
            }
        )
        self._last_request_time = 0.0

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        now = time.time()
        elapsed = now - self._last_request_time
        required_delay = self.config.request_delay_ms / 1000.0
        if elapsed < required_delay:
            time.sleep(required_delay - elapsed)
        self._last_request_time = time.time()

    def _make_request(
        self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make an API request with rate limiting and error handling."""
        self._rate_limit()
        url = f"{self.config.base_url}/{endpoint}"
        params = {"api_key": self.config.api_key}
        try:
            if method.upper() == "GET":
                response = self.session.get(
                    url, params=params, timeout=self.config.timeout
                )
            elif method.upper() == "POST":
                response = self.session.post(
                    url, params=params, json=data, timeout=self.config.timeout
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error: {e}", file=sys.stderr)
            if hasattr(e, "response") and e.response is not None:
                print(f"Response: {e.response.text}", file=sys.stderr)
            raise
        except requests.exceptions.RequestException as e:
            print(f"Request Error: {e}", file=sys.stderr)
            raise
        except json.JSONDecodeError as e:
            print(f"JSON Decode Error: {e}", file=sys.stderr)
            raise

    def get_user_info(self) -> Dict[str, Any]:
        """
        Get user info including balances.

        Returns dict with structure:
        {
            "user": {...},
            "balances": [
                {
                    "currency": "btc",
                    "main": "0.00001234",
                    "faucet": "0.00000100",
                    ...
                },
                ...
            ]
        }
        """
        return self._make_request("GET", "bot/user-info")

    def get_faucet_balances(self) -> List[Dict[str, Any]]:
        """
        Get all currencies with non-zero faucet balance.

        Returns list of dicts with currency and faucet balance info.
        """
        user_info = self.get_user_info()
        balances = user_info.get("balances", [])
        faucet_balances = []
        for bal in balances:
            if bal is None:
                continue
            faucet = bal.get("faucet")
            if faucet is not None:
                try:
                    faucet_val = float(faucet)
                    if faucet_val > 0:
                        faucet_balances.append(bal)
                except (ValueError, TypeError):
                    continue
        return faucet_balances

    def get_currency_stats(self, symbol: str) -> Dict[str, Any]:
        """Get statistics for a specific currency."""
        return self._make_request("GET", f"bot/stats/{symbol}")

    def play_dice(
        self,
        symbol: str,
        amount: str,
        chance: str,
        is_high: bool,
        faucet: bool = True,
    ) -> Dict[str, Any]:
        """
        Play dice game.

        Args:
            symbol: Currency symbol (e.g., 'btc', 'eth')
            amount: Bet amount as string
            chance: Win chance percentage as string (e.g., '50')
            is_high: True to bet on high numbers, False for low
            faucet: True to use faucet balance, False for main balance

        Returns:
            API response with bet result
        """
        data = {
            "symbol": symbol,
            "amount": amount,
            "chance": chance,
            "isHigh": is_high,
            "faucet": faucet,
        }
        return self._make_request("POST", "dice/play", data)

    def play_range_dice(
        self,
        symbol: str,
        amount: str,
        range_values: List[int],
        is_in: bool,
        faucet: bool = True,
    ) -> Dict[str, Any]:
        """
        Play range dice game.

        Args:
            symbol: Currency symbol
            amount: Bet amount as string
            range_values: [min, max] range to bet on
            is_in: True if betting number is in range, False otherwise
            faucet: True to use faucet balance

        Returns:
            API response with bet result
        """
        data = {
            "symbol": symbol,
            "amount": amount,
            "range": range_values,
            "isIn": is_in,
            "faucet": faucet,
        }
        return self._make_request("POST", "range-dice/play", data)

    def faucet_cashout(self, symbol: str) -> Dict[str, Any]:
        """
        Cash out faucet balance to main balance.

        Args:
            symbol: Currency symbol to cash out

        Returns:
            API response with cashout result
        """
        data = {"symbol": symbol}
        return self._make_request("POST", "faucet/cashout", data)

    def withdraw(
        self,
        symbol: str,
        address: str,
        amount: str,
    ) -> Dict[str, Any]:
        """
        Withdraw from main balance to external wallet.

        Args:
            symbol: Currency symbol to withdraw
            address: Destination wallet address
            amount: Amount to withdraw as string

        Returns:
            API response with withdrawal result
        """
        data = {
            "symbol": symbol,
            "address": address,
            "amount": amount,
        }
        return self._make_request("POST", "withdraw", data)

    def get_currencies(self) -> List[Dict[str, Any]]:
        """
        Get list of supported currencies with their info.

        Returns list of currency info dicts including exchange rates.
        """
        return self._make_request("GET", "currencies")
