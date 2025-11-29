# FaucetBot

Automated faucet claiming, roll, cashout, and withdrawal bot for [DuckDice.io](https://duckdice.io).

## Features

- **Browser-Based Faucet Claiming**: Claim free cryptocurrency using browser automation (bypasses Cloudflare)
- **Progressive Win Chance Strategy**: Rolls faucets all-in with increasing odds (0.01%, 0.02%, 0.03%, ...)
- **Faucet Balance Check**: Automatically detects all currencies with faucet balance
- **All-In Roll**: Bets the full faucet balance for maximum potential gains
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

# Install in development mode with browser support
pip install -e ".[browser]"

# Install Playwright browsers
playwright install chromium
```

## Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` with your settings:
```bash
# Required for rolling/status/cashout (not needed for claiming)
DUCKDICE_API_KEY=your-api-key-here

# Optional - Progressive Win Chance Strategy
FAUCET_BASE_WIN_CHANCE=0.01       # Base win chance for 1st faucet (default: 0.01%)
FAUCET_WIN_CHANCE_INCREMENT=0.01  # Increment per faucet (default: 0.01%)

# Optional - Cashout
FAUCET_CASHOUT_MIN_USD=20.0       # Min USD to trigger cashout (default: 20)

# Optional - Withdrawal
AUTO_WITHDRAW=false               # Enable auto-withdrawal
WITHDRAWAL_ADDRESS=your-wallet   # Your wallet address
WITHDRAWAL_MIN_USD=20.0           # Min USD to trigger withdrawal
```

Get your API key from: https://duckdice.io (Account Settings → Bot API)

## Usage

### Check Faucet Balances

```bash
faucetbot status
```

Shows all currencies with faucet balance and their USD values.

### Claim Faucets (Browser-Based)

Faucet claiming uses browser automation to bypass Cloudflare protection.

```bash
# First-time login (opens browser for manual login)
faucetbot claim --login --session-dir ~/.faucetbot-session

# Subsequent claims (uses saved session)
faucetbot claim --session-dir ~/.faucetbot-session

# Claim specific currency
faucetbot claim sol --session-dir ~/.faucetbot-session

# Run in visible browser mode (not headless)
faucetbot claim --no-headless --session-dir ~/.faucetbot-session
```

**Important Notes:**
- The `--login` flag opens a browser window for manual login
- Use `--session-dir` to persist your login session between runs
- The faucet API is protected by Cloudflare, so browser automation is required

Claims free cryptocurrency from the DuckDice faucet. Each currency can be claimed once per minute (approximately 45-50 faucets available daily).

### Run Single Pass

```bash
faucetbot run
```

Processes all faucet balances once with progressive win chances:
1. Checks each currency with faucet balance
2. Bets all-in with progressive win chance (1st: 0.01%, 2nd: 0.02%, ...)
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
- `--base-chance PCT`: Override base win chance (default: 0.01%)
- `--chance-increment PCT`: Override win chance increment (default: 0.01%)

### Roll Specific Currency

```bash
faucetbot roll btc
faucetbot roll btc --chance 1.5  # Roll with custom 1.5% win chance
```

Roll only a specific currency's faucet balance.

### Override Settings

```bash
faucetbot run --base-chance 0.02 --chance-increment 0.02 --cashout-min 10
```

- `--base-chance`: Override base win chance percentage
- `--chance-increment`: Override win chance increment
- `--cashout-min`: Override minimum USD for cashout

## How It Works

### Progressive Win Chance Strategy

The bot uses a progressive betting strategy where each faucet is rolled with an increasing win chance:

| Faucet # | Win Chance | Potential Payout |
|----------|------------|------------------|
| 1st      | 0.01%      | ~9900x           |
| 2nd      | 0.02%      | ~4950x           |
| 3rd      | 0.03%      | ~3300x           |
| 4th      | 0.04%      | ~2475x           |
| ...      | ...        | ...              |

This strategy aims for high-payout wins while spreading risk across multiple low-probability bets.

### Faucet Claiming

The bot can automatically claim faucets using the `faucetbot claim` command. There are typically 40-55 faucets available daily across different cryptocurrencies with a 60-second cooldown between claims per currency.

### Bot Workflow

1. **Claim Faucets**: Optionally claim free cryptocurrency from available faucets
2. **Check Balances**: Bot queries the API for all currency balances
3. **Filter Faucets**: Identifies currencies with non-zero faucet balance
4. **Roll**: For each faucet balance:
   - Places an all-in bet with progressive win chance
   - 1st faucet: 0.01%, 2nd: 0.02%, 3rd: 0.03%, etc.
5. **Cashout**: If the faucet balance USD value >= threshold:
   - Transfers faucet balance to main balance
6. **Withdraw** (optional): If main balance >= threshold:
   - Initiates withdrawal to configured wallet

## API Endpoints Used

- `GET /faucet` - Get faucet info and available currencies
- `GET /faucet/{symbol}/check` - Check if faucet can be claimed
- `POST /faucet` - Claim faucet for a currency
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
