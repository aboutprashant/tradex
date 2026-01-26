import time
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from config import Config
from broker_client import BrokerClient
from indicators import apply_all_indicators, MultiTimeframeAnalyzer
from notifications import notifier
from trade_logger import logger
from learning_engine import learning_engine
from symbols import symbol_manager, SYMBOL_UNIVERSE
from position_sizing import position_sizer
from support_resistance import sr_detector
from ml_model import ml_predictor
from sentiment import sentiment_filter

# ============================================
# UTILITY FUNCTIONS
# ============================================

def get_value(series_or_scalar):
    """Helper to extract a single float value from a Series or scalar."""
    if isinstance(series_or_scalar, pd.Series):
        return float(series_or_scalar.iloc[0])
    return float(series_or_scalar)


def is_market_open():
    """Check if the market is currently open (9:15 AM - 3:30 PM IST, Mon-Fri)."""
    now = datetime.now()
    
    # Check if it's a weekday
    if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False, "Weekend"
    
    market_open = now.replace(hour=Config.MARKET_OPEN_HOUR, minute=Config.MARKET_OPEN_MINUTE, second=0)
    market_close = now.replace(hour=Config.MARKET_CLOSE_HOUR, minute=Config.MARKET_CLOSE_MINUTE, second=0)
    
    if now < market_open:
        return False, f"Market opens at {Config.MARKET_OPEN_HOUR}:{Config.MARKET_OPEN_MINUTE:02d}"
    if now > market_close:
        return False, f"Market closed at {Config.MARKET_CLOSE_HOUR}:{Config.MARKET_CLOSE_MINUTE:02d}"
    
    return True, "Market Open"


def is_high_liquidity_window():
    """Check if we're in a high liquidity trading window."""
    now = datetime.now()
    current_minutes = now.hour * 60 + now.minute
    
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
    
    # Multi-timeframe filter - only buy if higher timeframes are bullish
    mtf_bullish = mtf_trend in ["STRONG_BULLISH", "BULLISH"]
    mtf_bearish = mtf_trend == "BEARISH"

    reasons = []

    # --- BUY CONDITIONS (with MTF confirmation) ---
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

    # --- SELL CONDITIONS ---
    if sma_crossover_sell and macd_bearish:
        reasons = ["SMA Crossover Down ✓", "MACD Bearish ✓"]
        return "SELL", indicators, reasons
    
    if mtf_bearish and macd_bearish:
        reasons = ["MTF Bearish ✓", "MACD Bearish ✓"]
        return "SELL", indicators, reasons

    # --- HOLD - Show why we're not trading ---
    hold_reasons = []
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
    
    return "HOLD", indicators, hold_reasons if hold_reasons else ["No signal"]


# ============================================
# DISPLAY FUNCTIONS
# ============================================

def print_status(symbol, signal, indicators, reasons, position, current_price, check_count):
    """Print a formatted status update."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
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
        print(f"📍 POSITION: {position['quantity']} units @ ₹{position['buy_price']:.2f}")
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
    broker = BrokerClient()
    if not broker.login():
        return

    # State management
    positions = {}  # symbol -> {quantity, buy_price, highest_price, entry_time}
    total_pnl = 0
    trade_count = 0
    daily_pnl = 0
    monthly_pnl = 0
    
    # Load any existing positions from previous run
    saved_positions = logger.load_positions()
    for pos in saved_positions:
        positions[pos['symbol']] = pos
        print(f"📍 Loaded position: {pos['symbol']} - {pos['quantity']} @ ₹{pos['buy_price']:.2f}")

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
    print(f"   Symbols: {', '.join(Config.SYMBOLS)}")
    print(f"   Capital: ₹{Config.CAPITAL}")
    print(f"   Stop Loss: {Config.SL_PCT*100}% | Target: {Config.TARGET_PCT*100}%")
    print(f"   Trailing SL: {Config.TRAILING_SL_PCT*100}%")
    print(f"   Max Daily Loss: {Config.MAX_DAILY_LOSS_PCT*100}%")
    print(f"   Check Interval: {Config.CHECK_INTERVAL_SECONDS}s")
    print(f"   Mode: {'PAPER TRADING' if Config.PAPER_TRADING else 'LIVE TRADING'}")
    print(f"\n⏳ Starting market monitoring...")

    check_count = 0
    last_daily_summary = None
    last_market_closed_alert = None
    market_was_open = False

    while True:
        try:
            check_count += 1
            now = datetime.now()
            
            # Check if market is open
            market_open, market_status = is_market_open()
            
            if not market_open:
                # Send market closed notification (only once per session)
                if last_market_closed_alert != now.date():
                    notifier.send_market_closed_alert(market_status)
                    last_market_closed_alert = now.date()
                    market_was_open = False
                
                # Send overnight position alert at market close
                if positions and last_daily_summary != now.date():
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
                    last_daily_summary = now.date()
                    daily_pnl = 0  # Reset daily PnL
                
                print(f"\n⏳ {market_status}. Sleeping for 5 minutes...")
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
            
            # Process each symbol
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
                    
                    # Print status
                    print_status(symbol, signal, indicators, reasons, position, current_price, check_count)
                    
                    # --- ENTRY LOGIC ---
                    if not position and signal in ["BUY", "STRONG_BUY"]:
                        # Check if we can open more positions
                        if len(positions) >= Config.MAX_POSITIONS:
                            print(f"⚠️ Max positions ({Config.MAX_POSITIONS}) reached. Skipping {symbol}")
                            continue
                        
                        # 📰 SENTIMENT: Check for news/events
                        skip_trade, sentiment_reason = sentiment_filter.should_skip_trading()
                        if skip_trade:
                            print(f"⚠️ Trade skipped: {sentiment_reason}")
                            continue
                        
                        # 📊 SUPPORT/RESISTANCE: Check if near support (good) or resistance (bad)
                        near_resistance, sr_levels = sr_detector.is_near_resistance(symbol)
                        if near_resistance and sr_levels:
                            print(f"⚠️ Price near resistance (₹{sr_levels['nearest_resistance']:.2f}), skipping buy")
                            continue
                        
                        near_support, sr_levels = sr_detector.is_near_support(symbol)
                        if near_support:
                            print(f"✅ Price near support (₹{sr_levels['nearest_support']:.2f}), good entry!")
                        
                        # 🧠 LEARNING: Check if we should take this trade based on past performance
                        rsi = indicators.get('RSI', 50)
                        current_hour = datetime.now().hour
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
                        
                        if not should_trade or not ml_take_trade:
                            print(f"   ⚠️ Trade skipped (low confidence)")
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
                                positions[symbol] = {
                                    'quantity': quantity,
                                    'buy_price': current_price,
                                    'highest_price': current_price,
                                    'entry_time': datetime.now().isoformat(),
                                    'signal_type': signal,
                                    'confidence': combined_confidence
                                }
                                trade_count += 1
                                
                                # Log and notify
                                logger.log_trade(symbol, "BUY", quantity, current_price, 
                                               signal, "", 0, indicators)
                                logger.save_positions([{**pos, 'symbol': sym} for sym, pos in positions.items()])
                                notifier.send_buy_alert(symbol, quantity, current_price, signal, indicators)
                                
                                print(f"   ✅ Order placed successfully!")
                    
                    # --- EXIT LOGIC ---
                    elif position:
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
                        
                        exit_reason = None
                        if current_price <= effective_sl:
                            exit_reason = "TRAILING SL" if trailing_sl > fixed_sl else "STOP LOSS"
                        elif current_price >= target:
                            exit_reason = "TARGET HIT"
                        elif signal == "SELL":
                            exit_reason = "TREND REVERSAL"
                        
                        if exit_reason:
                            pnl = (current_price - buy_price) * quantity
                            total_pnl += pnl
                            daily_pnl += pnl
                            monthly_pnl += pnl
                            
                            pnl_emoji = "✅" if pnl >= 0 else "❌"
                            
                            print(f"\n{'='*65}")
                            print(f"🛑 {exit_reason}")
                            print(f"{'='*65}")
                            print(f"   Symbol: {symbol}")
                            print(f"   Selling {quantity} units @ ₹{current_price:.2f}")
                            print(f"   {pnl_emoji} Trade PnL: ₹{pnl:.2f}")
                            print(f"   📊 Daily PnL: ₹{daily_pnl:.2f}")
                            print(f"   📈 Total PnL: ₹{total_pnl:.2f}")
                            
                            broker.place_order(symbol, quantity, "SELL")
                            
                            # Log and notify
                            logger.log_trade(symbol, "SELL", quantity, current_price,
                                           "", exit_reason, pnl, indicators)
                            notifier.send_sell_alert(symbol, quantity, buy_price, current_price, 
                                                   exit_reason, pnl)
                            
                            # Remove position
                            del positions[symbol]
                            logger.save_positions([{**pos, 'symbol': sym} for sym, pos in positions.items()])
                            
                            # 🧠 LEARNING: Re-analyze trades after each completed trade
                            print(f"\n🧠 Updating learning model...")
                            learning_engine.analyze_trades()
                            
                            print(f"   ✅ Order placed successfully!")
                
                except Exception as e:
                    print(f"❌ Error processing {symbol}: {e}")
                    notifier.send_error_alert(f"Error processing {symbol}: {e}")
            
            # Show next check time
            print(f"\n⏳ Next check in {Config.CHECK_INTERVAL_SECONDS}s... (Check #{check_count})")
            
        except Exception as e:
            print(f"❌ Error in main loop: {e}")
            notifier.send_error_alert(f"Main loop error: {e}")
        
        time.sleep(Config.CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
