# Trading Bot

Automated trading bot for Indian stock market using Angel One API.

## Quick Start

### Setup
1. Copy `config/env.example` to `.env` in project root
2. Fill in your Angel One API credentials
3. Install dependencies: `pip install -r requirements.txt`

### Run Bot
```bash
# Using main entry point
python main.py

# Or using shell script
./scripts/bot.sh start

# Or directly
python src/core/script.py
```

### Run Dashboard
```bash
./scripts/dashboard.sh start
# Visit http://localhost:5001
```

## Project Structure

See [documentations/PROJECT_STRUCTURE.md](documentations/PROJECT_STRUCTURE.md) for detailed structure.

## Key Features

- Automated trading with technical indicators
- Multi-timeframe analysis
- Machine learning predictions
- Risk management (stop-loss, trailing stop)
- Position tracking
- Telegram notifications
- Web dashboard

## Documentation

All documentation is in the `documentations/` folder:
- [Project Structure](documentations/PROJECT_STRUCTURE.md)
- [External Position Policy](documentations/EXTERNAL_POSITION_POLICY.md)
- [Cautionary Listing Fix](documentations/CAUTIONARY_LISTING_FIX.md)

## Scripts

- `main.py` - Main entry point
- `scripts/backtest.py` - Backtest strategies
- `scripts/optimize.py` - Optimize parameters
- `scripts/fundamental_analysis.py` - Analyze fundamentals

## Configuration

Edit `.env` file for configuration. See `config/env.example` for all options.
