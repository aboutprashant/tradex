# External Position Policy

## Overview
The bot will **NEVER** automatically sell stocks that it did not purchase. External positions (stocks bought manually or through other means) are tracked for monitoring purposes only.

## Policy Details

### Bot-Entered Positions
- **Identified by**: `bot_entered: True` flag
- **Actions Allowed**:
  - ✅ Automatic selling on stop-loss
  - ✅ Automatic selling on target hit
  - ✅ Automatic selling on trend reversal
  - ✅ Trailing stop-loss management

### External Positions
- **Identified by**: `bot_entered: False` flag or missing `bot_entered` field
- **Actions Allowed**:
  - ✅ Price tracking and monitoring
  - ✅ PnL calculation and display
  - ✅ Highest price tracking
  - ❌ **NO automatic selling**
  - ❌ **NO stop-loss execution**
  - ❌ **NO target-based selling**

## Implementation

### Main Trading Loop
When processing positions in the main trading symbols list:
```python
if not position.get('bot_entered', True):
    # External position - only track, don't sell
    # Update price tracking only
    continue  # Skip exit logic
```

### External Position Processing
For positions not in the trading list:
```python
if not position.get('bot_entered', True):
    # External position - only update price tracking, never sell
    # Calculate PnL for display only
    # No exit conditions checked
```

## Benefits

1. **Safety**: Prevents accidental selling of manually purchased stocks
2. **Control**: You maintain full control over external positions
3. **Monitoring**: Still tracks performance of all positions
4. **Transparency**: Clear distinction between bot and manual trades

## How to Identify Position Type

### In Logs
- `🤖 Bot` - Position entered by bot (can be sold automatically)
- `👤 External` - Position entered manually (tracked only)

### In Code
- `bot_entered: True` - Bot can sell
- `bot_entered: False` - Bot will NOT sell

## Manual Selling

If you want to sell an external position:
1. Place the order manually through your broker platform
2. The bot will detect the position closure on next sync
3. Position will be removed from tracking automatically

## Example

```
📍 Loaded bot position: GOLDBEES-EQ - 2 @ ₹130.88
   → bot_entered: True → Bot can sell this

📍 Found external position: DRREDDY-EQ - 4.0 @ ₹1287.34
   → bot_entered: False → Bot will track but NOT sell
```

## Code Changes

### Files Modified
- `script.py`: Added `bot_entered` checks before exit logic

### Key Changes
1. Main trading loop: Skip exit logic for external positions
2. External position processing: Only track, never sell
3. Clear comments explaining the policy
