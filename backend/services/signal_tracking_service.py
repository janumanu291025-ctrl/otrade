"""
Signal Tracking Service - Independent Market Signal Monitoring
===============================================================

This service continuously monitors market conditions and tracks trading signals
INDEPENDENTLY of the actual trading engine. It runs during market hours and:

1. Monitors NIFTY 50 price movements and trends
2. Detects crossover signals (7MA, 20MA, LBB)
3. Creates signal records in database when conditions are met
4. Tracks signal P&L based on price movements
5. Automatically closes signals when target/stoploss is hit

Key Features:
- Runs independently of trading engine status
- Does NOT place actual orders
- Purely for signal tracking and analysis
- Continues even if trading is disabled
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional
import pytz
from sqlalchemy.orm import Session
import asyncio
from collections import deque

from backend.models import TradingConfig, LiveTradingSignal
from backend.services.unified_broker_middleware import UnifiedBrokerMiddleware
from backend.services.market_calendar import is_market_open
from backend.services.trading_logic_service import TradingLogicService

logger = logging.getLogger(__name__)

IST = pytz.timezone('Asia/Kolkata')


class SignalTrackingService:
    """
    Independent signal tracking service that monitors market conditions
    and tracks signals regardless of trading engine status
    """
    
    def __init__(self, middleware: UnifiedBrokerMiddleware, db: Session, config: TradingConfig):
        """
        Initialize signal tracking service
        
        Args:
            middleware: Unified broker middleware for market data
            db: Database session
            config: Trading configuration to use for signal generation
        """
        self.middleware = middleware
        self.db = db
        self.config = config
        
        # Initialize trading logic service
        self.trading_logic = TradingLogicService()
        
        # Market data buffers
        self.major_candles = deque(maxlen=100)
        self.minor_candles = deque(maxlen=500)
        
        # Current market state
        self.nifty_ltp = 0.0
        self.major_trend = None
        self.minor_trend = None
        
        # Running state
        self.running = False
        self.monitor_task = None
        
        # Track recent signals to avoid duplicates
        self.recent_signals = {}  # key: f"{trigger}_{option_type}" -> timestamp
        self.signal_cooldown = 60  # seconds between same signal type
    
    async def start(self):
        """Start signal tracking service"""
        if self.running:
            logger.warning("Signal tracking already running")
            return
        
        self.running = True
        logger.info("Starting signal tracking service...")
        
        # Fetch initial data
        await self._fetch_initial_data()
        
        # Start monitoring task
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        
        logger.info("✓ Signal tracking service started")
    
    async def stop(self):
        """Stop signal tracking service"""
        logger.info("Stopping signal tracking service...")
        
        self.running = False
        
        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Signal tracking service stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop - runs every 5 seconds"""
        try:
            while self.running:
                # Only run during market hours
                if not is_market_open(self.db):
                    await asyncio.sleep(60)
                    continue
                
                # Update market data and check for signals
                await self._process_market_update()
                
                # Monitor open signals for price-based exits
                await self._monitor_open_signals()
                
                # Wait before next check
                await asyncio.sleep(5)
                
        except asyncio.CancelledError:
            logger.info("Signal monitoring loop cancelled")
        except Exception as e:
            logger.error(f"Error in signal monitoring loop: {e}")
    
    async def _fetch_initial_data(self):
        """Fetch initial historical data for indicators"""
        try:
            # Get NIFTY 50 historical data from broker
            # This would normally fetch candle data for both timeframes
            # For now, we'll start with empty buffers and build them from live data
            logger.info("Signal tracker initialized - will build candle data from live updates")
        except Exception as e:
            logger.error(f"Error fetching initial data: {e}")
    
    async def _process_market_update(self):
        """Process current market data and check for signal conditions"""
        try:
            # Get current NIFTY LTP
            nifty_data = self.middleware.get_ltp(["NSE:NIFTY 50"])
            if not nifty_data:
                return
            
            nifty_ltp = nifty_data.get("NSE:NIFTY 50", 0)
            if not nifty_ltp or nifty_ltp <= 0:
                return
            
            self.nifty_ltp = nifty_ltp
            timestamp = datetime.now(IST)
            
            # Update candle buffers
            self._update_candle_buffer(self.major_candles, timestamp, nifty_ltp, self.config.major_trend_timeframe)
            self._update_candle_buffer(self.minor_candles, timestamp, nifty_ltp, self.config.minor_trend_timeframe)
            
            # Calculate indicators
            major_indicators = self.trading_logic.calculate_indicators_from_deque(self.major_candles)
            minor_indicators = self.trading_logic.calculate_indicators_from_deque(self.minor_candles)
            
            if not major_indicators or not minor_indicators:
                return
            
            # Update trends
            self.major_trend = major_indicators.get('trend', 'neutral')
            self.minor_trend = minor_indicators.get('trend', 'neutral')
            
            # Check for crossover signals (need at least 2 candles)
            if len(self.minor_candles) >= 2:
                await self._check_crossover_signals(timestamp, nifty_ltp, major_indicators, minor_indicators)
                
        except Exception as e:
            logger.error(f"Error processing market update: {e}")
    
    def _update_candle_buffer(self, buffer: deque, timestamp: datetime, ltp: float, timeframe: str):
        """Update candle buffer with new tick"""
        # Convert timeframe to minutes
        timeframe_minutes = {
            '1min': 1,
            '3min': 3,
            '5min': 5,
            '15min': 15,
            '30min': 30,
            '1hour': 60
        }.get(timeframe, 1)
        
        # Round timestamp to timeframe boundary
        minutes = (timestamp.minute // timeframe_minutes) * timeframe_minutes
        candle_time = timestamp.replace(minute=minutes, second=0, microsecond=0)
        
        # Check if we need to create a new candle or update existing one
        if buffer and buffer[-1]['timestamp'] == candle_time:
            # Update existing candle
            candle = buffer[-1]
            candle['high'] = max(candle['high'], ltp)
            candle['low'] = min(candle['low'], ltp)
            candle['close'] = ltp
        else:
            # Create new candle
            buffer.append({
                'timestamp': candle_time,
                'open': ltp,
                'high': ltp,
                'low': ltp,
                'close': ltp
            })
    
    async def _check_crossover_signals(self, timestamp: datetime, nifty_ltp: float,
                                      major_ind: Dict, minor_ind: Dict):
        """Check for crossover signals and create signal records"""
        try:
            # Get last two candles for crossover detection
            prev_candle = self.minor_candles[-2]
            curr_candle = self.minor_candles[-1]
            
            # Detect crossovers
            crossovers = self.trading_logic.detect_crossovers_from_candles(
                prev_candle, curr_candle, minor_ind
            )
            
            if not crossovers:
                return
            
            logger.info(f"Detected {len(crossovers)} crossover(s) at {timestamp}")
            
            # Process each crossover
            for crossover in crossovers:
                await self._process_crossover_signal(timestamp, nifty_ltp, major_ind, minor_ind, crossover)
                
        except Exception as e:
            logger.error(f"Error checking crossover signals: {e}")
    
    async def _process_crossover_signal(self, timestamp: datetime, nifty_ltp: float,
                                       major_ind: Dict, minor_ind: Dict, crossover: Dict):
        """Process a crossover and create signal record if valid"""
        try:
            trigger = crossover['trigger']
            direction = crossover['direction']
            indicator_value = crossover['indicator_value']
            
            major_trend = major_ind.get('trend', 'neutral')
            minor_trend = minor_ind.get('trend', 'neutral')
            
            # Try both CE and PE to see which is valid
            for option_type in ['CE', 'PE']:
                should_trade, reason = self.trading_logic.evaluate_trade_decision(
                    major_trend=major_trend,
                    minor_trend=minor_trend,
                    option_type=option_type,
                    trigger=trigger,
                    crossover_direction=direction,
                    reverse_signals=self.config.reverse_signals
                )
                
                if should_trade:
                    # Check cooldown to avoid duplicate signals
                    signal_key = f"{trigger}_{option_type}"
                    last_signal_time = self.recent_signals.get(signal_key)
                    if last_signal_time:
                        time_diff = (timestamp - last_signal_time).total_seconds()
                        if time_diff < self.signal_cooldown:
                            logger.debug(f"Signal {signal_key} in cooldown ({time_diff:.0f}s)")
                            continue
                    
                    # Create signal record
                    await self._create_signal_record(
                        timestamp, nifty_ltp, option_type, trigger,
                        indicator_value, major_ind, minor_ind, reason
                    )
                    
                    # Update cooldown
                    self.recent_signals[signal_key] = timestamp
                    break
                    
        except Exception as e:
            logger.error(f"Error processing crossover signal: {e}")
    
    async def _create_signal_record(self, timestamp: datetime, nifty_ltp: float,
                                    option_type: str, trigger: str, indicator_value: float,
                                    major_ind: Dict, minor_ind: Dict, reason: str):
        """Create a signal tracking record in database"""
        try:
            # Create signal record (WITHOUT creating actual trade)
            signal = LiveTradingSignal(
                config_id=self.config.id,
                timestamp=timestamp,
                signal_date=timestamp,
                # Market data
                nifty_50_value=nifty_ltp,
                instrument=None,  # No actual contract selected
                instrument_token=None,
                # Trends
                major_trend=self.major_trend or 'neutral',
                minor_trend=self.minor_trend or 'neutral',
                # Major indicators
                major_ma7=major_ind.get('ma7'),
                major_ma20=major_ind.get('ma20'),
                major_lbb=major_ind.get('lbb'),
                major_ubb=major_ind.get('ubb'),
                # Minor indicators
                minor_ma7=minor_ind.get('ma7'),
                minor_ma20=minor_ind.get('ma20'),
                minor_lbb=minor_ind.get('lbb'),
                minor_ubb=minor_ind.get('ubb'),
                # Signal details
                signal_type='BUY',
                option_type=option_type,
                trigger=trigger,
                strike_price=None,  # Would be calculated if actually trading
                # Entry details (simulated)
                buy_price=None,  # Would need contract LTP
                quantity=None,
                # No trade link (signal only)
                trade_id=None,
                status='detected',  # Special status for tracking-only signals
                decision_reason=f"{option_type} signal detected on {trigger} @ {indicator_value:.2f} | {reason}"
            )
            
            self.db.add(signal)
            self.db.commit()
            
            logger.info(
                f"📊 Signal tracked: {option_type} on {trigger} @ {indicator_value:.2f} | "
                f"Nifty: {nifty_ltp:.2f} | {reason}"
            )
            
        except Exception as e:
            logger.error(f"Error creating signal record: {e}")
            self.db.rollback()
    
    async def _monitor_open_signals(self):
        """Monitor open signals and close them based on price movements"""
        try:
            # Get all open signals with contracts
            open_signals = self.db.query(LiveTradingSignal).filter(
                LiveTradingSignal.config_id == self.config.id,
                LiveTradingSignal.status == 'open',
                LiveTradingSignal.instrument_token.isnot(None),
                LiveTradingSignal.buy_price.isnot(None)
            ).all()
            
            if not open_signals:
                return
            
            # Get current prices
            instruments = [f"NFO:{signal.instrument}" for signal in open_signals if signal.instrument]
            if not instruments:
                return
            
            ltp_data = self.middleware.get_ltp(instruments)
            if not ltp_data:
                return
            
            # Check each signal
            for signal in open_signals:
                if not signal.instrument or not signal.buy_price:
                    continue
                
                instrument_key = f"NFO:{signal.instrument}"
                current_ltp = ltp_data.get(instrument_key, 0)
                
                if not current_ltp or current_ltp <= 0:
                    continue
                
                # Calculate P&L
                pnl = (current_ltp - signal.buy_price) * (signal.quantity or 0)
                pnl_pct = ((current_ltp - signal.buy_price) / signal.buy_price) * 100
                
                # Get trigger-specific target/stoploss
                trigger = signal.trigger
                if trigger == '7MA':
                    target_pct = self.config.buy_7ma_target_percentage
                    sl_pct = self.config.buy_7ma_stoploss_percentage
                elif trigger == '20MA':
                    target_pct = self.config.buy_20ma_target_percentage
                    sl_pct = self.config.buy_20ma_stoploss_percentage
                elif trigger == 'LBB':
                    target_pct = self.config.buy_lbb_target_percentage
                    sl_pct = self.config.buy_lbb_stoploss_percentage
                else:
                    continue
                
                # Calculate target and stoploss prices
                target_price = signal.buy_price * (1 + target_pct / 100)
                stoploss_price = signal.buy_price * (1 - sl_pct / 100)
                
                # Check if target or stoploss hit
                if current_ltp >= target_price:
                    signal.sell_time = datetime.now(IST)
                    signal.sell_price = current_ltp
                    signal.realized_pnl = pnl
                    signal.status = 'closed'
                    signal.exit_reason = 'target'
                    self.db.commit()
                    logger.info(f"📊 Signal target hit: {signal.instrument} P&L=₹{pnl:,.2f}")
                    
                elif current_ltp <= stoploss_price:
                    signal.sell_time = datetime.now(IST)
                    signal.sell_price = current_ltp
                    signal.realized_pnl = pnl
                    signal.status = 'closed'
                    signal.exit_reason = 'stoploss'
                    self.db.commit()
                    logger.info(f"📊 Signal stoploss hit: {signal.instrument} P&L=₹{pnl:,.2f}")
                    
        except Exception as e:
            logger.error(f"Error monitoring open signals: {e}")
            self.db.rollback()
