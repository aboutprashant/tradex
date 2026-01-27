import time
import sys
import os
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import pytz

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core.config import Config
from src.brokers.broker_client import BrokerClient
from src.indicators.indicators import apply_all_indicators, MultiTimeframeAnalyzer
from src.utils.notifications import notifier
from src.core.trade_logger import logger, app_logger
from src.ml.learning_engine import learning_engine
from src.strategies.symbols import symbol_manager, SYMBOL_UNIVERSE
from src.strategies.position_sizing import position_sizer
from src.indicators.support_resistance import sr_detector
from src.ml.ml_model import ml_predictor
from src.indicators.sentiment import sentiment_filter

# ============================================
# UTILITY FUNCTIONS
# ============================================

def get_value(series_or_scalar):
    """Helper to extract a single float value from a Series or scalar."""
    if isinstance(series_or_scalar, pd.Series):
        return float(series_or_scalar.iloc[0])
    return float(series_or_scalar)


def is_market_open():
    """Check if the market is currently open (9:15 AM - 3:30 PM IST, Mon-Fri).
    Uses IST timezone regardless of server location.
    """
    # Get current time in IST (Indian Standard Time, UTC+5:30)
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist)
    
    # Check if it's a weekday (Monday=0, Sunday=6)
    if now_ist.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False, "Weekend"
    
    # Create market open/close times in IST
    market_open = now_ist.replace(hour=Config.MARKET_OPEN_HOUR, minute=Config.MARKET_OPEN_MINUTE, second=0, microsecond=0)
    market_close = now_ist.replace(hour=Config.MARKET_CLOSE_HOUR, minute=Config.MARKET_CLOSE_MINUTE, second=0, microsecond=0)
    
    if now_ist < market_open:
        return False, f"Market opens at {Config.MARKET_OPEN_HOUR}:{Config.MARKET_OPEN_MINUTE:02d} IST"
    if now_ist > market_close:
        return False, f"Market closed at {Config.MARKET_CLOSE_HOUR}:{Config.MARKET_CLOSE_MINUTE:02d} IST"
    
    return True, "Market Open"


def is_high_liquidity_window():
    """Check if we're in a high liquidity trading window (uses IST)."""
    # Get current time in IST
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist)
    current_minutes = now_ist.hour * 60 + now_ist.minute
    
    for start_h, start_m, end_h, end_m in Config.HIGH_LIQUIDITY_WINDOWS:
        start_minutes = start_h * 60 + start_m
        end_minutes = end_h * 60 + end_m
        
        if start_minutes <= current_minutes <= end_minutes:
            return True, f"{start_h}:{start_m:02d}-{end_h}:{end_m:02d}"
    
    return False, "Low liquidity period"


def fetch_live_data(symbol):
    """Fetches the last 5 days of 5-minute data."""
    yf_symbol = symbol.replace("-EQ", ".NS")
    data = yf.download(yf_symbol, period="5d", interval="5m", progress=False)
    return data


# ============================================
# SIGNAL GENERATION
# ============================================

def get_optimized_signal(df, mtf_trend):
    """
    Optimized Signal Logic with Multiple Confirmations + Multi-Timeframe Filter.
    """
    if len(df) < 30:
        return "WAIT", {}, ["Not enough data"]
        
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    # Extract values safely
    sma_5_now = get_value(latest["SMA_5"])
    sma_20_now = get_value(latest["SMA_20"])
    sma_5_prev = get_value(prev["SMA_5"])
    sma_20_prev = get_value(prev["SMA_20"])
    rsi = get_value(latest["RSI"])
    macd = get_value(latest["MACD"])
    macd_signal = get_value(latest["MACD_Signal"])
    volume = get_value(latest["Volume"])
    volume_avg = get_value(latest["Volume_SMA"])
    close = get_value(latest["Close"])
    bb_lower = get_value(latest["BB_Lower"])
    bb_upper = get_value(latest["BB_Upper"])
    atr = get_value(latest["ATR"])

    indicators = {
        "RSI": rsi,
        "MACD": macd,
        "MACD_Signal": macd_signal,
        "SMA_5": sma_5_now,
        "SMA_20": sma_20_now,
        "Volume": volume,
        "Volume_Avg": volume_avg,
        "BB_Lower": bb_lower,
        "BB_Upper": bb_upper,
        "ATR": atr,
        "Close": close,
        "MTF_Trend": mtf_trend
    }

    # --- CHECK CONDITIONS ---
    sma_crossover_buy = (sma_5_prev < sma_20_prev) and (sma_5_now > sma_20_now)
    sma_crossover_sell = (sma_5_prev > sma_20_prev) and (sma_5_now < sma_20_now)
    rsi_oversold = rsi < Config.RSI_OVERSOLD
    rsi_ok = rsi < Config.RSI_OVERBOUGHT
    macd_bullish = macd > macd_signal
    macd_bearish = macd < macd_signal
    volume_ok = volume > (volume_avg * Config.VOLUME_MULTIPLIER)
    near_bb_lower = close <= bb_lower * 1.02
    
    # Momentum entry conditions (for uptrend pullbacks)
    already_uptrend = sma_5_now > sma_20_now  # Already in uptrend
    price_above_sma20 = close > sma_20_now  # Price still above support
    rsi_pullback = rsi < 50  # RSI pulled back from overbought (good entry zone)
    rsi_pullback_strong = rsi < 40  # Strong pullback
    
    # Multi-timeframe filter
    mtf_bullish = mtf_trend in ["STRONG_BULLISH", "BULLISH"]
    mtf_strong_bullish = mtf_trend == "STRONG_BULLISH"
    mtf_neutral = mtf_trend == "NEUTRAL"
    mtf_bearish = mtf_trend == "BEARISH"

    reasons = []
    
    # V2-specific RSI thresholds (more relaxed)
    if Config.TRADING_VERSION == "V2":
        # V2: Relaxed RSI for STRONG_BULLISH (up to 80) and BULLISH (up to 75)
        rsi_ok_strong_bullish = rsi < Config.RSI_OVERBOUGHT_V2_STRONG_BULLISH
        rsi_ok_bullish = rsi < Config.RSI_OVERBOUGHT_V2_BULLISH
    else:
        # V1: Standard thresholds
        rsi_ok_strong_bullish = rsi_ok
        rsi_ok_bullish = rsi_ok

    # --- BUY CONDITIONS ---
    
    # TEST MODE: Force entry for testing (very lenient conditions)
    if Config.TEST_MODE:
        # Test entry: Just need bullish MTF and oversold RSI (ignores MACD and trend)
        if mtf_bullish and rsi_oversold:
            reasons = ["TEST MODE ✓", f"MTF: {mtf_trend} ✓", f"RSI Oversold ({rsi:.1f} < {Config.RSI_OVERSOLD}) ✓", "Testing buy entry logic"]
            return "STRONG_BUY", indicators, reasons
        # Even more lenient: Just need STRONG_BULLISH MTF
        if mtf_strong_bullish and rsi < 50:
            reasons = ["TEST MODE ✓", f"MTF: {mtf_trend} ✓", f"RSI: {rsi:.1f} ✓", "Testing buy entry logic (lenient)"]
            return "BUY", indicators, reasons
    
    # V1 LOGIC (Conservative - Original)
    if Config.TRADING_VERSION == "V1":
        if mtf_bullish:
            # Strong Buy: SMA crossover + RSI oversold + MACD bullish + MTF bullish
            if sma_crossover_buy and rsi_oversold and macd_bullish and volume_ok:
                reasons = ["SMA Crossover ✓", "RSI Oversold ✓", "MACD Bullish ✓", "Volume ✓", "MTF Bullish ✓"]
                return "STRONG_BUY", indicators, reasons
            
            # Normal Buy: SMA crossover + RSI OK + MACD bullish + MTF bullish
            if sma_crossover_buy and rsi_ok and macd_bullish:
                reasons = ["SMA Crossover ✓", "RSI OK ✓", "MACD Bullish ✓", "MTF Bullish ✓"]
                return "BUY", indicators, reasons
            
            # Bounce Buy: Near BB lower + RSI oversold + MTF bullish
            if near_bb_lower and rsi_oversold and macd_bullish:
                reasons = ["Near BB Lower ✓", "RSI Oversold ✓", "MACD Bullish ✓", "MTF Bullish ✓"]
                return "BUY", indicators, reasons
            
            # Momentum Entry: Already in uptrend + RSI pullback + MACD bullish + MTF bullish
            # This catches pullbacks during strong uptrends (fixes "Uptrend waiting" trap)
            if already_uptrend and price_above_sma20 and rsi_pullback_strong and macd_bullish:
                reasons = ["Momentum Entry ✓", "Uptrend Pullback ✓", f"RSI Pullback ({rsi:.1f} < 40) ✓", "MACD Bullish ✓", "MTF Bullish ✓"]
                return "STRONG_BUY", indicators, reasons
            
            if already_uptrend and price_above_sma20 and rsi_pullback and macd_bullish:
                reasons = ["Momentum Entry ✓", "Uptrend Pullback ✓", f"RSI Pullback ({rsi:.1f} < 50) ✓", "MACD Bullish ✓", "MTF Bullish ✓"]
                return "BUY", indicators, reasons
    
    # V2 LOGIC (Aggressive - Relaxed filters)
    elif Config.TRADING_VERSION == "V2":
        # V2 Rule 1: STRONG_BULLISH MTF with relaxed RSI (up to 80)
        if mtf_strong_bullish:
            # IMPROVEMENT 1: Reversal Entry - Catch bottoms in downtrends when RSI is very oversold
            # This fixes the "Downtrend (no buy)" issue when RSI < 30
            if not already_uptrend and rsi < 30 and price_above_sma20:
                # Very oversold in STRONG_BULLISH MTF - likely reversal point
                if macd_bullish or volume_ok:  # MACD bullish OR high volume confirms reversal
                    reasons = ["Reversal Entry ✓ (V2)", "STRONG_BULLISH MTF ✓", f"RSI Very Oversold ({rsi:.1f} < 30) ✓", 
                              "Price Above SMA20 ✓", "Reversal Signal ✓"]
                    return "STRONG_BUY", indicators, reasons
            
            if sma_crossover_buy and rsi_oversold and macd_bullish and volume_ok:
                reasons = ["SMA Crossover ✓", "RSI Oversold ✓", "MACD Bullish ✓", "Volume ✓", "MTF STRONG_BULLISH ✓ (V2)"]
                return "STRONG_BUY", indicators, reasons
            
            if sma_crossover_buy and rsi_ok_strong_bullish and macd_bullish:
                reasons = [f"SMA Crossover ✓", f"RSI OK ({rsi:.1f} < 80) ✓", "MACD Bullish ✓", "MTF STRONG_BULLISH ✓ (V2)"]
                return "BUY", indicators, reasons
            
            if near_bb_lower and rsi_oversold and macd_bullish:
                reasons = ["Near BB Lower ✓", "RSI Oversold ✓", "MACD Bullish ✓", "MTF STRONG_BULLISH ✓ (V2)"]
                return "BUY", indicators, reasons
            
            # IMPROVEMENT 2: Relax MACD requirement for very oversold RSI
            # When RSI < 30, MACD can lag - allow entry with volume confirmation
            if rsi < 30 and price_above_sma20 and volume_ok:
                if macd_bullish:
                    reasons = ["Oversold Entry ✓ (V2)", "STRONG_BULLISH MTF ✓", f"RSI Very Oversold ({rsi:.1f} < 30) ✓", 
                              "MACD Bullish ✓", "Volume ✓"]
                    return "STRONG_BUY", indicators, reasons
                elif not macd_bearish or abs(macd - macd_signal) < 0.1:  # MACD neutral or very close
                    reasons = ["Oversold Entry ✓ (V2)", "STRONG_BULLISH MTF ✓", f"RSI Very Oversold ({rsi:.1f} < 30) ✓", 
                              "MACD Neutral ✓", "Volume ✓"]
                    return "BUY", indicators, reasons
            
            # Momentum Entry V2: STRONG_BULLISH uptrend + pullback (more aggressive)
            if already_uptrend and price_above_sma20 and rsi_pullback_strong:
                # Allow entry even if MACD is slightly bearish during strong uptrends
                if macd_bullish:
                    reasons = ["Momentum Entry ✓ (V2)", "STRONG_BULLISH Uptrend ✓", f"RSI Pullback ({rsi:.1f} < 40) ✓", "MACD Bullish ✓"]
                    return "STRONG_BUY", indicators, reasons
                elif rsi < 35:  # Very oversold during strong uptrend - allow entry
                    reasons = ["Momentum Entry ✓ (V2)", "STRONG_BULLISH Uptrend ✓", f"RSI Very Oversold ({rsi:.1f} < 35) ✓", "MACD Neutral"]
                    return "BUY", indicators, reasons
            
            if already_uptrend and price_above_sma20 and rsi_pullback and macd_bullish:
                reasons = ["Momentum Entry ✓ (V2)", "STRONG_BULLISH Uptrend ✓", f"RSI Pullback ({rsi:.1f} < 50) ✓", "MACD Bullish ✓"]
                return "BUY", indicators, reasons
        
        # V2 Rule 2: BULLISH MTF with relaxed RSI (up to 75)
        if mtf_bullish:
            # IMPROVEMENT 3: Reversal Entry for BULLISH MTF
            if not already_uptrend and rsi < 30 and price_above_sma20 and volume_ok:
                # Very oversold in BULLISH MTF - reversal opportunity
                if macd_bullish:
                    reasons = ["Reversal Entry ✓ (V2)", "BULLISH MTF ✓", f"RSI Very Oversold ({rsi:.1f} < 30) ✓", 
                              "Price Above SMA20 ✓", "MACD Bullish ✓", "Volume ✓"]
                    return "STRONG_BUY", indicators, reasons
                else:
                    reasons = ["Reversal Entry ✓ (V2)", "BULLISH MTF ✓", f"RSI Very Oversold ({rsi:.1f} < 30) ✓", 
                              "Price Above SMA20 ✓", "Volume ✓"]
                    return "BUY", indicators, reasons
            
            if sma_crossover_buy and rsi_oversold and macd_bullish and volume_ok:
                reasons = ["SMA Crossover ✓", "RSI Oversold ✓", "MACD Bullish ✓", "Volume ✓", "MTF Bullish ✓"]
                return "STRONG_BUY", indicators, reasons
            
            if sma_crossover_buy and rsi_ok_bullish and macd_bullish:
                reasons = [f"SMA Crossover ✓", f"RSI OK ({rsi:.1f} < 75) ✓", "MACD Bullish ✓", "MTF Bullish ✓ (V2)"]
                return "BUY", indicators, reasons
            
            # IMPROVEMENT 4: Relax MACD for very oversold RSI in BULLISH MTF
            if rsi < 30 and price_above_sma20 and volume_ok:
                reasons = ["Oversold Entry ✓ (V2)", "BULLISH MTF ✓", f"RSI Very Oversold ({rsi:.1f} < 30) ✓", 
                          "Volume ✓", "Price Above SMA20 ✓"]
                return "BUY", indicators, reasons
            
            # Momentum Entry V2: BULLISH uptrend + pullback
            if already_uptrend and price_above_sma20 and rsi_pullback_strong and macd_bullish:
                reasons = ["Momentum Entry ✓ (V2)", "BULLISH Uptrend ✓", f"RSI Pullback ({rsi:.1f} < 40) ✓", "MACD Bullish ✓"]
                return "STRONG_BUY", indicators, reasons
            
            if already_uptrend and price_above_sma20 and rsi_pullback and macd_bullish:
                reasons = ["Momentum Entry ✓ (V2)", "BULLISH Uptrend ✓", f"RSI Pullback ({rsi:.1f} < 50) ✓", "MACD Bullish ✓"]
                return "BUY", indicators, reasons
        
        # V2 Rule 3: NEUTRAL MTF with oversold RSI (new in V2)
        if mtf_neutral:
            if sma_crossover_buy and rsi_oversold and macd_bullish and volume_ok:
                reasons = ["SMA Crossover ✓", "RSI Oversold ✓", "MACD Bullish ✓", "Volume ✓", "MTF NEUTRAL ✓ (V2 - Oversold Entry)"]
                return "BUY", indicators, reasons
            
            if near_bb_lower and rsi_oversold and macd_bullish:
                reasons = ["Near BB Lower ✓", "RSI Oversold ✓", "MACD Bullish ✓", "MTF NEUTRAL ✓ (V2 - Oversold Entry)"]
                return "BUY", indicators, reasons
            
            # Momentum Entry V2: NEUTRAL MTF but in uptrend + strong oversold
            if already_uptrend and price_above_sma20 and rsi_oversold and macd_bullish:
                reasons = ["Momentum Entry ✓ (V2)", "NEUTRAL MTF Uptrend ✓", f"RSI Oversold ({rsi:.1f} < {Config.RSI_OVERSOLD}) ✓", "MACD Bullish ✓"]
                return "BUY", indicators, reasons

    # --- SELL CONDITIONS ---
    if sma_crossover_sell and macd_bearish:
        reasons = ["SMA Crossover Down ✓", "MACD Bearish ✓"]
        return "SELL", indicators, reasons
    
    if mtf_bearish and macd_bearish:
        reasons = ["MTF Bearish ✓", "MACD Bearish ✓"]
        return "SELL", indicators, reasons

    # --- HOLD - Show why we're not trading ---
    hold_reasons = []
    
    if Config.TRADING_VERSION == "V1":
        # V1: Standard hold reasons
        if not mtf_bullish:
            hold_reasons.append(f"MTF: {mtf_trend} (waiting for bullish)")
        if not sma_crossover_buy:
            if sma_5_now > sma_20_now:
                hold_reasons.append("Uptrend (waiting for entry)")
            else:
                hold_reasons.append("Downtrend (no buy)")
        if rsi > Config.RSI_OVERBOUGHT:
            hold_reasons.append(f"RSI Overbought ({rsi:.1f})")
        if not macd_bullish:
            hold_reasons.append("MACD Bearish")
    
    elif Config.TRADING_VERSION == "V2":
        # V2: More relaxed hold reasons
        if mtf_bearish:
            hold_reasons.append(f"MTF: {mtf_trend} (V2: only BEARISH blocks)")
        elif mtf_neutral and not rsi_oversold:
            hold_reasons.append(f"MTF: {mtf_trend} (V2: waiting for oversold RSI < {Config.RSI_OVERSOLD})")
        elif mtf_strong_bullish and rsi > Config.RSI_OVERBOUGHT_V2_STRONG_BULLISH:
            hold_reasons.append(f"RSI Overbought ({rsi:.1f} > {Config.RSI_OVERBOUGHT_V2_STRONG_BULLISH})")
        elif mtf_bullish and rsi > Config.RSI_OVERBOUGHT_V2_BULLISH:
            hold_reasons.append(f"RSI Overbought ({rsi:.1f} > {Config.RSI_OVERBOUGHT_V2_BULLISH})")
        
        if not sma_crossover_buy:
            if sma_5_now > sma_20_now:
                hold_reasons.append("Uptrend (waiting for entry)")
            else:
                hold_reasons.append("Downtrend (no buy)")
        if not macd_bullish:
            hold_reasons.append("MACD Bearish")
    
    return "HOLD", indicators, hold_reasons if hold_reasons else ["No signal"]


# ============================================
# DISPLAY FUNCTIONS
# ============================================

def print_status(symbol, signal, indicators, reasons, position, current_price, check_count):
    """Print a formatted status update."""
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S IST")
    
    print(f"\n{'='*65}")
    print(f"⏰ {now} | Check #{check_count}")
    print(f"{'='*65}")
    print(f"📊 {symbol} | Price: ₹{current_price:.2f}")
    print(f"   SMA(5): ₹{indicators.get('SMA_5', 0):.2f} | SMA(20): ₹{indicators.get('SMA_20', 0):.2f}")
    print(f"   RSI: {indicators.get('RSI', 0):.1f} | MACD: {indicators.get('MACD', 0):.3f}")
    print(f"   ATR: ₹{indicators.get('ATR', 0):.2f} | MTF: {indicators.get('MTF_Trend', 'N/A')}")
    print(f"{'─'*65}")
    
    if position:
        pnl = (current_price - position['buy_price']) * position['quantity']
        pnl_pct = ((current_price - position['buy_price']) / position['buy_price']) * 100
        pnl_emoji = "🟢" if pnl >= 0 else "🔴"
        position_type = "🤖 Bot" if position.get('bot_entered', True) else "👤 External"
        print(f"📍 POSITION: {position['quantity']} units @ ₹{position['buy_price']:.2f} ({position_type})")
        print(f"   {pnl_emoji} Unrealized PnL: ₹{pnl:.2f} ({pnl_pct:+.2f}%)")
        print(f"   🛡️ SL: ₹{position['buy_price'] * (1 - Config.SL_PCT):.2f} | 🎯 Target: ₹{position['buy_price'] * (1 + Config.TARGET_PCT):.2f}")
    else:
        print(f"📍 POSITION: None (waiting for entry)")
    
    print(f"{'─'*65}")
    
    signal_colors = {"STRONG_BUY": "🔥", "BUY": "📈", "SELL": "📉", "HOLD": "⏸️", "WAIT": "⏳"}
    print(f"📡 SIGNAL: {signal_colors.get(signal, '')} {signal}")
    print(f"   Reasons: {', '.join(reasons)}")
    print(f"{'='*65}")


# ============================================
# MAIN TRADING LOOP
# ============================================

def main():
    # Log bot startup
    app_logger.info("="*80)
    app_logger.info(f"🚀 TRADEX BOT STARTING | Mode: {'PAPER TRADING' if Config.PAPER_TRADING else 'LIVE TRADING'}")
    app_logger.info(f"   Strategy Version: {Config.TRADING_VERSION}")
    app_logger.info(f"   Capital: ₹{Config.CAPITAL} | Symbols: {', '.join(Config.SYMBOLS)}")
    app_logger.info(f"   Check Interval: {Config.CHECK_INTERVAL_SECONDS}s")
    if Config.TRADING_VERSION == "V2":
        app_logger.info(f"   V2 Features: Relaxed RSI (STRONG_BULLISH:80, BULLISH:75) | NEUTRAL MTF allowed with oversold RSI")
    app_logger.info("="*80)
    
    broker = BrokerClient()
    if not broker.login():
        app_logger.error("❌ Broker login failed - bot stopped")
        return

    app_logger.info("✅ Broker login successful")
    
    # State management
    positions = {}  # symbol -> {quantity, buy_price, highest_price, entry_time, bot_entered}
    total_pnl = 0
    trade_count = 0
    daily_pnl = 0
    monthly_pnl = 0
    
    # Load any existing positions from previous run (bot-entered positions)
    saved_positions = logger.load_positions()
    for pos in saved_positions:
        # Mark saved positions as bot-entered
        pos['bot_entered'] = pos.get('bot_entered', True)
        positions[pos['symbol']] = pos
        print(f"📍 Loaded bot position: {pos['symbol']} - {pos['quantity']} @ ₹{pos['buy_price']:.2f}")
    
    # Sync all positions from broker account (includes external positions)
    print("\n🔄 Syncing positions from broker account...")
    try:
        broker_positions = broker.sync_all_positions()
        for symbol, broker_pos in broker_positions.items():
            if symbol in positions:
                # Position already exists (from saved bot positions)
                # Keep bot_entered flag and other bot-specific data, but update current price
                positions[symbol]['current_price'] = broker_pos.get('current_price', positions[symbol].get('buy_price', 0))
                # Update highest_price if current price is higher
                if broker_pos.get('current_price', 0) > positions[symbol].get('highest_price', 0):
                    positions[symbol]['highest_price'] = broker_pos['current_price']
                print(f"   ✅ Updated bot position: {symbol} (current: ₹{broker_pos.get('current_price', 0):.2f})")
            else:
                # New position from broker (external position)
                positions[symbol] = broker_pos
                print(f"   📍 Found external position: {symbol} - {broker_pos['quantity']} @ ₹{broker_pos['buy_price']:.2f}")
        
        if broker_positions:
            print(f"   ✅ Synced {len(broker_positions)} position(s) from broker")
        else:
            print(f"   ℹ️ No positions found in broker account")
    except Exception as e:
        print(f"   ⚠️ Failed to sync broker positions: {e}")
        app_logger.warning(f"Failed to sync broker positions: {e}")
    
    # Save all positions (bot + external)
    if positions:
        logger.save_positions([{**pos, 'symbol': sym} for sym, pos in positions.items()])

    # Analyze past trades and learn
    print("\n📚 Initializing Learning Engine...")
    learning_engine.analyze_trades()
    print(learning_engine.get_insights_summary())
    
    # Get adjusted parameters from learning
    learned_params = learning_engine.get_adjusted_params()
    print(f"\n🧠 Using learned adjustments: RSI={learned_params['rsi_oversold']}-{learned_params['rsi_overbought']}, SL={learned_params['sl_pct']*100:.1f}%, Target={learned_params['target_pct']*100:.1f}%")
    
    # Send startup notification
    notifier.send_startup_alert(Config.CAPITAL, Config.SYMBOLS)
    
    print(f"\n{'🚀'*20}")
    print(f"ALGO TRADING BOT STARTED")
    print(f"{'🚀'*20}")
    print(f"\n📌 Configuration:")
    print(f"   Strategy Version: {Config.TRADING_VERSION}")
    print(f"   Symbols: {', '.join(Config.SYMBOLS)}")
    print(f"   Capital: ₹{Config.CAPITAL}")
    print(f"   Stop Loss: {Config.SL_PCT*100}% | Target: {Config.TARGET_PCT*100}%")
    print(f"   Trailing SL: {Config.TRAILING_SL_PCT*100}%")
    print(f"   Max Daily Loss: {Config.MAX_DAILY_LOSS_PCT*100}%")
    print(f"   Check Interval: {Config.CHECK_INTERVAL_SECONDS}s")
    print(f"   Mode: {'PAPER TRADING' if Config.PAPER_TRADING else 'LIVE TRADING'}")
    if Config.TRADING_VERSION == "V2":
        print(f"   V2 Features: Relaxed RSI (STRONG_BULLISH:80, BULLISH:75) | NEUTRAL MTF allowed")
    print(f"\n⏳ Starting market monitoring...")

    check_count = 0
    last_daily_summary = None
    last_market_closed_alert = None
    market_was_open = False
    last_position_sync = None
    POSITION_SYNC_INTERVAL = 300  # Sync positions every 5 minutes (300 seconds)

    while True:
        try:
            check_count += 1
            # Get current time in IST for all operations
            ist = pytz.timezone('Asia/Kolkata')
            now_ist = datetime.now(ist)
            now_date = now_ist.date()
            
            # Log check cycle start (show IST time)
            app_logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            app_logger.info(f"🔄 CHECK CYCLE #{check_count} | {now_ist.strftime('%Y-%m-%d %H:%M:%S IST')}")
            
            # Periodically sync positions from broker (every 5 minutes)
            if last_position_sync is None or (now_ist - last_position_sync).total_seconds() >= POSITION_SYNC_INTERVAL:
                try:
                    broker_positions = broker.sync_all_positions()
                    for symbol, broker_pos in broker_positions.items():
                        if symbol in positions:
                            # Update existing position with latest price from broker
                            positions[symbol]['current_price'] = broker_pos.get('current_price', positions[symbol].get('buy_price', 0))
                            # Update highest_price if current price is higher
                            if broker_pos.get('current_price', 0) > positions[symbol].get('highest_price', 0):
                                positions[symbol]['highest_price'] = broker_pos['current_price']
                            # Update quantity if it changed (manual adjustment)
                            if abs(broker_pos['quantity'] - positions[symbol]['quantity']) > 0.01:
                                print(f"   🔄 Position quantity updated: {symbol} ({positions[symbol]['quantity']} → {broker_pos['quantity']})")
                                positions[symbol]['quantity'] = broker_pos['quantity']
                        else:
                            # New position detected from broker
                            positions[symbol] = broker_pos
                            print(f"   📍 New external position detected: {symbol} - {broker_pos['quantity']} @ ₹{broker_pos['buy_price']:.2f}")
                    
                    # Remove positions that no longer exist in broker account
                    broker_symbols = set(broker_positions.keys())
                    positions_to_remove = []
                    for symbol in positions.keys():
                        if symbol not in broker_symbols and positions[symbol].get('bot_entered', True):
                            # Only remove bot-entered positions that are closed
                            # Keep external positions in case they're in different format
                            pass
                        elif symbol not in broker_symbols and not positions[symbol].get('bot_entered', False):
                            # External position closed
                            positions_to_remove.append(symbol)
                    
                    for symbol in positions_to_remove:
                        print(f"   🗑️ External position closed: {symbol}")
                        del positions[symbol]
                    
                    last_position_sync = now_ist
                    if broker_positions:
                        logger.save_positions([{**pos, 'symbol': sym} for sym, pos in positions.items()])
                except Exception as e:
                    app_logger.warning(f"Failed to sync positions: {e}")
            
            # Check if market is open (uses IST internally)
            market_open, market_status = is_market_open()
            logger.log_market_status("CLOSED" if not market_open else "OPEN", market_status)
            
            if not market_open:
                # Send market closed notification (only once per session)
                if last_market_closed_alert != now_date:
                    notifier.send_market_closed_alert(market_status)
                    last_market_closed_alert = now_date
                    market_was_open = False
                
                # Send overnight position alert at market close
                if positions and last_daily_summary != now_date:
                    overnight_positions = [
                        {**pos, 'symbol': sym} 
                        for sym, pos in positions.items()
                    ]
                    notifier.send_overnight_position_alert(overnight_positions)
                    
                    # Send daily summary
                    daily_stats = logger.get_daily_stats()
                    notifier.send_daily_summary(
                        daily_stats['trades'], 
                        daily_stats['pnl'],
                        total_pnl,
                        len(positions)
                    )
                    last_daily_summary = now_date
                    daily_pnl = 0  # Reset daily PnL
                
                # Show IST time in message
                ist_time_str = now_ist.strftime("%H:%M:%S IST")
                print(f"\n⏳ {market_status} ({ist_time_str}). Sleeping for 5 minutes...")
                time.sleep(300)
                continue
            
            # Send market open notification (once when market opens)
            if not market_was_open:
                notifier.send_market_open_alert()
                market_was_open = True
            
            # Check daily loss limit
            if daily_pnl <= -(Config.CAPITAL * Config.MAX_DAILY_LOSS_PCT):
                print(f"\n🛑 DAILY LOSS LIMIT REACHED: ₹{daily_pnl:.2f}")
                print(f"   Bot will resume tomorrow.")
                notifier.send_message(f"⚠️ Daily loss limit reached: ₹{daily_pnl:.2f}. Bot paused.")
                time.sleep(3600)  # Sleep for 1 hour
                continue
            
            # Check liquidity window (optional)
            if Config.TRADE_ONLY_HIGH_LIQUIDITY:
                in_liquidity, liquidity_status = is_high_liquidity_window()
                if not in_liquidity:
                    print(f"\n⏳ {liquidity_status}. Waiting for high liquidity window...")
                    time.sleep(300)
                    continue
            
            # Process each symbol and collect data for status notification
            symbols_data = []
            
            for symbol in Config.SYMBOLS:
                try:
                    # Get multi-timeframe trend
                    mtf = MultiTimeframeAnalyzer(symbol)
                    mtf_trend, mtf_indicators = mtf.get_multi_timeframe_signal()
                    
                    # Fetch and analyze data
                    df = fetch_live_data(symbol)
                    if df.empty:
                        print(f"⚠️ No data for {symbol}")
                        continue
                    
                    df = apply_all_indicators(df)
                    signal, indicators, reasons = get_optimized_signal(df, mtf_trend)
                    indicators.update(mtf_indicators)
                    
                    current_price = get_value(df.iloc[-1]["Close"])
                    position = positions.get(symbol)
                    
                    # Update position current_price if available
                    if position:
                        position['current_price'] = current_price
                        # Update highest_price if current price is higher
                        if current_price > position.get('highest_price', current_price):
                            position['highest_price'] = current_price
                    
                    # Filter SELL signals when there's no position (can't sell what you don't own)
                    # SELL signals are only valid when we have a position to exit
                    if not position and signal == "SELL":
                        # Convert SELL to HOLD - bearish conditions detected but no position to exit
                        signal = "HOLD"
                        # Preserve original bearish reasons but clarify no action can be taken
                        bearish_reasons = ', '.join(reasons)
                        reasons = [f"Bearish: {bearish_reasons}", "No position (cannot exit)"]
                    
                    # Collect data for status notification
                    symbols_data.append({
                        'symbol': symbol,
                        'price': current_price,
                        'signal': signal,
                        'indicators': indicators,
                        'reasons': reasons
                    })
                    
                    # Print status
                    print_status(symbol, signal, indicators, reasons, position, current_price, check_count)
                    
                    # Log check cycle to file
                    logger.log_check_cycle(check_count, symbol, signal, current_price, indicators, reasons, position)
                    
                    # --- ENTRY LOGIC ---
                    if not position and signal in ["BUY", "STRONG_BUY"]:
                        # Check if we can open more positions
                        if len(positions) >= Config.MAX_POSITIONS:
                            reason = f"Max positions ({Config.MAX_POSITIONS}) reached"
                            print(f"⚠️ {reason}. Skipping {symbol}")
                            logger.log_trade_decision(symbol, signal, "SKIPPED", reason, indicators)
                            continue
                        
                        # 📰 SENTIMENT: Check for news/events (skip in TEST MODE)
                        if not Config.TEST_MODE:
                            skip_trade, sentiment_reason = sentiment_filter.should_skip_trading()
                            if skip_trade:
                                print(f"⚠️ Trade skipped: {sentiment_reason}")
                                logger.log_trade_decision(symbol, signal, "SKIPPED", f"Sentiment: {sentiment_reason}", indicators)
                                continue
                        
                        # 📊 SUPPORT/RESISTANCE: Check if near support (good) or resistance (bad)
                        # Skip resistance check in TEST MODE
                        if not Config.TEST_MODE:
                            near_resistance, sr_levels = sr_detector.is_near_resistance(symbol)
                            if near_resistance and sr_levels:
                                reason = f"Price near resistance (₹{sr_levels['nearest_resistance']:.2f})"
                                print(f"⚠️ {reason}, skipping buy")
                                logger.log_trade_decision(symbol, signal, "SKIPPED", reason, indicators)
                                continue
                        
                        near_support, sr_levels = sr_detector.is_near_support(symbol)
                        if near_support:
                            print(f"✅ Price near support (₹{sr_levels['nearest_support']:.2f}), good entry!")
                        
                        # 🧠 LEARNING: Check if we should take this trade based on past performance
                        rsi = indicators.get('RSI', 50)
                        ist = pytz.timezone('Asia/Kolkata')
                        current_hour = datetime.now(ist).hour  # Use IST hour for learning engine
                        should_trade, learn_confidence, learn_reason = learning_engine.should_take_trade(
                            signal, rsi, current_hour
                        )
                        
                        # 🤖 ML MODEL: Get prediction
                        ml_take_trade, ml_probability, ml_confidence = ml_predictor.should_take_trade(indicators)
                        
                        # Combined confidence
                        combined_confidence = (learn_confidence + ml_confidence) / 2
                        
                        print(f"\n🧠 Analysis:")
                        print(f"   Learning Engine: {learn_confidence:.2f} ({learn_reason})")
                        print(f"   ML Prediction: {ml_probability:.2f} probability")
                        print(f"   Combined Confidence: {combined_confidence:.2f}")
                        
                        # Skip confidence checks in TEST MODE
                        if Config.TEST_MODE:
                            print(f"   ✅ TEST MODE: Bypassing confidence checks")
                            combined_confidence = 0.75  # Set reasonable confidence for test
                        elif not should_trade or not ml_take_trade:
                            reason = f"Low confidence - Learning: {learn_confidence:.2f}, ML: {ml_probability:.2f}, {learn_reason}"
                            print(f"   ⚠️ Trade skipped (low confidence)")
                            logger.log_trade_decision(symbol, signal, "SKIPPED", reason, indicators, combined_confidence)
                            notifier.send_message(
                                f"⚠️ Trade SKIPPED for {symbol}\n"
                                f"Signal: {signal}\n"
                                f"Learning: {learn_confidence:.2f}\n"
                                f"ML: {ml_probability:.2f}\n"
                                f"Reason: {learn_reason}"
                            )
                            continue
                        
                        # 📐 KELLY: Calculate optimal position size
                        quantity = position_sizer.calculate_position_size(
                            Config.CAPITAL, current_price, symbol, combined_confidence
                        )
                        
                        if quantity > 0:
                            signal_emoji = "🔥🔥🔥" if signal == "STRONG_BUY" else "📈📈"
                            print(f"\n{signal_emoji} EXECUTING BUY ORDER {signal_emoji}")
                            print(f"   Symbol: {symbol}")
                            print(f"   Quantity: {quantity} units @ ₹{current_price:.2f}")
                            print(f"   📐 Kelly Position: {(quantity * current_price / Config.CAPITAL * 100):.1f}% of capital")
                            print(f"   🧠 Confidence: {combined_confidence:.2f}")
                            
                            if broker.place_order(symbol, quantity, "BUY"):
                                ist = pytz.timezone('Asia/Kolkata')
                                positions[symbol] = {
                                    'quantity': quantity,
                                    'buy_price': current_price,
                                    'highest_price': current_price,
                                    'entry_time': datetime.now(ist).isoformat(),  # Store IST time
                                    'signal_type': signal,
                                    'confidence': combined_confidence,
                                    'bot_entered': True,  # Mark as bot-entered
                                    'current_price': current_price
                                }
                                trade_count += 1
                                
                                # Log and notify
                                logger.log_trade(symbol, "BUY", quantity, current_price, 
                                               signal, "", 0, indicators)
                                logger.log_trade_decision(symbol, signal, "EXECUTED", 
                                                         f"BUY {quantity} units @ ₹{current_price:.2f}", 
                                                         indicators, combined_confidence)
                                logger.save_positions([{**pos, 'symbol': sym} for sym, pos in positions.items()])
                                notifier.send_buy_alert(symbol, quantity, current_price, signal, indicators)
                                
                                print(f"   ✅ Order placed successfully!")
                    
                    # --- EXIT LOGIC ---
                    elif position:
                        # Only process exit logic for positions entered by the bot
                        if not position.get('bot_entered', True):
                            # External position - only track, don't sell
                            if current_price > position.get('highest_price', current_price):
                                position['highest_price'] = current_price
                            position['current_price'] = current_price
                            continue
                        
                        quantity = position['quantity']
                        buy_price = position['buy_price']
                        
                        # Update highest price for trailing stop
                        if current_price > position['highest_price']:
                            position['highest_price'] = current_price
                        
                        highest_price = position['highest_price']
                        
                        # Calculate stop-loss levels
                        fixed_sl = buy_price * (1 - Config.SL_PCT)
                        trailing_sl = highest_price * (1 - Config.TRAILING_SL_PCT)
                        effective_sl = max(fixed_sl, trailing_sl)
                        target = buy_price * (1 + Config.TARGET_PCT)
                        
                        # IMPROVEMENT 5: ATR-based trailing stop (more dynamic)
                        atr_value = indicators.get('ATR', 0)
                        if atr_value > 0:
                            atr_multiplier = 2.0  # Use 2x ATR for trailing stop
                            atr_trailing_sl = highest_price - (atr_value * atr_multiplier)
                            effective_sl = max(effective_sl, atr_trailing_sl)
                        
                        # IMPROVEMENT 6: Partial exit at 50% target
                        partial_target = buy_price * (1 + Config.TARGET_PCT * 0.5)
                        partial_exit_done = position.get('partial_exit_done', False)
                        
                        exit_reason = None
                        exit_quantity = quantity  # Default: exit full position
                        
                        if current_price <= effective_sl:
                            exit_reason = "TRAILING SL" if trailing_sl > fixed_sl else "STOP LOSS"
                        elif current_price >= target:
                            exit_reason = "TARGET HIT"
                        elif not partial_exit_done and current_price >= partial_target:
                            # Partial exit at 50% target - take profits on half position
                            exit_reason = "PARTIAL TARGET (50%)"
                            exit_quantity = max(1, quantity // 2)  # Exit half, keep at least 1 unit
                            position['partial_exit_done'] = True
                        elif signal == "SELL":
                            exit_reason = "TREND REVERSAL"
                        
                        if exit_reason:
                            pnl = (current_price - buy_price) * exit_quantity
                            total_pnl += pnl
                            daily_pnl += pnl
                            monthly_pnl += pnl
                            
                            pnl_emoji = "✅" if pnl >= 0 else "❌"
                            
                            print(f"\n{'='*65}")
                            print(f"🛑 {exit_reason}")
                            print(f"{'='*65}")
                            print(f"   Symbol: {symbol}")
                            print(f"   Selling {exit_quantity} units @ ₹{current_price:.2f}")
                            if exit_quantity < quantity:
                                print(f"   📊 Partial exit: {exit_quantity}/{quantity} units (keeping {quantity - exit_quantity} for full target)")
                            print(f"   {pnl_emoji} Trade PnL: ₹{pnl:.2f}")
                            print(f"   📊 Daily PnL: ₹{daily_pnl:.2f}")
                            print(f"   📈 Total PnL: ₹{total_pnl:.2f}")
                            
                            order_result = broker.place_order(symbol, exit_quantity, "SELL")
                            
                            # Only proceed if order was successful (or in paper trading mode)
                            if order_result or Config.PAPER_TRADING:
                                # Log and notify
                                logger.log_trade(symbol, "SELL", exit_quantity, current_price,
                                               "", exit_reason, pnl, indicators)
                                logger.log_trade_decision(symbol, signal, "EXECUTED", 
                                                         f"SELL {exit_quantity} units @ ₹{current_price:.2f} | {exit_reason} | PnL: ₹{pnl:.2f}", 
                                                         indicators)
                                notifier.send_sell_alert(symbol, exit_quantity, buy_price, current_price, 
                                                       exit_reason, pnl)
                                
                                # Update or remove position
                                if exit_quantity < quantity:
                                    # Partial exit - update position
                                    position['quantity'] -= exit_quantity
                                    # Adjust buy_price for remaining position (weighted average)
                                    remaining_value = (quantity - exit_quantity) * buy_price
                                    position['buy_price'] = remaining_value / (quantity - exit_quantity)
                                    print(f"   📊 Remaining position: {position['quantity']} units @ ₹{position['buy_price']:.2f}")
                                else:
                                    # Full exit - remove position
                                    del positions[symbol]
                                
                                logger.save_positions([{**pos, 'symbol': sym} for sym, pos in positions.items()])
                                
                                # 🧠 LEARNING: Re-analyze trades after each completed trade
                                if exit_quantity == quantity:  # Only update learning on full exits
                                    print(f"\n🧠 Updating learning model...")
                                    learning_engine.analyze_trades()
                                
                                print(f"   ✅ Order placed successfully!")
                            else:
                                print(f"   ⚠️ Order failed - position will remain in tracking")
                                print(f"   💡 You may need to manually place the order for {symbol}")
                                # Keep the position in tracking since order failed
                
                except Exception as e:
                    error_msg = f"Error processing {symbol}: {e}"
                    print(f"❌ {error_msg}")
                    logger.log_error(str(e), f"Processing {symbol}")
                    notifier.send_error_alert(error_msg)
            
            # Process positions for symbols not in trading list (external positions)
            # These positions are tracked for monitoring only - bot will NOT sell them
            tracked_symbols = set(Config.SYMBOLS)
            for symbol, position in list(positions.items()):
                if symbol not in tracked_symbols:
                    try:
                        # Only track external positions - never sell them automatically
                        if not position.get('bot_entered', True):
                            # External position - only update price tracking, never sell
                            try:
                                df = fetch_live_data(symbol)
                                if not df.empty:
                                    df = apply_all_indicators(df)
                                    current_price = get_value(df.iloc[-1]["Close"])
                                    position['current_price'] = current_price
                                    
                                    # Update highest_price for tracking
                                    if current_price > position.get('highest_price', current_price):
                                        position['highest_price'] = current_price
                                    
                                    # Calculate PnL for display only
                                    quantity = position['quantity']
                                    buy_price = position['buy_price']
                                    pnl = (current_price - buy_price) * quantity
                                    pnl_pct = ((current_price - buy_price) / buy_price * 100) if buy_price > 0 else 0
                                    
                                    # Just log status, but don't sell
                                    # Bot will only track external positions, never sell them
                            except Exception as e:
                                # Skip if we can't process this symbol
                                pass
                        else:
                            # Bot-entered position not in trading list - process normally
                            # This shouldn't happen often, but handle it just in case
                            try:
                                df = fetch_live_data(symbol)
                                if not df.empty:
                                    df = apply_all_indicators(df)
                                    current_price = get_value(df.iloc[-1]["Close"])
                                    position['current_price'] = current_price
                                    
                                    # Update highest_price
                                    if current_price > position.get('highest_price', current_price):
                                        position['highest_price'] = current_price
                                    
                                    # Check exit conditions for bot-entered positions
                                    quantity = position['quantity']
                                    buy_price = position['buy_price']
                                    highest_price = position['highest_price']
                                    
                                    fixed_sl = buy_price * (1 - Config.SL_PCT)
                                    trailing_sl = highest_price * (1 - Config.TRAILING_SL_PCT)
                                    effective_sl = max(fixed_sl, trailing_sl)
                                    target = buy_price * (1 + Config.TARGET_PCT)
                                    
                                    exit_reason = None
                                    if current_price <= effective_sl:
                                        exit_reason = "TRAILING SL" if trailing_sl > fixed_sl else "STOP LOSS"
                                    elif current_price >= target:
                                        exit_reason = "TARGET HIT"
                                    
                                    if exit_reason:
                                        pnl = (current_price - buy_price) * quantity
                                        total_pnl += pnl
                                        daily_pnl += pnl
                                        
                                        pnl_emoji = "✅" if pnl >= 0 else "❌"
                                        
                                        print(f"\n{'='*65}")
                                        print(f"🛑 {exit_reason} (Bot Position)")
                                        print(f"{'='*65}")
                                        print(f"   Symbol: {symbol}")
                                        print(f"   Selling {quantity} units @ ₹{current_price:.2f}")
                                        print(f"   {pnl_emoji} Trade PnL: ₹{pnl:.2f}")
                                        
                                        order_result = broker.place_order(symbol, quantity, "SELL")
                                        
                                        # Only proceed if order was successful (or in paper trading mode)
                                        if order_result or Config.PAPER_TRADING:
                                            logger.log_trade(symbol, "SELL", quantity, current_price,
                                                           "", exit_reason, pnl, {})
                                            notifier.send_sell_alert(symbol, quantity, buy_price, current_price, 
                                                                   exit_reason, pnl)
                                            
                                            del positions[symbol]
                                            logger.save_positions([{**pos, 'symbol': sym} for sym, pos in positions.items()])
                                            print(f"   ✅ Order placed successfully!")
                                        else:
                                            print(f"   ⚠️ Order failed - position will remain in tracking")
                                            print(f"   💡 You may need to manually place the order for {symbol}")
                            except Exception as e:
                                # Skip if we can't process this symbol
                                pass
                    except Exception as e:
                        # Skip if we can't process this symbol (might not be tradeable via yfinance)
                        pass
            
            # Send consolidated status notification to Telegram
            if symbols_data:
                notifier.send_check_status(check_count, symbols_data, positions, daily_pnl, total_pnl)
            
            # Log check cycle summary
            symbols_checked = len(symbols_data)
            open_positions = len(positions)
            app_logger.info(f"✅ CHECK #{check_count} COMPLETE | Symbols analyzed: {symbols_checked} | Open positions: {open_positions} | Daily PnL: ₹{daily_pnl:.2f} | Total PnL: ₹{total_pnl:.2f}")
            app_logger.info(f"⏳ Next check in {Config.CHECK_INTERVAL_SECONDS}s")
            
            # Show next check time
            print(f"\n⏳ Next check in {Config.CHECK_INTERVAL_SECONDS}s... (Check #{check_count})")
            
        except Exception as e:
            error_msg = f"Main loop error: {e}"
            print(f"❌ {error_msg}")
            logger.log_error(str(e), "Main loop")
            notifier.send_error_alert(error_msg)
        
        time.sleep(Config.CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
