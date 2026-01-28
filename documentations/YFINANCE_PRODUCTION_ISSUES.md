# yfinance Production Issues (AWS Sydney)

## Problem
yfinance works locally but fails on AWS production (Sydney region) with JSONDecodeError.

## Root Causes

### 1. **IP-Based Rate Limiting**
- Yahoo Finance aggressively rate-limits AWS IP addresses
- AWS IP ranges are often blocked or throttled
- Production servers make more requests → hit rate limits faster

### 2. **Geographic Restrictions**
- Yahoo Finance may have different behavior for different regions
- Sydney region might have stricter access controls
- Network routing differences can cause issues

### 3. **Network/Infrastructure Differences**
- AWS has different network paths than local machines
- Firewall/proxy configurations differ
- SSL/TLS certificate validation differences

### 4. **Concurrent Request Issues**
- Production makes multiple simultaneous requests
- Yahoo Finance may block concurrent requests from same IP
- No connection pooling/reuse

## Solutions Implemented

### 1. Error Suppression
- Suppressed all yfinance error messages
- Prevents log spam
- Bot continues processing other symbols

### 2. Retry Logic with Exponential Backoff
- 3 retry attempts with increasing delays (5s, 10s, 15s)
- Handles temporary API failures
- Reduces rate limiting impact

### 3. Rate Limiting Between Requests
- 3-second delay between symbol fetches
- Prevents hitting rate limits
- Reduces concurrent requests

### 4. Timeout Handling
- 15-second timeout per request
- Prevents hanging requests
- Faster failure recovery

## Additional Recommendations

### Option 1: Use Proxy/VPN (If Needed)
If issues persist, consider using a proxy:
```python
import requests
session = requests.Session()
session.proxies = {'http': 'proxy_url', 'https': 'proxy_url'}
# Pass session to yfinance
```

### Option 2: Use Alternative Data Source
Consider using:
- **NSE API** (official Indian stock exchange API)
- **Alpha Vantage** (paid but reliable)
- **Quandl** (financial data)
- **BSE API** (Bombay Stock Exchange)

### Option 3: Cache Data
- Cache yfinance data for 5-10 minutes
- Reduce API calls
- Use cached data when API fails

### Option 4: Use Different Region
- Try deploying to Mumbai region (closer to India)
- May have better connectivity to Yahoo Finance
- Lower latency for Indian stock data

## Current Status

✅ Error suppression implemented
✅ Retry logic with exponential backoff
✅ Rate limiting between requests
✅ Graceful failure handling

The bot will now:
- Suppress yfinance errors (no log spam)
- Retry failed requests automatically
- Continue processing other symbols
- Skip failed symbols gracefully

## Monitoring

Watch for:
- Symbols being skipped repeatedly
- Empty data returns
- Check if specific symbols fail more often

If issues persist, consider:
1. Switching to NSE API (official Indian exchange)
2. Using a proxy service
3. Deploying to Mumbai region instead of Sydney
