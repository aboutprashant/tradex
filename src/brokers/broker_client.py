import pyotp
import requests
import pandas as pd
import time
from datetime import datetime, timedelta
from SmartApi import SmartConnect
from src.core.config import Config

class RateLimiter:
    """Simple rate limiter to prevent exceeding API rate limits."""
    def __init__(self, max_calls_per_minute=30):
        self.max_calls = max_calls_per_minute
        self.calls = []
        self.min_delay = 2.0  # Minimum 2 seconds between calls
    
    def wait_if_needed(self):
        """Wait if we're approaching rate limit."""
        now = datetime.now()
        # Remove calls older than 1 minute
        self.calls = [call_time for call_time in self.calls 
                     if (now - call_time).total_seconds() < 60]
        
        # If we're close to limit, wait
        if len(self.calls) >= self.max_calls * 0.8:  # 80% of limit
            wait_time = 60 - (now - self.calls[0]).total_seconds() if self.calls else self.min_delay
            if wait_time > 0:
                print(f"   ⏳ Rate limit protection: waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
        
        # Always maintain minimum delay between calls
        if self.calls:
            last_call = self.calls[-1]
            time_since_last = (now - last_call).total_seconds()
            if time_since_last < self.min_delay:
                time.sleep(self.min_delay - time_since_last)
        
        # Record this call
        self.calls.append(datetime.now())

class BrokerClient:
    def __init__(self):
        self.obj = SmartConnect(api_key=Config.API_KEY)
        self.session_data = None
        self.token_cache = {}  # Cache for symbol tokens
        self.symbol_info = {}  # Cache for symbol info (token + trading_symbol name)
        self.last_login_time = None
        self.rate_limiter = RateLimiter(max_calls_per_minute=30)  # Angel One limit is ~30/min
        self.last_api_call_time = None
        self._load_tokens()
    
    def _load_tokens(self):
        """Load symbol tokens from Angel One API."""
        try:
            print("📥 Loading symbol tokens...")
            url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
            response = requests.get(url, timeout=30)
            data = response.json()
            
            # Build cache for NSE symbols - store both token and trading symbol name
            self.symbol_info = {}  # symbol -> {token, trading_symbol_name}
            for item in data:
                if item.get('exch_seg') == 'NSE':
                    symbol = item.get('symbol', '')
                    token = item.get('token', '')
                    name = item.get('name', '')  # This is the trading symbol name
                    if symbol and token:
                        self.token_cache[symbol] = token
                        # Store the trading symbol name for order placement
                        # Try using the full symbol first (SILVERIETF-EQ), fallback to name (SILVERIETF)
                        # Angel One API might require the full symbol format
                        self.symbol_info[symbol] = {
                            'token': token,
                            'trading_symbol': symbol,  # Use full symbol (SILVERIETF-EQ) first
                            'trading_symbol_alt': name if name else symbol.replace('-EQ', '')  # Alternative format
                        }
            
            print(f"   ✅ Loaded {len(self.token_cache)} NSE symbols")
        except Exception as e:
            print(f"   ⚠️ Failed to load tokens: {e}")
            # Fallback tokens for common symbols
            self.token_cache = {
                'GOLDBEES-EQ': '14428',
                'SILVERBEES-EQ': '14430',
                'NIFTYBEES-EQ': '10576',
                'BANKBEES-EQ': '12313',
                'SILVERIETF-EQ': '7942',
            }
            # Fallback symbol info
            self.symbol_info = {
                'GOLDBEES-EQ': {'token': '14428', 'trading_symbol': 'GOLDBEES-EQ', 'trading_symbol_alt': 'GOLDBEES'},
                'SILVERBEES-EQ': {'token': '14430', 'trading_symbol': 'SILVERBEES-EQ', 'trading_symbol_alt': 'SILVERBEES'},
                'NIFTYBEES-EQ': {'token': '10576', 'trading_symbol': 'NIFTYBEES-EQ', 'trading_symbol_alt': 'NIFTYBEES'},
                'BANKBEES-EQ': {'token': '12313', 'trading_symbol': 'BANKBEES-EQ', 'trading_symbol_alt': 'BANKBEES'},
                'SILVERIETF-EQ': {'token': '7942', 'trading_symbol': 'SILVERIETF-EQ', 'trading_symbol_alt': 'SILVERIETF'},
            }
            print(f"   Using fallback tokens for {len(self.token_cache)} symbols")
    
    def get_token(self, symbol):
        """Get the token for a symbol."""
        return self.token_cache.get(symbol, self.token_cache.get(symbol.replace('-EQ', ''), None))
    
    def get_trading_symbol(self, symbol):
        """Get the correct trading symbol name for order placement."""
        # Try using the full symbol format first (SILVERIETF-EQ)
        # If that doesn't work, we can fallback to name format (SILVERIETF)
        if hasattr(self, 'symbol_info') and symbol in self.symbol_info:
            # Try full symbol format first
            return self.symbol_info[symbol]['trading_symbol']
        else:
            # Fallback: use the symbol as-is (with -EQ)
            return symbol

    def login(self):
        if Config.PAPER_TRADING:
            print("--- PAPER TRADING MODE ACTIVE (Angel One Logic) ---")
            return True
        
        # Check if TOTP secret is configured
        if not Config.TOTP_SECRET or Config.TOTP_SECRET == "your_totp_secret":
            print("❌ ERROR: TOTP_SECRET not configured in .env file!")
            print("   Please get your TOTP secret from Angel One:")
            print("   1. Go to trade.angelone.in → Profile → Password & Security")
            print("   2. Enable External TOTP → Copy the secret key")
            print("   3. Paste it in your .env file as TOTP_SECRET=YOUR_KEY_HERE")
            return False
        
        # Check if MPIN is configured
        if not Config.MPIN or Config.MPIN == "your_mpin":
            print("❌ ERROR: MPIN not configured in .env file!")
            print("   Angel One now requires MPIN login (not password).")
            print("   Add your 4-digit MPIN to .env: MPIN=1234")
            return False
            
        try:
            totp = pyotp.TOTP(Config.TOTP_SECRET).now()
            
            # Use MPIN-based login (new Angel One requirement)
            self.session_data = self.obj.generateSession(
                clientCode=Config.CLIENT_CODE, 
                password=Config.MPIN,  # MPIN is now used instead of password
                totp=totp
            )
            
            # Check if login was actually successful
            if self.session_data is None or self.session_data.get('status') == False:
                error_msg = self.session_data.get('message', 'Unknown error') if self.session_data else 'No response'
                print(f"❌ Angel One Login failed: {error_msg}")
                return False
            
            # Set access token for future API calls
            auth_token = self.session_data['data']['jwtToken']
            refresh_token = self.session_data['data'].get('refreshToken', '')
            
            # Remove "Bearer " prefix if present (SmartAPI expects just the token)
            if auth_token.startswith('Bearer '):
                auth_token = auth_token[7:]  # Remove "Bearer " prefix
            
            # CRITICAL: Recreate SmartConnect object with the new token
            # Sometimes setAccessToken doesn't work, so we recreate the object
            self.obj = SmartConnect(api_key=Config.API_KEY)
            self.obj.setAccessToken(auth_token)
            
            # Also store refresh token if available for future use
            if refresh_token:
                self.obj.setRefreshToken(refresh_token)
            
            self.last_login_time = pd.Timestamp.now()
            
            # Verify token is set by checking if we can access it
            try:
                # Test if token is accessible
                token_check = getattr(self.obj, 'access_token', None) or getattr(self.obj, 'jwtToken', None)
                if not token_check:
                    print("⚠️ Warning: Token may not be set correctly in SmartAPI object")
            except:
                pass
            
            print("✅ Angel One Login Successful")
            print(f"   Logged in as: {self.session_data['data'].get('name', 'Unknown')}")
            print(f"   JWT Token: {auth_token[:30]}... (length: {len(auth_token)})")
            return True
        except Exception as e:
            print(f"❌ Angel One Login failed: {e}")
            return False

    def _ensure_valid_token(self):
        """Check if token is valid, re-login if needed."""
        if Config.PAPER_TRADING:
            return True
        
        # Check if we need to refresh token (every 12 hours or if last login was more than 12 hours ago)
        if self.last_login_time is None:
            return self.login()
        
        hours_since_login = (pd.Timestamp.now() - self.last_login_time).total_seconds() / 3600
        if hours_since_login > 12:
            print("🔄 Token may be expired, refreshing...")
            return self.login()
        
        return True
    
    def place_order(self, symbol, quantity, side, price=None):
        """
        side: 'BUY' or 'SELL'
        price: if None, it's a MARKET order, else a LIMIT order
        """
        if Config.PAPER_TRADING:
            print(f"[PAPER] Angel One Order: {side} {quantity} units of {symbol} at ₹{price or 'MARKET'}")
            return True

        # Ensure token is valid before placing order
        if not self._ensure_valid_token():
            print("❌ Cannot place order: Token refresh failed")
            return None

        try:
            # Get dynamic symbol token
            token = self.get_token(symbol)
            if not token:
                print(f"❌ Unknown symbol token for {symbol}")
                return None
            
            # Get the correct trading symbol name from master file (uses 'name' field)
            trading_symbol = self.get_trading_symbol(symbol)
            
            # Debug: Log what we're sending
            print(f"   📋 Order params: trading_symbol={trading_symbol}, symboltoken={token}, original={symbol}")
            
            order_params = {
                "variety": "NORMAL",
                "tradingsymbol": trading_symbol,
                "symboltoken": token,
                "transactiontype": side,
                "exchange": "NSE",
                "ordertype": "MARKET" if price is None else "LIMIT",
                "producttype": "DELIVERY",
                "duration": "DAY",
                "quantity": str(quantity)
            }
            if price:
                order_params["price"] = str(price)
            
            print(f"🔄 Placing {side} order: {quantity}x {trading_symbol} (Token: {token})")
            
            try:
                order_id = self.obj.placeOrder(order_params)
            except Exception as order_error:
                error_str = str(order_error)
                # Check if it's a token error from exception
                if 'Invalid Token' in error_str or 'AG8001' in error_str or 'token' in error_str.lower():
                    print("🔄 Token expired detected in exception, refreshing...")
                    import time
                    time.sleep(2)  # Wait to avoid rate limiting
                    if self.login():
                        # Retry order after re-login
                        print("🔄 Retrying order after token refresh...")
                        try:
                            order_id = self.obj.placeOrder(order_params)
                            if order_id:
                                print(f"✅ Angel One Order Placed Successfully after refresh. ID: {order_id}")
                                return order_id
                        except Exception as retry_e:
                            print(f"❌ Failed to place order after refresh: {retry_e}")
                            return None
                
                # Re-raise if not a token error
                raise order_error
            
            # Check if order_id is None (SmartAPI returns None on error)
            if order_id is None:
                # Try to get error from SmartAPI response
                # SmartAPI may store error in response attribute
                import time
                try:
                    # Check if there's a response attribute with error
                    if hasattr(self.obj, 'response'):
                        response = self.obj.response
                        if isinstance(response, dict):
                            error_msg = response.get('message', '')
                            error_code = response.get('errorCode', '')
                            
                            # Check for EDIS authorization error (AB1007)
                            if 'EDIS' in error_msg.upper() or error_code == 'AB1007':
                                print(f"\n{'='*70}")
                                print(f"⚠️ EDIS AUTHORIZATION REQUIRED")
                                print(f"{'='*70}")
                                print(f"   Symbol: {symbol}")
                                print(f"   Action: {side} {quantity} units")
                                print(f"   Error: {error_msg}")
                                print(f"\n   📋 EDIS Authorization Required:")
                                print(f"   In India, selling stocks in DELIVERY mode requires EDIS authorization.")
                                print(f"   You need to authorize the delivery instruction before selling.")
                                print(f"\n   💡 Solutions:")
                                print(f"   1. Authorize via Angel One mobile app:")
                                print(f"      - Open Angel One app")
                                print(f"      - Go to Orders → Pending EDIS")
                                print(f"      - Authorize the delivery instruction")
                                print(f"   2. Authorize via Angel One web platform:")
                                print(f"      - Login to Angel One website")
                                print(f"      - Go to Orders → EDIS Authorization")
                                print(f"      - Authorize the pending delivery")
                                print(f"   3. After authorization, the bot will retry on next check cycle")
                                print(f"   4. Or place the order manually after authorization")
                                print(f"{'='*70}\n")
                                # Log this for tracking
                                import logging
                                logging.warning(f"EDIS authorization required for {symbol} - {side} {quantity} units")
                                return None
                            
                            # Check for cautionary listing error (AB4036)
                            if 'cautionary' in error_msg.lower() or error_code == 'AB4036':
                                print(f"⚠️ {symbol} is on cautionary listing - cannot place MARKET orders")
                                print(f"   Error: {error_msg}")
                                print(f"   💡 Attempting LIMIT order as fallback...")
                                
                                # Try LIMIT order with current price (if available)
                                # For SELL orders, try a slightly lower price to ensure execution
                                # For BUY orders, try a slightly higher price
                                if price is None:
                                    # Try to get current market price
                                    try:
                                        import yfinance as yf
                                        yf_symbol = symbol.replace('-EQ', '.NS')
                                        ticker = yf.Ticker(yf_symbol)
                                        info = ticker.info
                                        current_market_price = info.get('currentPrice') or info.get('regularMarketPrice')
                                        
                                        if current_market_price:
                                            # For SELL: use slightly lower price (0.5% below)
                                            # For BUY: use slightly higher price (0.5% above)
                                            if side == 'SELL':
                                                limit_price = current_market_price * 0.995
                                            else:
                                                limit_price = current_market_price * 1.005
                                            
                                            print(f"   📊 Current market price: ₹{current_market_price:.2f}")
                                            print(f"   💰 Trying LIMIT order at ₹{limit_price:.2f}")
                                            
                                            order_params['ordertype'] = 'LIMIT'
                                            order_params['price'] = str(round(limit_price, 2))
                                            time.sleep(1)
                                            order_id = self.obj.placeOrder(order_params)
                                            if order_id:
                                                print(f"✅ LIMIT order placed successfully. ID: {order_id}")
                                                return order_id
                                            else:
                                                print(f"❌ LIMIT order also failed. Stock may be completely restricted.")
                                                print(f"   ⚠️ Manual intervention required for {symbol}")
                                                return None
                                    except Exception as limit_error:
                                        print(f"   ❌ Could not fetch market price for LIMIT order: {limit_error}")
                                
                                print(f"❌ Cannot place order for {symbol} - stock is on cautionary listing")
                                print(f"   💡 You may need to place this order manually through broker platform")
                                return None
                            
                            # Check for symbol mismatch error (AB1019)
                            if 'mismatch' in error_msg.lower() or error_code == 'AB1019':
                                print("🔄 Symbol format mismatch detected, trying alternative format...")
                                # Try alternative trading symbol format (name without -EQ)
                                if hasattr(self, 'symbol_info') and symbol in self.symbol_info:
                                    alt_symbol = self.symbol_info[symbol].get('trading_symbol_alt')
                                    if alt_symbol and alt_symbol != trading_symbol:
                                        print(f"   Trying alternative format: '{alt_symbol}' instead of '{trading_symbol}'")
                                        order_params['tradingsymbol'] = alt_symbol
                                        time.sleep(1)
                                        order_id = self.obj.placeOrder(order_params)
                                        if order_id:
                                            print(f"✅ Angel One Order Placed Successfully with alternative format. ID: {order_id}")
                                            return order_id
                            
                            if 'Invalid Token' in error_msg or error_code == 'AG8001':
                                print("🔄 Token expired detected in response, refreshing...")
                                time.sleep(2)  # Wait to avoid rate limiting
                                if self.login():
                                    # Retry order after re-login
                                    print("🔄 Retrying order after token refresh...")
                                    order_id = self.obj.placeOrder(order_params)
                                    if order_id:
                                        print(f"✅ Angel One Order Placed Successfully after refresh. ID: {order_id}")
                                        return order_id
                except:
                    pass
                
                # If we get here, token refresh might be needed anyway
                print("🔄 Order returned None, attempting token refresh...")
                # Wait a moment to avoid rate limiting
                import time
                time.sleep(2)  # Wait 2 seconds to avoid rate limit
                if self.login():
                    # Wait a moment for token to be fully set
                    time.sleep(1)
                    print("🔄 Retrying order after token refresh...")
                    order_id = self.obj.placeOrder(order_params)
                    if order_id:
                        print(f"✅ Angel One Order Placed Successfully after refresh. ID: {order_id}")
                        return order_id
                    else:
                        print("⚠️ Order still failed after token refresh. Token may need manual verification.")
                        print("   Check: 1) API key permissions 2) Account has trading access 3) Market hours")
                
                print(f"❌ Order placement returned no ID")
                return None
            
            print(f"✅ Angel One Order Placed Successfully. ID: {order_id}")
            return order_id
                
        except Exception as e:
            error_str = str(e)
            
            # Check for EDIS authorization error in exception (AB1007)
            if 'EDIS' in error_str.upper() or 'AB1007' in error_str:
                print(f"\n{'='*70}")
                print(f"⚠️ EDIS AUTHORIZATION REQUIRED")
                print(f"{'='*70}")
                print(f"   Symbol: {symbol}")
                print(f"   Action: {side} {quantity} units")
                print(f"   Error: {error_str}")
                print(f"\n   📋 EDIS Authorization Required:")
                print(f"   In India, selling stocks in DELIVERY mode requires EDIS authorization.")
                print(f"   You need to authorize the delivery instruction before selling.")
                print(f"\n   💡 Solutions:")
                print(f"   1. Authorize via Angel One mobile app (Orders → Pending EDIS)")
                print(f"   2. Authorize via Angel One web platform (Orders → EDIS Authorization)")
                print(f"   3. After authorization, bot will retry on next check cycle")
                print(f"{'='*70}\n")
                return None
            
            # Check for cautionary listing error in exception
            if 'cautionary' in error_str.lower() or 'AB4036' in error_str:
                print(f"⚠️ {symbol} is on cautionary listing - cannot place MARKET orders")
                print(f"   Error: {error_str}")
                print(f"   💡 You may need to place this order manually through broker platform")
                print(f"   💡 Or try placing a LIMIT order manually")
                return None
            
            # Final check for token errors in exception message
            if 'Invalid Token' in error_str or 'AG8001' in error_str:
                print("🔄 Token expired (final attempt), refreshing...")
                if self.login():
                    try:
                        # Retry order after re-login
                        print("🔄 Retrying order after token refresh...")
                        order_id = self.obj.placeOrder(order_params)
                        if order_id:
                            print(f"✅ Angel One Order Placed Successfully after refresh. ID: {order_id}")
                            return order_id
                    except Exception as retry_e:
                        print(f"❌ Failed to place order after refresh: {retry_e}")
                        return None
            
            print(f"❌ Failed to place Angel One order: {e}")
            return None
    
    def _handle_rate_limit_error(self, error_msg, retry_func, max_retries=3):
        """Handle rate limit errors with exponential backoff."""
        if "exceeding access rate" in str(error_msg).lower() or "rate" in str(error_msg).lower():
            for attempt in range(max_retries):
                wait_time = (2 ** attempt) * 5  # 5s, 10s, 20s
                print(f"   ⚠️ Rate limit hit. Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                time.sleep(wait_time)
                try:
                    return retry_func()
                except Exception as retry_error:
                    if attempt == max_retries - 1:
                        raise retry_error
                    if "exceeding access rate" not in str(retry_error).lower():
                        raise retry_error
            return None
        return None
    
    def get_positions(self):
        """Get current positions from Angel One with rate limiting."""
        if Config.PAPER_TRADING:
            print("   ⚠️ PAPER TRADING mode - skipping broker position fetch")
            return []
        
        def _fetch_positions():
            if not self._ensure_valid_token():
                print("   ⚠️ Token validation failed - cannot fetch positions")
                return []
            
            # Rate limit protection - wait BEFORE making the call
            self.rate_limiter.wait_if_needed()
            
            print("   🔄 Fetching positions from Angel One API...")
            positions = self.obj.position()
            print(f"   📥 Raw API response: {positions}")
            if positions:
                data = positions.get('data', [])
                # Check if data is None (API can return success with None data)
                if data is None:
                    print("   ℹ️ API returned success but no position data (data is None)")
                    return []
                print(f"   📊 Found {len(data)} position(s) in response")
                return data
            else:
                print("   ℹ️ No positions in API response")
                return []
        
        # Rate limit protection BEFORE attempting call
        self.rate_limiter.wait_if_needed()
        
        try:
            return _fetch_positions()
        except Exception as e:
            error_msg = str(e)
            # Check if it's a rate limit error (handle SmartAPI DataException)
            if ("exceeding access rate" in error_msg.lower() or 
                "rate" in error_msg.lower() or
                "access denied" in error_msg.lower()):
                print(f"   ⚠️ Rate limit detected: {error_msg}")
                print(f"   ⏳ Waiting 30 seconds before retry...")
                time.sleep(30)  # Wait longer for rate limit
                try:
                    # Rate limit again before retry
                    self.rate_limiter.wait_if_needed()
                    return _fetch_positions()
                except Exception as retry_error:
                    retry_msg = str(retry_error)
                    if "exceeding access rate" in retry_msg.lower() or "rate" in retry_msg.lower():
                        print(f"   ⚠️ Still rate limited. Skipping this cycle.")
                        return []  # Return empty instead of failing
                    print(f"   ❌ Failed after retry: {retry_error}")
                    return []
            else:
                print(f"   ❌ Failed to get positions: {e}")
                import traceback
                print(f"   📋 Traceback: {traceback.format_exc()}")
                return []
    
    def normalize_broker_position(self, broker_pos):
        """
        Normalize broker position data to bot's position format.
        Maps broker symbol format to bot symbol format and extracts relevant fields.
        """
        # Broker might return symbol in different formats:
        # - tradingsymbol: "GOLDBEES" or "GOLDBEES-EQ"
        # - symbolname: "GOLDBEES"
        # - symboltoken: token number
        
        trading_symbol = broker_pos.get('tradingsymbol', '') or broker_pos.get('symbolname', '') or broker_pos.get('symbol', '')
        if not trading_symbol:
            print(f"      ⚠️ No trading symbol found in position: {list(broker_pos.keys())}")
            return None
        
        # Normalize symbol format: ensure it ends with -EQ for equity
        # If broker returns "GOLDBEES", convert to "GOLDBEES-EQ"
        if not trading_symbol.endswith('-EQ'):
            # Check if this symbol exists in our cache with -EQ
            symbol_with_eq = f"{trading_symbol}-EQ"
            if symbol_with_eq in self.token_cache:
                trading_symbol = symbol_with_eq
            else:
                # Try to find in symbol_info
                for sym, info in self.symbol_info.items():
                    if info.get('trading_symbol_alt') == trading_symbol or info.get('trading_symbol') == trading_symbol:
                        trading_symbol = sym
                        break
        
        # Extract position data
        # Try multiple field names for quantity (netqty, quantity, buyqty, sellqty)
        quantity = float(broker_pos.get('netqty', 0) or broker_pos.get('quantity', 0) or 
                         broker_pos.get('buyqty', 0) or broker_pos.get('sellqty', 0) or 0)
        if quantity == 0:
            print(f"      ⚠️ Zero quantity position for {trading_symbol}, skipping")
            return None  # Skip zero quantity positions
        
        # Get average price (entry price)
        avg_price = float(broker_pos.get('averageprice', 0) or broker_pos.get('buyprice', 0) or broker_pos.get('ltp', 0))
        if avg_price == 0:
            avg_price = float(broker_pos.get('ltp', 0))  # Fallback to LTP
        
        # Get current price (LTP)
        current_price = float(broker_pos.get('ltp', 0) or broker_pos.get('lasttradedprice', 0) or avg_price)
        
        # Calculate PnL if available, otherwise calculate from price difference
        pnl = float(broker_pos.get('pnl', 0) or broker_pos.get('unrealised', 0))
        if pnl == 0 and avg_price > 0:
            pnl = (current_price - avg_price) * abs(quantity)
        
        return {
            'symbol': trading_symbol,
            'quantity': abs(quantity),  # Always positive
            'buy_price': avg_price,
            'current_price': current_price,
            'highest_price': max(current_price, avg_price),  # Initialize with current or buy price
            'pnl': pnl,
            'broker_data': broker_pos,  # Keep original for reference
            'bot_entered': False,  # Mark as external position
            'entry_time': broker_pos.get('filldate', broker_pos.get('orderdate', '')),  # Use broker's date if available
        }
    
    def sync_all_positions(self):
        """
        Fetch all positions from broker and normalize them.
        Returns a dictionary: symbol -> normalized position data
        Includes both intraday positions and delivery holdings.
        Returns None if sync failed due to rate limiting (to prevent position deletion).
        """
        sync_failed = False
        
        # Get intraday positions
        try:
            broker_positions = self.get_positions()
            # Check if positions call failed due to rate limit (empty list might be valid)
            # We'll track this separately
        except Exception as e:
            error_msg = str(e)
            if "exceeding access rate" in error_msg.lower() or "rate" in error_msg.lower():
                sync_failed = True
                broker_positions = []
            else:
                broker_positions = []
        
        # Also get delivery holdings (for DELIVERY product type positions)
        # Add delay between position and holdings calls to avoid rate limiting
        time.sleep(2)  # 2 second delay between API calls
        
        def _fetch_holdings():
            if not Config.PAPER_TRADING and self._ensure_valid_token():
                # Rate limit protection
                self.rate_limiter.wait_if_needed()
                holdings = self.obj.holding()
                holdings_data = holdings.get('data', []) if holdings else []
                print(f"   📊 Found {len(holdings_data)} holding(s) in response")
                return holdings_data
            return []
        
        print("   🔄 Fetching holdings from Angel One API...")
        # Rate limit protection BEFORE attempting call
        self.rate_limiter.wait_if_needed()
        
        try:
            holdings_data = _fetch_holdings()
            broker_positions.extend(holdings_data)
        except Exception as e:
            error_msg = str(e)
            # Check if it's a rate limit error (handle SmartAPI DataException)
            if ("exceeding access rate" in error_msg.lower() or 
                "rate" in error_msg.lower() or
                "access denied" in error_msg.lower()):
                sync_failed = True
                print(f"   ⚠️ Rate limit detected for holdings: {error_msg}")
                print(f"   ⏳ Waiting 30 seconds before retry...")
                time.sleep(30)  # Wait longer for rate limit
                try:
                    # Rate limit again before retry
                    self.rate_limiter.wait_if_needed()
                    holdings_data = _fetch_holdings()
                    if holdings_data:
                        broker_positions.extend(holdings_data)
                        sync_failed = False  # Retry succeeded
                except Exception as retry_error:
                    retry_msg = str(retry_error)
                    if "exceeding access rate" in retry_msg.lower() or "rate" in retry_msg.lower():
                        sync_failed = True
                        print(f"   ⚠️ Still rate limited. Holdings fetch failed.")
                    else:
                        print(f"   ⚠️ Failed to get holdings after retry: {retry_error}")
            else:
                print(f"   ⚠️ Failed to get holdings: {e}")
        
        # If sync failed due to rate limiting, return None to signal failure
        if sync_failed:
            print(f"   ⚠️ Position sync failed due to rate limiting. Returning None to preserve existing positions.")
            return None
        
        normalized = {}
        
        print(f"   🔍 Total broker positions/holdings: {len(broker_positions)}")
        if broker_positions:
            print(f"   📋 Sample position keys: {list(broker_positions[0].keys()) if broker_positions else 'N/A'}")
        
        for idx, broker_pos in enumerate(broker_positions):
            print(f"   🔍 Processing position #{idx+1}: {broker_pos.get('tradingsymbol', broker_pos.get('symbolname', 'Unknown'))}")
            normalized_pos = self.normalize_broker_position(broker_pos)
            if normalized_pos:
                symbol = normalized_pos['symbol']
                normalized[symbol] = normalized_pos
                print(f"   ✅ Normalized: {symbol} - {normalized_pos['quantity']} @ ₹{normalized_pos['buy_price']:.2f}")
            else:
                print(f"   ⚠️ Failed to normalize position: {broker_pos.get('tradingsymbol', broker_pos.get('symbolname', 'Unknown'))}")
        
        return normalized
    
    def get_holdings(self):
        """Get current holdings from Angel One."""
        if Config.PAPER_TRADING:
            return []
        try:
            holdings = self.obj.holding()
            return holdings.get('data', []) if holdings else []
        except Exception as e:
            print(f"❌ Failed to get holdings: {e}")
            return []
    
    def get_order_book(self):
        """Get order book from Angel One."""
        if Config.PAPER_TRADING:
            return []
        try:
            orders = self.obj.orderBook()
            return orders.get('data', []) if orders else []
        except Exception as e:
            print(f"❌ Failed to get order book: {e}")
            return []
    
    def check_tradeable(self, symbol):
        """
        Check if a stock is tradeable (not on cautionary listing).
        Returns (is_tradeable, reason) tuple.
        """
        if Config.PAPER_TRADING:
            return True, "Paper trading mode"
        
        # Try to place a test order (with very small quantity) to check if it's tradeable
        # Actually, we can't do this without risking an order. Instead, we'll just document
        # that stocks on cautionary listing will fail with AB4036 error.
        # This method is a placeholder for future enhancement.
        return True, "Check will be done during actual order placement"