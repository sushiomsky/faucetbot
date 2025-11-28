"""
FaucetBot CLI - Command line interface for the DuckDice faucet bot.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from .api import DuckDiceAPI, DuckDiceConfig
from .bot import FaucetBot, BotConfig


def get_env_float(key: str, default: float) -> float:
    """Get a float from environment variable."""
    val = os.environ.get(key)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        return default


def get_env_int(key: str, default: int) -> int:
    """Get an int from environment variable."""
    val = os.environ.get(key)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def get_env_bool(key: str, default: bool) -> bool:
    """Get a boolean from environment variable."""
    val = os.environ.get(key)
    if val is None:
        return default
    return val.lower() in ("true", "1", "yes", "on")


def main(args: Optional[list[str]] = None) -> int:
    """Main entry point for the CLI."""
    # Load .env file if available
    if load_dotenv is not None:
        load_dotenv()
    
    parser = argparse.ArgumentParser(
        prog="faucetbot",
        description="DuckDice faucet roll automation bot with progressive win chance strategy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  faucetbot claim                # Claim all available faucets
  faucetbot claim sol            # Claim faucet for specific currency
  faucetbot run                  # Run single pass (progressive: 0.01%, 0.02%, ...)
  faucetbot run --continuous     # Run continuously
  faucetbot status               # Show current faucet balances
  faucetbot roll btc             # Roll specific currency only
  faucetbot roll btc --chance 1  # Roll with custom 1% win chance

Progressive Strategy:
  Faucets are rolled all-in with increasing win chances:
  - 1st faucet: 0.01% (base chance)
  - 2nd faucet: 0.02% (base + increment)
  - 3rd faucet: 0.03% (base + 2*increment)
  - And so on...

Environment Variables:
  DUCKDICE_API_KEY              API key (required)
  DUCKDICE_BASE_URL             API base URL
  DUCKDICE_TIMEOUT              Request timeout (seconds)
  FAUCET_BASE_WIN_CHANCE        Base win chance for 1st faucet (default: 0.01)
  FAUCET_WIN_CHANCE_INCREMENT   Win chance increment per faucet (default: 0.01)
  FAUCET_CASHOUT_MIN_USD        Min USD for cashout (default: 20)
  AUTO_WITHDRAW                 Enable auto-withdrawal (default: false)
  WITHDRAWAL_ADDRESS            Wallet address for withdrawal
  WITHDRAWAL_MIN_USD            Min USD for withdrawal (default: 20)
  REQUEST_DELAY_MS              Delay between requests (default: 1000)
        """,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # status command
    status_parser = subparsers.add_parser("status", help="Show current faucet balances")
    status_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    
    # run command
    run_parser = subparsers.add_parser("run", help="Run the faucet bot")
    run_parser.add_argument(
        "-c", "--continuous",
        action="store_true",
        help="Run continuously",
    )
    run_parser.add_argument(
        "-i", "--interval",
        type=int,
        default=60,
        help="Interval between passes in seconds (default: 60)",
    )
    run_parser.add_argument(
        "--stop-on-cashout",
        action="store_true",
        help="Stop after a successful cashout",
    )
    run_parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum number of iterations",
    )
    run_parser.add_argument(
        "--base-chance",
        type=float,
        default=None,
        help="Base win chance for first faucet (default: 0.01%%)",
    )
    run_parser.add_argument(
        "--chance-increment",
        type=float,
        default=None,
        help="Win chance increment per faucet (default: 0.01%%)",
    )
    run_parser.add_argument(
        "--cashout-min",
        type=float,
        default=None,
        help="Minimum USD for cashout (overrides FAUCET_CASHOUT_MIN_USD)",
    )
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    
    # roll command (single currency)
    roll_parser = subparsers.add_parser("roll", help="Roll a specific currency")
    roll_parser.add_argument("currency", help="Currency symbol (e.g., btc, eth)")
    roll_parser.add_argument(
        "--chance",
        type=float,
        default=None,
        help="Win chance percentage",
    )
    roll_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    
    # claim command
    claim_parser = subparsers.add_parser("claim", help="Claim faucet for a currency")
    claim_parser.add_argument(
        "currency",
        nargs="?",
        default=None,
        help="Currency symbol (e.g., sol, btc). If not specified, tries all currencies.",
    )
    claim_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    
    parsed = parser.parse_args(args)
    
    if not parsed.command:
        parser.print_help()
        return 1
    
    # Get API key
    api_key = os.environ.get("DUCKDICE_API_KEY")
    if not api_key:
        print("Error: DUCKDICE_API_KEY environment variable is required", file=sys.stderr)
        print("Set it in your .env file or export it in your shell", file=sys.stderr)
        return 1
    
    # Create API config
    api_config = DuckDiceConfig(
        api_key=api_key,
        base_url=os.environ.get("DUCKDICE_BASE_URL", "https://duckdice.io/api"),
        timeout=get_env_int("DUCKDICE_TIMEOUT", 30),
        request_delay_ms=get_env_int("REQUEST_DELAY_MS", 1000),
    )
    
    api = DuckDiceAPI(api_config)
    
    # Handle commands
    if parsed.command == "status":
        return cmd_status(api, verbose=parsed.verbose)
    elif parsed.command == "run":
        # Create bot config with progressive win chance strategy
        bot_config = BotConfig(
            base_win_chance=parsed.base_chance or get_env_float("FAUCET_BASE_WIN_CHANCE", 0.01),
            win_chance_increment=parsed.chance_increment or get_env_float("FAUCET_WIN_CHANCE_INCREMENT", 0.01),
            cashout_min_usd=parsed.cashout_min or get_env_float("FAUCET_CASHOUT_MIN_USD", 20.0),
            auto_withdraw=get_env_bool("AUTO_WITHDRAW", False),
            withdrawal_address=os.environ.get("WITHDRAWAL_ADDRESS", ""),
            withdrawal_min_usd=get_env_float("WITHDRAWAL_MIN_USD", 20.0),
            verbose=parsed.verbose,
        )
        return cmd_run(
            api,
            bot_config,
            continuous=parsed.continuous,
            interval=parsed.interval,
            stop_on_cashout=parsed.stop_on_cashout,
            max_iterations=parsed.max_iterations,
        )
    elif parsed.command == "roll":
        # For single roll, use --chance if provided, otherwise use base_win_chance
        base_chance = parsed.chance if parsed.chance else get_env_float("FAUCET_BASE_WIN_CHANCE", 0.01)
        bot_config = BotConfig(
            base_win_chance=base_chance,
            win_chance_increment=get_env_float("FAUCET_WIN_CHANCE_INCREMENT", 0.01),
            cashout_min_usd=get_env_float("FAUCET_CASHOUT_MIN_USD", 20.0),
            auto_withdraw=get_env_bool("AUTO_WITHDRAW", False),
            withdrawal_address=os.environ.get("WITHDRAWAL_ADDRESS", ""),
            withdrawal_min_usd=get_env_float("WITHDRAWAL_MIN_USD", 20.0),
            verbose=parsed.verbose,
        )
        return cmd_roll(api, bot_config, parsed.currency, parsed.chance)
    elif parsed.command == "claim":
        bot_config = BotConfig(
            verbose=parsed.verbose,
        )
        return cmd_claim(api, bot_config, parsed.currency)
    
    return 0


def cmd_status(api: DuckDiceAPI, verbose: bool = False) -> int:
    """Show current faucet balances."""
    print("Fetching user info...")
    
    try:
        user_info = api.get_user_info()
    except Exception as e:
        print(f"Error fetching user info: {e}", file=sys.stderr)
        return 1
    
    user = user_info.get("user", {})
    balances = user_info.get("balances", [])
    
    print(f"\nUser: {user.get('name', 'Unknown')}")
    print(f"Level: {user.get('level', 'Unknown')}")
    print()
    
    print("Faucet Balances:")
    print("-" * 50)
    
    has_faucet = False
    for bal in balances:
        if bal is None:
            continue
        currency = bal.get("currency", "")
        faucet = bal.get("faucet", "0")
        try:
            faucet_val = float(faucet)
            if faucet_val > 0:
                has_faucet = True
                main = bal.get("main", "0")
                print(f"  {currency.upper()}: {faucet} (main: {main})")
        except (ValueError, TypeError):
            continue
    
    if not has_faucet:
        print("  No faucet balances found.")
    
    print()
    
    if verbose:
        print("\nAll Balances:")
        print("-" * 50)
        for bal in balances:
            if bal is None:
                continue
            currency = bal.get("currency", "")
            main = bal.get("main", "0")
            faucet = bal.get("faucet", "0")
            print(f"  {currency.upper()}: main={main}, faucet={faucet}")
    
    return 0


def cmd_run(
    api: DuckDiceAPI,
    config: BotConfig,
    continuous: bool = False,
    interval: int = 60,
    stop_on_cashout: bool = False,
    max_iterations: Optional[int] = None,
) -> int:
    """Run the faucet bot."""
    # Note: config.verbose is already set from parsed args in main()
    bot = FaucetBot(api, config)
    
    try:
        if continuous:
            bot.run_continuous(
                interval_sec=interval,
                stop_on_cashout=stop_on_cashout,
                max_iterations=max_iterations,
            )
        else:
            results = bot.run_single_pass()
            if not results:
                print("\nNo faucet balances to process.")
            else:
                print(f"\nProcessed {len(results)} currencies.")
                wins = sum(1 for r in results if r.win)
                cashouts = sum(1 for r in results if r.cashout_success)
                print(f"Wins: {wins}/{len(results)}")
                if cashouts > 0:
                    print(f"Cashouts: {cashouts}")
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    return 0


def cmd_roll(api: DuckDiceAPI, config: BotConfig, currency: str, win_chance: Optional[float] = None) -> int:
    """Roll a specific currency."""
    # Note: config.verbose is already set from parsed args in main()
    bot = FaucetBot(api, config)
    
    # Get faucet balance for this currency
    print(f"Checking faucet balance for {currency.upper()}...")
    
    try:
        faucet_currencies = bot.get_faucet_currencies()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    target = None
    for fc in faucet_currencies:
        if fc["currency"].lower() == currency.lower():
            target = fc
            break
    
    if not target:
        print(f"No faucet balance found for {currency.upper()}")
        return 1
    
    print(f"Found: {target['faucet_balance']} {currency.upper()} (~${target['faucet_usd']:.4f} USD)")
    
    # Use provided win_chance or default to base_win_chance
    effective_chance = win_chance if win_chance is not None else config.base_win_chance
    
    try:
        result = bot.roll_faucet(currency.lower(), target["faucet_balance"], effective_chance)
        print()
        print("Result:", "WIN" if result.win else "LOSS")
        print(f"  Win chance: {result.win_chance}%")
        print(f"  Roll: {result.roll_number}")
        print(f"  Profit: {result.profit}")
        print(f"  New faucet balance: {result.new_faucet_balance}")
        if result.cashout_triggered:
            print(f"  Cashout: {'Success' if result.cashout_success else 'Failed'}")
        if result.withdrawal_triggered:
            print(f"  Withdrawal: {'Success' if result.withdrawal_success else 'Failed'}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    return 0


def cmd_claim(api: DuckDiceAPI, config: BotConfig, currency: Optional[str] = None) -> int:
    """Claim faucet for a specific currency or all currencies."""
    bot = FaucetBot(api, config)
    
    if currency:
        # Claim specific currency
        print(f"Claiming faucet for {currency.upper()}...")
        try:
            result = bot.claim_faucet(currency.lower())
            print()
            if result.success:
                print(f"Success! Claimed {result.amount} {currency.upper()}")
            else:
                print(f"Failed to claim: {result.error}")
                return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    else:
        # Claim all available faucets
        print("Claiming all available faucets...")
        try:
            results = bot.claim_all_faucets()
            print()
            
            successful = [r for r in results if r.success]
            failed = [r for r in results if not r.success]
            
            if successful:
                print(f"Successfully claimed {len(successful)} faucet(s):")
                for r in successful:
                    print(f"  {r.currency.upper()}: {r.amount}")
            
            if failed:
                print(f"\nFailed to claim {len(failed)} faucet(s):")
                for r in failed:
                    print(f"  {r.currency.upper()}: {r.error}")
            
            if not results:
                print("No faucets available to claim.")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
