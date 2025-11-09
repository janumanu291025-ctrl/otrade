"""
Historical Data Service
=======================

Provides functions to fetch, cache, and replay historical market data
for paper trading simulation during off-market hours.

Features:
- Fetch historical data from broker API (Kite Connect)
- Cache data to database to avoid redundant API calls
- Replay historical ticks at configurable intervals
- Support for multiple symbols and timeframes
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable
import asyncio
import pytz
from sqlalchemy.orm import Session

from backend.broker.kite.client import KiteBroker

logger = logging.getLogger(__name__)

# IST timezone
IST = pytz.timezone('Asia/Kolkata')


class HistoricalDataService:
    """
    Service for fetching and replaying historical market data
    """
    
    def __init__(self, broker: KiteBroker, db: Session):
        """
        Initialize historical data service
        
        Args:
            broker: Broker client for fetching data
            db: Database session for caching
        """
        self.broker = broker
        self.db = db
        self.replay_active = False
        self.replay_task = None
    
    def fetch_historical_data(
        self,
        symbol: str,
        instrument_token: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "minute"
    ) -> List[Dict]:
        """
        Fetch historical data from broker API
        
        Args:
            symbol: Trading symbol (e.g., "NIFTY 50")
            instrument_token: Instrument token for API call
            start_date: Start date for historical data
            end_date: End date for historical data
            interval: Data interval (minute, 3minute, 5minute, 15minute, etc.)
        
        Returns:
            List of candles: [{timestamp, open, high, low, close, volume, ltp}, ...]
        """
        try:
            logger.info(f"Fetching historical data for {symbol} from {start_date} to {end_date}")
            
            # Fetch from broker API
            data = self.broker.get_historical_data(
                instrument_token=instrument_token,
                from_date=start_date,
                to_date=end_date,
                interval=interval
            )
            
            if not data:
                logger.warning(f"No historical data received for {symbol}")
                return []
            
            # Transform data to include LTP (use close price)
            transformed_data = []
            for candle in data:
                transformed_data.append({
                    'timestamp': candle['date'],
                    'open': float(candle['open']),
                    'high': float(candle['high']),
                    'low': float(candle['low']),
                    'close': float(candle['close']),
                    'ltp': float(candle['close']),  # Use close as LTP
                    'volume': int(candle.get('volume', 0))
                })
            
            logger.info(f"Fetched {len(transformed_data)} candles for {symbol}")
            
            # Cache to database
            self._cache_historical_data(symbol, instrument_token, transformed_data)
            
            return transformed_data
        
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            
            # Try to load from cache
            cached_data = self._load_from_cache(symbol, start_date, end_date)
            if cached_data:
                logger.info(f"Loaded {len(cached_data)} candles from cache for {symbol}")
                return cached_data
            
            raise
    
    def _cache_historical_data(
        self,
        symbol: str,
        instrument_token: str,
        data: List[Dict]
    ):
        """
        Cache historical data to database
        
        Args:
            symbol: Trading symbol
            instrument_token: Instrument token
            data: List of candles to cache
        """
        try:
            from backend.models import HistoricalData
            
            # Delete existing data for this symbol and date range
            if data:
                start_date = data[0]['timestamp']
                end_date = data[-1]['timestamp']
                
                self.db.query(HistoricalData).filter(
                    HistoricalData.symbol == symbol,
                    HistoricalData.timestamp >= start_date,
                    HistoricalData.timestamp <= end_date
                ).delete()
            
            # Insert new data
            for candle in data:
                hist_data = HistoricalData(
                    symbol=symbol,
                    instrument_token=instrument_token,
                    timestamp=candle['timestamp'],
                    open=candle['open'],
                    high=candle['high'],
                    low=candle['low'],
                    close=candle['close'],
                    ltp=candle['ltp'],
                    volume=candle['volume']
                )
                self.db.add(hist_data)
            
            self.db.commit()
            logger.info(f"Cached {len(data)} candles to database for {symbol}")
        
        except Exception as e:
            logger.error(f"Error caching historical data: {e}")
            self.db.rollback()
    
    def _load_from_cache(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """
        Load historical data from database cache
        
        Args:
            symbol: Trading symbol
            start_date: Start date
            end_date: End date
        
        Returns:
            List of cached candles
        """
        try:
            from backend.models import HistoricalData
            
            cached_data = self.db.query(HistoricalData).filter(
                HistoricalData.symbol == symbol,
                HistoricalData.timestamp >= start_date,
                HistoricalData.timestamp <= end_date
            ).order_by(HistoricalData.timestamp).all()
            
            if not cached_data:
                return []
            
            return [
                {
                    'timestamp': d.timestamp,
                    'open': float(d.open),
                    'high': float(d.high),
                    'low': float(d.low),
                    'close': float(d.close),
                    'ltp': float(d.ltp),
                    'volume': d.volume
                }
                for d in cached_data
            ]
        
        except Exception as e:
            logger.error(f"Error loading from cache: {e}")
            return []
    
    async def replay_historical_data(
        self,
        data: List[Dict],
        callback: Callable,
        interval: float = 1.0,
        speed_multiplier: float = 1.0
    ):
        """
        Replay historical data by emitting ticks at specified intervals
        
        Args:
            data: List of historical candles to replay
            callback: Async callback function to process each tick
                      Should accept (instrument_token: str, tick_data: Dict or float)
            interval: Base interval between ticks in seconds
            speed_multiplier: Speed multiplier (1.0 = real-time, 2.0 = 2x speed, etc.)
        """
        logger.info(f"replay_historical_data called with {len(data) if data else 0} candles")
        
        if not data:
            logger.warning("No data to replay")
            return
        
        self.replay_active = True
        actual_interval = interval / speed_multiplier
        
        logger.info(f"Starting replay of {len(data)} ticks at {actual_interval:.2f}s intervals (speed: {speed_multiplier}x)")
        
        try:
            for i, candle in enumerate(data):
                if not self.replay_active:
                    logger.info("Replay stopped")
                    break
                
                # Extract LTP and timestamp
                ltp = candle['ltp']
                timestamp = candle['timestamp']
                
                # Create tick data dict with timestamp
                tick_data = {
                    'last_price': ltp,
                    'timestamp': timestamp,
                    'open': candle.get('open', ltp),
                    'high': candle.get('high', ltp),
                    'low': candle.get('low', ltp),
                    'close': candle.get('close', ltp)
                }
                
                # Call the callback with the tick data including timestamp
                await callback("256265", tick_data)
                
                if (i + 1) % 50 == 0 or (i + 1) >= len(data) - 5:  # Log every 50 ticks AND last 5
                    logger.info(f"Replayed {i+1}/{len(data)} ticks: LTP={ltp:.2f} at {timestamp}")
                
                # Wait for next tick
                if i < len(data) - 1:
                    await asyncio.sleep(actual_interval)
            
            logger.info(f"Replay completed: {len(data)} ticks processed")
            if len(data) > 0:
                logger.info(f"Final timestamp: {data[-1]['timestamp']}")
        
        except asyncio.CancelledError:
            logger.info("Replay cancelled")
        except Exception as e:
            logger.error(f"Error during replay: {e}")
        finally:
            self.replay_active = False
    
    def stop_replay(self):
        """
        Stop ongoing replay
        """
        if self.replay_active:
            logger.info("Stopping replay...")
            self.replay_active = False
            
            if self.replay_task and not self.replay_task.done():
                self.replay_task.cancel()
    
    def get_recent_trading_day(self, days_back: int = 1) -> datetime:
        """
        Get a recent trading day for fetching historical data
        
        Args:
            days_back: Number of days to go back
        
        Returns:
            datetime: A recent trading day
        """
        from backend.services.market_calendar import is_trading_day
        
        now = datetime.now(IST)
        target_date = now - timedelta(days=days_back)
        
        # Find previous trading day
        while not is_trading_day(target_date):
            target_date = target_date - timedelta(days=1)
        
        return target_date
    
    def prepare_simulation_data(
        self,
        symbol: str = "NIFTY 50",
        instrument_token: str = "256265",
        days_back: int = 1,
        interval: str = "minute"
    ) -> List[Dict]:
        """
        Prepare data for simulation by fetching a recent trading day
        
        Args:
            symbol: Trading symbol
            instrument_token: Instrument token
            days_back: Number of days back to fetch (default: 1 = yesterday)
            interval: Data interval
        
        Returns:
            List of candles ready for replay
        """
        try:
            # Get a recent trading day
            target_date = self.get_recent_trading_day(days_back)
            
            # Set time range for market hours (9:15 AM to 3:30 PM)
            start_time = target_date.replace(hour=9, minute=15, second=0, microsecond=0)
            end_time = target_date.replace(hour=15, minute=30, second=0, microsecond=0)
            
            logger.info(f"Preparing simulation data for {target_date.date()}")
            
            # Fetch historical data
            data = self.fetch_historical_data(
                symbol=symbol,
                instrument_token=instrument_token,
                start_date=start_time,
                end_date=end_time,
                interval=interval
            )
            
            if not data:
                logger.warning(f"No data available for {target_date.date()}")
                return []
            
            logger.info(f"Prepared {len(data)} candles for simulation")
            if len(data) > 0:
                logger.info(f"Data range: {data[0]['timestamp']} to {data[-1]['timestamp']}")
            return data
        
        except Exception as e:
            logger.error(f"Error preparing simulation data: {e}")
            return []
    
    async def start_replay_simulation(
        self,
        callback: Callable,
        symbol: str = "NIFTY 50",
        instrument_token: str = "256265",
        days_back: int = 1,
        interval: str = "minute",
        replay_speed: float = 1.0
    ):
        """
        Start a complete replay simulation session
        
        Args:
            callback: Async callback for processing ticks
            symbol: Trading symbol
            instrument_token: Instrument token
            days_back: Number of days back to simulate
            interval: Data interval
            replay_speed: Speed multiplier for replay
        """
        try:
            # Prepare data
            data = self.prepare_simulation_data(
                symbol=symbol,
                instrument_token=instrument_token,
                days_back=days_back,
                interval=interval
            )
            
            if not data:
                raise Exception("No simulation data available")
            
            # Start replay
            self.replay_task = asyncio.create_task(
                self.replay_historical_data(
                    data=data,
                    callback=callback,
                    interval=1.0,
                    speed_multiplier=replay_speed
                )
            )
            
            await self.replay_task
        
        except Exception as e:
            logger.error(f"Error in replay simulation: {e}")
            raise
