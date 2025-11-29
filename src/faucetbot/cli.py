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
from .bot import FaucetBot, BotConfig, BetMode, NormalModeConfig


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
  faucetbot normal btc           # Run normal mode (Junkhead strategy)
  faucetbot normal btc --max-bets 20  # Limit to 20 bets

Progressive Strategy (faucet mode):
  Faucets are rolled all-in with increasing win chances:
  - 1st faucet: 0.01% (base chance)
  - 2nd faucet: 0.02% (base + increment)
  - 3rd faucet: 0.03% (base + 2*increment)
  - And so on...

Normal Mode (Junkhead Strategy):
  Bets with main balance using percentage-based sizing:
  - Low-Risk: ~2.0x payout (49.5% win), 5% of balance
  - High-Risk: ~8.2x payout (12% win), 1% of balance
  - High-risk bets placed every N low-risk bets
  - Alternates between over/under directions

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
  
  # Normal Mode Environment Variables
  NORMAL_LOW_RISK_WIN_CHANCE    Low-risk win chance % (default: 49.5)
  NORMAL_LOW_RISK_BET_PERCENT   Low-risk bet size % of balance (default: 5.0)
  NORMAL_HIGH_RISK_WIN_CHANCE   High-risk win chance % (default: 12.0)
  NORMAL_HIGH_RISK_BET_PERCENT  High-risk bet size % of balance (default: 1.0)
  NORMAL_HIGH_RISK_FREQUENCY    High-risk bet every N bets (default: 5)
  NORMAL_MAX_BETS               Max bets per session (default: 50)
  NORMAL_STOP_LOSS_PERCENT      Stop loss % (default: 50)
  NORMAL_TAKE_PROFIT_PERCENT    Take profit % (default: 50)
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
    
    # normal command (Junkhead strategy)
    normal_parser = subparsers.add_parser(
        "normal",
        help="Run normal mode betting (Junkhead strategy) with percentage-based bet sizing"
    )
    normal_parser.add_argument("currency", help="Currency symbol to bet with (e.g., btc, eth)")
    normal_parser.add_argument(
        "--max-bets",
        type=int,
        default=None,
        help="Maximum number of bets (default: 50)",
    )
    normal_parser.add_argument(
        "--low-risk-chance",
        type=float,
        default=None,
        help="Low-risk win chance %% (default: 49.5 for ~2.0x payout)",
    )
    normal_parser.add_argument(
        "--low-risk-percent",
        type=float,
        default=None,
        help="Low-risk bet size as %% of balance (default: 5.0)",
    )
    normal_parser.add_argument(
        "--high-risk-chance",
        type=float,
        default=None,
        help="High-risk win chance %% (default: 12.0 for ~8.2x payout)",
    )
    normal_parser.add_argument(
        "--high-risk-percent",
        type=float,
        default=None,
        help="High-risk bet size as %% of balance (default: 1.0)",
    )
    normal_parser.add_argument(
        "--high-risk-frequency",
        type=int,
        default=None,
        help="Place high-risk bet every N bets (default: 5, 0 to disable)",
    )
    normal_parser.add_argument(
        "--stop-loss",
        type=float,
        default=None,
        help="Stop loss percentage (default: 50)",
    )
    normal_parser.add_argument(
        "--take-profit",
        type=float,
        default=None,
        help="Take profit percentage (default: 50)",
    )
    normal_parser.add_argument(
        "--no-alternate",
        action="store_true",
        help="Disable direction alternation (always bet one direction)",
    )
    normal_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    
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
    elif parsed.command == "normal":
        # Create normal mode config
        normal_config = NormalModeConfig(
            low_risk_win_chance=parsed.low_risk_chance or get_env_float("NORMAL_LOW_RISK_WIN_CHANCE", 49.5),
            low_risk_bet_percent=parsed.low_risk_percent or get_env_float("NORMAL_LOW_RISK_BET_PERCENT", 5.0),
            high_risk_win_chance=parsed.high_risk_chance or get_env_float("NORMAL_HIGH_RISK_WIN_CHANCE", 12.0),
            high_risk_bet_percent=parsed.high_risk_percent or get_env_float("NORMAL_HIGH_RISK_BET_PERCENT", 1.0),
            high_risk_frequency=parsed.high_risk_frequency if parsed.high_risk_frequency is not None else get_env_int("NORMAL_HIGH_RISK_FREQUENCY", 5),
            alternate_direction=not parsed.no_alternate,
            max_bets_per_session=parsed.max_bets or get_env_int("NORMAL_MAX_BETS", 50),
            stop_loss_percent=parsed.stop_loss or get_env_float("NORMAL_STOP_LOSS_PERCENT", 50.0),
            take_profit_percent=parsed.take_profit or get_env_float("NORMAL_TAKE_PROFIT_PERCENT", 50.0),
        )
        bot_config = BotConfig(
            mode=BetMode.NORMAL,
            normal_mode=normal_config,
            auto_withdraw=get_env_bool("AUTO_WITHDRAW", False),
            withdrawal_address=os.environ.get("WITHDRAWAL_ADDRESS", ""),
            withdrawal_min_usd=get_env_float("WITHDRAWAL_MIN_USD", 20.0),
            verbose=parsed.verbose,
        )
        return cmd_normal(api, bot_config, parsed.currency, parsed.max_bets)
    
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


def cmd_normal(
    api: DuckDiceAPI,
    config: BotConfig,
    currency: str,
    max_bets: Optional[int] = None,
) -> int:
    """Run normal mode betting session with Junkhead strategy."""
    bot = FaucetBot(api, config)
    
    print(f"Starting Normal Mode (Junkhead Strategy) for {currency.upper()}...")
    print()
    print("Strategy Settings:")
    print(f"  Low-Risk: {config.normal_mode.low_risk_win_chance}% win chance, {config.normal_mode.low_risk_bet_percent}% bet size")
    print(f"  High-Risk: {config.normal_mode.high_risk_win_chance}% win chance, {config.normal_mode.high_risk_bet_percent}% bet size")
    print(f"  High-Risk Frequency: Every {config.normal_mode.high_risk_frequency} bets")
    print(f"  Direction Alternation: {'Enabled' if config.normal_mode.alternate_direction else 'Disabled'}")
    print(f"  Stop Loss: {config.normal_mode.stop_loss_percent}%")
    print(f"  Take Profit: {config.normal_mode.take_profit_percent}%")
    print(f"  Max Bets: {max_bets or config.normal_mode.max_bets_per_session}")
    print()
    
    try:
        results = bot.run_normal_mode_session(currency.lower(), max_bets)
        
        if not results:
            print("\nNo bets were placed. Check if you have balance for this currency.")
            return 1
        
        # Print summary
        print()
        print("=" * 50)
        print("Final Results:")
        wins = sum(1 for r in results if r.win)
        losses = len(results) - wins
        total_profit = sum(float(r.profit) for r in results)
        
        print(f"  Total bets: {len(results)}")
        print(f"  Wins: {wins} ({wins/len(results)*100:.1f}%)")
        print(f"  Losses: {losses} ({losses/len(results)*100:.1f}%)")
        print(f"  Total profit: {total_profit:.8f}")
        
        low_risk_bets = [r for r in results if r.strategy and r.strategy.value == "low_risk"]
        high_risk_bets = [r for r in results if r.strategy and r.strategy.value == "high_risk"]
        
        if low_risk_bets:
            low_wins = sum(1 for r in low_risk_bets if r.win)
            print(f"  Low-Risk: {low_wins}/{len(low_risk_bets)} wins ({low_wins/len(low_risk_bets)*100:.1f}%)")
        
        if high_risk_bets:
            high_wins = sum(1 for r in high_risk_bets if r.win)
            print(f"  High-Risk: {high_wins}/{len(high_risk_bets)} wins ({high_wins/len(high_risk_bets)*100:.1f}%)")
        
        if results:
            final_balance = results[-1].new_main_balance
            final_usd = results[-1].usd_value
            print(f"  Final balance: {final_balance} (~${final_usd:.2f} USD)")
        
    except KeyboardInterrupt:
        print("\nSession stopped by user.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
