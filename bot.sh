#!/bin/bash
# ============================================
# TRADING BOT CONTROL SCRIPT
# ============================================
# Usage:
#   ./bot.sh start   - Start the bot
#   ./bot.sh stop    - Stop the bot
#   ./bot.sh restart - Restart the bot
#   ./bot.sh status  - Check if bot is running
#   ./bot.sh logs    - View live logs
# ============================================

BOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="$BOT_DIR/venv/bin/python"
SCRIPT="$BOT_DIR/script.py"
PID_FILE="$BOT_DIR/bot.pid"
LOG_FILE="$BOT_DIR/logs/bot.log"

# Ensure log directory exists
mkdir -p "$BOT_DIR/logs"

start_bot() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "⚠️  Bot is already running (PID: $PID)"
            return 1
        fi
    fi
    
    echo "🚀 Starting Trading Bot..."
    cd "$BOT_DIR"
    
    # Load environment variables
    if [ -f "$BOT_DIR/.env" ]; then
        export $(cat "$BOT_DIR/.env" | grep -v '^#' | xargs)
    fi
    
    # Start the bot in background (with unbuffered output for real-time logs)
    nohup "$VENV_PYTHON" -u "$SCRIPT" >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    
    sleep 2
    
    if ps -p $(cat "$PID_FILE") > /dev/null 2>&1; then
        echo "✅ Bot started successfully (PID: $(cat $PID_FILE))"
        echo "📝 Logs: tail -f $LOG_FILE"
    else
        echo "❌ Failed to start bot. Check logs: $LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

stop_bot() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "🛑 Stopping Trading Bot (PID: $PID)..."
            kill $PID
            sleep 2
            
            if ps -p $PID > /dev/null 2>&1; then
                echo "⚠️  Bot didn't stop gracefully, forcing..."
                kill -9 $PID
            fi
            
            rm -f "$PID_FILE"
            echo "✅ Bot stopped"
        else
            echo "⚠️  Bot is not running (stale PID file)"
            rm -f "$PID_FILE"
        fi
    else
        # Try to find and kill any running instance
        PIDS=$(pgrep -f "python.*script.py")
        if [ -n "$PIDS" ]; then
            echo "🛑 Stopping Trading Bot..."
            kill $PIDS
            echo "✅ Bot stopped"
        else
            echo "⚠️  Bot is not running"
        fi
    fi
}

status_bot() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "✅ Bot is running (PID: $PID)"
            echo ""
            echo "📊 Process Info:"
            ps -p $PID -o pid,ppid,%cpu,%mem,etime,command
            return 0
        else
            echo "❌ Bot is not running (stale PID file)"
            rm -f "$PID_FILE"
            return 1
        fi
    else
        PIDS=$(pgrep -f "python.*script.py")
        if [ -n "$PIDS" ]; then
            echo "✅ Bot is running (PID: $PIDS)"
            return 0
        else
            echo "❌ Bot is not running"
            return 1
        fi
    fi
}

view_logs() {
    if [ -f "$LOG_FILE" ]; then
        echo "📝 Viewing logs (Ctrl+C to exit)..."
        tail -f "$LOG_FILE"
    else
        echo "⚠️  No log file found"
    fi
}

case "$1" in
    start)
        start_bot
        ;;
    stop)
        stop_bot
        ;;
    restart)
        stop_bot
        sleep 2
        start_bot
        ;;
    status)
        status_bot
        ;;
    logs)
        view_logs
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the trading bot"
        echo "  stop    - Stop the trading bot"
        echo "  restart - Restart the trading bot"
        echo "  status  - Check if bot is running"
        echo "  logs    - View live logs"
        exit 1
        ;;
esac
