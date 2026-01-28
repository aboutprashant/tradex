"""
Support and Resistance Level Detection
Identifies key price levels for better entry/exit decisions.
"""
import pandas as pd
import numpy as np
import yfinance as yf

class SupportResistance:
    """
    Detects support and resistance levels using multiple methods:
    1. Pivot Points (Daily)
    2. Swing Highs/Lows
    3. Volume Profile (Price levels with high volume)
    """
    
    def __init__(self):
        self.cache = {}
    
    def get_yf_symbol(self, symbol):
        """Convert to Yahoo Finance symbol."""
        return symbol.replace("-EQ", ".NS")
    
    def calculate_pivot_points(self, high, low, close):
        """
        Calculate classic pivot points.
        Returns: dict with pivot, support levels (S1, S2, S3), resistance levels (R1, R2, R3)
        """
        pivot = (high + low + close) / 3
        
        r1 = 2 * pivot - low
        s1 = 2 * pivot - high
        
        r2 = pivot + (high - low)
        s2 = pivot - (high - low)
        
        r3 = high + 2 * (pivot - low)
        s3 = low - 2 * (high - pivot)
        
        return {
            'pivot': pivot,
            'r1': r1, 'r2': r2, 'r3': r3,
            's1': s1, 's2': s2, 's3': s3
        }
    
    def find_swing_points(self, df, window=5):
        """
        Find swing highs and lows.
        A swing high is a high that is higher than 'window' bars on each side.
        """
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        highs = df['High'].values
        lows = df['Low'].values
        
        swing_highs = []
        swing_lows = []
        
        for i in range(window, len(df) - window):
            # Check for swing high
            is_swing_high = True
            for j in range(1, window + 1):
                if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                    is_swing_high = False
                    break
            if is_swing_high:
                swing_highs.append(highs[i])
            
            # Check for swing low
            is_swing_low = True
            for j in range(1, window + 1):
                if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                    is_swing_low = False
                    break
            if is_swing_low:
                swing_lows.append(lows[i])
        
        return swing_highs, swing_lows
    
    def cluster_levels(self, levels, tolerance_pct=0.5):
        """
        Cluster nearby price levels into zones.
        Returns representative levels for each cluster.
        """
        if not levels:
            return []
        
        levels = sorted(levels)
        clusters = []
        current_cluster = [levels[0]]
        
        for level in levels[1:]:
            if abs(level - current_cluster[-1]) / current_cluster[-1] <= tolerance_pct / 100:
                current_cluster.append(level)
            else:
                clusters.append(sum(current_cluster) / len(current_cluster))
                current_cluster = [level]
        
        clusters.append(sum(current_cluster) / len(current_cluster))
        
        return clusters
    
    def get_levels(self, symbol, days=60):
        """
        Get all support and resistance levels for a symbol.
        """
        try:
            yf_symbol = self.get_yf_symbol(symbol)
            # Retry logic for yfinance API calls
            df = None
            for attempt in range(3):
                try:
                    df = yf.download(yf_symbol, period=f"{days}d", interval="1d", progress=False, timeout=10)
                    if df is not None and not df.empty:
                        break
                except Exception as e:
                    if attempt < 2:
                        import time
                        time.sleep(2 * (attempt + 1))  # Exponential backoff
                        continue
                    else:
                        print(f"⚠️ Error fetching support/resistance for {symbol}: {e}")
                        return None
            
            if df is None or df.empty:
                return None
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # Get yesterday's data for pivot points
            yesterday = df.iloc[-2] if len(df) > 1 else df.iloc[-1]
            pivot_points = self.calculate_pivot_points(
                float(yesterday['High']),
                float(yesterday['Low']),
                float(yesterday['Close'])
            )
            
            # Get swing points
            swing_highs, swing_lows = self.find_swing_points(df)
            
            # Combine and cluster resistance levels
            all_resistance = [pivot_points['r1'], pivot_points['r2'], pivot_points['r3']]
            all_resistance.extend(swing_highs[-10:])  # Last 10 swing highs
            resistance_levels = self.cluster_levels(all_resistance)
            
            # Combine and cluster support levels
            all_support = [pivot_points['s1'], pivot_points['s2'], pivot_points['s3']]
            all_support.extend(swing_lows[-10:])  # Last 10 swing lows
            support_levels = self.cluster_levels(all_support)
            
            current_price = float(df['Close'].iloc[-1])
            
            # Find nearest levels
            nearest_support = max([s for s in support_levels if s < current_price], default=None)
            nearest_resistance = min([r for r in resistance_levels if r > current_price], default=None)
            
            return {
                'current_price': current_price,
                'pivot': pivot_points['pivot'],
                'support_levels': sorted(support_levels),
                'resistance_levels': sorted(resistance_levels),
                'nearest_support': nearest_support,
                'nearest_resistance': nearest_resistance,
                'distance_to_support_pct': ((current_price - nearest_support) / current_price * 100) if nearest_support else None,
                'distance_to_resistance_pct': ((nearest_resistance - current_price) / current_price * 100) if nearest_resistance else None
            }
            
        except Exception as e:
            print(f"⚠️ Error calculating S/R for {symbol}: {e}")
            return None
    
    def is_near_support(self, symbol, threshold_pct=2):
        """
        Check if price is near a support level.
        Good for buying opportunities.
        """
        levels = self.get_levels(symbol)
        if not levels or levels['distance_to_support_pct'] is None:
            return False, None
        
        is_near = levels['distance_to_support_pct'] <= threshold_pct
        return is_near, levels
    
    def is_near_resistance(self, symbol, threshold_pct=2):
        """
        Check if price is near a resistance level.
        Consider taking profits or avoiding new buys.
        """
        levels = self.get_levels(symbol)
        if not levels or levels['distance_to_resistance_pct'] is None:
            return False, None
        
        is_near = levels['distance_to_resistance_pct'] <= threshold_pct
        return is_near, levels
    
    def get_risk_reward(self, symbol, entry_price=None):
        """
        Calculate risk-reward ratio based on S/R levels.
        """
        levels = self.get_levels(symbol)
        if not levels:
            return None
        
        price = entry_price or levels['current_price']
        support = levels['nearest_support']
        resistance = levels['nearest_resistance']
        
        if not support or not resistance:
            return None
        
        risk = price - support  # Distance to stop loss
        reward = resistance - price  # Distance to target
        
        if risk <= 0:
            return None
        
        ratio = reward / risk
        
        return {
            'entry': price,
            'stop_loss': support,
            'target': resistance,
            'risk': risk,
            'reward': reward,
            'risk_reward_ratio': ratio
        }


# Singleton instance
sr_detector = SupportResistance()
