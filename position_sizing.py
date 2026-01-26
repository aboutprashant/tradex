"""
Position Sizing with Kelly Criterion
Calculates optimal position size based on historical win rate and payoff ratio.
"""
import os
import csv
from config import Config

class PositionSizer:
    """
    Implements Kelly Criterion and other position sizing strategies.
    
    Kelly Formula: f* = (p * b - q) / b
    Where:
        f* = fraction of capital to bet
        p = probability of winning
        b = ratio of win to loss (payoff ratio)
        q = probability of losing (1 - p)
    """
    
    def __init__(self):
        self.trade_file = os.path.join(Config.LOG_DIR, Config.TRADE_LOG_FILE)
        self.min_trades_for_kelly = 10  # Need at least 10 trades for reliable Kelly
        self.max_kelly_fraction = 0.25  # Never bet more than 25% (half-Kelly is safer)
    
    def get_trade_statistics(self, symbol=None):
        """
        Calculate win rate and average win/loss from trade history.
        """
        if not os.path.exists(self.trade_file):
            return None
        
        wins = []
        losses = []
        
        try:
            with open(self.trade_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['action'] != 'SELL':
                        continue
                    
                    if symbol and row.get('symbol') != symbol:
                        continue
                    
                    pnl = float(row.get('pnl', 0) or 0)
                    
                    if pnl > 0:
                        wins.append(pnl)
                    elif pnl < 0:
                        losses.append(abs(pnl))
        except Exception as e:
            print(f"⚠️ Error reading trade history: {e}")
            return None
        
        total_trades = len(wins) + len(losses)
        
        if total_trades < self.min_trades_for_kelly:
            return None
        
        win_rate = len(wins) / total_trades
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 1  # Avoid division by zero
        
        return {
            'total_trades': total_trades,
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'payoff_ratio': avg_win / avg_loss if avg_loss > 0 else 1
        }
    
    def calculate_kelly_fraction(self, stats=None, symbol=None):
        """
        Calculate the Kelly Criterion optimal fraction.
        """
        if stats is None:
            stats = self.get_trade_statistics(symbol)
        
        if stats is None:
            # Not enough data, use conservative default
            return Config.MAX_POSITION_PCT
        
        p = stats['win_rate']  # Probability of winning
        q = 1 - p  # Probability of losing
        b = stats['payoff_ratio']  # Win/Loss ratio
        
        # Kelly formula
        kelly = (p * b - q) / b
        
        # Clamp to reasonable range
        kelly = max(0, min(kelly, self.max_kelly_fraction))
        
        # Use half-Kelly for safety (reduces variance)
        half_kelly = kelly / 2
        
        return half_kelly
    
    def calculate_position_size(self, capital, price, symbol=None, confidence=1.0):
        """
        Calculate the number of shares/units to buy.
        
        Args:
            capital: Available capital
            price: Current price per unit
            symbol: Symbol to trade (for symbol-specific stats)
            confidence: Learning engine confidence (0-1)
        
        Returns:
            quantity: Number of units to buy
        """
        # Get Kelly fraction
        kelly_fraction = self.calculate_kelly_fraction(symbol=symbol)
        
        # Adjust by confidence
        adjusted_fraction = kelly_fraction * confidence
        
        # Calculate position value
        position_value = capital * adjusted_fraction
        
        # Calculate quantity
        quantity = int(position_value // price)
        
        # Ensure at least 1 unit if we have enough capital
        if quantity == 0 and capital >= price:
            quantity = 1
        
        return quantity
    
    def get_sizing_recommendation(self, capital, price, symbol=None):
        """
        Get a detailed position sizing recommendation.
        """
        stats = self.get_trade_statistics(symbol)
        kelly = self.calculate_kelly_fraction(stats, symbol)
        quantity = self.calculate_position_size(capital, price, symbol)
        
        recommendation = {
            'quantity': quantity,
            'position_value': quantity * price,
            'position_pct': (quantity * price) / capital * 100 if capital > 0 else 0,
            'kelly_fraction': kelly,
            'method': 'kelly' if stats else 'default'
        }
        
        if stats:
            recommendation['stats'] = stats
        
        return recommendation


# Singleton instance
position_sizer = PositionSizer()
