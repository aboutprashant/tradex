# EDIS Authorization Guide

## What is EDIS?

**EDIS** (Electronic Delivery Instruction Slip) is a regulatory requirement in India for selling stocks in **DELIVERY** mode. When you sell stocks that you hold in your demat account, you need to authorize the delivery instruction before the order can be executed.

## Error Code: AB1007

When you see this error:
```
You have not authorised this transaction via EDIS. Please tap reorder to try again.
Error Code: AB1007
```

This means the bot tried to sell a stock in DELIVERY mode, but EDIS authorization is pending.

## Why This Happens

- The bot is selling stocks in **DELIVERY** mode (not intraday)
- EDIS authorization is required by SEBI regulations for delivery trades
- The authorization must be done manually through Angel One platform

## How to Authorize EDIS

### Option 1: Angel One Mobile App (Recommended)

1. Open **Angel One** mobile app
2. Go to **Orders** section
3. Look for **Pending EDIS** or **EDIS Authorization**
4. Find the pending delivery instruction for the stock
5. Tap **Authorize** or **Approve**
6. Confirm the authorization

### Option 2: Angel One Web Platform

1. Login to **Angel One** website (https://www.angelone.in)
2. Go to **Orders** → **EDIS Authorization**
3. Find the pending delivery instruction
4. Click **Authorize** or **Approve**
5. Confirm the authorization

### Option 3: After Authorization

Once authorized:
- The bot will automatically retry the order on the next check cycle (usually within 60 seconds)
- Or you can manually place the order through the broker platform

## Bot Behavior

When EDIS error occurs:
- ✅ Bot logs the error with clear instructions
- ✅ Position remains in tracking (not removed)
- ✅ Bot continues monitoring other symbols
- ✅ Bot will retry on next check cycle after authorization

## Prevention Tips

### For Automated Trading:
If you want to avoid EDIS authorization delays:
- Consider using **INTRADAY** product type instead of DELIVERY
- Note: This changes your trading strategy (intraday vs delivery)
- Requires different risk management

### For Delivery Trading:
- Pre-authorize EDIS for frequently traded stocks
- Check EDIS settings in Angel One account
- Enable auto-authorization if available (check with broker)

## Current Bot Configuration

The bot currently uses:
- **Product Type**: DELIVERY
- **Duration**: DAY
- **Order Type**: MARKET (or LIMIT as fallback)

This is appropriate for:
- ✅ Long-term holding strategies
- ✅ ETF trading
- ✅ Swing trading

## Troubleshooting

### If authorization doesn't work:
1. Check if stock is in your demat account
2. Verify you have sufficient holdings
3. Check if stock is on cautionary listing
4. Contact Angel One support if issues persist

### If bot keeps retrying:
- The bot will retry every check cycle (60 seconds)
- After authorization, the order should go through
- If it still fails, check for other errors (cautionary listing, etc.)

## Related Errors

- **AB4036**: Cautionary listing (different issue)
- **AG8001**: Invalid token (login issue)
- **AB1007**: EDIS authorization (this guide)

## Summary

EDIS authorization is a **regulatory requirement** in India for delivery trades. The bot handles this gracefully by:
1. Detecting the error
2. Providing clear instructions
3. Keeping the position tracked
4. Retrying after authorization

You just need to authorize via Angel One app/website, and the bot will handle the rest!
