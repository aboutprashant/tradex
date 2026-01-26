#!/bin/bash
# ============================================
# DEPLOYMENT SCRIPT FOR TRADING BOT
# ============================================
# This script sets up the trading bot for automatic startup
# Run: ./deploy.sh
# ============================================

BOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_FILE="$BOT_DIR/com.prashant.tradingbot.plist"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"

echo "🚀 TRADING BOT DEPLOYMENT"
echo "========================="
echo ""

# 1. Check if venv exists
if [ ! -d "$BOT_DIR/venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "   Please run: python3 -m venv venv"
    exit 1
fi

# 2. Check if .env exists
if [ ! -f "$BOT_DIR/.env" ]; then
    echo "❌ .env file not found!"
    echo "   Please copy env.example to .env and fill in your credentials"
    exit 1
fi

# 3. Create logs directory
mkdir -p "$BOT_DIR/logs"
echo "✅ Logs directory created"

# 4. Make bot.sh executable
chmod +x "$BOT_DIR/bot.sh"
echo "✅ bot.sh made executable"

# 5. Install dependencies
echo ""
echo "📦 Installing dependencies..."
"$BOT_DIR/venv/bin/pip" install -r "$BOT_DIR/requirements.txt" -q
echo "✅ Dependencies installed"

# 6. Test the bot briefly
echo ""
echo "🧪 Testing bot startup..."
cd "$BOT_DIR"
"$BOT_DIR/venv/bin/python" -c "
from config import Config
from broker_client import BrokerClient
print('✅ Config loaded')
print(f'   Symbols: {Config.SYMBOLS}')
print(f'   Capital: ₹{Config.CAPITAL}')
print(f'   Mode: {\"PAPER\" if Config.PAPER_TRADING else \"LIVE\"}')
"

if [ $? -ne 0 ]; then
    echo "❌ Bot test failed! Please check your configuration."
    exit 1
fi

# 7. Ask about auto-start
echo ""
echo "📅 AUTO-START SETUP"
echo "==================="
echo "Do you want the bot to automatically start at 9:00 AM on weekdays?"
echo ""
read -p "Install auto-start? (y/n): " INSTALL_AUTOSTART

if [ "$INSTALL_AUTOSTART" = "y" ] || [ "$INSTALL_AUTOSTART" = "Y" ]; then
    # Create LaunchAgents directory if needed
    mkdir -p "$LAUNCHD_DIR"
    
    # Copy plist file
    cp "$PLIST_FILE" "$LAUNCHD_DIR/"
    
    # Load the launch agent
    launchctl unload "$LAUNCHD_DIR/com.prashant.tradingbot.plist" 2>/dev/null
    launchctl load "$LAUNCHD_DIR/com.prashant.tradingbot.plist"
    
    echo "✅ Auto-start configured!"
    echo "   Bot will start at 9:00 AM on weekdays"
fi

echo ""
echo "🎉 DEPLOYMENT COMPLETE!"
echo "======================="
echo ""
echo "📋 QUICK COMMANDS:"
echo "   Start bot:    ./bot.sh start"
echo "   Stop bot:     ./bot.sh stop"
echo "   View status:  ./bot.sh status"
echo "   View logs:    ./bot.sh logs"
echo ""
echo "📱 You will receive Telegram alerts for all trades!"
echo ""

# Ask if they want to start now
read -p "Start the bot now? (y/n): " START_NOW

if [ "$START_NOW" = "y" ] || [ "$START_NOW" = "Y" ]; then
    "$BOT_DIR/bot.sh" start
fi
