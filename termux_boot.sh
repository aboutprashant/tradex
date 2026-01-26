#!/data/data/com.termux/files/usr/bin/bash
# ============================================
# Termux Auto-Start Script for Trading Bot
# Place this in ~/.termux/boot/
# ============================================

# Wait for network
sleep 30

# Navigate to project
cd ~/Algo

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Start the bot
nohup python script.py > logs/bot.log 2>&1 &

# Optional: Start dashboard
# nohup python dashboard.py > logs/dashboard.log 2>&1 &

echo "Trading bot started at $(date)" >> logs/startup.log
