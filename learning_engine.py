import os
import csv
import json
from datetime import datetime, timedelta
from config import Config

class LearningEngine:
    """
    Adaptive learning system that analyzes past trades and adjusts parameters.
    
    What it learns:
    1. Which RSI levels lead to better trades
    2. Which signal types (STRONG_BUY vs BUY) perform better
    3. Optimal stop-loss and target levels based on ATR
    4. Best times of day to trade
    5. Which symbols perform better
    """
    
    def __init__(self):
        self.trade_file = os.path.join(Config.LOG_DIR, Config.TRADE_LOG_FILE)
        self.learning_file = os.path.join(Config.LOG_DIR, "learning_data.json")
        self.insights = self._load_insights()
    
    def _load_insights(self):
        """Load previously learned insights."""
        if os.path.exists(self.learning_file):
            try:
                with open(self.learning_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        
        return {
            "last_updated": None,
            "total_trades_analyzed": 0,
            "adjustments": {
                "rsi_oversold": Config.RSI_OVERSOLD,
                "rsi_overbought": Config.RSI_OVERBOUGHT,
                "sl_pct": Config.SL_PCT,
                "target_pct": Config.TARGET_PCT
            },
            "signal_performance": {
                "STRONG_BUY": {"wins": 0, "losses": 0, "total_pnl": 0},
                "BUY": {"wins": 0, "losses": 0, "total_pnl": 0},
                "BOUNCE_BUY": {"wins": 0, "losses": 0, "total_pnl": 0}
            },
            "exit_performance": {
                "Target Hit": {"count": 0, "avg_pnl": 0},
                "Stop Loss": {"count": 0, "avg_pnl": 0},
                "Trailing SL": {"count": 0, "avg_pnl": 0},
                "Trend Reversal": {"count": 0, "avg_pnl": 0}
            },
            "rsi_analysis": {
                "winning_rsi_avg": 0,
                "losing_rsi_avg": 0,
                "best_rsi_range": [30, 40]
            },
            "time_analysis": {
                "best_hours": [],
                "worst_hours": []
            },
            "symbol_performance": {}
        }
    
    def _save_insights(self):
        """Save learned insights to file."""
        self.insights["last_updated"] = datetime.now().isoformat()
        
        os.makedirs(Config.LOG_DIR, exist_ok=True)
        with open(self.learning_file, 'w') as f:
            json.dump(self.insights, f, indent=2)
    
    def analyze_trades(self):
        """Analyze all past trades and update insights."""
        if not os.path.exists(self.trade_file):
            print("📚 No trade history to learn from yet.")
            return
        
        trades = []
        with open(self.trade_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                trades.append(row)
        
        if len(trades) < 2:
            print("📚 Not enough trades to analyze.")
            return
        
        # Pair BUY and SELL trades
        buy_trades = [t for t in trades if t['action'] in ['BUY', 'STRONG_BUY', 'BOUNCE_BUY']]
        sell_trades = [t for t in trades if t['action'] == 'SELL']
        
        # Reset performance counters
        for sig_type in self.insights["signal_performance"]:
            self.insights["signal_performance"][sig_type] = {"wins": 0, "losses": 0, "total_pnl": 0}
        
        winning_rsi = []
        losing_rsi = []
        hour_performance = {}
        
        for sell in sell_trades:
            try:
                pnl = float(sell.get('pnl', 0) or 0)
                signal_type = sell.get('signal_type', 'BUY')
                reason = sell.get('reason', '')
                rsi = float(sell.get('rsi', 0) or 0)
                symbol = sell.get('symbol', '')
                
                # Parse timestamp for hour analysis
                timestamp = sell.get('timestamp', '')
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp)
                        hour = dt.hour
                        if hour not in hour_performance:
                            hour_performance[hour] = {"wins": 0, "losses": 0, "total_pnl": 0}
                        hour_performance[hour]["total_pnl"] += pnl
                        if pnl > 0:
                            hour_performance[hour]["wins"] += 1
                        else:
                            hour_performance[hour]["losses"] += 1
                    except:
                        pass
                
                # Update signal performance
                if signal_type in self.insights["signal_performance"]:
                    self.insights["signal_performance"][signal_type]["total_pnl"] += pnl
                    if pnl > 0:
                        self.insights["signal_performance"][signal_type]["wins"] += 1
                    else:
                        self.insights["signal_performance"][signal_type]["losses"] += 1
                
                # Update exit performance
                if reason in self.insights["exit_performance"]:
                    self.insights["exit_performance"][reason]["count"] += 1
                    prev_avg = self.insights["exit_performance"][reason]["avg_pnl"]
                    count = self.insights["exit_performance"][reason]["count"]
                    self.insights["exit_performance"][reason]["avg_pnl"] = (prev_avg * (count - 1) + pnl) / count
                
                # RSI analysis
                if rsi > 0:
                    if pnl > 0:
                        winning_rsi.append(rsi)
                    else:
                        losing_rsi.append(rsi)
                
                # Symbol performance
                if symbol:
                    if symbol not in self.insights["symbol_performance"]:
                        self.insights["symbol_performance"][symbol] = {"wins": 0, "losses": 0, "total_pnl": 0}
                    self.insights["symbol_performance"][symbol]["total_pnl"] += pnl
                    if pnl > 0:
                        self.insights["symbol_performance"][symbol]["wins"] += 1
                    else:
                        self.insights["symbol_performance"][symbol]["losses"] += 1
                
            except Exception as e:
                print(f"⚠️ Error analyzing trade: {e}")
        
        # Calculate RSI insights
        if winning_rsi:
            self.insights["rsi_analysis"]["winning_rsi_avg"] = sum(winning_rsi) / len(winning_rsi)
        if losing_rsi:
            self.insights["rsi_analysis"]["losing_rsi_avg"] = sum(losing_rsi) / len(losing_rsi)
        
        # Find best RSI range for buying
        if winning_rsi:
            min_winning_rsi = min(winning_rsi)
            max_winning_rsi = max(winning_rsi)
            self.insights["rsi_analysis"]["best_rsi_range"] = [
                max(20, min_winning_rsi - 5),
                min(50, max_winning_rsi + 5)
            ]
        
        # Time analysis
        if hour_performance:
            sorted_hours = sorted(hour_performance.items(), key=lambda x: x[1]["total_pnl"], reverse=True)
            self.insights["time_analysis"]["best_hours"] = [h for h, _ in sorted_hours[:3]]
            self.insights["time_analysis"]["worst_hours"] = [h for h, _ in sorted_hours[-2:]]
        
        self.insights["total_trades_analyzed"] = len(sell_trades)
        self._generate_adjustments()
        self._save_insights()
        
        print(f"📚 Analyzed {len(sell_trades)} trades and updated learning model.")
    
    def _generate_adjustments(self):
        """Generate parameter adjustments based on analysis."""
        
        # Adjust RSI thresholds based on winning trades
        best_range = self.insights["rsi_analysis"]["best_rsi_range"]
        if best_range[0] != Config.RSI_OVERSOLD:
            self.insights["adjustments"]["rsi_oversold"] = int(best_range[0])
        
        # Adjust SL/Target based on exit performance
        target_stats = self.insights["exit_performance"]["Target Hit"]
        sl_stats = self.insights["exit_performance"]["Stop Loss"]
        
        if target_stats["count"] > 0 and sl_stats["count"] > 0:
            # If too many stop losses, maybe widen SL
            total_exits = target_stats["count"] + sl_stats["count"]
            sl_ratio = sl_stats["count"] / total_exits
            
            if sl_ratio > 0.5:  # More than 50% trades hitting SL
                # Widen stop loss by 0.5%
                new_sl = min(0.08, Config.SL_PCT + 0.005)
                self.insights["adjustments"]["sl_pct"] = new_sl
                print(f"📚 Learning: Widening SL to {new_sl*100}% (too many SL hits)")
            
            if sl_ratio < 0.2:  # Less than 20% trades hitting SL
                # Tighten stop loss
                new_sl = max(0.02, Config.SL_PCT - 0.005)
                self.insights["adjustments"]["sl_pct"] = new_sl
                print(f"📚 Learning: Tightening SL to {new_sl*100}% (SL rarely hit)")
    
    def get_adjusted_params(self):
        """Get the current adjusted parameters."""
        return self.insights["adjustments"]
    
    def should_take_trade(self, signal_type, rsi, hour):
        """
        Use learned insights to decide if a trade should be taken.
        Returns: (should_trade: bool, confidence: float, reason: str)
        """
        confidence = 1.0
        reasons = []
        
        # Check signal type performance
        sig_perf = self.insights["signal_performance"].get(signal_type, {})
        if sig_perf.get("wins", 0) + sig_perf.get("losses", 0) > 5:
            win_rate = sig_perf["wins"] / (sig_perf["wins"] + sig_perf["losses"])
            if win_rate < 0.4:
                confidence *= 0.7
                reasons.append(f"{signal_type} has low win rate ({win_rate*100:.0f}%)")
            elif win_rate > 0.6:
                confidence *= 1.2
                reasons.append(f"{signal_type} has high win rate ({win_rate*100:.0f}%)")
        
        # Check RSI range
        best_range = self.insights["rsi_analysis"]["best_rsi_range"]
        if not (best_range[0] <= rsi <= best_range[1]):
            confidence *= 0.8
            reasons.append(f"RSI {rsi:.1f} outside optimal range {best_range}")
        else:
            confidence *= 1.1
            reasons.append(f"RSI {rsi:.1f} in optimal range")
        
        # Check time of day
        if hour in self.insights["time_analysis"]["worst_hours"]:
            confidence *= 0.7
            reasons.append(f"Hour {hour} historically poor")
        elif hour in self.insights["time_analysis"]["best_hours"]:
            confidence *= 1.2
            reasons.append(f"Hour {hour} historically good")
        
        # Decision threshold
        should_trade = confidence >= 0.8
        
        return should_trade, confidence, "; ".join(reasons)
    
    def get_insights_summary(self):
        """Get a summary of learned insights for display."""
        summary = []
        summary.append("📚 LEARNING ENGINE INSIGHTS")
        summary.append(f"   Trades Analyzed: {self.insights['total_trades_analyzed']}")
        
        # Signal performance
        summary.append("\n   Signal Performance:")
        for sig, perf in self.insights["signal_performance"].items():
            total = perf["wins"] + perf["losses"]
            if total > 0:
                win_rate = (perf["wins"] / total) * 100
                summary.append(f"   • {sig}: {win_rate:.0f}% win rate, ₹{perf['total_pnl']:.2f} PnL")
        
        # Best RSI range
        best_range = self.insights["rsi_analysis"]["best_rsi_range"]
        summary.append(f"\n   Optimal RSI Range: {best_range[0]}-{best_range[1]}")
        
        # Best hours
        best_hours = self.insights["time_analysis"]["best_hours"]
        if best_hours:
            summary.append(f"   Best Trading Hours: {', '.join(map(str, best_hours))}:00")
        
        # Adjustments
        adj = self.insights["adjustments"]
        summary.append(f"\n   Current Adjustments:")
        summary.append(f"   • RSI Oversold: {adj['rsi_oversold']}")
        summary.append(f"   • SL: {adj['sl_pct']*100:.1f}% | Target: {adj['target_pct']*100:.1f}%")
        
        return "\n".join(summary)


# Singleton instance
learning_engine = LearningEngine()
