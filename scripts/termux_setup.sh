#!/data/data/com.termux/files/usr/bin/bash
# ============================================
# Termux Setup Script
# Run this once to set up the bot on Android
# ============================================

echo "🤖 Setting up Trading Bot on Termux..."
echo ""

# Update packages
echo "📦 Updating packages..."
pkg update -y && pkg upgrade -y

# Install dependencies
echo "📦 Installing Python and dependencies..."
pkg install python git termux-api -y

# Install Python packages
echo "🐍 Installing Python packages..."
pip install smartapi-python pyotp python-dotenv pandas yfinance requests numpy

# Try to install optional packages (may fail on some devices)
pip install flask scikit-learn 2>/dev/null || echo "⚠️ Flask/sklearn not available, using fallback"

# Create logs directory
mkdir -p logs

# Make scripts executable
chmod +x bot.sh
chmod +x dashboard.sh 2>/dev/null

# Set up auto-start with Termux:Boot
echo ""
echo "📱 Setting up auto-start..."
mkdir -p ~/.termux/boot
cp termux_boot.sh ~/.termux/boot/start_bot.sh
chmod +x ~/.termux/boot/start_bot.sh

# Acquire wake lock to prevent sleep
echo ""
echo "🔋 Acquiring wake lock..."
termux-wake-lock

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Edit .env with your credentials: nano .env"
echo "   2. Test the bot: python src/core/script.py"
echo "   3. Start in background: ./bot.sh start"
echo ""
echo "📱 The bot will auto-start when Termux opens!"
echo "🔋 Wake lock acquired - phone won't sleep while Termux is open"
