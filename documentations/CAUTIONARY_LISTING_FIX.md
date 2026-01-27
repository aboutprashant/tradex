# Cautionary Listing Error Fix (AB4036)

## Problem
Some stocks are placed on "cautionary listing" by the exchange (NSE), which prevents MARKET orders from being executed. This affects stocks like:
- AFFLE-EQ
- BHARTIHEXA-EQ
- And potentially others

## Error Message
```
The order cannot be processed as the token is categorised under cautionary listings by the exchange.
Error Code: AB4036
```

## Solution Implemented

### 1. Error Detection
The bot now detects AB4036 errors and handles them gracefully:
- Detects the error in both exception handlers and response checks
- Provides clear error messages to the user
- Attempts LIMIT order as fallback (if market price is available)

### 2. Order Handling
- **Before**: Order would fail silently, position would still be removed from tracking
- **After**: 
  - Order failure is detected
  - Position remains in tracking if order fails
  - User is notified that manual intervention may be required

### 3. Fallback Strategy
When a stock is on cautionary listing:
1. Bot attempts to get current market price
2. Tries to place a LIMIT order instead of MARKET order
   - For SELL: 0.5% below market price
   - For BUY: 0.5% above market price
3. If LIMIT order also fails, user is notified

## Manual Workaround

If automatic LIMIT order also fails, you need to:

1. **Place order manually** through Angel One platform
2. **Use LIMIT order** instead of MARKET order
3. **Check stock status** on NSE website for cautionary listing details

## Stocks Currently Affected
Based on your logs:
- AFFLE-EQ
- BHARTIHEXA-EQ

## Future Enhancements
- Pre-check stocks before attempting trades
- Maintain a blacklist of stocks on cautionary listing
- Automatic retry with LIMIT orders at different price levels
- Integration with NSE API to check cautionary listing status

## Code Changes

### broker_client.py
- Added AB4036 error detection
- Added LIMIT order fallback logic
- Improved error messages

### script.py
- Added order result checking
- Position tracking now persists if order fails
- Better error handling for failed orders

## Testing
To test the fix:
1. The bot will automatically handle cautionary listing errors
2. Check logs for clear error messages
3. Positions will remain tracked if order fails
4. Manual intervention message will be displayed
