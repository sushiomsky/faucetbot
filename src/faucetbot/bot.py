"""
FaucetBot - Core bot logic for automated faucet roll, cashout and withdrawal.

Workflow:
1. Check all currencies with faucet balance
2. For each currency with balance:
   a. Bet all-in with configured win chance
   b. If win and balance >= threshold USD value, cashout to main
   c. If auto-withdraw enabled and main balance >= threshold, withdraw
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Dict, List, Optional

import requests

from .api import DuckDiceAPI


@dataclass
class BotConfig:
    """Configuration for FaucetBot."""
    # Betting configuration - Progressive strategy
    # First faucet: base_win_chance (0.01%), second: 0.02%, etc.
    base_win_chance: float = 0.01  # Starting win chance percentage
    win_chance_increment: float = 0.01  # Increment per faucet
    bet_high: bool = True  # Bet on high numbers
    
    # Cashout thresholds
    cashout_min_usd: float = 20.0  # Minimum USD to trigger faucet cashout
    
    # Withdrawal configuration
    auto_withdraw: bool = False
    withdrawal_address: str = ""
    withdrawal_min_usd: float = 20.0  # Minimum USD to trigger withdrawal
    
    # Price cache settings
    price_refresh_sec: int = 300  # Refresh prices every 5 minutes
    
    # Logging
    verbose: bool = True


@dataclass
class RollResult:
    """Result of a faucet roll operation."""
    currency: str
    bet_amount: str
    win: bool
    profit: str
    new_faucet_balance: str
    new_main_balance: str
    roll_number: int
    win_chance: float = 0.0  # The win chance used for this roll
    cashout_triggered: bool = False
    cashout_success: bool = False
    withdrawal_triggered: bool = False
    withdrawal_success: bool = False
    usd_value: float = 0.0


@dataclass
class ClaimResult:
    """Result of a faucet claim operation."""
    currency: str
    success: bool
    amount: str = "0"
    error: str = ""
    cooldown_remaining: int = 0  # Seconds until next claim available


class FaucetBot:
    """
    Automated faucet roll bot for DuckDice.
    
    Handles the full workflow of checking faucet balances, rolling,
    cashing out when profitable, and optionally withdrawing.
    """
    
    # CoinGecko API base URL for price lookups
    COINGECKO_API_URL = "https://api.coingecko.com/api/v3/simple/price"
    
    # Map common cryptocurrency symbols to CoinGecko IDs
    COINGECKO_ID_MAP: Dict[str, str] = {
        "btc": "bitcoin",
        "eth": "ethereum",
        "ltc": "litecoin",
        "doge": "dogecoin",
        "xrp": "ripple",
        "trx": "tron",
        "bnb": "binancecoin",
        "usdt": "tether",
        "usdc": "usd-coin",
        "sol": "solana",
        "ada": "cardano",
        "dot": "polkadot",
        "matic": "matic-network",
        "shib": "shiba-inu",
        "avax": "avalanche-2",
        "link": "chainlink",
        "xlm": "stellar",
        "atom": "cosmos",
        "etc": "ethereum-classic",
        "bch": "bitcoin-cash",
        "xmr": "monero",
        "dash": "dash",
        "zec": "zcash",
        "neo": "neo",
        "eos": "eos",
    }
    
    def __init__(
        self,
        api: DuckDiceAPI,
        config: BotConfig,
        logger: Optional[Callable[[str], None]] = None,
    ):
        self.api = api
        self.config = config
        self.logger = logger or print
        self._price_cache: Dict[str, float] = {}
        self._price_cache_time: Dict[str, float] = {}

    def log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.config.verbose:
            self.logger(message)

    def _get_usd_price(self, symbol: str) -> float:
        """
        Get USD price for a currency using CoinGecko API.
        
        Uses a cache to avoid excessive API calls.
        """
        symbol_lower = symbol.lower()
        now = time.time()
        
        # Check cache
        if symbol_lower in self._price_cache:
            cache_time = self._price_cache_time.get(symbol_lower, 0)
            if (now - cache_time) < self.config.price_refresh_sec:
                return self._price_cache[symbol_lower]
        
        coingecko_id = self.COINGECKO_ID_MAP.get(symbol_lower, symbol_lower)
        
        try:
            url = f"{self.COINGECKO_API_URL}?ids={coingecko_id}&vs_currencies=usd"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            price = float(data.get(coingecko_id, {}).get("usd", 0.0))
            if price > 0:
                self._price_cache[symbol_lower] = price
                self._price_cache_time[symbol_lower] = now
                return price
        except Exception as e:
            self.log(f"Warning: Failed to fetch price for {symbol}: {e}")
        
        # Return cached price if available, otherwise 0
        return self._price_cache.get(symbol_lower, 0.0)

    def _to_decimal(self, value: Any) -> Decimal:
        """Safely convert a value to Decimal."""
        if value is None:
            return Decimal(0)
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return Decimal(0)

    def _calculate_usd_value(self, amount: Decimal, symbol: str) -> float:
        """Calculate USD value of an amount."""
        price = self._get_usd_price(symbol)
        return float(amount) * price

    def get_faucet_currencies(self) -> List[Dict[str, Any]]:
        """
        Get all currencies with non-zero faucet balance.
        
        Returns list of dicts with currency info and USD values.
        """
        faucet_balances = self.api.get_faucet_balances()
        result = []
        
        for bal in faucet_balances:
            currency = bal.get("currency", "").lower()
            faucet_amount = self._to_decimal(bal.get("faucet", 0))
            main_amount = self._to_decimal(bal.get("main", 0))
            
            usd_value = self._calculate_usd_value(faucet_amount, currency)
            
            result.append({
                "currency": currency,
                "faucet_balance": str(faucet_amount),
                "main_balance": str(main_amount),
                "faucet_usd": usd_value,
            })
        
        return result

    def get_faucet_info(self) -> Dict[str, Any]:
        """
        Get faucet info including available currencies and limits.
        
        Returns dict with faucet status information.
        """
        return self.api.get_faucet_info()

    def check_faucet_claim(self, currency: str) -> Dict[str, Any]:
        """
        Check if faucet can be claimed for a specific currency.
        
        Args:
            currency: Currency symbol (e.g., 'sol', 'btc')
            
        Returns:
            Dict with claim availability info
        """
        return self.api.check_faucet_claim(currency)

    def claim_faucet(self, currency: str) -> ClaimResult:
        """
        Claim the faucet for a specific currency.
        
        Args:
            currency: Currency symbol to claim (e.g., 'sol', 'btc')
            
        Returns:
            ClaimResult with claim outcome
        """
        self.log(f"Claiming faucet for {currency.upper()}...")
        
        result = ClaimResult(
            currency=currency,
            success=False,
        )
        
        try:
            # First check if claim is available
            check_response = self.api.check_faucet_claim(currency)
            
            # Check if there's a cooldown or other restriction
            if check_response.get("error"):
                result.error = check_response.get("error", "Unknown error")
                self.log(f"  Cannot claim: {result.error}")
                return result
            
            # Attempt to claim the faucet
            response = self.api.claim_faucet(currency)
            
            # Check for successful claim
            if response.get("error"):
                result.error = response.get("error", "Claim failed")
                self.log(f"  Claim failed: {result.error}")
            else:
                result.success = True
                # Extract amount from response
                result.amount = str(response.get("amount", "0"))
                self.log(f"  Successfully claimed {result.amount} {currency.upper()}!")
                
        except Exception as e:
            result.error = str(e)
            self.log(f"  Claim error: {e}")
        
        return result

    def claim_all_faucets(self) -> List[ClaimResult]:
        """
        Attempt to claim faucets for all available currencies.
        
        Returns list of ClaimResults for each currency attempted.
        """
        results = []
        
        self.log("Fetching available faucets...")
        
        try:
            faucet_info = self.api.get_faucet_info()
            
            # Get currencies that can be claimed
            currencies = faucet_info.get("currencies", [])
            if not currencies:
                # If no currencies list, try to get from user info
                user_info = self.api.get_user_info()
                balances = user_info.get("balances", [])
                currencies = [bal.get("currency") for bal in balances if bal]
            
            self.log(f"Found {len(currencies)} currencies to try...")
            
            for currency in currencies:
                if not currency:
                    continue
                    
                try:
                    result = self.claim_faucet(currency.lower())
                    results.append(result)
                    
                    # Add delay between claims to avoid rate limiting
                    if result.success:
                        time.sleep(1)
                except Exception as e:
                    self.log(f"  Error claiming {currency}: {e}")
                    results.append(ClaimResult(
                        currency=currency,
                        success=False,
                        error=str(e),
                    ))
                    
        except Exception as e:
            self.log(f"Error fetching faucet info: {e}")
        
        return results
        """
        Roll the full faucet balance for a currency.
        
        Args:
            currency: Currency symbol
            amount: Amount to bet (usually full faucet balance)
            win_chance: Win chance percentage for this roll
            
        Returns:
            RollResult with bet outcome and any triggered actions
        """
        self.log(f"Rolling {amount} {currency.upper()} with {win_chance}% chance...")
        
        result = RollResult(
            currency=currency,
            bet_amount=amount,
            win=False,
            profit="0",
            new_faucet_balance="0",
            new_main_balance="0",
            roll_number=0,
            win_chance=win_chance,
        )
        
        try:
            # Place the bet
            response = self.api.play_dice(
                symbol=currency,
                amount=amount,
                chance=str(win_chance),
                is_high=self.config.bet_high,
                faucet=True,
            )
            
            bet = response.get("bet", {})
            user = response.get("user", {})
            
            result.win = bool(bet.get("result"))
            result.profit = str(bet.get("profit", "0"))
            result.roll_number = int(bet.get("number", 0))
            
            # Get updated balances
            balances = user.get("balances", [])
            for bal in balances:
                if bal.get("currency", "").lower() == currency.lower():
                    result.new_faucet_balance = str(bal.get("faucet", "0"))
                    result.new_main_balance = str(bal.get("main", "0"))
                    break
            
            # Calculate USD value
            new_faucet = self._to_decimal(result.new_faucet_balance)
            result.usd_value = self._calculate_usd_value(new_faucet, currency)
            
            status = "WIN" if result.win else "LOSS"
            self.log(f"  {status}! Roll: {result.roll_number}, Profit: {result.profit}")
            self.log(f"  New faucet balance: {result.new_faucet_balance} (~${result.usd_value:.2f} USD)")
            
            # Check if we should cashout
            if result.usd_value >= self.config.cashout_min_usd:
                result.cashout_triggered = True
                self.log(f"  Faucet balance >= ${self.config.cashout_min_usd}, triggering cashout...")
                try:
                    self.api.faucet_cashout(currency)
                    result.cashout_success = True
                    self.log(f"  Cashout successful!")
                    
                    # Check for auto-withdrawal
                    if self.config.auto_withdraw and self.config.withdrawal_address:
                        # Refresh user info to get new main balance
                        user_info = self.api.get_user_info()
                        for bal in user_info.get("balances", []):
                            if bal.get("currency", "").lower() == currency.lower():
                                main_bal = self._to_decimal(bal.get("main", 0))
                                main_usd = self._calculate_usd_value(main_bal, currency)
                                
                                if main_usd >= self.config.withdrawal_min_usd:
                                    result.withdrawal_triggered = True
                                    self.log(f"  Main balance ${main_usd:.2f} >= ${self.config.withdrawal_min_usd}, withdrawing...")
                                    try:
                                        self.api.withdraw(
                                            symbol=currency,
                                            address=self.config.withdrawal_address,
                                            amount=str(main_bal),
                                        )
                                        result.withdrawal_success = True
                                        self.log(f"  Withdrawal initiated!")
                                    except Exception as e:
                                        self.log(f"  Withdrawal failed: {e}")
                                break
                except Exception as e:
                    self.log(f"  Cashout failed: {e}")
                    
        except Exception as e:
            self.log(f"  Roll failed: {e}")
            raise
        
        return result

    def run_single_pass(self) -> List[RollResult]:
        """
        Run a single pass over all faucet balances.
        
        For each currency with faucet balance:
        1. Roll all-in with progressive win chance (0.01%, 0.02%, 0.03%, ...)
        2. Cashout if threshold met
        3. Withdraw if configured
        
        Returns list of RollResults for each currency processed.
        """
        results = []
        
        self.log("Checking faucet balances...")
        faucet_currencies = self.get_faucet_currencies()
        
        if not faucet_currencies:
            self.log("No currencies with faucet balance found.")
            return results
        
        self.log(f"Found {len(faucet_currencies)} currencies with faucet balance:")
        for fc in faucet_currencies:
            self.log(f"  {fc['currency'].upper()}: {fc['faucet_balance']} (~${fc['faucet_usd']:.4f} USD)")
        
        # Progressive win chance: 1st faucet = base_win_chance, 2nd = base + increment, etc.
        faucet_index = 0
        for fc in faucet_currencies:
            currency = fc["currency"]
            amount = fc["faucet_balance"]
            
            # Skip if amount is essentially zero
            if self._to_decimal(amount) <= 0:
                continue
            
            faucet_index += 1
            # Calculate progressive win chance
            win_chance = self.config.base_win_chance + (faucet_index - 1) * self.config.win_chance_increment
            
            try:
                result = self.roll_faucet(currency, amount, win_chance)
                results.append(result)
            except Exception as e:
                self.log(f"Error processing {currency}: {e}")
        
        return results

    def run_continuous(
        self,
        interval_sec: int = 60,
        stop_on_cashout: bool = False,
        max_iterations: Optional[int] = None,
    ) -> None:
        """
        Run the bot continuously.
        
        Args:
            interval_sec: Seconds between each pass
            stop_on_cashout: Stop after a successful cashout
            max_iterations: Maximum number of passes (None for infinite)
        """
        iteration = 0
        
        self.log("Starting FaucetBot in continuous mode...")
        self.log(f"  Progressive win chance: {self.config.base_win_chance}%, +{self.config.win_chance_increment}% per faucet")
        self.log(f"  Cashout threshold: ${self.config.cashout_min_usd}")
        self.log(f"  Auto-withdraw: {self.config.auto_withdraw}")
        self.log(f"  Interval: {interval_sec}s")
        
        try:
            while True:
                iteration += 1
                self.log(f"\n=== Pass {iteration} ===")
                
                results = self.run_single_pass()
                
                # Check for successful cashout
                if stop_on_cashout:
                    for r in results:
                        if r.cashout_success:
                            self.log("Cashout successful! Stopping as requested.")
                            return
                
                # Check iteration limit
                if max_iterations is not None and iteration >= max_iterations:
                    self.log(f"Reached max iterations ({max_iterations}). Stopping.")
                    return
                
                # Wait for next pass
                self.log(f"Waiting {interval_sec}s before next pass...")
                time.sleep(interval_sec)
                
        except KeyboardInterrupt:
            self.log("\nBot stopped by user.")
