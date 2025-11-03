"""
Market Time Service
===================

Unified service for all market timing operations:
- Market hours management (default: 9:15 AM - 3:30 PM)
- Webhook connection timing (default: 9:00 AM - 3:30 PM, 15 minutes before market opens)
- Order placement window (default: 9:20 AM - 3:15 PM)
- Square-off time (default: 3:20 PM)
- Holiday management (persistent database storage)
- Weekend and trading day validation
- IST timezone handling

This service provides a single source of truth for all time-based trading logic.
"""
import logging
from datetime import datetime, time, timedelta
from typing import List, Optional, Dict
import pytz
from sqlalchemy.orm import Session
import json

from backend.models import MarketHours, Holiday

logger = logging.getLogger(__name__)

# IST timezone
IST = pytz.timezone('Asia/Kolkata')


class MarketTimeService:
    """
    Unified service for all market timing operations
    """
    
    def __init__(self, db: Session):
        """
        Initialize market time service
        
        Args:
            db: Database session
        """
        self.db = db
    
    # ==================== Configuration Management ====================
    
    def get_config(self) -> MarketHours:
        """
        Get market hours configuration from database
        
        Returns:
            MarketHours configuration object
        """
        config = self.db.query(MarketHours).first()
        
        if not config:
            # Create default configuration
            config = MarketHours(
                start_time="09:15",
                end_time="15:30",
                webhook_start_time="09:00",
                order_placement_start_time="09:20",
                order_placement_end_time="15:15",
                square_off_time="15:20",
                trading_days=json.dumps([0, 1, 2, 3, 4]),  # Monday to Friday
                polling_interval_seconds=300
            )
            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)
        
        return config
    
    def update_config(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        webhook_start_time: Optional[str] = None,
        order_placement_start_time: Optional[str] = None,
        order_placement_end_time: Optional[str] = None,
        square_off_time: Optional[str] = None,
        trading_days: Optional[List[int]] = None,
        webhook_url: Optional[str] = None,
        polling_interval_seconds: Optional[int] = None
    ) -> MarketHours:
        """
        Update market hours configuration
        
        Args:
            start_time: Market start time (HH:MM format)
            end_time: Market end time (HH:MM format)
            webhook_start_time: Webhook connection start time (HH:MM format)
            order_placement_start_time: Order placement start time (HH:MM format)
            order_placement_end_time: Order placement end time (HH:MM format)
            square_off_time: Square-off time (HH:MM format)
            trading_days: List of trading days [0=Monday, ..., 6=Sunday]
            webhook_url: Webhook URL for postback
            polling_interval_seconds: Polling interval in seconds
        
        Returns:
            Updated MarketHours configuration
        """
        config = self.get_config()
        
        if start_time is not None:
            config.start_time = start_time
        if end_time is not None:
            config.end_time = end_time
        if webhook_start_time is not None:
            config.webhook_start_time = webhook_start_time
        if order_placement_start_time is not None:
            config.order_placement_start_time = order_placement_start_time
        if order_placement_end_time is not None:
            config.order_placement_end_time = order_placement_end_time
        if square_off_time is not None:
            config.square_off_time = square_off_time
        if trading_days is not None:
            config.trading_days = json.dumps(trading_days)
        if webhook_url is not None:
            config.webhook_url = webhook_url
        if polling_interval_seconds is not None:
            config.polling_interval_seconds = polling_interval_seconds
        
        self.db.commit()
        self.db.refresh(config)
        
        return config
    
    # ==================== Holiday Management ====================
    
    def get_holidays(self, year: Optional[int] = None) -> List[Holiday]:
        """
        Get list of holidays from database
        
        Args:
            year: Filter by year (optional)
        
        Returns:
            List of Holiday objects
        """
        query = self.db.query(Holiday)
        
        if year:
            start_date = f"{year}-01-01"
            end_date = f"{year}-12-31"
            query = query.filter(Holiday.date >= start_date, Holiday.date <= end_date)
        
        return query.order_by(Holiday.date).all()
    
    def get_holiday_dates(self, year: Optional[int] = None) -> List[str]:
        """
        Get list of holiday dates in YYYY-MM-DD format
        
        Args:
            year: Filter by year (optional)
        
        Returns:
            List of date strings
        """
        holidays = self.get_holidays(year)
        return [h.date for h in holidays]
    
    def add_holiday(self, date: str, name: str, description: Optional[str] = None) -> Holiday:
        """
        Add a new holiday to database
        
        Args:
            date: Holiday date (YYYY-MM-DD format)
            name: Holiday name
            description: Optional description
        
        Returns:
            Created Holiday object
        """
        # Check if holiday already exists
        existing = self.db.query(Holiday).filter(Holiday.date == date).first()
        if existing:
            logger.warning(f"Holiday on {date} already exists")
            return existing
        
        # Create new holiday
        new_holiday = Holiday(date=date, name=name, description=description)
        self.db.add(new_holiday)
        self.db.commit()
        self.db.refresh(new_holiday)
        
        logger.info(f"Added holiday: {date} - {name}")
        return new_holiday
    
    def remove_holiday(self, date: str) -> bool:
        """
        Remove a holiday by date
        
        Args:
            date: Holiday date (YYYY-MM-DD format)
        
        Returns:
            True if removed, False if not found
        """
        holiday = self.db.query(Holiday).filter(Holiday.date == date).first()
        
        if holiday:
            self.db.delete(holiday)
            self.db.commit()
            logger.info(f"Removed holiday: {date}")
            return True
        
        return False
    
    def is_holiday(self, date: datetime) -> bool:
        """
        Check if a given date is a holiday
        
        Args:
            date: Date to check
        
        Returns:
            True if holiday, False otherwise
        """
        date_str = date.strftime('%Y-%m-%d')
        holiday = self.db.query(Holiday).filter(Holiday.date == date_str).first()
        return holiday is not None
    
    # ==================== Time and Timezone ====================
    
    def get_current_ist_time(self) -> datetime:
        """
        Get current time in IST timezone
        
        Returns:
            Current datetime in IST
        """
        return datetime.now(IST)
    
    def convert_to_ist(self, dt: datetime) -> datetime:
        """
        Convert datetime to IST timezone
        
        Args:
            dt: Datetime to convert
        
        Returns:
            Datetime in IST
        """
        if dt.tzinfo is None:
            dt = IST.localize(dt)
        else:
            dt = dt.astimezone(IST)
        return dt
    
    # ==================== Trading Day Validation ====================
    
    def is_trading_day(self, check_date: Optional[datetime] = None) -> bool:
        """
        Check if a given date is a trading day (not weekend or holiday)
        
        Args:
            check_date: Date to check (defaults to current date)
        
        Returns:
            True if trading day, False otherwise
        """
        if check_date is None:
            check_date = self.get_current_ist_time()
        
        # Ensure date is in IST
        check_date = self.convert_to_ist(check_date)
        
        # Check if weekend (Saturday=5, Sunday=6)
        if check_date.weekday() >= 5:
            logger.debug(f"{check_date.date()} is a weekend")
            return False
        
        # Check if holiday
        if self.is_holiday(check_date):
            logger.debug(f"{check_date.date()} is a holiday")
            return False
        
        return True
    
    # ==================== Market Status Checks ====================
    
    def is_market_open(self, check_time: Optional[datetime] = None) -> bool:
        """
        Check if market is currently open (9:15 AM - 3:30 PM on trading days)
        
        Args:
            check_time: Time to check (defaults to current time)
        
        Returns:
            True if market is open, False otherwise
        """
        if check_time is None:
            check_time = self.get_current_ist_time()
        
        # Ensure time is in IST
        check_time = self.convert_to_ist(check_time)
        
        config = self.get_config()
        
        # Check if today is a trading day
        if not self.is_trading_day(check_time):
            return False
        
        # Check if current day is in trading_days configuration
        weekday = check_time.weekday()
        trading_days = config.trading_days
        if isinstance(trading_days, str):
            trading_days = json.loads(trading_days)
        
        if weekday not in trading_days:
            return False
        
        # Parse market hours
        start_hour, start_minute = map(int, config.start_time.split(':'))
        end_hour, end_minute = map(int, config.end_time.split(':'))
        
        market_start = time(start_hour, start_minute)
        market_end = time(end_hour, end_minute)
        
        current_time = check_time.time()
        
        # Check if current time is within market hours
        is_open = market_start <= current_time <= market_end
        
        if is_open:
            logger.debug(f"Market is open at {current_time}")
        else:
            logger.debug(f"Market closed: Outside trading hours ({current_time})")
        
        return is_open
    
    def is_webhook_connection_time(self, check_time: Optional[datetime] = None) -> bool:
        """
        Check if webhook connection should be active (9:00 AM - 3:30 PM, 15 minutes before market opens)
        
        Args:
            check_time: Time to check (defaults to current time)
        
        Returns:
            True if webhook should be connected, False otherwise
        """
        if check_time is None:
            check_time = self.get_current_ist_time()
        
        # Ensure time is in IST
        check_time = self.convert_to_ist(check_time)
        
        config = self.get_config()
        
        # Check if today is a trading day
        if not self.is_trading_day(check_time):
            return False
        
        # Check if current day is in trading_days configuration
        weekday = check_time.weekday()
        trading_days = config.trading_days
        if isinstance(trading_days, str):
            trading_days = json.loads(trading_days)
        
        if weekday not in trading_days:
            return False
        
        # Parse webhook connection time
        webhook_start_hour, webhook_start_minute = map(int, config.webhook_start_time.split(':'))
        end_hour, end_minute = map(int, config.end_time.split(':'))
        
        webhook_start = time(webhook_start_hour, webhook_start_minute)
        webhook_end = time(end_hour, end_minute)
        
        current_time = check_time.time()
        
        # Check if current time is within webhook connection hours
        is_connection_time = webhook_start <= current_time <= webhook_end
        
        if is_connection_time:
            logger.debug(f"Webhook connection time active at {current_time}")
        else:
            logger.debug(f"Webhook connection time: Outside hours ({current_time})")
        
        return is_connection_time
    
    def is_order_placement_time(self, check_time: Optional[datetime] = None) -> bool:
        """
        Check if orders can be placed (9:20 AM - 3:15 PM on trading days)
        
        Args:
            check_time: Time to check (defaults to current time)
        
        Returns:
            True if orders can be placed, False otherwise
        """
        if check_time is None:
            check_time = self.get_current_ist_time()
        
        # Ensure time is in IST
        check_time = self.convert_to_ist(check_time)
        
        config = self.get_config()
        
        # Check if today is a trading day
        if not self.is_trading_day(check_time):
            return False
        
        # Check if current day is in trading_days configuration
        weekday = check_time.weekday()
        trading_days = config.trading_days
        if isinstance(trading_days, str):
            trading_days = json.loads(trading_days)
        
        if weekday not in trading_days:
            return False
        
        # Parse order placement window
        start_hour, start_minute = map(int, config.order_placement_start_time.split(':'))
        end_hour, end_minute = map(int, config.order_placement_end_time.split(':'))
        
        placement_start = time(start_hour, start_minute)
        placement_end = time(end_hour, end_minute)
        
        current_time = check_time.time()
        
        # Check if current time is within order placement window
        can_place = placement_start <= current_time <= placement_end
        
        if can_place:
            logger.debug(f"Order placement allowed at {current_time}")
        else:
            logger.debug(f"Order placement not allowed: Outside window ({current_time})")
        
        return can_place
    
    def is_square_off_time(self, check_time: Optional[datetime] = None) -> bool:
        """
        Check if it's time to square off positions (default: 3:20 PM)
        
        Args:
            check_time: Time to check (defaults to current time)
        
        Returns:
            True if it's square-off time or later, False otherwise
        """
        if check_time is None:
            check_time = self.get_current_ist_time()
        
        # Ensure time is in IST
        check_time = self.convert_to_ist(check_time)
        
        config = self.get_config()
        
        # Check if today is a trading day
        if not self.is_trading_day(check_time):
            return False
        
        # Parse square-off time
        square_hour, square_minute = map(int, config.square_off_time.split(':'))
        square_off = time(square_hour, square_minute)
        
        current_time = check_time.time()
        
        # Check if current time is at or after square-off time
        is_square_off = current_time >= square_off
        
        if is_square_off:
            logger.debug(f"Square-off time reached at {current_time}")
        
        return is_square_off
    
    # ==================== Market Status Information ====================
    
    def get_market_status(self) -> Dict:
        """
        Get detailed market status information
        
        Returns:
            Dictionary with market status details
        """
        now = self.get_current_ist_time()
        config = self.get_config()
        is_open = self.is_market_open(now)
        is_trading = self.is_trading_day(now)
        
        # Parse trading_days
        trading_days = config.trading_days
        if isinstance(trading_days, str):
            trading_days = json.loads(trading_days)
        
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        trading_day_names = [day_names[i] for i in trading_days]
        
        status = {
            'is_open': is_open,
            'is_active': is_open,
            'is_trading_day': is_trading,
            'is_webhook_connection_time': self.is_webhook_connection_time(now),
            'is_order_placement_time': self.is_order_placement_time(now),
            'is_square_off_time': self.is_square_off_time(now),
            'current_time': now.strftime('%Y-%m-%d %H:%M:%S %Z'),
            'current_day': day_names[now.weekday()],
            'market_open_time': config.start_time,
            'market_close_time': config.end_time,
            'webhook_start_time': config.webhook_start_time,
            'order_placement_start_time': config.order_placement_start_time,
            'order_placement_end_time': config.order_placement_end_time,
            'square_off_time': config.square_off_time,
            'trading_days': trading_day_names,
            'next_trading_day': None
        }
        
        # Find next trading day if market is closed
        if not is_trading:
            next_day = now
            for _ in range(10):
                next_day = next_day.replace(hour=0, minute=0, second=0, microsecond=0)
                next_day = next_day + timedelta(days=1)
                if self.is_trading_day(next_day):
                    status['next_trading_day'] = next_day.strftime('%Y-%m-%d')
                    break
        
        return status
    
    def time_until_market_open(self) -> Dict:
        """
        Calculate time remaining until market opens
        
        Returns:
            Dictionary with time details
        """
        now = self.get_current_ist_time()
        config = self.get_config()
        
        if self.is_market_open(now):
            return {
                'is_open': True,
                'seconds': 0,
                'formatted': 'Market is currently open'
            }
        
        # Parse market start time
        start_hour, start_minute = map(int, config.start_time.split(':'))
        
        # Find next market open time
        next_open = now.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
        
        # Parse market end time
        end_hour, end_minute = map(int, config.end_time.split(':'))
        market_end = time(end_hour, end_minute)
        
        # If market already closed today, move to next trading day
        if now.time() > market_end:
            next_open = next_open + timedelta(days=1)
        
        # Skip to next trading day
        while not self.is_trading_day(next_open):
            next_open = next_open + timedelta(days=1)
        
        time_diff = next_open - now
        seconds = int(time_diff.total_seconds())
        
        # Format human-readable
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 24:
            days = hours // 24
            hours = hours % 24
            formatted = f"{days} day(s), {hours} hour(s), {minutes} minute(s)"
        else:
            formatted = f"{hours} hour(s), {minutes} minute(s), {secs} second(s)"
        
        return {
            'is_open': False,
            'seconds': seconds,
            'formatted': formatted,
            'opens_at': next_open.strftime('%Y-%m-%d %H:%M:%S %Z')
        }
    
    def time_until_market_close(self) -> Dict:
        """
        Calculate time remaining until market closes
        
        Returns:
            Dictionary with time details
        """
        now = self.get_current_ist_time()
        config = self.get_config()
        
        if not self.is_market_open(now):
            return {
                'is_open': False,
                'seconds': 0,
                'formatted': 'Market is currently closed'
            }
        
        # Parse market end time
        end_hour, end_minute = map(int, config.end_time.split(':'))
        market_close = now.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
        
        time_diff = market_close - now
        seconds = int(time_diff.total_seconds())
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        formatted = f"{hours} hour(s), {minutes} minute(s), {secs} second(s)"
        
        return {
            'is_open': True,
            'seconds': seconds,
            'formatted': formatted,
            'closes_at': market_close.strftime('%Y-%m-%d %H:%M:%S %Z')
        }
    
    # ==================== Polling Configuration ====================
    
    def should_use_webhook(self) -> bool:
        """
        Check if webhook should be used for order updates
        
        Returns:
            True if webhook connection time is active, False otherwise
        """
        return self.is_webhook_connection_time()
    
    def should_use_polling(self) -> bool:
        """
        Check if API polling should be used for order updates
        
        Returns:
            True if polling should be used (webhook not active), False otherwise
        """
        return not self.is_webhook_connection_time()
    
    def get_polling_interval(self) -> int:
        """
        Get the polling interval in seconds
        
        Returns:
            Polling interval in seconds
        """
        config = self.get_config()
        return config.polling_interval_seconds


# ==================== Convenience Functions ====================

def get_market_time_service(db: Session) -> MarketTimeService:
    """
    Get market time service instance
    
    Args:
        db: Database session
    
    Returns:
        MarketTimeService instance
    """
    return MarketTimeService(db)


# Standalone functions for backward compatibility

def get_current_ist_time() -> datetime:
    """Get current time in IST timezone (doesn't require db)"""
    return datetime.now(IST)


def is_market_open(db: Session, check_time: Optional[datetime] = None) -> bool:
    """Check if market is currently open"""
    service = get_market_time_service(db)
    return service.is_market_open(check_time)


def is_webhook_connection_time(db: Session, check_time: Optional[datetime] = None) -> bool:
    """Check if webhook connection should be active"""
    service = get_market_time_service(db)
    return service.is_webhook_connection_time(check_time)


def is_order_placement_time(db: Session, check_time: Optional[datetime] = None) -> bool:
    """Check if orders can be placed"""
    service = get_market_time_service(db)
    return service.is_order_placement_time(check_time)


def is_square_off_time(db: Session, check_time: Optional[datetime] = None) -> bool:
    """Check if it's square-off time"""
    service = get_market_time_service(db)
    return service.is_square_off_time(check_time)


def is_trading_day(db: Session, date: Optional[datetime] = None) -> bool:
    """Check if date is a trading day"""
    service = get_market_time_service(db)
    return service.is_trading_day(date)


def get_market_status(db: Session) -> Dict:
    """Get detailed market status"""
    service = get_market_time_service(db)
    return service.get_market_status()


def should_use_webhook(db: Session) -> bool:
    """Check if webhook should be used"""
    service = get_market_time_service(db)
    return service.should_use_webhook()


def should_use_polling(db: Session) -> bool:
    """Check if polling should be used"""
    service = get_market_time_service(db)
    return service.should_use_polling()


def get_polling_interval(db: Session) -> int:
    """Get polling interval in seconds"""
    service = get_market_time_service(db)
    return service.get_polling_interval()
