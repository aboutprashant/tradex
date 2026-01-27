import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import yfinance as yf
import pandas as pd
from src.core.config import Config
from src.indicators.indicators import apply_all_indicators, MultiTimeframeAnalyzer

def get_value(series_or_scalar):
    """Helper to extract a single float value."""
    if isinstance(series_or_scalar, pd.Series):
        return float(series_or_scalar.iloc[0])
    return float(series_or_scalar)


def backtest_symbol(symbol, days=180, interval="1h"):
    """
    Backtest the OPTIMIZED strategy with multi-timeframe analysis.
    """
    print(f"\n{'='*60}")
    print(f"🔍 BACKTESTING: {symbol}")
    print(f"{'='*60}")
    
    yf_symbol = symbol.replace("-EQ", ".NS")
    data = yf.download(yf_symbol, period=f"{days}d", interval=interval, progress=False)
    
    if data.empty:
        print(f"❌ No data found for {symbol}")
        return None

    df = apply_all_indicators(data.copy())
    
    # Simulation State
    initial_capital = Config.CAPITAL
    capital = initial_capital
    position = None
    highest_price = 0
    trades = []

    for i in range(50, len(df)):
        row = df.iloc[i]
        prev_row = df.iloc[i-1]
        
        close = get_value(row["Close"])
        sma_5 = get_value(row["SMA_5"])
        sma_20 = get_value(row["SMA_20"])
        sma_5_prev = get_value(prev_row["SMA_5"])
        sma_20_prev = get_value(prev_row["SMA_20"])
        rsi = get_value(row["RSI"])
        macd = get_value(row["MACD"])
        macd_signal = get_value(row["MACD_Signal"])
        volume = get_value(row["Volume"])
        volume_avg = get_value(row["Volume_SMA"])
        bb_lower = get_value(row["BB_Lower"])
        ema_9 = get_value(row["EMA_9"])
        ema_21 = get_value(row["EMA_21"])

        # Simulate multi-timeframe trend (simplified for backtest)
        # Using EMA crossover as proxy for higher timeframe trend
        mtf_bullish = ema_9 > ema_21 and close > sma_20

        # --- BUY LOGIC ---
        if position is None:
            sma_crossover = (sma_5_prev < sma_20_prev) and (sma_5 > sma_20)
            rsi_ok = rsi < Config.RSI_OVERBOUGHT
            macd_bullish = macd > macd_signal
            volume_ok = volume > (volume_avg * Config.VOLUME_MULTIPLIER)
            near_bb_lower = close <= bb_lower * 1.02
            rsi_oversold = rsi < Config.RSI_OVERSOLD

            buy_signal = False
            signal_type = ""

            if mtf_bullish:
                if sma_crossover and rsi_oversold and macd_bullish and volume_ok:
                    buy_signal = True
                    signal_type = "STRONG_BUY"
                elif sma_crossover and rsi_ok and macd_bullish:
                    buy_signal = True
                    signal_type = "BUY"
                elif near_bb_lower and rsi_oversold and macd_bullish:
                    buy_signal = True
                    signal_type = "BOUNCE_BUY"

            if buy_signal:
                quantity = int(capital // close)
                if quantity > 0:
                    position = {
                        'quantity': quantity,
                        'buy_price': close,
                        'entry_idx': i
                    }
                    highest_price = close
                    capital -= quantity * close
                    trades.append({
                        "type": signal_type, 
                        "price": close, 
                        "date": df.index[i],
                        "rsi": rsi,
                        "quantity": quantity
                    })

        # --- SELL LOGIC ---
        elif position:
            if close > highest_price:
                highest_price = close

            buy_price = position['buy_price']
            quantity = position['quantity']
            
            fixed_sl = buy_price * (1 - Config.SL_PCT)
            trailing_sl = highest_price * (1 - Config.TRAILING_SL_PCT)
            effective_sl = max(fixed_sl, trailing_sl)
            target = buy_price * (1 + Config.TARGET_PCT)

            sma_crossover_sell = (sma_5_prev > sma_20_prev) and (sma_5 < sma_20)
            macd_bearish = macd < macd_signal

            reason = ""
            if close <= effective_sl:
                reason = "Trailing SL" if trailing_sl > fixed_sl else "Stop Loss"
            elif close >= target:
                reason = "Target Hit"
            elif sma_crossover_sell and macd_bearish:
                reason = "Trend Reversal"

            if reason:
                pnl = (close - buy_price) * quantity
                capital += quantity * close
                trades.append({
                    "type": "SELL", 
                    "price": close, 
                    "date": df.index[i], 
                    "reason": reason,
                    "pnl": pnl,
                    "hold_time": i - position['entry_idx']
                })
                position = None
                highest_price = 0

    # --- RESULTS ---
    final_value = capital + (position['quantity'] * get_value(df.iloc[-1]["Close"]) if position else 0)
    total_pnl = final_value - initial_capital
    pnl_pct = (total_pnl / initial_capital) * 100

    sell_trades = [t for t in trades if t["type"] == "SELL"]
    total_trades = len(sell_trades)
    wins = len([t for t in sell_trades if t.get("pnl", 0) > 0])
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

    # Calculate average win and loss
    win_amounts = [t["pnl"] for t in sell_trades if t.get("pnl", 0) > 0]
    loss_amounts = [t["pnl"] for t in sell_trades if t.get("pnl", 0) <= 0]
    avg_win = sum(win_amounts) / len(win_amounts) if win_amounts else 0
    avg_loss = sum(loss_amounts) / len(loss_amounts) if loss_amounts else 0
    
    # Average hold time
    hold_times = [t.get("hold_time", 0) for t in sell_trades]
    avg_hold = sum(hold_times) / len(hold_times) if hold_times else 0

    print(f"\nSymbol:           {symbol}")
    print(f"Period:           {days} days ({interval})")
    print(f"Initial Capital:  ₹{initial_capital:.2f}")
    print(f"Final Value:      ₹{final_value:.2f}")
    print(f"Total PnL:        ₹{total_pnl:.2f} ({pnl_pct:.2f}%)")
    print(f"{'─'*60}")
    print(f"Total Trades:     {total_trades}")
    print(f"Wins:             {wins} | Losses: {total_trades - wins}")
    print(f"Win Rate:         {win_rate:.1f}%")
    print(f"Avg Win:          ₹{avg_win:.2f}")
    print(f"Avg Loss:         ₹{avg_loss:.2f}")
    print(f"Avg Hold Time:    {avg_hold:.1f} bars")
    
    if len(trades) > 0:
        print(f"\n📝 Last 5 Trades:")
        for t in trades[-5:]:
            reason_str = f" ({t['reason']})" if 'reason' in t else ""
            pnl_str = f" PnL: ₹{t['pnl']:.2f}" if 'pnl' in t else ""
            rsi_str = f" RSI: {t['rsi']:.1f}" if 'rsi' in t else ""
            print(f"   {t['date'].strftime('%Y-%m-%d %H:%M')} | {t['type']} @ ₹{t['price']:.2f}{reason_str}{pnl_str}{rsi_str}")

    return {
        "symbol": symbol,
        "pnl": total_pnl,
        "pnl_pct": pnl_pct,
        "win_rate": win_rate,
        "total_trades": total_trades,
        "final_value": final_value,
        "avg_win": avg_win,
        "avg_loss": avg_loss
    }


def backtest_all_symbols():
    """Backtest all configured symbols and show combined results."""
    print(f"\n{'🔍'*30}")
    print(f"MULTI-SYMBOL BACKTEST")
    print(f"{'🔍'*30}")
    
    results = []
    for symbol in Config.SYMBOLS:
        result = backtest_symbol(symbol, days=180, interval="1h")
        if result:
            results.append(result)
    
    if results:
        print(f"\n{'='*60}")
        print(f"📊 COMBINED RESULTS")
        print(f"{'='*60}")
        
        total_pnl = sum(r['pnl'] for r in results)
        avg_win_rate = sum(r['win_rate'] for r in results) / len(results)
        total_trades = sum(r['total_trades'] for r in results)
        
        print(f"\nSymbols Tested:   {', '.join(r['symbol'] for r in results)}")
        print(f"Combined PnL:     ₹{total_pnl:.2f}")
        print(f"Avg Win Rate:     {avg_win_rate:.1f}%")
        print(f"Total Trades:     {total_trades}")
        
        print(f"\n📊 Per-Symbol Summary:")
        for r in results:
            emoji = "🟢" if r['pnl'] >= 0 else "🔴"
            print(f"   {emoji} {r['symbol']}: ₹{r['pnl']:.2f} ({r['pnl_pct']:.1f}%) | Win Rate: {r['win_rate']:.1f}% | Trades: {r['total_trades']}")


if __name__ == "__main__":
    backtest_all_symbols()
