# FaucetBot

Automated faucet roll, cashout, and withdrawal bot for [DuckDice.io](https://duckdice.io).

## Features

- **Faucet Balance Check**: Automatically detects all currencies with faucet balance
- **All-In Roll**: Bets the full faucet balance with configurable win chance
- **Auto Cashout**: Transfers faucet balance to main balance when USD threshold is met
- **Auto Withdrawal**: Optionally withdraws from main balance to your wallet
- **Price Tracking**: Real-time USD value calculation via CoinGecko API
- **Rate Limiting**: Built-in request throttling to respect API limits

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/sushiomsky/faucetbot.git
cd faucetbot

# Install in development mode
pip install -e .

# Or install dependencies directly
pip install requests python-dotenv
```

## Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` with your settings:
```bash
# Required
DUCKDICE_API_KEY=your-api-key-here

# Optional - Betting
FAUCET_WIN_CHANCE=50.0          # Win chance percentage (default: 50)

# Optional - Cashout
FAUCET_CASHOUT_MIN_USD=20.0     # Min USD to trigger cashout (default: 20)

# Optional - Withdrawal
AUTO_WITHDRAW=false              # Enable auto-withdrawal
WITHDRAWAL_ADDRESS=your-wallet  # Your wallet address
WITHDRAWAL_MIN_USD=20.0          # Min USD to trigger withdrawal
```

Get your API key from: https://duckdice.io (Account Settings → Bot API)

## Usage

### Check Faucet Balances

```bash
faucetbot status
```

Shows all currencies with faucet balance and their USD values.

### Run Single Pass

```bash
faucetbot run
```

Processes all faucet balances once:
1. Checks each currency with faucet balance
2. Bets all-in with configured win chance
3. Cashes out to main if balance >= $20 USD
4. Withdraws to wallet if configured

### Run Continuously

```bash
faucetbot run --continuous --interval 60
```

Runs in a loop, checking for faucet balances every 60 seconds.

Options:
- `--interval SECONDS`: Time between passes (default: 60)
- `--stop-on-cashout`: Stop after a successful cashout
- `--max-iterations N`: Maximum number of passes

### Roll Specific Currency

```bash
faucetbot roll btc
```

Roll only a specific currency's faucet balance.

### Override Settings

```bash
faucetbot run --chance 75 --cashout-min 10
```

- `--chance`: Override win chance percentage
- `--cashout-min`: Override minimum USD for cashout

## How It Works

### Faucet Claiming (Manual)

Currently, claiming faucets must be done manually on the DuckDice website. There are typically 40-55 faucets available daily across different cryptocurrencies.

### Bot Workflow

1. **Check Balances**: Bot queries the API for all currency balances
2. **Filter Faucets**: Identifies currencies with non-zero faucet balance
3. **Roll**: For each faucet balance:
   - Places an all-in bet at the configured win chance
   - Win chance of 50% gives ~1.98x payout
4. **Cashout**: If the faucet balance USD value >= threshold:
   - Transfers faucet balance to main balance
5. **Withdraw** (optional): If main balance >= threshold:
   - Initiates withdrawal to configured wallet

### Win Chance Strategy

- **50%** (default): Balanced risk/reward, ~1.98x payout on win
- **75%**: Lower risk, ~1.32x payout on win
- **25%**: Higher risk, ~3.96x payout on win

## API Endpoints Used

- `GET /bot/user-info` - Get user info and balances
- `POST /dice/play` - Play dice game
- `POST /faucet/cashout` - Transfer faucet to main balance
- `POST /withdraw` - Withdraw to external wallet

## Development

### Project Structure

```
faucetbot/
├── src/
│   └── faucetbot/
│       ├── __init__.py    # Package exports
│       ├── api.py         # DuckDice API client
│       ├── bot.py         # Core bot logic
│       └── cli.py         # Command line interface
├── pyproject.toml         # Package configuration
├── .env.example           # Environment template
└── README.md              # This file
```

### Running Tests

```bash
# Install test dependencies
pip install pytest

# Run tests
pytest
```

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## Disclaimer

This bot is for educational purposes. Use responsibly and be aware of DuckDice's terms of service regarding automated betting and faucet usage. Gambling involves risk - never bet more than you can afford to lose.
