#!/bin/bash
# ============================================
# Dashboard Control Script
# Usage: ./dashboard.sh [start|stop|status]
# ============================================

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_PYTHON="$SCRIPT_DIR/venv/bin/python"
PID_FILE="$SCRIPT_DIR/logs/dashboard.pid"
LOG_FILE="$SCRIPT_DIR/logs/dashboard.log"

start() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "⚠️ Dashboard already running (PID: $PID)"
            echo "   Visit: http://localhost:5000"
            return
        fi
    fi
    
    echo "🌐 Starting Dashboard..."
    cd "$SCRIPT_DIR"
    source "$SCRIPT_DIR/venv/bin/activate"
    
    nohup "$VENV_PYTHON" dashboard.py > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    
    sleep 2
    echo "✅ Dashboard started! PID: $(cat $PID_FILE)"
    echo "🌐 Visit: http://localhost:5000"
}

stop() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "🛑 Stopping Dashboard (PID: $PID)..."
            kill $PID
            rm -f "$PID_FILE"
            echo "✅ Dashboard stopped"
        else
            echo "⚠️ Dashboard not running (stale PID file)"
            rm -f "$PID_FILE"
        fi
    else
        echo "⚠️ Dashboard is not running"
    fi
}

status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "✅ Dashboard is running (PID: $PID)"
            echo "🌐 URL: http://localhost:5000"
        else
            echo "⚠️ Dashboard is not running (stale PID file)"
        fi
    else
        echo "⚠️ Dashboard is not running"
    fi
}

logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -50 "$LOG_FILE"
    else
        echo "No logs found"
    fi
}

case "$1" in
    start) start ;;
    stop) stop ;;
    status) status ;;
    restart) stop; sleep 1; start ;;
    logs) logs ;;
    *)
        echo "Usage: $0 {start|stop|status|restart|logs}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the dashboard"
        echo "  stop    - Stop the dashboard"
        echo "  status  - Check if dashboard is running"
        echo "  restart - Restart the dashboard"
        echo "  logs    - View dashboard logs"
        exit 1
        ;;
esac
