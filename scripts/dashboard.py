"""
Web Dashboard for Trading Bot Monitoring
Real-time view of positions, trades, and performance.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import csv
import json
from datetime import datetime
from flask import Flask, render_template_string, jsonify
from src.core.config import Config

app = Flask(__name__)

# HTML Template with embedded CSS and JS
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚀 Trading Bot Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'SF Mono', 'Fira Code', monospace;
            background: linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 50%, #16213e 100%);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
        }
        
        .header {
            text-align: center;
            padding: 20px;
            margin-bottom: 30px;
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        
        .header h1 {
            font-size: 2.5em;
            background: linear-gradient(90deg, #00ff88, #00ccff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        
        .status-badge {
            display: inline-block;
            padding: 8px 20px;
            border-radius: 20px;
            font-weight: bold;
            animation: pulse 2s infinite;
        }
        
        .status-running { background: #00ff8855; color: #00ff88; }
        .status-stopped { background: #ff555555; color: #ff5555; }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .card {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(255,255,255,0.1);
            transition: transform 0.3s, box-shadow 0.3s;
        }
        
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0,255,136,0.2);
        }
        
        .card h3 {
            color: #00ccff;
            margin-bottom: 15px;
            font-size: 1.2em;
        }
        
        .stat {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        
        .stat:last-child { border-bottom: none; }
        
        .stat-label { color: #888; }
        .stat-value { font-weight: bold; }
        .stat-value.positive { color: #00ff88; }
        .stat-value.negative { color: #ff5555; }
        
        .positions-table, .trades-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        
        .positions-table th, .trades-table th {
            text-align: left;
            padding: 12px;
            background: rgba(0,204,255,0.2);
            color: #00ccff;
        }
        
        .positions-table td, .trades-table td {
            padding: 12px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        
        .positions-table tr:hover, .trades-table tr:hover {
            background: rgba(255,255,255,0.05);
        }
        
        .trade-buy { color: #00ff88; }
        .trade-sell { color: #ff5555; }
        
        .refresh-btn {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: linear-gradient(135deg, #00ff88, #00ccff);
            color: #000;
            border: none;
            padding: 15px 30px;
            border-radius: 30px;
            font-weight: bold;
            cursor: pointer;
            font-size: 1em;
            transition: transform 0.3s;
        }
        
        .refresh-btn:hover {
            transform: scale(1.1);
        }
        
        .chart-container {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 30px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        
        .no-data {
            text-align: center;
            padding: 40px;
            color: #666;
            font-style: italic;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 Trading Bot Dashboard</h1>
        <p style="margin-bottom: 10px;">Real-time monitoring for your algo trading</p>
        <span class="status-badge {{ 'status-running' if status.running else 'status-stopped' }}">
            {{ '● RUNNING' if status.running else '○ STOPPED' }}
        </span>
        <span style="margin-left: 20px; color: #888;">
            Mode: {{ 'PAPER' if config.paper_trading else 'LIVE' }}
        </span>
    </div>
    
    <div class="grid">
        <div class="card">
            <h3>📊 Performance</h3>
            <div class="stat">
                <span class="stat-label">Total PnL</span>
                <span class="stat-value {{ 'positive' if stats.total_pnl >= 0 else 'negative' }}">
                    ₹{{ "%.2f"|format(stats.total_pnl) }}
                </span>
            </div>
            <div class="stat">
                <span class="stat-label">Today's PnL</span>
                <span class="stat-value {{ 'positive' if stats.daily_pnl >= 0 else 'negative' }}">
                    ₹{{ "%.2f"|format(stats.daily_pnl) }}
                </span>
            </div>
            <div class="stat">
                <span class="stat-label">Win Rate</span>
                <span class="stat-value">{{ "%.1f"|format(stats.win_rate) }}%</span>
            </div>
            <div class="stat">
                <span class="stat-label">Total Trades</span>
                <span class="stat-value">{{ stats.total_trades }}</span>
            </div>
        </div>
        
        <div class="card">
            <h3>⚙️ Configuration</h3>
            <div class="stat">
                <span class="stat-label">Capital</span>
                <span class="stat-value">₹{{ config.capital }}</span>
            </div>
            <div class="stat">
                <span class="stat-label">Symbols</span>
                <span class="stat-value">{{ config.symbols|join(', ') }}</span>
            </div>
            <div class="stat">
                <span class="stat-label">Stop Loss</span>
                <span class="stat-value">{{ config.sl_pct }}%</span>
            </div>
            <div class="stat">
                <span class="stat-label">Target</span>
                <span class="stat-value">{{ config.target_pct }}%</span>
            </div>
        </div>
        
        <div class="card">
            <h3>🧠 Learning Engine</h3>
            <div class="stat">
                <span class="stat-label">Trades Analyzed</span>
                <span class="stat-value">{{ learning.trades_analyzed }}</span>
            </div>
            <div class="stat">
                <span class="stat-label">Best Signal</span>
                <span class="stat-value">{{ learning.best_signal }}</span>
            </div>
            <div class="stat">
                <span class="stat-label">Optimal RSI</span>
                <span class="stat-value">{{ learning.rsi_range }}</span>
            </div>
            <div class="stat">
                <span class="stat-label">Status</span>
                <span class="stat-value positive">Active</span>
            </div>
        </div>
        
        <div class="card">
            <h3>📅 Market Status</h3>
            <div class="stat">
                <span class="stat-label">Market</span>
                <span class="stat-value {{ 'positive' if market.is_open else 'negative' }}">
                    {{ 'OPEN' if market.is_open else 'CLOSED' }}
                </span>
            </div>
            <div class="stat">
                <span class="stat-label">Sentiment</span>
                <span class="stat-value">{{ market.sentiment }}</span>
            </div>
            <div class="stat">
                <span class="stat-label">Events Today</span>
                <span class="stat-value">{{ market.events or 'None' }}</span>
            </div>
            <div class="stat">
                <span class="stat-label">Last Update</span>
                <span class="stat-value">{{ status.last_update }}</span>
            </div>
        </div>
    </div>
    
    <div class="card" style="margin-bottom: 30px;">
        <h3>📍 Open Positions</h3>
        {% if positions %}
        <table class="positions-table">
            <thead>
                <tr>
                    <th>Symbol</th>
                    <th>Qty</th>
                    <th>Entry</th>
                    <th>Current</th>
                    <th>PnL</th>
                    <th>PnL %</th>
                </tr>
            </thead>
            <tbody>
                {% for pos in positions %}
                <tr>
                    <td>{{ pos.symbol }}</td>
                    <td>{{ pos.quantity }}</td>
                    <td>₹{{ "%.2f"|format(pos.buy_price) }}</td>
                    <td>₹{{ "%.2f"|format(pos.current_price) }}</td>
                    <td class="{{ 'positive' if pos.pnl >= 0 else 'negative' }}">
                        ₹{{ "%.2f"|format(pos.pnl) }}
                    </td>
                    <td class="{{ 'positive' if pos.pnl_pct >= 0 else 'negative' }}">
                        {{ "%.2f"|format(pos.pnl_pct) }}%
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p class="no-data">No open positions</p>
        {% endif %}
    </div>
    
    <div class="card">
        <h3>📜 Recent Trades</h3>
        {% if trades %}
        <table class="trades-table">
            <thead>
                <tr>
                    <th>Time</th>
                    <th>Symbol</th>
                    <th>Action</th>
                    <th>Price</th>
                    <th>PnL</th>
                </tr>
            </thead>
            <tbody>
                {% for trade in trades[-10:]|reverse %}
                <tr>
                    <td>{{ trade.timestamp }}</td>
                    <td>{{ trade.symbol }}</td>
                    <td class="{{ 'trade-buy' if 'BUY' in trade.action else 'trade-sell' }}">
                        {{ trade.action }}
                    </td>
                    <td>₹{{ trade.price }}</td>
                    <td class="{{ 'positive' if (trade.pnl|float) >= 0 else 'negative' }}">
                        {{ trade.pnl if trade.pnl else '-' }}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p class="no-data">No trades yet</p>
        {% endif %}
    </div>
    
    <button class="refresh-btn" onclick="location.reload()">🔄 Refresh</button>
    
    <script>
        // Auto-refresh every 60 seconds
        setTimeout(() => location.reload(), 60000);
    </script>
</body>
</html>
"""


def get_bot_status():
    """Check if bot is running."""
    import subprocess
    try:
        result = subprocess.run(['pgrep', '-f', 'python.*src/core/script.py'], capture_output=True)
        running = result.returncode == 0
    except:
        running = False
    
    return {
        'running': running,
        'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }


def get_config_info():
    """Get current configuration."""
    return {
        'capital': Config.CAPITAL,
        'symbols': Config.SYMBOLS,
        'sl_pct': Config.SL_PCT * 100,
        'target_pct': Config.TARGET_PCT * 100,
        'paper_trading': Config.PAPER_TRADING
    }


def get_stats():
    """Get trading statistics."""
    trade_file = os.path.join(Config.LOG_DIR, Config.TRADE_LOG_FILE)
    
    stats = {
        'total_pnl': 0,
        'daily_pnl': 0,
        'win_rate': 0,
        'total_trades': 0
    }
    
    if not os.path.exists(trade_file):
        return stats
    
    today = datetime.now().strftime('%Y-%m-%d')
    wins = 0
    total = 0
    
    try:
        with open(trade_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['action'] != 'SELL':
                    continue
                
                pnl = float(row.get('pnl', 0) or 0)
                stats['total_pnl'] += pnl
                total += 1
                
                if pnl > 0:
                    wins += 1
                
                if row['timestamp'].startswith(today):
                    stats['daily_pnl'] += pnl
        
        stats['total_trades'] = total
        stats['win_rate'] = (wins / total * 100) if total > 0 else 0
        
    except Exception as e:
        print(f"Error reading stats: {e}")
    
    return stats


def get_positions():
    """Get current open positions."""
    position_file = os.path.join(Config.LOG_DIR, "positions.json")
    
    if not os.path.exists(position_file):
        return []
    
    try:
        with open(position_file, 'r') as f:
            data = json.load(f)
            positions = data.get('positions', [])
            
            # Add current price and PnL (simplified - would need live data)
            for pos in positions:
                pos['current_price'] = pos.get('buy_price', 0) * 1.01  # Placeholder
                pos['pnl'] = (pos['current_price'] - pos['buy_price']) * pos['quantity']
                pos['pnl_pct'] = ((pos['current_price'] - pos['buy_price']) / pos['buy_price'] * 100) if pos['buy_price'] > 0 else 0
            
            return positions
    except:
        return []


def get_trades():
    """Get recent trades."""
    trade_file = os.path.join(Config.LOG_DIR, Config.TRADE_LOG_FILE)
    
    if not os.path.exists(trade_file):
        return []
    
    trades = []
    try:
        with open(trade_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                trades.append({
                    'timestamp': row['timestamp'][:16],
                    'symbol': row['symbol'],
                    'action': row['action'],
                    'price': row['price'],
                    'pnl': row.get('pnl', '')
                })
    except:
        pass
    
    return trades[-20:]  # Last 20 trades


def get_learning_info():
    """Get learning engine status."""
    learning_file = os.path.join(Config.LOG_DIR, "learning_data.json")
    
    info = {
        'trades_analyzed': 0,
        'best_signal': 'N/A',
        'rsi_range': f"{Config.RSI_OVERSOLD}-{Config.RSI_OVERBOUGHT}"
    }
    
    if os.path.exists(learning_file):
        try:
            with open(learning_file, 'r') as f:
                data = json.load(f)
                info['trades_analyzed'] = data.get('total_trades_analyzed', 0)
                
                # Find best signal
                signals = data.get('signal_performance', {})
                best = max(signals.items(), key=lambda x: x[1].get('total_pnl', 0), default=('N/A', {}))
                info['best_signal'] = best[0]
                
                rsi = data.get('rsi_analysis', {}).get('best_rsi_range', [30, 40])
                info['rsi_range'] = f"{rsi[0]}-{rsi[1]}"
        except:
            pass
    
    return info


def get_market_info():
    """Get market status."""
    from script import is_market_open
    
    is_open, status = is_market_open()
    
    return {
        'is_open': is_open,
        'status': status,
        'sentiment': 'NEUTRAL',
        'events': None
    }


@app.route('/')
def dashboard():
    """Main dashboard page."""
    return render_template_string(
        DASHBOARD_HTML,
        status=get_bot_status(),
        config=get_config_info(),
        stats=get_stats(),
        positions=get_positions(),
        trades=get_trades(),
        learning=get_learning_info(),
        market=get_market_info()
    )


@app.route('/api/status')
def api_status():
    """API endpoint for bot status."""
    return jsonify({
        'status': get_bot_status(),
        'stats': get_stats(),
        'positions': get_positions()
    })


@app.route('/api/trades')
def api_trades():
    """API endpoint for trades."""
    return jsonify(get_trades())


def run_dashboard(host=None, port=None, debug=False):
    """Run the dashboard server."""
    # Use config values if available, otherwise defaults
    host = host or Config.DASHBOARD_HOST
    port = port or Config.DASHBOARD_PORT
    
    print(f"🌐 Starting dashboard at http://localhost:{port}")
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run_dashboard(debug=True)
