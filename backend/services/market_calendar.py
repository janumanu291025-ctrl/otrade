"""
Market Calendar Service - Simplified
Minimal market timing using exchange_calendars library.
Only checks: is trading day, market hours, next trading session.
"""
import pandas as pd
import exchange_calendars as xcals
from datetime import datetime, time, timedelta
from typing import Dict, Optional
from functools import lru_cache
import pytz
import logging

logger = logging.getLogger(__name__)

IST = pytz.timezone('Asia/Kolkata')

_calendar_cache = None


def get_exchange_calendar():
    """Get cached exchange calendar instance"""
    global _calendar_cache
    if _calendar_cache is None:
        _calendar_cache = xcals.get_calendar('XBOM')
        logger.info(f"Calendar: {_calendar_cache.name} ({_calendar_cache.sessions.min().date()} to {_calendar_cache.sessions.max().date()})")
    return _calendar_cache


class MarketCalendar:
    """Minimal market calendar service"""
    
    def __init__(self):
        self.calendar = get_exchange_calendar()
        self.tz = IST
    
    def get_current_time(self) -> datetime:
        """Get current time in IST"""
        return datetime.now(IST)
    
    def convert_to_ist(self, dt: datetime) -> datetime:
        """Convert datetime to IST"""
        if dt.tzinfo is None:
            dt = IST.localize(dt)
        else:
            dt = dt.astimezone(IST)
        return dt
    
    # ==================== Trading Day Check ====================
    
    @lru_cache(maxsize=365)
    def is_trading_day(self, date_str: str) -> bool:
        """Check if date is a trading day (cached)"""
        date_only = pd.Timestamp(date_str)
        
        # Check calendar range
        if date_only < self.calendar.sessions.min() or date_only > self.calendar.sessions.max():
            # Outside calendar: weekday = trading day
            return date_only.weekday() < 5
        
        return self.calendar.is_session(date_only)
    
    def is_trading_day_dt(self, check_date: Optional[datetime] = None) -> bool:
        """Check if a datetime is a trading day"""
        if check_date is None:
            check_date = self.get_current_time()
        
        check_date = self.convert_to_ist(check_date)
        date_str = check_date.strftime('%Y-%m-%d')
        return self.is_trading_day(date_str)
    
    # ==================== Market Status ====================
    
    def is_market_open(self, check_time: Optional[datetime] = None) -> bool:
        """Check if market is currently open"""
        if check_time is None:
            check_time = self.get_current_time()
        
        check_time = self.convert_to_ist(check_time)
        
        if not self.is_trading_day_dt(check_time):
            return False
        
        pd_time = pd.Timestamp(check_time)
        pd_date = pd.Timestamp(check_time.date())
        
        # Check calendar range
        if pd_date < self.calendar.sessions.min() or pd_date > self.calendar.sessions.max():
            # Future dates: use default hours
            current_time = check_time.time()
            return time(9, 15) <= current_time <= time(15, 30)
        
        return self.calendar.is_open_at_time(pd_time)
    
    def get_market_open_close(self, date: Optional[datetime] = None) -> Dict[str, Optional[time]]:
        """Get market open/close times for a date"""
        if date is None:
            date = self.get_current_time()
        
        date = self.convert_to_ist(date)
        date_only = pd.Timestamp(date.date())
        
        if not self.is_trading_day(date_only.strftime('%Y-%m-%d')):
            return {'open': None, 'close': None}
        
        # Check calendar range
        if date_only < self.calendar.sessions.min() or date_only > self.calendar.sessions.max():
            # Future dates: use default hours
            return {'open': time(9, 15), 'close': time(15, 30)}
        
        schedule = self.calendar.schedule.loc[date_only:date_only]
        if len(schedule) > 0:
            row = schedule.iloc[0]
            open_time = row['open'].tz_convert(IST).time()
            close_time = row['close'].tz_convert(IST).time()
            return {'open': open_time, 'close': close_time}
        
        return {'open': None, 'close': None}
    
    def get_market_status(self) -> Dict:
        """Get market status"""
        now = self.get_current_time()
        is_open = self.is_market_open(now)
        is_trading = self.is_trading_day_dt(now)
        hours = self.get_market_open_close(now)
        
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        status = {
            'is_open': is_open,
            'is_trading_day': is_trading,
            'current_time': now.strftime('%Y-%m-%d %H:%M:%S %Z'),
            'current_day': day_names[now.weekday()],
            'market_open_time': hours['open'].strftime('%H:%M') if hours['open'] else None,
            'market_close_time': hours['close'].strftime('%H:%M') if hours['close'] else None,
            'exchange': self.calendar.name,
            'next_trading_day': None
        }
        
        # Find next trading day
        if not is_trading:
            next_day = now.date() + timedelta(days=1)
            for _ in range(10):
                # Create datetime from date for checking
                check_dt = datetime.combine(next_day, time(0, 0))
                check_dt = self.convert_to_ist(check_dt)
                if self.is_trading_day_dt(check_dt):
                    status['next_trading_day'] = next_day.strftime('%Y-%m-%d')
                    break
                next_day = next_day + timedelta(days=1)
        
        return status
    
    def get_next_trading_day(self, from_date: Optional[datetime] = None) -> Optional[str]:
        """Get next trading day after given date"""
        if from_date is None:
            from_date = self.get_current_time()
        
        from_date = self.convert_to_ist(from_date)
        
        # Ensure from_date is a datetime, not a date
        if not isinstance(from_date, datetime):
            from_date = datetime.combine(from_date, time(0, 0))
        
        next_day = from_date.date() + timedelta(days=1)
        
        for _ in range(30):
            if self.is_trading_day_dt(datetime.combine(next_day, time(0, 0))):
                return next_day.strftime('%Y-%m-%d')
            next_day = next_day + timedelta(days=1)
        
        return None


# ==================== Global Instance ====================

_market_calendar_instance = None


def get_market_calendar() -> MarketCalendar:
    """Get global market calendar instance (singleton)"""
    global _market_calendar_instance
    if _market_calendar_instance is None:
        _market_calendar_instance = MarketCalendar()
    return _market_calendar_instance


# ==================== Convenience Functions ====================

def is_market_open(check_time: Optional[datetime] = None) -> bool:
    """Check if market is currently open"""
    calendar = get_market_calendar()
    return calendar.is_market_open(check_time)


def is_trading_day(date: Optional[datetime] = None) -> bool:
    """Check if date is a trading day"""
    calendar = get_market_calendar()
    return calendar.is_trading_day_dt(date)


def get_market_status() -> Dict:
    """Get detailed market status"""
    calendar = get_market_calendar()
    return calendar.get_market_status()


def get_market_open_close(date: Optional[datetime] = None) -> Dict[str, Optional[time]]:
    """Get market open/close times"""
    calendar = get_market_calendar()
    return calendar.get_market_open_close(date)


def get_next_trading_day(from_date: Optional[datetime] = None) -> Optional[str]:
    """Get next trading day"""
    calendar = get_market_calendar()
    return calendar.get_next_trading_day(from_date)


def get_current_ist_time() -> datetime:
    """Get current time in IST"""
    return datetime.now(IST)
