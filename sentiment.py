"""
Sentiment and News Filter
Skips trading during major news events or negative sentiment.
"""
import requests
from datetime import datetime, date
from config import Config

# Major market events calendar (manually maintained)
# Format: "YYYY-MM-DD": "Event Description"
MARKET_EVENTS = {
    # RBI Policy Dates (example - update with actual dates)
    "2026-02-07": "RBI Monetary Policy",
    "2026-04-09": "RBI Monetary Policy",
    "2026-06-06": "RBI Monetary Policy",
    "2026-08-07": "RBI Monetary Policy",
    
    # US Fed Meetings (affects Indian markets)
    "2026-01-29": "US Fed Meeting",
    "2026-03-19": "US Fed Meeting",
    "2026-05-07": "US Fed Meeting",
    
    # Indian Market Holidays (don't trade)
    "2026-01-26": "Republic Day",
    "2026-03-14": "Holi",
    "2026-04-14": "Ambedkar Jayanti",
    "2026-08-15": "Independence Day",
    "2026-10-02": "Gandhi Jayanti",
    "2026-11-04": "Diwali",
    
    # Budget
    "2026-02-01": "Union Budget",
    
    # Quarterly Results Season (high volatility)
    # Add specific dates when major companies report
}

# Events that cause high volatility - be cautious
HIGH_VOLATILITY_EVENTS = [
    "RBI Monetary Policy",
    "US Fed Meeting", 
    "Union Budget",
    "Election Results"
]

# Events when market is closed
MARKET_HOLIDAYS = [
    "Republic Day",
    "Holi",
    "Ambedkar Jayanti",
    "Independence Day",
    "Gandhi Jayanti",
    "Diwali"
]


class SentimentFilter:
    """
    Filters trades based on market sentiment and news events.
    """
    
    def __init__(self):
        self.cache_duration = 300  # 5 minutes
        self.last_check = None
        self.cached_result = None
    
    def get_today_events(self):
        """
        Get any scheduled events for today.
        """
        today = date.today().isoformat()
        event = MARKET_EVENTS.get(today)
        return event
    
    def is_market_holiday(self):
        """
        Check if today is a market holiday.
        """
        event = self.get_today_events()
        if event and event in MARKET_HOLIDAYS:
            return True, event
        return False, None
    
    def is_high_volatility_day(self):
        """
        Check if today has events that cause high volatility.
        """
        event = self.get_today_events()
        if event and event in HIGH_VOLATILITY_EVENTS:
            return True, event
        return False, None
    
    def should_skip_trading(self):
        """
        Main method to check if trading should be skipped.
        Returns: (should_skip: bool, reason: str)
        """
        # Check for holiday
        is_holiday, holiday_name = self.is_market_holiday()
        if is_holiday:
            return True, f"Market Holiday: {holiday_name}"
        
        # Check for high volatility events
        is_volatile, event_name = self.is_high_volatility_day()
        if is_volatile:
            # Don't skip, but return warning
            return False, f"⚠️ High Volatility: {event_name} - Trade with caution"
        
        return False, "No events affecting trading"
    
    def get_market_sentiment(self):
        """
        Get overall market sentiment.
        This is a simplified version - can be enhanced with actual news APIs.
        
        Returns: 'BULLISH', 'BEARISH', or 'NEUTRAL'
        """
        # For now, return neutral
        # Can be enhanced with:
        # 1. News API integration
        # 2. Twitter/X sentiment
        # 3. FII/DII data
        # 4. VIX levels
        
        return "NEUTRAL", "No sentiment data available"
    
    def check_trading_conditions(self):
        """
        Comprehensive check of all trading conditions.
        Returns a detailed status dict.
        """
        status = {
            'can_trade': True,
            'warnings': [],
            'events': [],
            'sentiment': 'NEUTRAL'
        }
        
        # Check holidays
        is_holiday, holiday_name = self.is_market_holiday()
        if is_holiday:
            status['can_trade'] = False
            status['events'].append(f"Holiday: {holiday_name}")
        
        # Check volatility events
        is_volatile, event_name = self.is_high_volatility_day()
        if is_volatile:
            status['warnings'].append(f"High volatility expected: {event_name}")
            status['events'].append(event_name)
        
        # Get sentiment
        sentiment, sentiment_note = self.get_market_sentiment()
        status['sentiment'] = sentiment
        
        if sentiment == 'BEARISH':
            status['warnings'].append("Market sentiment is bearish")
        
        return status
    
    def get_trade_adjustment(self, base_confidence):
        """
        Adjust trade confidence based on sentiment and events.
        """
        status = self.check_trading_conditions()
        
        adjusted_confidence = base_confidence
        
        # Reduce confidence on high volatility days
        if status['warnings']:
            adjusted_confidence *= 0.8
        
        # Reduce confidence on bearish sentiment
        if status['sentiment'] == 'BEARISH':
            adjusted_confidence *= 0.7
        elif status['sentiment'] == 'BULLISH':
            adjusted_confidence *= 1.1
        
        return adjusted_confidence, status


# Singleton instance
sentiment_filter = SentimentFilter()
