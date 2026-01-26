import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ============================================
    # ANGEL ONE CREDENTIALS
    # ============================================
    API_KEY = os.getenv("API_KEY")
    CLIENT_CODE = os.getenv("CLIENT_CODE")
    PASSWORD = os.getenv("PASSWORD")
    MPIN = os.getenv("MPIN")
    TOTP_SECRET = os.getenv("TOTP_SECRET")
    
    # ============================================
    # TELEGRAM ALERTS
    # ============================================
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "False") == "True"
    
    # ============================================
    # TRADING SETTINGS
    # ============================================
    PAPER_TRADING = os.getenv("PAPER_TRADING", "True") == "True"
    CAPITAL = float(os.getenv("CAPITAL", 1000))
    
    # Symbols to trade (ETFs - expanded)
    SYMBOLS = os.getenv("SYMBOLS", "GOLDBEES-EQ,SILVERBEES-EQ,NIFTYBEES-EQ,BANKBEES-EQ").split(",")
    PRIMARY_SYMBOL = SYMBOLS[0] if SYMBOLS else "GOLDBEES-EQ"
    
    # Symbol Rotation
    ENABLE_SECTOR_ROTATION = os.getenv("ENABLE_SECTOR_ROTATION", "False") == "True"
    ROTATION_CHECK_HOURS = 4  # Check every 4 hours for better performing symbols
    
    # ============================================
    # RISK MANAGEMENT (Aggressive - per your request)
    # ============================================
    SL_PCT = 0.05              # 5% Stop Loss per trade
    TARGET_PCT = 0.08          # 8% Target (better risk-reward for aggressive)
    TRAILING_SL_PCT = 0.03     # 3% Trailing Stop Loss
    MAX_DAILY_LOSS_PCT = 0.10  # 10% max daily loss
    MAX_MONTHLY_LOSS_PCT = 0.10  # 10% max monthly loss
    
    # Position sizing
    MAX_POSITION_PCT = 0.50    # Max 50% of capital in single position
    MAX_POSITIONS = 2          # Max 2 positions at a time (Gold + Silver)
    
    # ============================================
    # TECHNICAL INDICATORS
    # ============================================
    SMA_FAST = 5
    SMA_SLOW = 20
    RSI_PERIOD = 14
    RSI_OVERSOLD = 35
    RSI_OVERBOUGHT = 70
    VOLUME_MULTIPLIER = 1.0
    
    # ============================================
    # MULTI-TIMEFRAME SETTINGS
    # ============================================
    PRIMARY_TIMEFRAME = "5m"    # Entry signals
    HIGHER_TIMEFRAME = "1h"     # Trend confirmation
    DAILY_TIMEFRAME = "1d"      # Overall trend
    
    # ============================================
    # MARKET HOURS FILTER (IST)
    # ============================================
    MARKET_OPEN_HOUR = 9
    MARKET_OPEN_MINUTE = 15
    MARKET_CLOSE_HOUR = 15
    MARKET_CLOSE_MINUTE = 30
    
    # High liquidity windows (best times to trade)
    HIGH_LIQUIDITY_WINDOWS = [
        (9, 30, 11, 30),   # Morning session
        (13, 30, 15, 15),  # Afternoon session
    ]
    TRADE_ONLY_HIGH_LIQUIDITY = False  # Set True to only trade during high liquidity
    
    # ============================================
    # LOGGING
    # ============================================
    LOG_DIR = os.getenv("LOG_DIR", "logs")
    TRADE_LOG_FILE = "trades.csv"
    POSITION_LOG_FILE = "positions.json"
    
    # ============================================
    # CHECK INTERVAL
    # ============================================
    CHECK_INTERVAL_SECONDS = 60  # Check every 1 minute for aggressive trading
    
    # ============================================
    # MACHINE LEARNING
    # ============================================
    ML_ENABLED = os.getenv("ML_ENABLED", "True") == "True"
    ML_MIN_CONFIDENCE = 0.55  # Minimum confidence to take trade
    ML_RETRAIN_INTERVAL = 7  # Retrain model every 7 days
    
    # ============================================
    # DASHBOARD
    # ============================================
    DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", 5000))
    
    # ============================================
    # LEARNING ENGINE
    # ============================================
    LEARNING_ENABLED = os.getenv("LEARNING_ENABLED", "True") == "True"
    LEARNING_MIN_TRADES = 10
    
    # ============================================
    # SENTIMENT FILTER
    # ============================================
    SENTIMENT_ENABLED = os.getenv("SENTIMENT_ENABLED", "True") == "True"