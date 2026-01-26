import pyotp
from SmartApi import SmartConnect
from config import Config

class BrokerClient:
    def __init__(self):
        self.obj = SmartConnect(api_key=Config.API_KEY)
        self.session_data = None

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
            self.obj.setAccessToken(auth_token)
            
            print("✅ Angel One Login Successful")
            print(f"   Logged in as: {self.session_data['data'].get('name', 'Unknown')}")
            return True
        except Exception as e:
            print(f"❌ Angel One Login failed: {e}")
            return False

    def place_order(self, symbol, quantity, side, price=None):
        """
        side: 'BUY' or 'SELL'
        price: if None, it's a MARKET order, else a LIMIT order
        """
        if Config.PAPER_TRADING:
            print(f"[PAPER] Angel One Order: {side} {quantity} units of {symbol} at ₹{price or 'MARKET'}")
            return True

        try:
            order_params = {
                "variety": "NORMAL",
                "tradingsymbol": symbol,
                "symboltoken": "10571", # Token for NIFTYBEES-EQ (NSE)
                "transactiontype": side,
                "exchange": "NSE",
                "ordertype": "MARKET" if price is None else "LIMIT",
                "producttype": "DELIVERY",
                "duration": "DAY",
                "quantity": str(quantity)
            }
            if price:
                order_params["price"] = str(price)
            
            order_id = self.obj.placeOrder(order_params)
            print(f"Angel One Order Placed Successfully. ID: {order_id}")
            return order_id
        except Exception as e:
            print(f"Failed to place Angel One order: {e}")
            return None
