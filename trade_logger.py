import os
import json
import csv
import logging
from datetime import datetime
from config import Config

# Set up file logging
def setup_logging():
    """Configure logging to file and console."""
    log_dir = Config.LOG_DIR
    today = datetime.now().strftime('%Y-%m-%d')
    daily_log_dir = os.path.join(log_dir, today)
    
    if not os.path.exists(daily_log_dir):
        os.makedirs(daily_log_dir)
    
    log_file = os.path.join(daily_log_dir, 'app.log')
    
    # Create logger
    logger = logging.getLogger('tradex')
    logger.setLevel(logging.DEBUG)
    
    # Clear existing handlers
    logger.handlers = []
    
    # File handler - logs everything
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
    file_handler.setFormatter(file_formatter)
    
    # Console handler - only INFO and above
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Initialize the app logger
app_logger = setup_logging()

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
    
    def log_check_cycle(self, check_count, symbol, signal, price, indicators, reasons, position=None):
        """Log every check cycle for analysis."""
        indicators = indicators or {}
        reasons_str = ', '.join(reasons) if reasons else 'No reasons'
        
        # Build position info
        position_info = ""
        if position:
            pnl = (price - position['buy_price']) * position['quantity']
            pnl_pct = ((price - position['buy_price']) / position['buy_price']) * 100
            position_info = f" | Position: {position['quantity']} @ ₹{position['buy_price']:.2f} | PnL: ₹{pnl:.2f} ({pnl_pct:+.2f}%)"
        
        log_msg = (
            f"CHECK #{check_count} | {symbol} | {signal} | Price: ₹{price:.2f} | "
            f"RSI: {indicators.get('RSI', 0):.1f} | MACD: {indicators.get('MACD', 0):.3f} | "
            f"SMA5: ₹{indicators.get('SMA_5', 0):.2f} | SMA20: ₹{indicators.get('SMA_20', 0):.2f} | "
            f"MTF: {indicators.get('MTF_Trend', 'N/A')} | Reasons: {reasons_str}{position_info}"
        )
        
        app_logger.info(log_msg)
    
    def log_trade_decision(self, symbol, signal, decision, reason, indicators=None, confidence=None):
        """Log trade decisions (why we took or skipped a trade)."""
        indicators = indicators or {}
        conf_str = f" | Confidence: {confidence:.2f}" if confidence else ""
        
        log_msg = (
            f"TRADE DECISION | {symbol} | Signal: {signal} | Decision: {decision} | "
            f"Reason: {reason} | RSI: {indicators.get('RSI', 0):.1f}{conf_str}"
        )
        
        app_logger.info(log_msg)
    
    def log_error(self, error_msg, context=""):
        """Log errors with context."""
        log_msg = f"ERROR | {context} | {error_msg}" if context else f"ERROR | {error_msg}"
        app_logger.error(log_msg)
    
    def log_market_status(self, status, reason=""):
        """Log market open/close status."""
        log_msg = f"MARKET STATUS | {status}" + (f" | {reason}" if reason else "")
        app_logger.info(log_msg)


# Singleton instance
logger = TradeLogger()
