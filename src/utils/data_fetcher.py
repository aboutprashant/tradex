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
            
            # Method 1: Try using REST API directly (most reliable for AWS Mumbai)
            # Enabled for AWS production - Mumbai region should have better connectivity
            use_rest_api = True  # Enabled for AWS Mumbai region
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
                        
                        # Get client IP (try to get AWS instance IP, fallback to localhost)
                        try:
                            import socket
                            # Try to get actual IP, but fallback to localhost
                            client_ip = socket.gethostbyname(socket.gethostname())
                            if client_ip.startswith('127.'):
                                # If localhost, try to get public IP or use localhost
                                client_ip = '127.0.0.1'
                        except:
                            client_ip = '127.0.0.1'
                        
                        headers = {
                            'Authorization': f'Bearer {auth_token}',
                            'Content-Type': 'application/json',
                            'Accept': 'application/json',
                            'X-UserType': 'USER',
                            'X-SourceID': 'WEB',
                            'X-ClientLocalIP': client_ip,
                            'X-ClientPublicIP': client_ip,  # Use same IP for both
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
                        
                        # Use longer timeout for AWS (network latency)
                        api_response = requests.post(url, json=payload, headers=headers, timeout=30)
                        
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
                                        error_msg = response.get('message', 'No data in response')
                                        error_code = response.get('errorcode', '')
                                        if error_code:
                                            last_error = f"API Error {error_code}: {error_msg}"
                                        else:
                                            last_error = f"API returned no data: {error_msg}"
                                        response = None
                                except ValueError as json_error:
                                    # JSON parsing failed - response might be empty or invalid
                                    last_error = f"JSON parse error: {json_error}, Response: {response_text[:100]}"
                                    response = None
                            else:
                                # Empty response
                                last_error = "Empty response from API"
                                response = None
                        elif api_response.status_code == 401:
                            # Authentication failed - token might be expired
                            last_error = f"Authentication failed (401) - token may be expired"
                            response = None
                            # Try to refresh token
                            try:
                                if self.broker.login():
                                    # Retry once after login
                                    api_response = requests.post(url, json=payload, headers=headers, timeout=30)
                                    if api_response.status_code == 200:
                                        response_text = api_response.text.strip()
                                        if response_text:
                                            response = api_response.json()
                            except:
                                pass
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
    
    def fetch_from_yfinance(self, symbol, period="5d", interval="5m", retries=3):
        """
        Fetch data from yfinance (fallback only).
        Only used when Angel One fails.
        Enhanced with retries and better error handling for AWS.
        """
        if not YFINANCE_AVAILABLE:
            return None
        
        yf_symbol = symbol.replace("-EQ", ".NS")
        
        # Try multiple symbol formats for Indian stocks
        symbol_formats = [
            yf_symbol,  # GOLDBEES.NS
            symbol.replace("-EQ", "").lower() + ".ns",  # goldbees.ns
            symbol.replace("-EQ", "").upper() + ".NS",  # GOLDBEES.NS
        ]
        
        for attempt in range(retries):
            for sym_format in symbol_formats:
                try:
                    # Add delay between retries (exponential backoff)
                    if attempt > 0:
                        time.sleep(2 ** attempt)  # 2s, 4s, 8s
                    
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        # Use session with custom headers to avoid AWS IP blocking
                        import yfinance as yf
                        ticker = yf.Ticker(sym_format, session=None)
                        
                        # Try different download methods
                        try:
                            # Method 1: Direct download
                            data = ticker.history(period=period, interval=interval, timeout=20)
                            if data is not None and not data.empty:
                                return data
                        except:
                            # Method 2: Try download with different parameters
                            data = yf.download(
                                sym_format,
                                period=period,
                                interval=interval,
                                progress=False,
                                timeout=20,
                                threads=False,
                                show_errors=False
                            )
                            if data is not None and not data.empty:
                                return data
                            
                except Exception as e:
                    # Try next symbol format or retry
                    if attempt == retries - 1 and sym_format == symbol_formats[-1]:
                        # Last attempt failed - log for debugging
                        error_msg = str(e)
                        if "HTTPSConnectionPool" not in error_msg and "timeout" not in error_msg.lower():
                            # Only log non-network errors
                            pass
                    continue
        
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
        data = self.fetch_from_yfinance(symbol, period, interval, retries=3)
        if data is not None and not data.empty:
            self._save_to_cache(symbol, interval, data)
            print(f"yfinance data received for {symbol}")
            return data
        
        # Try alternative data source: NSE API (if available)
        data = self._fetch_from_nse_alternative(symbol, period, interval)
        if data is not None and not data.empty:
            self._save_to_cache(symbol, interval, data)
            print(f"✅ Alternative data source succeeded for {symbol}")
            return data
        
        # Both failed - return empty DataFrame
        print(f"❌ All data sources failed for {symbol}")
        return pd.DataFrame()
    
    def _fetch_from_nse_alternative(self, symbol, period="5d", interval="5m"):
        """
        Alternative data source: Try NSE official API or web scraping as last resort.
        This is a fallback when both Angel One and yfinance fail.
        """
        try:
            # Try NSE official API (free tier)
            # Format: https://www.nseindia.com/api/historical/cm/equity?symbol=GOLDBEES
            nse_symbol = symbol.replace("-EQ", "")
            
            # For now, return None - can be implemented later
            # This requires proper session handling with NSE website
            return None
            
        except Exception:
            return None


# Global instance (will be initialized in script.py)
data_fetcher = None

def get_data_fetcher(broker_client):
    """Get or create global data fetcher instance."""
    global data_fetcher
    if data_fetcher is None:
        data_fetcher = DataFetcher(broker_client)
    return data_fetcher
