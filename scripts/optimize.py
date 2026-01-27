import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import yfinance as yf
import pandas as pd
import itertools
from src.indicators.indicators import apply_all_indicators

def get_value(series_or_scalar):
    if isinstance(series_or_scalar, pd.Series):
        return float(series_or_scalar.iloc[0])
    return float(series_or_scalar)


def run_backtest_with_params(df, capital, sl_pct, target_pct, trailing_sl_pct, 
                              rsi_oversold, rsi_overbought, volume_mult):
    """
    Run backtest with specific parameters.
    Returns: dict with pnl, win_rate, trades, etc.
    """
    initial_capital = capital
    current_capital = capital
    position = 0
    buy_price = 0
    highest_price = 0
    trades = []

    for i in range(30, len(df)):
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

        # BUY LOGIC
        if position == 0:
            sma_crossover = (sma_5_prev < sma_20_prev) and (sma_5 > sma_20)
            rsi_ok = rsi < rsi_overbought
            macd_bullish = macd > macd_signal
            volume_ok = volume > (volume_avg * volume_mult)
            near_bb_lower = close <= bb_lower * 1.02

            buy_signal = False

            if sma_crossover and rsi < rsi_oversold and macd_bullish and volume_ok:
                buy_signal = True
            elif sma_crossover and rsi_ok and macd_bullish:
                buy_signal = True
            elif near_bb_lower and rsi < rsi_oversold and macd_bullish:
                buy_signal = True

            if buy_signal:
                quantity = int(current_capital // close)
                if quantity > 0:
                    position = quantity
                    buy_price = close
                    highest_price = close
                    current_capital -= position * buy_price
                    trades.append({"type": "BUY", "price": buy_price})

        # SELL LOGIC
        else:
            if close > highest_price:
                highest_price = close

            fixed_sl = buy_price * (1 - sl_pct)
            trailing_sl = highest_price * (1 - trailing_sl_pct)
            effective_sl = max(fixed_sl, trailing_sl)
            target = buy_price * (1 + target_pct)

            sma_crossover_sell = (sma_5_prev > sma_20_prev) and (sma_5 < sma_20)
            macd_bearish = macd < macd_signal

            should_sell = False
            if close <= effective_sl:
                should_sell = True
            elif close >= target:
                should_sell = True
            elif sma_crossover_sell and macd_bearish:
                should_sell = True

            if should_sell:
                pnl = (close - buy_price) * position
                current_capital += position * close
                trades.append({"type": "SELL", "pnl": pnl})
                position = 0
                buy_price = 0
                highest_price = 0

    final_value = current_capital + (position * get_value(df.iloc[-1]["Close"]) if position > 0 else 0)
    total_pnl = final_value - initial_capital
    pnl_pct = (total_pnl / initial_capital) * 100

    sell_trades = [t for t in trades if t["type"] == "SELL"]
    total_trades = len(sell_trades)
    wins = len([t for t in sell_trades if t.get("pnl", 0) > 0])
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

    return {
        "pnl": total_pnl,
        "pnl_pct": pnl_pct,
        "win_rate": win_rate,
        "total_trades": total_trades,
        "wins": wins,
        "final_value": final_value
    }


def optimize_parameters(symbol, days=180, capital=1000):
    """
    Grid search to find the best parameter combination.
    """
    print(f"🔬 PARAMETER OPTIMIZATION for {symbol}")
    print(f"   Testing all combinations... This may take a minute.\n")

    yf_symbol = symbol.replace("-EQ", ".NS")
    data = yf.download(yf_symbol, period=f"{days}d", interval="1h", progress=False)
    df = apply_all_indicators(data.copy())

    # Parameter Grid
    sl_range = [0.01, 0.015, 0.02]           # Stop Loss: 1%, 1.5%, 2%
    target_range = [0.02, 0.03, 0.04]        # Target: 2%, 3%, 4%
    trailing_range = [0.005, 0.01, 0.015]    # Trailing SL: 0.5%, 1%, 1.5%
    rsi_oversold_range = [30, 35, 40]        # RSI Oversold
    rsi_overbought_range = [60, 65, 70]      # RSI Overbought
    volume_mult_range = [1.0, 1.2, 1.5]      # Volume Multiplier

    best_result = None
    best_params = None
    results = []

    combinations = list(itertools.product(
        sl_range, target_range, trailing_range, 
        rsi_oversold_range, rsi_overbought_range, volume_mult_range
    ))

    print(f"   Testing {len(combinations)} parameter combinations...\n")

    for params in combinations:
        sl, target, trailing, rsi_os, rsi_ob, vol_mult = params
        
        result = run_backtest_with_params(
            df, capital, sl, target, trailing, rsi_os, rsi_ob, vol_mult
        )
        result["params"] = {
            "SL_PCT": sl, "TARGET_PCT": target, "TRAILING_SL_PCT": trailing,
            "RSI_OVERSOLD": rsi_os, "RSI_OVERBOUGHT": rsi_ob, "VOLUME_MULT": vol_mult
        }
        results.append(result)

        # Score: Prioritize profit but also consider win rate and number of trades
        score = result["pnl"] * (result["win_rate"] / 100) * (1 + result["total_trades"] / 50)
        
        if best_result is None or score > best_result["score"]:
            result["score"] = score
            best_result = result
            best_params = params

    # Print Top 5 Results
    results.sort(key=lambda x: x["pnl"], reverse=True)
    
    print("="*60)
    print("🏆 TOP 5 PARAMETER COMBINATIONS (by Profit)")
    print("="*60)
    
    for i, r in enumerate(results[:5], 1):
        p = r["params"]
        print(f"\n#{i}: PnL: ₹{r['pnl']:.2f} ({r['pnl_pct']:.2f}%) | Win Rate: {r['win_rate']:.1f}% | Trades: {r['total_trades']}")
        print(f"    SL: {p['SL_PCT']*100}% | Target: {p['TARGET_PCT']*100}% | Trailing: {p['TRAILING_SL_PCT']*100}%")
        print(f"    RSI: {p['RSI_OVERSOLD']}-{p['RSI_OVERBOUGHT']} | Vol Mult: {p['VOLUME_MULT']}")

    print("\n" + "="*60)
    print("✅ RECOMMENDED PARAMETERS (Best Overall Score)")
    print("="*60)
    p = best_result["params"]
    print(f"PnL: ₹{best_result['pnl']:.2f} ({best_result['pnl_pct']:.2f}%)")
    print(f"Win Rate: {best_result['win_rate']:.1f}%")
    print(f"Total Trades: {best_result['total_trades']}")
    print(f"\nUpdate your config.py with:")
    print("-"*40)
    print(f"SL_PCT = {p['SL_PCT']}")
    print(f"TARGET_PCT = {p['TARGET_PCT']}")
    print(f"TRAILING_SL_PCT = {p['TRAILING_SL_PCT']}")
    print(f"RSI_OVERSOLD = {p['RSI_OVERSOLD']}")
    print(f"RSI_OVERBOUGHT = {p['RSI_OVERBOUGHT']}")
    print(f"VOLUME_MULTIPLIER = {p['VOLUME_MULT']}")

    return best_result


if __name__ == "__main__":
    optimize_parameters("NIFTYBEES-EQ", days=180, capital=1000)
