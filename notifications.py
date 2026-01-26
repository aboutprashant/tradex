import requests
from config import Config
from datetime import datetime

class TelegramNotifier:
    """Sends trading alerts via Telegram."""
    
    def __init__(self):
        self.bot_token = Config.TELEGRAM_BOT_TOKEN
        self.chat_id = Config.TELEGRAM_CHAT_ID
        self.enabled = Config.TELEGRAM_ENABLED
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
    
    def send_message(self, message, parse_mode="HTML"):
        """Send a message to Telegram."""
        if not self.enabled:
            print(f"[Telegram Disabled] {message[:50]}...")
            return False
        
        if not self.bot_token or not self.chat_id:
            print("⚠️ Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
            return False
        
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode
            }
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"⚠️ Telegram send failed: {e}")
            return False
    
    def send_startup_alert(self, capital, symbols):
        """Send bot startup notification."""
        msg = f"""
🚀 <b>ALGO BOT STARTED</b>

⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
💰 Capital: ₹{capital:,.2f}
📊 Symbols: {', '.join(symbols)}
🎯 Mode: {'PAPER TRADING' if Config.PAPER_TRADING else 'LIVE TRADING'}

Bot is now monitoring the market...
        """
        return self.send_message(msg.strip())
    
    def send_buy_alert(self, symbol, quantity, price, signal_type, indicators):
        """Send buy order notification."""
        emoji = "🔥" if signal_type == "STRONG_BUY" else "📈"
        msg = f"""
{emoji} <b>BUY ORDER EXECUTED</b>

📊 Symbol: {symbol}
📦 Quantity: {quantity} units
💵 Price: ₹{price:.2f}
📡 Signal: {signal_type}

<b>Indicators:</b>
• RSI: {indicators.get('RSI', 0):.1f}
• MACD: {indicators.get('MACD', 0):.3f}
• SMA(5): ₹{indicators.get('SMA_5', 0):.2f}
• SMA(20): ₹{indicators.get('SMA_20', 0):.2f}

🛡️ Stop Loss: ₹{price * (1 - Config.SL_PCT):.2f}
🎯 Target: ₹{price * (1 + Config.TARGET_PCT):.2f}
        """
        return self.send_message(msg.strip())
    
    def send_sell_alert(self, symbol, quantity, buy_price, sell_price, reason, pnl):
        """Send sell order notification."""
        emoji = "✅" if pnl >= 0 else "❌"
        pnl_pct = ((sell_price - buy_price) / buy_price) * 100
        
        msg = f"""
{emoji} <b>SELL ORDER EXECUTED</b>

📊 Symbol: {symbol}
📦 Quantity: {quantity} units
💵 Buy Price: ₹{buy_price:.2f}
💵 Sell Price: ₹{sell_price:.2f}
📍 Reason: {reason}

<b>Result:</b>
{'✅' if pnl >= 0 else '❌'} PnL: ₹{pnl:.2f} ({pnl_pct:+.2f}%)
        """
        return self.send_message(msg.strip())
    
    def send_position_update(self, symbol, quantity, buy_price, current_price):
        """Send position status update."""
        pnl = (current_price - buy_price) * quantity
        pnl_pct = ((current_price - buy_price) / buy_price) * 100
        emoji = "🟢" if pnl >= 0 else "🔴"
        
        msg = f"""
📍 <b>POSITION UPDATE</b>

📊 {symbol}
📦 Holding: {quantity} units @ ₹{buy_price:.2f}
💵 Current: ₹{current_price:.2f}
{emoji} Unrealized: ₹{pnl:.2f} ({pnl_pct:+.2f}%)

🛡️ SL: ₹{buy_price * (1 - Config.SL_PCT):.2f}
🎯 Target: ₹{buy_price * (1 + Config.TARGET_PCT):.2f}
        """
        return self.send_message(msg.strip())
    
    def send_daily_summary(self, trades_today, pnl_today, total_pnl, open_positions):
        """Send end-of-day summary."""
        msg = f"""
📊 <b>DAILY SUMMARY</b>
📅 {datetime.now().strftime('%Y-%m-%d')}

📈 Trades Today: {trades_today}
💰 Today's PnL: ₹{pnl_today:.2f}
📊 Total PnL: ₹{total_pnl:.2f}
📍 Open Positions: {open_positions}

Bot will resume tomorrow at market open.
        """
        return self.send_message(msg.strip())
    
    def send_error_alert(self, error_message):
        """Send error notification."""
        msg = f"""
⚠️ <b>ERROR ALERT</b>

{error_message}

Please check the bot logs.
        """
        return self.send_message(msg.strip())
    
    def send_overnight_position_alert(self, positions):
        """Send overnight position holding alert."""
        if not positions:
            return
        
        pos_text = ""
        for pos in positions:
            pnl = (pos.get('current_price', pos['buy_price']) - pos['buy_price']) * pos['quantity']
            pos_text += f"\n• {pos['symbol']}: {pos['quantity']} @ ₹{pos['buy_price']:.2f} (PnL: ₹{pnl:.2f})"
        
        msg = f"""
🌙 <b>OVERNIGHT POSITIONS</b>

The following positions are being held overnight:
{pos_text}

Market closed. Will resume monitoring at 9:15 AM.
        """
        return self.send_message(msg.strip())
    
    def send_market_closed_alert(self, reason, next_open=None):
        """Send market closed notification."""
        now = datetime.now()
        
        if next_open:
            next_open_str = next_open
        elif now.weekday() == 4:  # Friday
            next_open_str = "Monday 9:15 AM"
        elif now.weekday() == 5:  # Saturday
            next_open_str = "Monday 9:15 AM"
        elif now.weekday() == 6:  # Sunday
            next_open_str = "Tomorrow 9:15 AM"
        elif now.hour >= 15:  # After market close
            next_open_str = "Tomorrow 9:15 AM"
        else:
            next_open_str = "9:15 AM today"
        
        msg = f"""
🔒 <b>MARKET CLOSED</b>

⏰ Time: {now.strftime('%Y-%m-%d %H:%M:%S')}
📍 Reason: {reason}
⏳ Next Open: {next_open_str}

Bot is waiting for market to open...
        """
        return self.send_message(msg.strip())
    
    def send_market_open_alert(self):
        """Send market open notification."""
        msg = f"""
🔔 <b>MARKET OPEN!</b>

⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Bot is now actively monitoring for trade signals.
        """
        return self.send_message(msg.strip())


# Singleton instance
notifier = TelegramNotifier()
