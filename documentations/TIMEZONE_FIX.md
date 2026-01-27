# Timezone Fix for AWS Production (Sydney Region)

## Problem
The bot was running on AWS in Sydney region and checking market hours using Sydney local time instead of IST (Indian Standard Time). This caused the bot to:
- Make checks when market was closed
- Miss market open/close times
- Use wrong timezone for all time-based operations

## Root Cause
The `is_market_open()` function and other datetime operations used `datetime.now()` which returns the server's local timezone (Sydney = UTC+10/11), not IST (UTC+5:30).

## Solution
All time operations now use **IST (Indian Standard Time)** regardless of server location:

### Changes Made

1. **Added pytz library** to requirements.txt
2. **Updated `is_market_open()` function**:
   - Now uses `datetime.now(ist)` instead of `datetime.now()`
   - All market hour checks use IST timezone
   - Returns IST time in status messages

3. **Updated `is_high_liquidity_window()` function**:
   - Uses IST for liquidity window checks

4. **Updated all datetime references**:
   - `print_status()` - Shows IST time
   - Position sync timestamps - Uses IST
   - Entry time logging - Stores IST time
   - Daily summary dates - Uses IST date
   - Learning engine hour checks - Uses IST hour

## Code Changes

### Before
```python
def is_market_open():
    now = datetime.now()  # Uses server timezone (Sydney)
    # ... checks using server time
```

### After
```python
def is_market_open():
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist)  # Always uses IST
    # ... checks using IST time
```

## Verification

The bot now:
- ✅ Checks market hours using IST (9:15 AM - 3:30 PM IST)
- ✅ Shows IST time in all logs
- ✅ Correctly identifies market open/closed status
- ✅ Works correctly regardless of server location

## Testing

To verify the fix:
1. Check logs show IST time: `2026-01-27 14:02:38 IST`
2. Market closed message shows IST: `Market closed at 15:30 IST`
3. Bot sleeps when market is closed (after 3:30 PM IST)
4. Bot resumes checks at market open (9:15 AM IST)

## Installation

After deploying, install pytz:
```bash
pip install pytz
```

Or update requirements:
```bash
pip install -r requirements.txt
```

## Timezone Reference

- **IST**: UTC+5:30 (Indian Standard Time)
- **Sydney**: UTC+10 (AEST) or UTC+11 (AEDT)
- **Difference**: Sydney is ~4.5-5.5 hours ahead of IST

## Example

**Before (Sydney time)**:
- Server time: 14:02 (2:02 PM Sydney)
- Market check: Uses Sydney time → Wrong!

**After (IST time)**:
- Server time: 14:02 (2:02 PM Sydney)
- IST time: 09:32 (9:32 AM IST)
- Market check: Uses IST → Correct! (Market opens at 9:15 AM IST)
