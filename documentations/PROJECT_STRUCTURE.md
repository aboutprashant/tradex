# Project Structure

## Overview
This document describes the folder structure of the Trading Bot application.

## Directory Structure

```
Algo/
├── src/                    # Source code
│   ├── __init__.py
│   ├── core/              # Core trading logic
│   │   ├── __init__.py
│   │   ├── config.py      # Configuration management
│   │   ├── script.py       # Main trading bot
│   │   └── trade_logger.py # Logging utilities
│   ├── brokers/           # Broker integrations
│   │   ├── __init__.py
│   │   └── broker_client.py # Angel One broker client
│   ├── indicators/         # Technical indicators
│   │   ├── __init__.py
│   │   ├── indicators.py   # Main indicators (RSI, MACD, SMA, etc.)
│   │   ├── support_resistance.py # Support/Resistance detection
│   │   └── sentiment.py    # Sentiment analysis
│   ├── strategies/         # Trading strategies
│   │   ├── __init__.py
│   │   ├── position_sizing.py # Position sizing logic
│   │   └── symbols.py      # Symbol management
│   ├── ml/                # Machine learning
│   │   ├── __init__.py
│   │   ├── ml_model.py     # ML prediction model
│   │   └── learning_engine.py # Learning from trades
│   └── utils/             # Utilities
│       ├── __init__.py
│       └── notifications.py # Telegram notifications
├── scripts/                # Executable/utility scripts
│   ├── backtest.py         # Backtesting tool
│   ├── optimize.py         # Parameter optimization
│   ├── fundamental_analysis.py # Fundamental analysis
│   ├── fetch_tokens.py     # Token fetcher
│   ├── dashboard.py        # Web dashboard
│   ├── bot.sh              # Bot control script
│   ├── dashboard.sh        # Dashboard control script
│   ├── deploy.sh           # Deployment script
│   ├── termux_boot.sh      # Termux auto-start
│   ├── termux_bot.sh       # Termux bot control
│   └── termux_setup.sh     # Termux setup
├── config/                 # Configuration files
│   ├── env.example         # Environment variables template
│   └── com.prashant.tradingbot.plist # macOS launchd config
├── logs/                   # Log files
│   ├── bot.log             # Bot logs
│   ├── dashboard.log       # Dashboard logs
│   ├── trades.csv          # Trade history
│   ├── positions.json      # Current positions
│   └── learning_data.json  # ML training data
├── documentations/         # Documentation
│   ├── README.md
│   ├── CAUTIONARY_LISTING_FIX.md
│   ├── EXTERNAL_POSITION_POLICY.md
│   ├── LOGGING_SUMMARY.md
│   └── PROJECT_STRUCTURE.md
├── data/                   # Data storage (optional)
├── tests/                  # Test files (optional)
├── requirements.txt        # Python dependencies
├── README.md              # Main README (if moved back)
└── venv/                  # Virtual environment
```

## Module Organization

### Core (`src/core/`)
- **config.py**: Configuration management, loads from `.env` file
- **script.py**: Main trading bot entry point
- **trade_logger.py**: Logging utilities for trades and application logs

### Brokers (`src/brokers/`)
- **broker_client.py**: Angel One API integration

### Indicators (`src/indicators/`)
- **indicators.py**: Technical indicators (RSI, MACD, SMA, Bollinger Bands, ATR)
- **support_resistance.py**: Support and resistance level detection
- **sentiment.py**: Market sentiment analysis

### Strategies (`src/strategies/`)
- **position_sizing.py**: Position sizing calculations
- **symbols.py**: Symbol management and sector rotation

### ML (`src/ml/`)
- **ml_model.py**: Machine learning prediction model
- **learning_engine.py**: Learning from past trades to improve strategy

### Utils (`src/utils/`)
- **notifications.py**: Telegram notification system

## Scripts (`scripts/`)

### Trading Scripts
- **backtest.py**: Backtest trading strategies
- **optimize.py**: Optimize strategy parameters
- **fundamental_analysis.py**: Analyze stock fundamentals

### Control Scripts
- **bot.sh**: Start/stop/restart bot (Linux/macOS)
- **dashboard.sh**: Start/stop dashboard
- **termux_bot.sh**: Bot control for Android/Termux
- **termux_boot.sh**: Auto-start for Termux

## Configuration

### Environment Variables
Create a `.env` file in the project root (copy from `config/env.example`):
- API credentials
- Trading parameters
- Notification settings

### Logs
All logs are stored in the `logs/` directory:
- `bot.log`: Main bot execution logs
- `dashboard.log`: Dashboard server logs
- `trades.csv`: Trade history
- `positions.json`: Current positions snapshot

## Running the Application

### Main Bot
```bash
# Using shell script
./scripts/bot.sh start

# Direct execution
python src/core/script.py
```

### Dashboard
```bash
# Using shell script
./scripts/dashboard.sh start

# Direct execution
python scripts/dashboard.py
```

### Backtesting
```bash
python scripts/backtest.py
```

### Fundamental Analysis
```bash
python scripts/fundamental_analysis.py
```

## Import Paths

All imports use the `src.` prefix:
```python
from src.core.config import Config
from src.brokers.broker_client import BrokerClient
from src.indicators.indicators import apply_all_indicators
```

Scripts in the `scripts/` folder add the project root to the path:
```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
```

## Benefits of This Structure

1. **Modularity**: Clear separation of concerns
2. **Maintainability**: Easy to find and update code
3. **Scalability**: Easy to add new features
4. **Testing**: Clear structure for unit tests
5. **Documentation**: Organized documentation folder
