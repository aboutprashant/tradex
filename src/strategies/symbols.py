"""
Symbol Manager with Sector Rotation
Dynamically selects the best performing symbols to trade.
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from src.core.config import Config

# All available symbols for trading
SYMBOL_UNIVERSE = {
    # ETFs
    "GOLDBEES-EQ": {"name": "Gold ETF", "sector": "Commodities", "token": "14428"},
    "SILVERBEES-EQ": {"name": "Silver ETF", "sector": "Commodities", "token": "14429"},
    "NIFTYBEES-EQ": {"name": "Nifty 50 ETF", "sector": "Index", "token": "10571"},
    "BANKBEES-EQ": {"name": "Bank Nifty ETF", "sector": "Banking", "token": "16236"},
    "JUNIORBEES-EQ": {"name": "Nifty Next 50 ETF", "sector": "Index", "token": "14427"},
    "CPSEETF-EQ": {"name": "CPSE ETF", "sector": "PSU", "token": "36441"},
    
    # Liquid large caps (for reference)
    "RELIANCE-EQ": {"name": "Reliance Industries", "sector": "Energy", "token": "2885"},
    "TCS-EQ": {"name": "TCS", "sector": "IT", "token": "11536"},
    "HDFCBANK-EQ": {"name": "HDFC Bank", "sector": "Banking", "token": "1333"},
    "INFY-EQ": {"name": "Infosys", "sector": "IT", "token": "1594"},
    "ICICIBANK-EQ": {"name": "ICICI Bank", "sector": "Banking", "token": "4963"},
}


class SymbolManager:
    """
    Manages symbol selection and sector rotation.
    Selects the best performing symbols based on momentum.
    """
    
    def __init__(self):
        self.performance_cache = {}
        self.last_update = None
        self.update_interval = timedelta(hours=4)  # Update every 4 hours
    
    def get_symbol_info(self, symbol):
        """Get symbol metadata."""
        return SYMBOL_UNIVERSE.get(symbol, {"name": symbol, "sector": "Unknown", "token": "0"})
    
    def get_yf_symbol(self, symbol):
        """Convert Angel One symbol to Yahoo Finance symbol."""
        return symbol.replace("-EQ", ".NS")
    
    def calculate_momentum(self, symbol, days=20):
        """
        Calculate momentum score for a symbol.
        Higher score = stronger upward momentum.
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
                        print(f"⚠️ Error fetching momentum for {symbol}: {e}")
                        return 0
            
            if df is None or df.empty or len(df) < 10:
                return 0
            
            # Handle multi-index
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # Calculate returns
            returns = df['Close'].pct_change().dropna()
            
            # Momentum score: weighted recent returns
            if len(returns) < 5:
                return 0
            
            # Recent returns weighted more heavily
            weights = [1, 1, 2, 2, 3]  # Last 5 days
            recent_returns = returns.tail(5).values
            weighted_return = sum(r * w for r, w in zip(recent_returns, weights)) / sum(weights)
            
            # Volatility adjustment (lower vol = higher score)
            volatility = returns.std()
            if volatility > 0:
                sharpe_like = weighted_return / volatility
            else:
                sharpe_like = weighted_return
            
            # Trend strength (price above moving averages)
            current_price = float(df['Close'].iloc[-1])
            sma_10 = float(df['Close'].rolling(10).mean().iloc[-1])
            sma_20 = float(df['Close'].rolling(20).mean().iloc[-1])
            
            trend_score = 0
            if current_price > sma_10:
                trend_score += 1
            if current_price > sma_20:
                trend_score += 1
            if sma_10 > sma_20:
                trend_score += 1
            
            # Combined score
            momentum_score = (sharpe_like * 100) + (trend_score * 10)
            
            return momentum_score
            
        except Exception as e:
            print(f"⚠️ Error calculating momentum for {symbol}: {e}")
            return 0
    
    def rank_symbols(self, symbols=None):
        """
        Rank symbols by momentum score.
        Returns list of (symbol, score) tuples sorted by score descending.
        """
        if symbols is None:
            symbols = list(SYMBOL_UNIVERSE.keys())
        
        now = datetime.now()
        
        # Use cache if recent
        if self.last_update and (now - self.last_update) < self.update_interval:
            if self.performance_cache:
                return sorted(self.performance_cache.items(), key=lambda x: x[1], reverse=True)
        
        print("📊 Calculating symbol momentum scores...")
        
        scores = {}
        for symbol in symbols:
            score = self.calculate_momentum(symbol)
            scores[symbol] = score
            info = self.get_symbol_info(symbol)
            print(f"   {symbol} ({info['sector']}): {score:.2f}")
        
        self.performance_cache = scores
        self.last_update = now
        
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    def get_top_symbols(self, n=3, min_score=0):
        """
        Get top N symbols by momentum.
        Useful for sector rotation strategy.
        """
        ranked = self.rank_symbols()
        top = [(sym, score) for sym, score in ranked if score > min_score][:n]
        return [sym for sym, score in top]
    
    def get_sector_leaders(self):
        """
        Get the best performing symbol from each sector.
        """
        sectors = {}
        ranked = self.rank_symbols()
        
        for symbol, score in ranked:
            info = self.get_symbol_info(symbol)
            sector = info['sector']
            
            if sector not in sectors:
                sectors[sector] = (symbol, score)
        
        return sectors
    
    def should_rotate(self, current_symbols, threshold=20):
        """
        Check if we should rotate to better performing symbols.
        Returns True if there are significantly better options.
        """
        ranked = self.rank_symbols()
        
        if not ranked:
            return False, []
        
        # Get scores for current symbols
        current_scores = {sym: self.performance_cache.get(sym, 0) for sym in current_symbols}
        avg_current = sum(current_scores.values()) / len(current_scores) if current_scores else 0
        
        # Get top available symbols
        top_symbols = ranked[:len(current_symbols)]
        avg_top = sum(score for _, score in top_symbols) / len(top_symbols) if top_symbols else 0
        
        # Rotate if top symbols are significantly better
        if avg_top > avg_current + threshold:
            new_symbols = [sym for sym, _ in top_symbols]
            return True, new_symbols
        
        return False, current_symbols


# Singleton instance
symbol_manager = SymbolManager()
