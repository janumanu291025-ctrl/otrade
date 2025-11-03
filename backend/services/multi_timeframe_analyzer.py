"""
Multi-Timeframe Analysis Service
Calculates indicators across all timeframes for NIFTY 50
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
from collections import deque
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class MultiTimeframeAnalyzer:
    """Analyzes NIFTY 50 across multiple timeframes with live updates"""
    
    # All supported timeframes
    TIMEFRAMES = [
        '15sec',   # 15 seconds
        '1min',    # 1 minute
        '3min',    # 3 minutes
        '5min',    # 5 minutes
        '10min',   # 10 minutes
        '15min',   # 15 minutes
        '30min',   # 30 minutes
        '1hour',   # 1 hour
        '2hour',   # 2 hours
        '4hour',   # 4 hours
        'day',     # Daily
        'week',    # Weekly
        'month',   # Monthly
        'quarter'  # Quarterly
    ]
    
    # Timeframe configurations (seconds, candle count to maintain)
    TIMEFRAME_CONFIG = {
        '15sec': {'seconds': 15, 'candles': 200},
        '1min': {'seconds': 60, 'candles': 200},
        '3min': {'seconds': 180, 'candles': 200},
        '5min': {'seconds': 300, 'candles': 200},
        '10min': {'seconds': 600, 'candles': 200},
        '15min': {'seconds': 900, 'candles': 200},
        '30min': {'seconds': 1800, 'candles': 200},
        '1hour': {'seconds': 3600, 'candles': 200},
        '2hour': {'seconds': 7200, 'candles': 200},
        '4hour': {'seconds': 14400, 'candles': 200},
        'day': {'seconds': 86400, 'candles': 200},
        'week': {'seconds': 604800, 'candles': 200},
        'month': {'seconds': 2592000, 'candles': 200},
        'quarter': {'seconds': 7776000, 'candles': 200}
    }
    
    def __init__(self, broker_client):
        self.broker = broker_client
        self.instrument_token = None  # NIFTY 50 token
        self.current_ltp = 0.0
        self.day_open = 0.0
        self.day_high = 0.0
        self.day_low = 0.0
        self.prev_close = 0.0
        
        # Store candle data for each timeframe
        # Structure: {timeframe: [{'timestamp', 'open', 'high', 'low', 'close', 'volume'}]}
        self.candles: Dict[str, deque] = {}
        
        # Current candle being built for each timeframe
        self.current_candles: Dict[str, Dict] = {}
        
        # Last update time for each timeframe
        self.last_update: Dict[str, datetime] = {}
        
        # Initialize data structures
        for tf in self.TIMEFRAMES:
            max_candles = self.TIMEFRAME_CONFIG[tf]['candles']
            self.candles[tf] = deque(maxlen=max_candles)
            self.current_candles[tf] = None
            self.last_update[tf] = None
        
        logger.info(f"MultiTimeframeAnalyzer initialized for {len(self.TIMEFRAMES)} timeframes")
    
    def set_instrument_token(self, token: int):
        """Set the NIFTY 50 instrument token"""
        self.instrument_token = token
        logger.info(f"NIFTY 50 instrument token set: {token}")
    
    def update_tick(self, tick_data: Dict):
        """
        Update with new tick data
        Called from websocket during market hours
        """
        try:
            # Extract price from tick
            # Note: Kite WebSocket sends index prices in correct format (not multiplied by 100)
            # Only equity prices are multiplied by 100
            ltp = tick_data.get('last_price', 0)
            
            self.current_ltp = ltp
            
            # Update OHLC data
            ohlc = tick_data.get('ohlc', {})
            if ohlc:
                self.day_open = ohlc.get('open', self.day_open)
                self.day_high = ohlc.get('high', self.day_high)
                self.day_low = ohlc.get('low', self.day_low)
            
            # Update day high/low if current price is outside range
            if ltp > 0:
                if self.day_high == 0 or ltp > self.day_high:
                    self.day_high = ltp
                if self.day_low == 0 or ltp < self.day_low:
                    self.day_low = ltp
            
            timestamp = datetime.now()
            
            # Update all timeframes
            for tf in self.TIMEFRAMES:
                self._update_timeframe_candle(tf, ltp, timestamp, tick_data)
        
        except Exception as e:
            logger.error(f"Error updating tick: {str(e)}", exc_info=True)
    
    def _update_timeframe_candle(self, timeframe: str, ltp: float, timestamp: datetime, tick_data: Dict):
        """Update candle for a specific timeframe"""
        try:
            config = self.TIMEFRAME_CONFIG[timeframe]
            interval_seconds = config['seconds']
            
            # Determine candle boundary based on timeframe
            candle_start = self._get_candle_start_time(timestamp, interval_seconds)
            
            # Check if we need to close current candle and start new one
            current = self.current_candles[timeframe]
            
            if current is None or current['timestamp'] != candle_start:
                # Close previous candle and add to history
                if current is not None:
                    self.candles[timeframe].append(current)
                
                # Start new candle
                self.current_candles[timeframe] = {
                    'timestamp': candle_start,
                    'open': ltp,
                    'high': ltp,
                    'low': ltp,
                    'close': ltp,
                    'volume': tick_data.get('volume', 0)
                }
            else:
                # Update current candle
                current['high'] = max(current['high'], ltp)
                current['low'] = min(current['low'], ltp)
                current['close'] = ltp
                current['volume'] = tick_data.get('volume', 0)
            
            self.last_update[timeframe] = timestamp
        
        except Exception as e:
            logger.error(f"Error updating {timeframe} candle: {str(e)}", exc_info=True)
    
    def _get_candle_start_time(self, timestamp: datetime, interval_seconds: int) -> datetime:
        """Get the start time of the candle for given timestamp and interval"""
        epoch = datetime(1970, 1, 1)
        total_seconds = int((timestamp - epoch).total_seconds())
        
        # Round down to nearest interval
        candle_seconds = (total_seconds // interval_seconds) * interval_seconds
        return epoch + timedelta(seconds=candle_seconds)
    
    def calculate_indicators(self, timeframe: str) -> Dict:
        """
        Calculate all indicators for a specific timeframe
        Returns: {
            'ma7': float,
            'ma20': float,
            'bb_upper': float,
            'bb_middle': float,
            'bb_lower': float,
            'trend': str,
            'signal': str
        }
        """
        try:
            # Get closed candles + current candle
            all_candles = list(self.candles[timeframe])
            if self.current_candles[timeframe]:
                all_candles.append(self.current_candles[timeframe])
            
            if len(all_candles) < 20:
                return {
                    'ma7': None,
                    'ma20': None,
                    'bb_upper': None,
                    'bb_middle': None,
                    'bb_lower': None,
                    'trend': 'insufficient_data',
                    'signal': 'none'
                }
            
            # Extract close prices
            closes = [c['close'] for c in all_candles]
            
            # Calculate 7-period MA
            ma7 = sum(closes[-7:]) / 7 if len(closes) >= 7 else None
            
            # Calculate 20-period MA
            ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else None
            
            # Calculate Bollinger Bands (20, 2)
            bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(closes, 20, 2.0)
            
            # Determine trend
            trend = 'uptrend' if ma7 and ma20 and ma7 > ma20 else 'downtrend'
            
            # Determine signal
            signal = 'none'
            current_price = closes[-1]
            if len(closes) >= 2:
                prev_price = closes[-2]
                
                # Check for MA7 crossover
                if ma7 and len(closes) >= 8:
                    prev_ma7 = sum(closes[-8:-1]) / 7
                    if prev_price >= prev_ma7 and current_price < ma7:
                        signal = 'cross_below_ma7'
                    elif prev_price <= prev_ma7 and current_price > ma7:
                        signal = 'cross_above_ma7'
                
                # Check for MA20 crossover
                if ma20 and len(closes) >= 21:
                    prev_ma20 = sum(closes[-21:-1]) / 20
                    if prev_price >= prev_ma20 and current_price < ma20:
                        signal = 'cross_below_ma20'
                    elif prev_price <= prev_ma20 and current_price > ma20:
                        signal = 'cross_above_ma20'
                
                # Check for BB crossover
                if bb_lower and prev_price >= bb_lower and current_price < bb_lower:
                    signal = 'cross_below_bb_lower'
                if bb_upper and prev_price <= bb_upper and current_price > bb_upper:
                    signal = 'cross_above_bb_upper'
            
            return {
                'ma7': round(ma7, 2) if ma7 else None,
                'ma20': round(ma20, 2) if ma20 else None,
                'bb_upper': round(bb_upper, 2) if bb_upper else None,
                'bb_middle': round(bb_middle, 2) if bb_middle else None,
                'bb_lower': round(bb_lower, 2) if bb_lower else None,
                'trend': trend,
                'signal': signal
            }
        
        except Exception as e:
            logger.error(f"Error calculating indicators for {timeframe}: {str(e)}", exc_info=True)
            return {
                'ma7': None,
                'ma20': None,
                'bb_upper': None,
                'bb_middle': None,
                'bb_lower': None,
                'trend': 'error',
                'signal': 'none'
            }
    
    def _calculate_bollinger_bands(self, data: List[float], period: int = 20, std_dev: float = 2.0):
        """Calculate Bollinger Bands"""
        if len(data) < period:
            return None, None, None
        
        recent_data = data[-period:]
        middle = sum(recent_data) / period
        
        # Calculate standard deviation
        variance = sum((x - middle) ** 2 for x in recent_data) / period
        std = variance ** 0.5
        
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        
        return upper, middle, lower
    
    def get_all_timeframe_analysis(self) -> Dict:
        """
        Get analysis for all timeframes
        Returns: {
            'ltp': float,
            'day_open': float,
            'day_high': float,
            'day_low': float,
            'prev_close': float,
            'timestamp': str,
            'timeframes': {
                '15sec': {...indicators...},
                '1min': {...indicators...},
                ...
            }
        }
        """
        try:
            analysis = {
                'ltp': round(self.current_ltp, 2),
                'day_open': round(self.day_open, 2),
                'day_high': round(self.day_high, 2),
                'day_low': round(self.day_low, 2),
                'prev_close': round(self.prev_close, 2),
                'timestamp': datetime.now().isoformat(),
                'timeframes': {}
            }
            
            for tf in self.TIMEFRAMES:
                indicators = self.calculate_indicators(tf)
                analysis['timeframes'][tf] = indicators
            
            return analysis
        
        except Exception as e:
            logger.error(f"Error getting all timeframe analysis: {str(e)}", exc_info=True)
            return {
                'ltp': self.current_ltp,
                'day_open': self.day_open,
                'day_high': self.day_high,
                'day_low': self.day_low,
                'prev_close': self.prev_close,
                'timestamp': datetime.now().isoformat(),
                'timeframes': {},
                'error': str(e)
            }
    
    async def fetch_historical_data(self):
        """Fetch historical data for all timeframes to initialize candles"""
        try:
            if not self.instrument_token:
                logger.warning("Instrument token not set, cannot fetch historical data")
                return
            
            logger.info("Fetching historical data for all timeframes...")
            
            # Fetch today's OHLC data for day open/high/low
            try:
                # Fetch last 5 days to ensure we get previous close
                from_date = datetime.now() - timedelta(days=5)
                to_date = datetime.now()
                
                day_data = self.broker.get_historical_data(
                    instrument_token=self.instrument_token,
                    from_date=from_date,
                    to_date=to_date,
                    interval='day'
                )
                
                if day_data and len(day_data) > 0:
                    today = day_data[-1]
                    self.day_open = today.get('open', 0)
                    self.day_high = today.get('high', 0)
                    self.day_low = today.get('low', 0)
                    
                    # Get previous day's close
                    if len(day_data) > 1:
                        self.prev_close = day_data[-2].get('close', 0)
                    else:
                        # If only one day, try to get close from that day
                        self.prev_close = today.get('close', 0)
                    
                    logger.info(f"Day OHLC: Open={self.day_open}, High={self.day_high}, Low={self.day_low}, PrevClose={self.prev_close}")
                else:
                    logger.warning("No daily data returned from broker")
            except Exception as e:
                logger.error(f"Error fetching day OHLC: {str(e)}", exc_info=True)
            
            # For each timeframe, fetch appropriate historical data
            for tf in self.TIMEFRAMES:
                try:
                    config = self.TIMEFRAME_CONFIG[tf]
                    interval_seconds = config['seconds']
                    candles_needed = config['candles']
                    
                    # Calculate how far back we need to go
                    lookback_seconds = interval_seconds * candles_needed
                    from_date = datetime.now() - timedelta(seconds=lookback_seconds * 1.5)  # Extra buffer
                    to_date = datetime.now()
                    
                    # Map our timeframe to Kite API format
                    kite_interval = self._map_to_kite_interval(tf)
                    
                    if kite_interval:
                        # Fetch historical data
                        historical_data = self.broker.get_historical_data(
                            instrument_token=self.instrument_token,
                            from_date=from_date,
                            to_date=to_date,
                            interval=kite_interval
                        )
                        
                        if historical_data:
                            # Convert to our candle format
                            for candle in historical_data:
                                self.candles[tf].append({
                                    'timestamp': candle['date'],
                                    'open': candle['open'],
                                    'high': candle['high'],
                                    'low': candle['low'],
                                    'close': candle['close'],
                                    'volume': candle['volume']
                                })
                            
                            logger.info(f"Loaded {len(historical_data)} candles for {tf}")
                    
                except Exception as e:
                    logger.error(f"Error fetching historical data for {tf}: {str(e)}")
            
            logger.info("Historical data fetch completed")
        
        except Exception as e:
            logger.error(f"Error in fetch_historical_data: {str(e)}", exc_info=True)
    
    def _map_to_kite_interval(self, timeframe: str) -> Optional[str]:
        """Map our timeframe format to Kite API interval format"""
        mapping = {
            '15sec': None,  # Not supported by Kite, will use tick aggregation
            '1min': 'minute',
            '3min': '3minute',
            '5min': '5minute',
            '10min': '10minute',
            '15min': '15minute',
            '30min': '30minute',
            '1hour': '60minute',
            '2hour': None,  # Aggregate from 1 hour
            '4hour': None,  # Aggregate from 1 hour
            'day': 'day',
            'week': None,  # Aggregate from day
            'month': None,  # Aggregate from day
            'quarter': None  # Aggregate from day
        }
        return mapping.get(timeframe)
