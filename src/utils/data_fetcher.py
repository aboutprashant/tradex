"""
Data Fetcher with Fallback Mechanism
Uses Angel One API as primary source, yfinance as fallback.
This solves the AWS production issue by using a reliable data source.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import warnings
import requests
from src.brokers.broker_client import BrokerClient
from src.core.config import Config

# Import yfinance only for fallback
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

class DataFetcher:
    """
    Fetches market data with fallback mechanism:
    1. Primary: Angel One API (reliable, works on AWS)
    2. Fallback: yfinance (if Angel One fails)
    """
    
    def __init__(self, broker_client: BrokerClient):
        self.broker = broker_client
        self.cache = {}  # Simple in-memory cache
        self.cache_ttl = 60  # Cache for 60 seconds
        
    def _get_from_cache(self, symbol, interval):
        """Get data from cache if available and fresh."""
        cache_key = f"{symbol}_{interval}"
        if cache_key in self.cache:
            data, timestamp = self.cache[cache_key]
            if (datetime.now() - timestamp).total_seconds() < self.cache_ttl:
                return data
        return None
    
    def _save_to_cache(self, symbol, interval, data):
        """Save data to cache."""
        cache_key = f"{symbol}_{interval}"
        self.cache[cache_key] = (data, datetime.now())
    
    def fetch_from_angel_one(self, symbol, period="5d", interval="5m"):
        """
        Fetch data from Angel One API (primary source).
        This works reliably on AWS production.
        """
        try:
            token = self.broker.get_token(symbol)
            if not token:
                return None
            
            # Ensure we're logged in
            if not self.broker.session_data:
                if not self.broker.login():
                    return None
            
            # Calculate date range
            end_date = datetime.now()
            if period == "5d":
                start_date = end_date - timedelta(days=5)
            elif period == "60d":
                start_date = end_date - timedelta(days=60)
            else:
                start_date = end_date - timedelta(days=5)
            
            # Map interval to Angel One format
            interval_map = {
                "5m": "FIVE_MINUTE",
                "1h": "ONE_HOUR", 
                "1d": "ONE_DAY"
            }
            angel_interval = interval_map.get(interval, "FIVE_MINUTE")
            
            # Use SmartAPI's getCandleData method
            # Note: SmartAPI method signature varies by version - try multiple approaches
            from_date_str = start_date.strftime("%Y-%m-%d %H:%M")
            to_date_str = end_date.strftime("%Y-%m-%d %H:%M")
            
            response = None
            last_error = None
            
            # Method 1: Try using REST API directly (most reliable)
            # Note: Currently disabled due to authentication/endpoint issues
            # Uncomment and fix if needed, otherwise falls back to yfinance
            use_rest_api = False  # Set to True to enable REST API attempts
            if use_rest_api:
                try:
                    auth_token = None
                    if hasattr(self.broker.obj, 'access_token'):
                        auth_token = self.broker.obj.access_token
                    elif hasattr(self.broker, 'session_data') and self.broker.session_data:
                        auth_token = self.broker.session_data.get('data', {}).get('jwtToken', '')
                    
                    if auth_token:
                        # Remove Bearer prefix if present
                        if auth_token.startswith('Bearer '):
                            auth_token = auth_token[7:]
                        
                        # Use Angel One REST API directly
                        url = "https://apiconnect.angelbroking.com/rest/secure/angelbroking/market/v1/getCandleData"
                        headers = {
                            'Authorization': f'Bearer {auth_token}',
                            'Content-Type': 'application/json',
                            'Accept': 'application/json',
                            'X-UserType': 'USER',
                            'X-SourceID': 'WEB',
                            'X-ClientLocalIP': '127.0.0.1',
                            'X-ClientPublicIP': '127.0.0.1',
                            'X-MACAddress': '00:00:00:00:00:00',
                            'X-PrivateKey': self.broker.obj.api_key
                        }
                        payload = {
                            "exchange": "NSE",
                            "symboltoken": token,
                            "interval": angel_interval,
                            "fromdate": from_date_str,
                            "todate": to_date_str
                        }
                        
                        api_response = requests.post(url, json=payload, headers=headers, timeout=10)
                        
                        # Check if response has content before parsing JSON
                        if api_response.status_code == 200:
                            response_text = api_response.text.strip()
                            if response_text:
                                try:
                                    response = api_response.json()
                                    if response.get('status') and response.get('data'):
                                        # Success - use this response
                                        pass
                                    else:
                                        # API returned success but no data
                                        response = None
                                except ValueError as json_error:
                                    # JSON parsing failed - response might be empty or invalid
                                    last_error = f"JSON parse error: {json_error}, Response: {response_text[:100]}"
                                    response = None
                            else:
                                # Empty response
                                last_error = "Empty response from API"
                                response = None
                        else:
                            # Non-200 status code
                            response_text = api_response.text[:200] if api_response.text else "No response text"
                            last_error = f"HTTP {api_response.status_code}: {response_text}"
                            response = None
                except requests.exceptions.RequestException as e:
                    last_error = f"Request failed: {e}"
                    response = None
                except Exception as e:
                    last_error = f"Unexpected error: {e}"
                    response = None
            else:
                # REST API disabled - skip silently
                response = None
            
            # Method 2: Try SmartAPI wrapper methods (if REST API failed)
            if not response:
                try:
                    # Try with positional arguments only (no keyword args)
                    response = self.broker.obj.getCandleData(
                        "NSE", token, angel_interval, from_date_str, to_date_str
                    )
                except (TypeError, AttributeError) as e1:
                    try:
                        # Try without exchange parameter
                        response = self.broker.obj.getCandleData(
                            token, angel_interval, from_date_str, to_date_str
                        )
                    except (TypeError, AttributeError) as e2:
                        try:
                            # Try with exchange+token combined
                            exchange_token = f"NSE|{token}"
                            response = self.broker.obj.getCandleData(
                                exchange_token, angel_interval, from_date_str, to_date_str
                            )
                        except Exception as e3:
                            # All methods failed - log and return None
                            # Don't print verbose errors for every symbol - just return None silently
                            # The outer exception handler will log a simpler message
                            return None
            
            if response and response.get('status') and response.get('data'):
                # Convert Angel One response to pandas DataFrame
                candles = response['data']
                df_data = []
                for candle in candles:
                    # Handle different candle formats
                    if isinstance(candle, (list, tuple)) and len(candle) >= 5:
                        # Format: [timestamp, open, high, low, close, volume]
                        timestamp = candle[0]
                        open_price = float(candle[1])
                        high_price = float(candle[2])
                        low_price = float(candle[3])
                        close_price = float(candle[4])
                        volume = float(candle[5]) if len(candle) > 5 else 0
                        
                        # Parse timestamp (could be string or milliseconds)
                        if isinstance(timestamp, (int, float)):
                            dt = pd.to_datetime(timestamp, unit='ms')
                        else:
                            dt = pd.to_datetime(timestamp)
                        
                        df_data.append({
                            'Open': open_price,
                            'High': high_price,
                            'Low': low_price,
                            'Close': close_price,
                            'Volume': volume,
                            'Datetime': dt
                        })
                    elif isinstance(candle, dict):
                        # Format: dict with keys
                        df_data.append({
                            'Open': float(candle.get('open', candle.get('Open', 0))),
                            'High': float(candle.get('high', candle.get('High', 0))),
                            'Low': float(candle.get('low', candle.get('Low', 0))),
                            'Close': float(candle.get('close', candle.get('Close', 0))),
                            'Volume': float(candle.get('volume', candle.get('Volume', 0))),
                            'Datetime': pd.to_datetime(candle.get('datetime', candle.get('Datetime', candle.get('time', ''))))
                        })
                
                if df_data:
                    df = pd.DataFrame(df_data)
                    df.set_index('Datetime', inplace=True)
                    df.sort_index(inplace=True)
                    return df
                    
            return None
                
        except Exception as e:
            # Only log if it's not a common/expected error (like JSON parse errors from empty responses)
            error_str = str(e)
            if "Expecting value" not in error_str and "JSON" not in error_str:
                print(f"⚠️ Error fetching from Angel One for {symbol}: {e}")
            return None
    
    def fetch_from_yfinance(self, symbol, period="5d", interval="5m"):
        """
        Fetch data from yfinance (fallback only).
        Only used when Angel One fails.
        """
        if not YFINANCE_AVAILABLE:
            return None
            
        try:
            yf_symbol = symbol.replace("-EQ", ".NS")
            
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                data = yf.download(
                    yf_symbol,
                    period=period,
                    interval=interval,
                    progress=False,
                    timeout=15,
                    threads=False
                )
                
            if data is not None and not data.empty:
                return data
        except Exception as e:
            # Silent failure - this is fallback
            pass
        
        return None
    
    def fetch_live_data(self, symbol, period="5d", interval="5m"):
        """
        Fetch market data with intelligent fallback.
        Primary: Angel One API (works on AWS)
        Fallback: yfinance (if Angel One fails)
        """
        # Check cache first
        cached_data = self._get_from_cache(symbol, interval)
        if cached_data is not None:
            return cached_data
        
        # Try Angel One first (reliable on AWS)
        data = self.fetch_from_angel_one(symbol, period, interval)
        if data is not None and not data.empty:
            self._save_to_cache(symbol, interval, data)
            return data
        
        # Fallback to yfinance (may fail on AWS, but worth trying)
        print(f"Angel One data unavailable for {symbol}, trying yfinance fallback...")
        data = self.fetch_from_yfinance(symbol, period, interval)
        if data is not None and not data.empty:
            self._save_to_cache(symbol, interval, data)
            print(f"yfinance data received for {symbol}")

            return data
        
        # Both failed - return empty DataFrame
        print(f"❌ Both Angel One and yfinance failed for {symbol}")
        return pd.DataFrame()


# Global instance (will be initialized in script.py)
data_fetcher = None

def get_data_fetcher(broker_client):
    """Get or create global data fetcher instance."""
    global data_fetcher
    if data_fetcher is None:
        data_fetcher = DataFetcher(broker_client)
    return data_fetcher
