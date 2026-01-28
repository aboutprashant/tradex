import pandas as pd
import numpy as np
import yfinance as yf
from src.core.config import Config

def calculate_rsi(prices, period=14):
    """
    RSI (Relative Strength Index): Measures momentum.
    - RSI > 70: Stock is "overbought" (might fall soon)
    - RSI < 30: Stock is "oversold" (might rise soon)
    """
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """
    MACD (Moving Average Convergence Divergence): Trend confirmation.
    - When MACD line crosses above Signal line: Bullish
    - When MACD line crosses below Signal line: Bearish
    """
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_bollinger_bands(prices, period=20, std_dev=2):
    """
    Bollinger Bands: Measures volatility.
    - Price near lower band: Potential buy opportunity
    - Price near upper band: Potential sell opportunity
    """
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper_band = sma + (std_dev * std)
    lower_band = sma - (std_dev * std)
    return upper_band, sma, lower_band

def calculate_atr(high, low, close, period=14):
    """
    ATR (Average True Range): Measures volatility for dynamic stop-loss.
    Higher ATR = More volatile stock = Wider stop-loss needed
    """
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.rolling(window=period).mean()
    return atr

def calculate_ema(prices, period):
    """Exponential Moving Average - more responsive to recent prices."""
    return prices.ewm(span=period, adjust=False).mean()

def apply_all_indicators(df):
    """Apply all technical indicators to the dataframe."""
    # Handle multi-index columns from yfinance
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # Simple Moving Averages
    df["SMA_5"] = df["Close"].rolling(window=5).mean()
    df["SMA_20"] = df["Close"].rolling(window=20).mean()
    df["SMA_50"] = df["Close"].rolling(window=50).mean()
    
    # Exponential Moving Averages
    df["EMA_9"] = calculate_ema(df["Close"], 9)
    df["EMA_21"] = calculate_ema(df["Close"], 21)
    
    # RSI
    df["RSI"] = calculate_rsi(df["Close"], period=14)
    
    # MACD
    df["MACD"], df["MACD_Signal"], df["MACD_Hist"] = calculate_macd(df["Close"])
    
    # Bollinger Bands
    df["BB_Upper"], df["BB_Middle"], df["BB_Lower"] = calculate_bollinger_bands(df["Close"])
    
    # ATR for dynamic stop-loss
    df["ATR"] = calculate_atr(df["High"], df["Low"], df["Close"])
    
    # Volume Moving Average
    df["Volume_SMA"] = df["Volume"].rolling(window=20).mean()
    
    return df


class MultiTimeframeAnalyzer:
    """
    Analyzes multiple timeframes to confirm trade signals.
    Higher timeframe trend should align with lower timeframe entry.
    """
    
    def __init__(self, symbol):
        self.symbol = symbol.replace("-EQ", ".NS")
    
    def get_daily_trend(self):
        """
        Get the overall daily trend.
        Returns: 'BULLISH', 'BEARISH', or 'NEUTRAL'
        """
        try:
            # Retry logic for yfinance API calls
            df = None
            for attempt in range(3):
                try:
                    df = yf.download(self.symbol, period="60d", interval="1d", progress=False, timeout=10, show_errors=False)
                    if df is not None and not df.empty:
                        break
                except Exception as e:
                    if attempt < 2:
                        import time
                        time.sleep(2 * (attempt + 1))  # Exponential backoff
                        continue
                    else:
                        print(f"⚠️ Error fetching daily trend for {self.symbol}: {e}")
                        return "NEUTRAL", {}
            
            if df is None or df.empty or len(df) < 20:
                return "NEUTRAL", {}
            
            df = apply_all_indicators(df)
            latest = df.iloc[-1]
            
            close = self._get_value(latest["Close"])
            sma_20 = self._get_value(latest["SMA_20"])
            sma_50 = self._get_value(latest["SMA_50"])
            rsi = self._get_value(latest["RSI"])
            macd = self._get_value(latest["MACD"])
            macd_signal = self._get_value(latest["MACD_Signal"])
            
            indicators = {
                "daily_close": close,
                "daily_sma_20": sma_20,
                "daily_sma_50": sma_50,
                "daily_rsi": rsi,
                "daily_macd": macd
            }
            
            # Bullish if price > SMA20 > SMA50 and MACD bullish
            if close > sma_20 and sma_20 > sma_50 and macd > macd_signal:
                return "BULLISH", indicators
            
            # Bearish if price < SMA20 < SMA50 and MACD bearish
            if close < sma_20 and sma_20 < sma_50 and macd < macd_signal:
                return "BEARISH", indicators
            
            return "NEUTRAL", indicators
            
        except Exception as e:
            print(f"⚠️ Error getting daily trend: {e}")
            return "NEUTRAL", {}
    
    def get_hourly_trend(self):
        """
        Get the hourly trend for timing entries.
        Returns: 'BULLISH', 'BEARISH', or 'NEUTRAL'
        """
        try:
            # Retry logic for yfinance API calls
            df = None
            for attempt in range(3):
                try:
                    df = yf.download(self.symbol, period="5d", interval="1h", progress=False, timeout=10, show_errors=False)
                    if df is not None and not df.empty:
                        break
                except Exception as e:
                    if attempt < 2:
                        import time
                        time.sleep(2 * (attempt + 1))  # Exponential backoff
                        continue
                    else:
                        print(f"⚠️ Error fetching hourly trend for {self.symbol}: {e}")
                        return "NEUTRAL", {}
            
            if df is None or df.empty or len(df) < 20:
                return "NEUTRAL", {}
            
            df = apply_all_indicators(df)
            latest = df.iloc[-1]
            
            close = self._get_value(latest["Close"])
            sma_20 = self._get_value(latest["SMA_20"])
            ema_9 = self._get_value(latest["EMA_9"])
            ema_21 = self._get_value(latest["EMA_21"])
            rsi = self._get_value(latest["RSI"])
            macd = self._get_value(latest["MACD"])
            macd_signal = self._get_value(latest["MACD_Signal"])
            
            indicators = {
                "hourly_close": close,
                "hourly_ema_9": ema_9,
                "hourly_ema_21": ema_21,
                "hourly_rsi": rsi,
                "hourly_macd": macd
            }
            
            # Bullish if EMA9 > EMA21 and MACD bullish
            if ema_9 > ema_21 and macd > macd_signal:
                return "BULLISH", indicators
            
            # Bearish if EMA9 < EMA21 and MACD bearish
            if ema_9 < ema_21 and macd < macd_signal:
                return "BEARISH", indicators
            
            return "NEUTRAL", indicators
            
        except Exception as e:
            print(f"⚠️ Error getting hourly trend: {e}")
            return "NEUTRAL", {}
    
    def get_multi_timeframe_signal(self):
        """
        Combine daily and hourly trends for final signal.
        Only allows buys when both timeframes are bullish.
        """
        daily_trend, daily_indicators = self.get_daily_trend()
        hourly_trend, hourly_indicators = self.get_hourly_trend()
        
        combined_indicators = {**daily_indicators, **hourly_indicators}
        
        # Strong buy: Both daily and hourly bullish
        if daily_trend == "BULLISH" and hourly_trend == "BULLISH":
            return "STRONG_BULLISH", combined_indicators
        
        # Moderate buy: Daily bullish, hourly neutral
        if daily_trend == "BULLISH" and hourly_trend == "NEUTRAL":
            return "BULLISH", combined_indicators
        
        # Sell signal: Both bearish
        if daily_trend == "BEARISH" and hourly_trend == "BEARISH":
            return "BEARISH", combined_indicators
        
        # Wait: Mixed signals
        return "NEUTRAL", combined_indicators
    
    def _get_value(self, series_or_scalar):
        """Helper to extract a single float value."""
        if isinstance(series_or_scalar, pd.Series):
            return float(series_or_scalar.iloc[0])
        return float(series_or_scalar)
