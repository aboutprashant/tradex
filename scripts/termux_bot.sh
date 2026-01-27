#!/data/data/com.termux/files/usr/bin/bash
# ============================================
# Termux Bot Control Script
# Simpler version for Android
# ============================================

cd ~/Algo

case "$1" in
    start)
        echo "🚀 Starting Trading Bot..."
        termux-wake-lock
        nohup python src/core/script.py > logs/bot.log 2>&1 &
        echo $! > logs/bot.pid
        echo "✅ Bot started! PID: $(cat logs/bot.pid)"
        ;;
    stop)
        if [ -f logs/bot.pid ]; then
            kill $(cat logs/bot.pid) 2>/dev/null
            rm logs/bot.pid
            echo "🛑 Bot stopped"
        else
            echo "⚠️ Bot not running"
        fi
        ;;
    status)
        if [ -f logs/bot.pid ] && ps -p $(cat logs/bot.pid) > /dev/null 2>&1; then
            echo "✅ Bot is running (PID: $(cat logs/bot.pid))"
        else
            echo "⚠️ Bot is not running"
        fi
        ;;
    logs)
        tail -50 logs/bot.log
        ;;
    restart)
        $0 stop
        sleep 2
        $0 start
        ;;
    *)
        echo "Usage: $0 {start|stop|status|logs|restart}"
        ;;
esac
