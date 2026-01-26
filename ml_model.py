"""
Machine Learning Model for Trade Prediction
Uses historical trade data to predict probability of success.
"""
import os
import csv
import json
import pickle
from datetime import datetime
from config import Config

# Try to import sklearn, fall back to simple model if not available
try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("⚠️ scikit-learn not installed. Using simple prediction model.")


class MLPredictor:
    """
    Machine Learning model to predict trade success.
    
    Features used:
    - RSI
    - MACD
    - MACD Histogram
    - Volume ratio (current/average)
    - Distance from SMA20
    - Hour of day
    - Day of week
    - ATR (volatility)
    """
    
    def __init__(self):
        self.model_file = os.path.join(Config.LOG_DIR, "ml_model.pkl")
        self.scaler_file = os.path.join(Config.LOG_DIR, "ml_scaler.pkl")
        self.trade_file = os.path.join(Config.LOG_DIR, Config.TRADE_LOG_FILE)
        self.model = None
        self.scaler = None
        self.min_samples = 20  # Minimum trades needed to train
        self.is_trained = False
        
        self._load_model()
    
    def _load_model(self):
        """Load trained model from disk."""
        if not SKLEARN_AVAILABLE:
            return
        
        try:
            if os.path.exists(self.model_file) and os.path.exists(self.scaler_file):
                with open(self.model_file, 'rb') as f:
                    self.model = pickle.load(f)
                with open(self.scaler_file, 'rb') as f:
                    self.scaler = pickle.load(f)
                self.is_trained = True
                print("📊 ML Model loaded successfully")
        except Exception as e:
            print(f"⚠️ Could not load ML model: {e}")
    
    def _save_model(self):
        """Save trained model to disk."""
        if not SKLEARN_AVAILABLE or not self.model:
            return
        
        try:
            os.makedirs(Config.LOG_DIR, exist_ok=True)
            with open(self.model_file, 'wb') as f:
                pickle.dump(self.model, f)
            with open(self.scaler_file, 'wb') as f:
                pickle.dump(self.scaler, f)
            print("📊 ML Model saved")
        except Exception as e:
            print(f"⚠️ Could not save ML model: {e}")
    
    def _extract_features(self, indicators, timestamp=None):
        """
        Extract features from indicators for ML model.
        """
        if timestamp is None:
            timestamp = datetime.now()
        elif isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp)
            except:
                timestamp = datetime.now()
        
        features = [
            indicators.get('RSI', 50),
            indicators.get('MACD', 0),
            indicators.get('MACD_Signal', 0),
            indicators.get('MACD', 0) - indicators.get('MACD_Signal', 0),  # MACD Histogram
            indicators.get('Volume', 0) / max(indicators.get('Volume_Avg', 1), 1),  # Volume ratio
            (indicators.get('Close', 0) - indicators.get('SMA_20', indicators.get('Close', 0))) / max(indicators.get('SMA_20', 1), 1) * 100,  # Distance from SMA20
            indicators.get('ATR', 0) / max(indicators.get('Close', 1), 1) * 100,  # ATR as % of price
            timestamp.hour,
            timestamp.weekday(),
        ]
        
        return features
    
    def _get_training_data(self):
        """
        Load and prepare training data from trade history.
        """
        if not os.path.exists(self.trade_file):
            return None, None
        
        X = []  # Features
        y = []  # Labels (1 = win, 0 = loss)
        
        try:
            with open(self.trade_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['action'] != 'SELL':
                        continue
                    
                    pnl = float(row.get('pnl', 0) or 0)
                    
                    # Extract features from stored indicators
                    indicators = {
                        'RSI': float(row.get('rsi', 50) or 50),
                        'MACD': float(row.get('macd', 0) or 0),
                        'MACD_Signal': 0,
                        'SMA_5': float(row.get('sma_5', 0) or 0),
                        'SMA_20': float(row.get('sma_20', 0) or 0),
                        'Close': float(row.get('price', 0) or 0),
                        'Volume': 1,
                        'Volume_Avg': 1,
                        'ATR': 0
                    }
                    
                    timestamp = row.get('timestamp', '')
                    features = self._extract_features(indicators, timestamp)
                    
                    X.append(features)
                    y.append(1 if pnl > 0 else 0)
        
        except Exception as e:
            print(f"⚠️ Error loading training data: {e}")
            return None, None
        
        if len(X) < self.min_samples:
            return None, None
        
        return X, y
    
    def train(self):
        """
        Train the ML model on historical trade data.
        """
        if not SKLEARN_AVAILABLE:
            print("⚠️ scikit-learn not available, cannot train ML model")
            return False
        
        X, y = self._get_training_data()
        
        if X is None or len(X) < self.min_samples:
            print(f"📊 Not enough data to train ML model (need {self.min_samples} trades)")
            return False
        
        print(f"📊 Training ML model on {len(X)} trades...")
        
        try:
            # Scale features
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            
            # Train model
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=5,
                min_samples_split=5,
                random_state=42
            )
            self.model.fit(X_scaled, y)
            
            # Calculate training accuracy
            accuracy = self.model.score(X_scaled, y)
            print(f"📊 ML Model trained! Accuracy: {accuracy*100:.1f}%")
            
            self.is_trained = True
            self._save_model()
            
            return True
            
        except Exception as e:
            print(f"❌ Error training ML model: {e}")
            return False
    
    def predict(self, indicators):
        """
        Predict probability of trade success.
        Returns: (probability, confidence_level)
        """
        if not SKLEARN_AVAILABLE or not self.is_trained:
            # Fall back to simple heuristic
            return self._simple_predict(indicators)
        
        try:
            features = self._extract_features(indicators)
            features_scaled = self.scaler.transform([features])
            
            # Get probability of winning
            proba = self.model.predict_proba(features_scaled)[0]
            win_probability = proba[1] if len(proba) > 1 else 0.5
            
            # Confidence based on how far from 0.5 the prediction is
            confidence = abs(win_probability - 0.5) * 2
            
            return win_probability, confidence
            
        except Exception as e:
            print(f"⚠️ ML prediction error: {e}")
            return self._simple_predict(indicators)
    
    def _simple_predict(self, indicators):
        """
        Simple rule-based prediction when ML is not available.
        """
        score = 0.5
        
        rsi = indicators.get('RSI', 50)
        macd = indicators.get('MACD', 0)
        macd_signal = indicators.get('MACD_Signal', 0)
        
        # RSI scoring
        if 30 <= rsi <= 40:
            score += 0.15  # Good buy zone
        elif rsi < 30:
            score += 0.1  # Oversold
        elif rsi > 70:
            score -= 0.15  # Overbought
        
        # MACD scoring
        if macd > macd_signal:
            score += 0.1  # Bullish
        else:
            score -= 0.1  # Bearish
        
        # Clamp to [0, 1]
        score = max(0, min(1, score))
        confidence = abs(score - 0.5) * 2
        
        return score, confidence
    
    def should_take_trade(self, indicators, threshold=0.55):
        """
        Decide if trade should be taken based on ML prediction.
        """
        probability, confidence = self.predict(indicators)
        
        take_trade = probability >= threshold
        
        return take_trade, probability, confidence
    
    def get_feature_importance(self):
        """
        Get feature importance from trained model.
        """
        if not SKLEARN_AVAILABLE or not self.is_trained:
            return None
        
        feature_names = [
            'RSI', 'MACD', 'MACD_Signal', 'MACD_Histogram',
            'Volume_Ratio', 'Distance_SMA20', 'ATR_Pct',
            'Hour', 'Weekday'
        ]
        
        importance = self.model.feature_importances_
        
        return dict(zip(feature_names, importance))


# Singleton instance
ml_predictor = MLPredictor()
