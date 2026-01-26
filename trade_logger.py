import os
import json
import csv
from datetime import datetime
from config import Config

class TradeLogger:
    """Logs all trades and positions to files for record keeping."""
    
    def __init__(self):
        self.log_dir = Config.LOG_DIR
        self.trade_file = os.path.join(self.log_dir, Config.TRADE_LOG_FILE)
        self.position_file = os.path.join(self.log_dir, Config.POSITION_LOG_FILE)
        self._ensure_log_dir()
        self._ensure_trade_file()
    
    def _ensure_log_dir(self):
        """Create log directory if it doesn't exist."""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
    
    def _ensure_trade_file(self):
        """Create trade CSV file with headers if it doesn't exist."""
        if not os.path.exists(self.trade_file):
            with open(self.trade_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'symbol', 'action', 'quantity', 'price',
                    'signal_type', 'reason', 'pnl', 'rsi', 'macd',
                    'sma_5', 'sma_20', 'is_paper'
                ])
    
    def log_trade(self, symbol, action, quantity, price, signal_type="", reason="", 
                  pnl=0, indicators=None):
        """Log a trade to CSV file."""
        indicators = indicators or {}
        
        row = [
            datetime.now().isoformat(),
            symbol,
            action,
            quantity,
            f"{price:.2f}",
            signal_type,
            reason,
            f"{pnl:.2f}" if pnl else "",
            f"{indicators.get('RSI', ''):.1f}" if indicators.get('RSI') else "",
            f"{indicators.get('MACD', ''):.3f}" if indicators.get('MACD') else "",
            f"{indicators.get('SMA_5', ''):.2f}" if indicators.get('SMA_5') else "",
            f"{indicators.get('SMA_20', ''):.2f}" if indicators.get('SMA_20') else "",
            "PAPER" if Config.PAPER_TRADING else "LIVE"
        ]
        
        with open(self.trade_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(row)
        
        print(f"📝 Trade logged: {action} {quantity} {symbol} @ ₹{price:.2f}")
    
    def save_positions(self, positions):
        """Save current open positions to JSON file."""
        data = {
            'last_updated': datetime.now().isoformat(),
            'positions': positions
        }
        with open(self.position_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_positions(self):
        """Load open positions from JSON file (for bot restart recovery)."""
        if not os.path.exists(self.position_file):
            return []
        
        try:
            with open(self.position_file, 'r') as f:
                data = json.load(f)
                return data.get('positions', [])
        except Exception as e:
            print(f"⚠️ Error loading positions: {e}")
            return []
    
    def get_daily_stats(self):
        """Get today's trading statistics."""
        today = datetime.now().strftime('%Y-%m-%d')
        trades_today = []
        
        if not os.path.exists(self.trade_file):
            return {'trades': 0, 'pnl': 0, 'wins': 0, 'losses': 0}
        
        with open(self.trade_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['timestamp'].startswith(today):
                    trades_today.append(row)
        
        sell_trades = [t for t in trades_today if t['action'] == 'SELL']
        total_pnl = sum(float(t['pnl']) for t in sell_trades if t['pnl'])
        wins = len([t for t in sell_trades if float(t['pnl'] or 0) > 0])
        losses = len([t for t in sell_trades if float(t['pnl'] or 0) < 0])
        
        return {
            'trades': len(sell_trades),
            'pnl': total_pnl,
            'wins': wins,
            'losses': losses
        }
    
    def get_monthly_stats(self):
        """Get this month's trading statistics."""
        this_month = datetime.now().strftime('%Y-%m')
        trades_month = []
        
        if not os.path.exists(self.trade_file):
            return {'trades': 0, 'pnl': 0, 'wins': 0, 'losses': 0}
        
        with open(self.trade_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['timestamp'].startswith(this_month):
                    trades_month.append(row)
        
        sell_trades = [t for t in trades_month if t['action'] == 'SELL']
        total_pnl = sum(float(t['pnl']) for t in sell_trades if t['pnl'])
        wins = len([t for t in sell_trades if float(t['pnl'] or 0) > 0])
        losses = len([t for t in sell_trades if float(t['pnl'] or 0) < 0])
        
        return {
            'trades': len(sell_trades),
            'pnl': total_pnl,
            'wins': wins,
            'losses': losses
        }


# Singleton instance
logger = TradeLogger()
