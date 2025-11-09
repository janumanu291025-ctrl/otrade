"""
Paper Trading Engine - Real-time Trading with Live Market Data
================================================================

This module manages paper trading with live market data:
1. Receives live LTP updates via webhook
2. Calculates indicators in real-time
3. Generates buy/sell signals based on backtest logic
4. Manages paper trades with target/stoploss
5. Provides live updates to GUI

Uses unified BrokerDataService for consistent data access.

"""
import logging
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import pytz
from sqlalchemy.orm import Session
import asyncio
from collections import deque

from backend.models import (
    TradingConfig, PaperTrade, PaperTradingMarketData, 
    PaperTradingAlert, Instrument
)
from backend.services.broker_data_service import BrokerDataService
from backend.services.market_calendar import is_market_open, get_market_status
from backend.services.historical_data import HistoricalDataService
from backend.services.trading_logic_service import TradingLogicService

logger = logging.getLogger(__name__)


class PaperTradingEngine:
    """
    Real-time paper trading engine with support for live and historical simulation modes
    """
    
    def __init__(self, broker_data_service: BrokerDataService, db: Optional[Session] = None, mode: str = "auto", selected_date: Optional[str] = None):
        """
        Initialize paper trading engine
        
        Args:
            broker_data_service: Unified broker data service
            db: Database session (optional, used only for initialization, engine creates its own session)
            mode: Trading mode - "live", "historical", or "auto" (default)
                  "auto" automatically switches based on market hours
        """
        self.broker_data = broker_data_service
        # Create our own database session for long-running operations
        from backend.database import SessionLocal
        self.db = SessionLocal()
        self.config: Optional[TradingConfig] = None
        self.running = False
        
        # Initialize unified trading logic service
        self.trading_logic = TradingLogicService()
        
        # Trading mode
        self.mode = mode  # "live", "historical", or "auto"
        self.selected_date = selected_date  # Specific date for historical simulation
        self.current_mode = None  # Actual active mode
        self.historical_service = None
        self.replay_task = None  # Store the replay task reference
        
        # Live data buffers (using deque for efficient FIFO operations)
        self.major_candles = deque(maxlen=100)  # Last 100 major timeframe candles
        self.minor_candles = deque(maxlen=500)  # Last 500 minor timeframe candles
        
        # Current market data
        self.nifty_ltp = 0.0
        self.positions_ltp = {}  # instrument_token: ltp
        self.current_timestamp = None  # Track current simulation timestamp
        
        # Trend tracking
        self.major_trend = None
        self.major_trend_changed_at = None
        self.minor_trend = None
        self.minor_trend_changed_at = None
        
        # Cache for option historical data (instrument_token: list of historical candles)
        self.option_historical_cache: Dict[str, List[Dict]] = {}
        
        # Active positions tracking
        self.active_positions: Dict[str, PaperTrade] = {}  # key: f"{option_type}_{trigger}"
        
        # Last check time for square off
        self.last_check_time = None
    
    def load_config(self, config_id: int) -> bool:
        """Load paper trading configuration"""
        try:
            # Use our own database session to load the config
            self.config = self.db.query(TradingConfig).filter(
                TradingConfig.id == config_id
            ).first()
            
            if not self.config:
                logger.error(f"Config {config_id} not found")
                return False
            
            logger.info(f"Loaded config: {self.config.name}")
            return True
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return False
    
    async def start(self):
        """Start paper trading engine"""
        if not self.config:
            raise Exception("Config not loaded")
        
        # Validate config still exists in database
        try:
            config_check = self.db.query(TradingConfig).filter(
                TradingConfig.id == self.config.id
            ).first()
            if not config_check:
                raise Exception(f"Config {self.config.id} does not exist in database")
        except Exception as e:
            logger.error(f"Config validation failed: {e}")
            raise Exception(f"Cannot start paper trading: {e}")
        
        # Determine trading mode first
        logger.info("Determining trading mode...")
        self._determine_mode()
        logger.info(f"Trading mode determined: {self.current_mode}")
        
        # Clear old paper trades ONLY for historical mode (selected_date specified)
        if self.current_mode == "historical" and self.selected_date:
            logger.info(f"Historical mode detected for date {self.selected_date} - clearing old paper trades")
            self._clear_paper_trades_for_date()
            logger.info("Old paper trades cleared")
        elif self.current_mode == "live":
            logger.info("Live mode detected - preserving existing paper trades")
        
        self.running = True
        self.config.status = "running"
        self.config.started_at = datetime.now()
        self.db.commit()
        
        # Load open positions
        await self._load_open_positions()
        
        # Fetch initial historical data for indicators
        await self._fetch_initial_data()
        
        # Start historical simulation if in historical mode
        logger.info(f"Checking if should start historical simulation: current_mode={self.current_mode}")
        if self.current_mode == "historical":
            logger.info("Starting historical simulation...")
            await self._start_historical_simulation()
            logger.info("Historical simulation started")
        else:
            logger.info("Not starting historical simulation (mode is not historical)")
        
        mode_msg = f"Paper trading started in {self.current_mode.upper()} mode"
        self._add_alert("info", mode_msg)
        logger.info(mode_msg)
    
    async def stop(self):
        """Stop paper trading engine"""
        self.running = False
        
        # Wait for replay task to complete gracefully FIRST (includes square-off)
        # Do NOT stop the historical service yet - it's needed for square-off
        if self.replay_task and not self.replay_task.done():
            try:
                logger.info("Waiting for historical replay to complete (includes square-off)...")
                await asyncio.wait_for(self.replay_task, timeout=5.0)
                logger.info("Replay task completed successfully")
            except asyncio.TimeoutError:
                logger.warning("Replay task timeout - cancelling")
                self.replay_task.cancel()
                try:
                    await self.replay_task
                except asyncio.CancelledError:
                    pass
            except asyncio.CancelledError:
                logger.info("Replay task was cancelled")
            except Exception as e:
                logger.error(f"Error waiting for replay task: {e}")
        
        # NOW stop historical simulation if active
        if self.historical_service:
            self.historical_service.stop_replay()
            self.historical_service = None
        
        self.config.status = "stopped"
        self.config.started_at = datetime.now()
        self.db.commit()
        
        # Add alert before closing session
        self._add_alert("info", "Paper trading stopped")
        logger.info("Paper trading stopped")
        
        # Close our database session
        self.db.close()
    
    async def pause(self):
        """Pause paper trading (no new entries)"""
        self.config.status = "paused"
        self.db.commit()
        self._add_alert("info", "Paper trading paused - No new entries")
    
    async def resume(self):
        """Resume paper trading"""
        self.config.status = "running"
        self.db.commit()
        self._add_alert("info", "Paper trading resumed")
    
    def suspend_ce(self, suspend: bool):
        """Suspend/resume CE entries"""
        self.config.suspend_ce = suspend
        self.db.commit()
        msg = "CE entries suspended" if suspend else "CE entries resumed"
        self._add_alert("info", msg)
    
    def suspend_pe(self, suspend: bool):
        """Suspend/resume PE entries"""
        self.config.suspend_pe = suspend
        self.db.commit()
        msg = "PE entries suspended" if suspend else "PE entries resumed"
        self._add_alert("info", msg)
    
    async def process_ltp_update(self, instrument_token: str, ltp: float):
        """
        Process live LTP update from webhook or historical replay
        
        Args:
            instrument_token: Instrument token (e.g., "256265" for NIFTY 50)
            ltp: Last traded price (can be float or dict with 'last_price' and 'timestamp')
        """
        if not self.running:
            return
        
        try:
            # Update NIFTY LTP
            if instrument_token == "256265":  # NIFTY 50
                # Handle both float and dict formats
                if isinstance(ltp, dict):
                    self.nifty_ltp = ltp.get('last_price', 0.0)
                    await self._process_nifty_update(ltp)
                else:
                    self.nifty_ltp = ltp
                    await self._process_nifty_update(ltp)
            else:
                # Update position LTP
                if isinstance(ltp, dict):
                    ltp_value = ltp.get('last_price', 0.0)
                else:
                    ltp_value = ltp
                self.positions_ltp[instrument_token] = ltp_value
                await self._process_position_update(instrument_token, ltp_value)
        
        except RuntimeError as e:
            # Config was deleted - stop engine
            logger.error(f"Engine stopped due to missing config: {e}")
            self.running = False
        except Exception as e:
            logger.error(f"Error processing LTP update: {e}")
            # For non-config-related errors, add alert but don't stop
            try:
                self._add_alert("error", f"Error processing market data: {str(e)}")
            except Exception as alert_error:
                logger.error(f"Could not add alert after LTP error: {alert_error}")
    
    async def _process_nifty_update(self, tick_data):
        """Process NIFTY 50 tick data and generate trading signals."""
        now = datetime.now(pytz.timezone('Asia/Kolkata'))
        
        # In historical mode, use the simulation timestamp if provided
        if self.is_historical_mode() and isinstance(tick_data, dict):
            timestamp = tick_data.get('timestamp')
            if timestamp:
                if isinstance(timestamp, str):
                    now = pd.to_datetime(timestamp).tz_localize('Asia/Kolkata')
                elif isinstance(timestamp, datetime):
                    if timestamp.tzinfo is None:
                        now = timestamp.replace(tzinfo=pytz.timezone('Asia/Kolkata'))
                    else:
                        now = timestamp
        
        self.current_timestamp = now
        
        # Update NIFTY LTP - handle both dict and float inputs
        if isinstance(tick_data, dict):
            self.nifty_ltp = tick_data.get('last_price', 0.0)
        else:
            self.nifty_ltp = tick_data
        
        # Debug logging for late times
        if now.hour == 15 and now.minute >= 25:
            logger.info(f"Late time NIFTY update: LTP={self.nifty_ltp:.2f} at {now}")
        else:
            logger.debug(f"Processing NIFTY update: LTP={self.nifty_ltp:.2f} at {now}")
        
        # Update candle buffers
        self._update_candle_buffer(self.major_candles, now, self.nifty_ltp, self.config.major_trend_timeframe)
        self._update_candle_buffer(self.minor_candles, now, self.nifty_ltp, self.config.minor_trend_timeframe)
        
        # Calculate indicators
        major_indicators = self._calculate_indicators(self.major_candles)
        minor_indicators = self._calculate_indicators(self.minor_candles)
        
        logger.debug(f"Indicators - Major: {major_indicators.get('trend', 'N/A')}, Minor: {minor_indicators.get('trend', 'N/A')}")
        
        # Store market data
        try:
            self._store_market_data(now, self.nifty_ltp, major_indicators, minor_indicators)
        except RuntimeError as e:
            # Config was deleted, engine is already stopped by _store_market_data
            logger.error(f"Stopping NIFTY update processing: {e}")
            return
        
        # Check for trading signals
        await self._check_signals(now, self.nifty_ltp, major_indicators, minor_indicators)
        
        # Check exits and square off
        await self._check_exits(now, self.nifty_ltp, major_indicators, minor_indicators)
        await self._check_square_off(now)
    
    async def _process_position_update(self, instrument_token: str, ltp: float):
        """Process position LTP update"""
        try:
            # Find open trades with this instrument
            open_trades = self.db.query(PaperTrade).filter(
                PaperTrade.config_id == self.config.id,
                PaperTrade.instrument_token == instrument_token,
                PaperTrade.status == "open"
            ).all()
            
            for trade in open_trades:
                # Update current price and unrealized P&L
                trade.current_price = ltp
                trade.unrealized_pnl = (ltp - trade.entry_price) * trade.quantity
                
                # Update max profit/loss
                if trade.unrealized_pnl > trade.max_profit:
                    trade.max_profit = trade.unrealized_pnl
                if trade.unrealized_pnl < trade.max_loss:
                    trade.max_loss = trade.unrealized_pnl
                
                # Check target and stoploss
                if ltp >= trade.target_price:
                    await self._exit_trade(trade, ltp, "target")
                elif ltp <= trade.stoploss_price:
                    await self._exit_trade(trade, ltp, "stoploss")
            
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            error_msg = str(e)
            # Check if it's a foreign key constraint error (config deleted)
            if "FOREIGN KEY constraint failed" in error_msg or "foreign key" in error_msg.lower():
                logger.error(f"Config {self.config.id} no longer exists - stopping paper trading engine")
                self.running = False
                raise RuntimeError(f"Config {self.config.id} was deleted - stopping engine")
            else:
                logger.error(f"Error processing position update: {e}")
                raise
    
    def _update_candle_buffer(self, buffer: deque, timestamp: datetime, ltp: float, timeframe: str):
        """Update candle buffer with new tick"""
        # Convert timeframe to minutes
        tf_minutes = self._timeframe_to_minutes(timeframe)
        
        # Round timestamp to timeframe
        candle_time = timestamp.replace(second=0, microsecond=0)
        candle_time = candle_time.replace(minute=(candle_time.minute // tf_minutes) * tf_minutes)
        
        # Check if we need to create new candle or update existing
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
    
    def _calculate_indicators(self, candles: deque) -> Dict:
        """
        Calculate indicators from candle buffer
        Uses unified TradingLogicService
        """
        # Update service parameters from config
        if self.config:
            self.trading_logic.ma_short_period = self.config.ma_short_period
            self.trading_logic.ma_long_period = self.config.ma_long_period
        
        return self.trading_logic.calculate_indicators_from_deque(candles)
    
    def _store_market_data(self, timestamp: datetime, nifty_ltp: float, 
                          major_ind: Dict, minor_ind: Dict):
        """Store market data snapshot and track trend changes"""
        try:
            # Check for major trend change
            major_trend = major_ind.get('trend')
            if major_trend and major_trend != self.major_trend:
                self.major_trend = major_trend
                self.major_trend_changed_at = timestamp
                logger.info(f"Major trend changed to {major_trend} at {timestamp}")
            
            # Check for minor trend change
            minor_trend = minor_ind.get('trend')
            if minor_trend and minor_trend != self.minor_trend:
                self.minor_trend = minor_trend
                self.minor_trend_changed_at = timestamp
                logger.info(f"Minor trend changed to {minor_trend} at {timestamp}")
            
            data = PaperTradingMarketData(
                config_id=self.config.id,
                timestamp=timestamp,
                nifty_ltp=nifty_ltp,
                major_ma7=major_ind.get('ma7'),
                major_ma20=major_ind.get('ma20'),
                major_lbb=major_ind.get('lbb'),
                major_ubb=major_ind.get('ubb'),
                major_trend=major_trend,
                major_trend_changed_at=self.major_trend_changed_at,
                minor_ma7=minor_ind.get('ma7'),
                minor_ma20=minor_ind.get('ma20'),
                minor_lbb=minor_ind.get('lbb'),
                minor_ubb=minor_ind.get('ubb'),
                minor_trend=minor_trend,
                minor_trend_changed_at=self.minor_trend_changed_at,
                positions_ltp=self.positions_ltp
            )
            self.db.add(data)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            error_msg = str(e)
            # Check if it's a foreign key constraint error (config deleted)
            if "FOREIGN KEY constraint failed" in error_msg or "foreign key" in error_msg.lower():
                logger.error(f"Config {self.config.id} no longer exists - stopping paper trading engine")
                self.running = False
                raise RuntimeError(f"Config {self.config.id} was deleted - stopping engine")
            else:
                logger.error(f"Error storing market data: {e}")
                raise
    
    async def _check_signals(self, timestamp: datetime, nifty_ltp: float,
                            major_ind: Dict, minor_ind: Dict):
        """Check for trading signals based on crossovers"""
        # Only check signals if we have enough candle data
        if len(self.minor_candles) < 2:
            logger.debug(f"Not enough minor candles for signal detection: {len(self.minor_candles)}")
            return
        
        # Get last two candles for crossover detection
        prev_candle = self.minor_candles[-2]  # Previous candle
        curr_candle = self.minor_candles[-1]  # Current candle
        
        # Check for crossovers
        crossovers = self._detect_crossovers(prev_candle, curr_candle, minor_ind)
        
        if crossovers:
            logger.info(f"Detected {len(crossovers)} crossover(s) at {timestamp}: {[c['type'] for c in crossovers]}")
        
        if not crossovers:
            return
        
        # Apply trend-based logic for each crossover
        for crossover in crossovers:
            await self._process_crossover_signal(timestamp, nifty_ltp, major_ind, minor_ind, crossover)
    
    def _detect_crossovers(self, prev_candle: Dict, curr_candle: Dict, indicators: Dict) -> List[Dict]:
        """
        Detect price crossovers with indicators
        Uses unified TradingLogicService
        """
        return self.trading_logic.detect_crossovers_from_candles(prev_candle, curr_candle, indicators)
    
    async def _process_crossover_signal(self, timestamp: datetime, nifty_ltp: float,
                                       major_ind: Dict, minor_ind: Dict, crossover: Dict):
        """
        Process a crossover signal with trend-based logic
        Uses unified TradingLogicService for decision making
        """
        trigger = crossover['trigger']
        direction = crossover['direction']
        indicator_value = crossover['indicator_value']
        
        # Get current trends
        major_trend = major_ind.get('trend', 'neutral')
        minor_trend = minor_ind.get('trend', 'neutral')
        
        logger.info(f"Processing crossover: {trigger} {direction} @ {indicator_value:.2f} | Major: {major_trend}, Minor: {minor_trend}")
        
        # Try both CE and PE to see which one is valid
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
                logger.info(f"✅ Trade signal: {reason}")
                await self._execute_entry(
                    timestamp, nifty_ltp, major_trend, trigger,
                    self._get_target_pct(trigger),
                    self._get_stoploss_pct(trigger),
                    indicator_value, option_type, major_ind, minor_ind
                )
                break  # Only execute one trade per crossover
            else:
                logger.debug(f"❌ Trade skipped ({option_type}): {reason}")
    
    def _get_target_pct(self, trigger: str) -> float:
        """Get target percentage for trigger"""
        if trigger == '7ma':
            return self.config.buy_7ma_target_percentage
        elif trigger == '20ma':
            return self.config.buy_20ma_target_percentage
        elif trigger == 'lbb':
            return self.config.buy_lbb_target_percentage
        return 2.5  # Default
    
    def _get_stoploss_pct(self, trigger: str) -> float:
        """Get stoploss percentage for trigger"""
        if trigger == '7ma':
            return self.config.buy_7ma_stoploss_percentage
        elif trigger == '20ma':
            return self.config.buy_20ma_stoploss_percentage
        elif trigger == 'lbb':
            return self.config.buy_lbb_stoploss_percentage
        return 90.0  # Default
    
    def _generate_entry_comment(self, trigger: str, indicator_value: float, 
                                option_type: str, major_trend: str, minor_trend: str,
                                major_ind: Dict, minor_ind: Dict) -> str:
        """
        Generate entry comment explaining why the trade was triggered
        
        Args:
            trigger: Entry trigger (7ma, 20ma, lbb)
            indicator_value: Value at crossover
            option_type: CE or PE
            major_trend: Major timeframe trend
            minor_trend: Minor timeframe trend
            major_ind: Major timeframe indicators
            minor_ind: Minor timeframe indicators
        
        Returns:
            Human-readable explanation of trade entry
        """
        trigger_name = {
            '7ma': '7-period Moving Average',
            '20ma': '20-period Moving Average',
            'lbb': 'Lower Bollinger Band'
        }.get(trigger, trigger.upper())
        
        trend_desc = f"Major: {major_trend.title()}, Minor: {minor_trend.title()}"
        
        # Determine crossover direction based on option type and trend
        if option_type == 'CE':
            direction = "crossed below"
            strategy = "support"
        else:  # PE
            direction = "crossed above"
            strategy = "resistance"
        
        # Build comment
        comment = (
            f"{option_type} entry triggered by price {direction} {trigger_name} "
            f"at ₹{indicator_value:.2f}. "
            f"Trading as {strategy} in {trend_desc} market. "
        )
        
        # Add MA context
        major_7ma = major_ind.get('ma7')
        major_20ma = major_ind.get('ma20')
        if major_7ma and major_20ma:
            if major_7ma > major_20ma:
                comment += "Major trend: 7MA > 20MA (bullish). "
            else:
                comment += "Major trend: 7MA < 20MA (bearish). "
        
        return comment
    
    async def _execute_entry(self, timestamp: datetime, nifty_ltp: float, trend: str,
                            trigger: str, target_pct: float, sl_pct: float, 
                            indicator_value: float, option_type: str = None,
                            major_ind: Dict = None, minor_ind: Dict = None):
        """Execute trade entry"""
        # Default to empty dicts if not provided
        if major_ind is None:
            major_ind = {}
        if minor_ind is None:
            minor_ind = {}
        
        # Determine option type based on trend if not provided
        if option_type is None:
            if trend == 'uptrend':
                option_type = 'CE' if not self.config.reverse_signals else 'PE'
            else:
                option_type = 'PE' if not self.config.reverse_signals else 'CE'
        
        logger.info(f"Attempting entry: {option_type} on {trigger} @ {indicator_value:.2f}")
        
        # Check if suspended
        if option_type == 'CE' and self.config.suspend_ce:
            logger.info("CE entries suspended - Skipping")
            return
        if option_type == 'PE' and self.config.suspend_pe:
            logger.info("PE entries suspended - Skipping")
            return
        
        # Check if position already exists
        position_key = f"{option_type}_{trigger}"
        if position_key in self.active_positions:
            logger.info(f"Position already exists for {position_key} - Skipping")
            return  # Position already active
        
        # Find contract
        logger.debug(f"Finding contract: {option_type} near strike {nifty_ltp}")
        contract = await self._find_contract(nifty_ltp, option_type, timestamp)
        if not contract:
            msg = f"No contract found for {option_type} near {nifty_ltp}"
            self._add_alert("error", msg)
            logger.warning(msg)
            return
        
        logger.info(f"Found contract: {contract['tradingsymbol']} (strike: {contract['strike']})")
        
        # Pre-fetch historical data for this option contract (in historical mode)
        if self.is_historical_mode():
            await self._prefetch_option_data(contract['instrument_token'], timestamp)
        
        # Get contract LTP
        ltp = await self._get_contract_ltp(contract['instrument_token'])
        if not ltp:
            msg = f"Failed to get LTP for {contract['tradingsymbol']}"
            self._add_alert("error", msg)
            logger.warning(msg)
            return
        
        logger.info(f"Contract LTP: ₹{ltp:.2f}")
        
        # Calculate quantity using formula: max_lots = available_fund / (ltp * lot_size), then round down
        capital_per_trade = self.config.current_capital * (self.config.capital_allocation_pct / 100)
        
        if ltp <= 0 or self.config.lot_size <= 0:
            msg = f"Invalid parameters for quantity calculation: LTP={ltp}, lot_size={self.config.lot_size}"
            self._add_alert("error", msg)
            logger.error(msg)
            return
            
        max_lots = int(capital_per_trade / (ltp * self.config.lot_size))
        quantity = max_lots * self.config.lot_size
        
        if max_lots < 1:
            msg = f"Insufficient capital for {contract['tradingsymbol']}: Required ₹{ltp * self.config.lot_size:.2f} per lot, Available ₹{capital_per_trade:.2f}"
            self._add_alert("info", msg)
            logger.info(msg)
            return
        
        logger.info(f"Calculated quantity: {max_lots} lots x {self.config.lot_size} = {quantity} units (capital: ₹{capital_per_trade:.2f})")
        
        # Calculate target and stoploss
        target_price = ltp * (1 + target_pct / 100)
        stoploss_price = ltp * (1 - sl_pct / 100)
        
        # Get current NIFTY price
        current_nifty_ltp = await self._get_current_nifty_ltp()
        
        # Calculate cash after buy
        cash_after_buy = self.config.current_capital - (ltp * quantity)
        
        # Generate entry comment explaining why this trade happened
        entry_comment = self._generate_entry_comment(
            trigger, indicator_value, option_type, 
            self.major_trend, self.minor_trend,
            major_ind, minor_ind
        )
        
        # Create trade
        trade = PaperTrade(
            config_id=self.config.id,
            date=timestamp.date(),
            instrument=contract['tradingsymbol'],
            instrument_token=contract['instrument_token'],
            option_type=option_type,
            strike=contract['strike'],
            entry_time=timestamp,
            entry_price=ltp,
            entry_trigger=trigger,
            crossover_value=indicator_value,
            quantity=quantity,
            target_price=target_price,
            stoploss_price=stoploss_price,
            current_price=ltp,
            status="open",
            # Market context
            nifty_price=current_nifty_ltp,
            cash_after_buy=cash_after_buy,
            major_trend=self.major_trend,
            minor_trend=self.minor_trend,
            major_7ma=major_ind.get('ma7', 0),
            major_20ma=major_ind.get('ma20', 0),
            minor_7ma=minor_ind.get('ma7', 0),
            minor_20ma=minor_ind.get('ma20', 0),
            max_drawdown_pct=0.0,
            entry_comment=entry_comment,
            highest_price=ltp,  # Initialize with entry price
            lowest_price=ltp    # Initialize with entry price
        )
        
        self.db.add(trade)
        self.db.commit()
        self.db.refresh(trade)
        
        # Add to active positions
        self.active_positions[position_key] = trade
        
        # Update capital
        self.config.current_capital -= (ltp * quantity)
        self.db.commit()
        
        # Alert
        msg = (f"🟢 BUY {trade.instrument} @ ₹{ltp:.2f} | "
               f"Qty: {quantity} | Target: ₹{target_price:.2f} | "
               f"SL: ₹{stoploss_price:.2f} | Trigger: {trigger.upper()}")
        self._add_alert("entry", msg, trade.id)
        logger.info(msg)
    
    async def _check_exits(self, timestamp: datetime, nifty_ltp: float,
                          major_ind: Dict, minor_ind: Dict):
        """Check exit conditions for open positions"""
        # Get all open trades
        open_trades = self.db.query(PaperTrade).filter(
            PaperTrade.config_id == self.config.id,
            PaperTrade.status == "open"
        ).all()
        
        if not open_trades:
            return
        
        # Update position prices and check for exits
        for trade in open_trades:
            # Get current LTP for the option
            ltp = await self._get_contract_ltp(trade.instrument_token)
            
            if not ltp:
                logger.debug(f"Could not get LTP for {trade.instrument}, skipping exit check")
                continue
            
            # Update current price and unrealized P&L
            trade.current_price = ltp
            trade.unrealized_pnl = (ltp - trade.entry_price) * trade.quantity
            
            # Update highest and lowest prices
            if trade.highest_price is None or ltp > trade.highest_price:
                trade.highest_price = ltp
            if trade.lowest_price is None or ltp < trade.lowest_price:
                trade.lowest_price = ltp
            
            # Update max profit/loss
            if trade.unrealized_pnl > trade.max_profit:
                trade.max_profit = trade.unrealized_pnl
            if trade.unrealized_pnl < trade.max_loss:
                trade.max_loss = trade.unrealized_pnl
            
            # Calculate max drawdown percentage
            if trade.entry_price > 0:
                current_dd_pct = ((ltp - trade.entry_price) / trade.entry_price) * 100
                if trade.max_drawdown_pct is None or current_dd_pct < trade.max_drawdown_pct:
                    trade.max_drawdown_pct = current_dd_pct
            
            # Check target and stoploss
            if ltp >= trade.target_price:
                logger.info(f"Target hit for {trade.instrument}: LTP={ltp:.2f} >= Target={trade.target_price:.2f}")
                await self._exit_trade(trade, ltp, "target")
            elif ltp <= trade.stoploss_price:
                logger.info(f"Stoploss hit for {trade.instrument}: LTP={ltp:.2f} <= SL={trade.stoploss_price:.2f}")
                await self._exit_trade(trade, ltp, "stoploss")
        
        self.db.commit()
    
    async def _exit_trade(self, trade: PaperTrade, exit_price: float, reason: str):
        """Exit trade"""
        # Use current_timestamp if available, otherwise use current time
        exit_time = self.current_timestamp if self.current_timestamp else datetime.now(pytz.timezone('Asia/Kolkata'))
        
        trade.exit_time = exit_time
        trade.exit_price = exit_price
        trade.exit_reason = reason
        trade.pnl = (exit_price - trade.entry_price) * trade.quantity
        trade.pnl_percentage = ((exit_price - trade.entry_price) / trade.entry_price) * 100
        trade.status = "closed"
        
        # Update capital
        self.config.current_capital += (exit_price * trade.quantity)
        
        # Remove from active positions
        position_key = f"{trade.option_type}_{trade.entry_trigger}"
        if position_key in self.active_positions:
            del self.active_positions[position_key]
        
        self.db.commit()
        
        # Alert
        pnl_emoji = "🟢" if trade.pnl >= 0 else "🔴"
        msg = (f"{pnl_emoji} SELL {trade.instrument} @ ₹{exit_price:.2f} | "
               f"P&L: ₹{trade.pnl:,.2f} ({trade.pnl_percentage:+.2f}%) | "
               f"Reason: {reason.upper()}")
        self._add_alert("exit", msg, trade.id)
        logger.info(msg)
    
    async def _check_square_off(self, timestamp: datetime):
        """Check if it's time to square off all positions"""
        if not self.config.square_off_enabled:
            return
        
        current_time = timestamp.time()
        square_off_time = datetime.strptime(self.config.square_off_time, "%H:%M").time()
        
        # Initialize last_check_time if not set
        if self.last_check_time is None:
            self.last_check_time = current_time
            logger.info(f"Square-off check initialized: current={current_time}, target={square_off_time}")
            return
        
        # Debug logging for time near square-off
        if current_time.hour == 15 and current_time.minute >= 25:
            logger.debug(f"Near square-off: last={self.last_check_time}, current={current_time}, target={square_off_time}")
        
        # Check if we've crossed square off time (comparing times only)
        if self.last_check_time < square_off_time <= current_time:
            logger.info(f"✅ Square-off time reached: {square_off_time} (current: {current_time})")
            await self._square_off_all()
        
        self.last_check_time = current_time
    
    async def _square_off_all(self):
        """Square off all open positions at market price"""
        open_trades = self.db.query(PaperTrade).filter(
            PaperTrade.config_id == self.config.id,
            PaperTrade.status == "open"
        ).all()
        
        if not open_trades:
            return
        
        logger.info(f"Executing square-off for {len(open_trades)} open positions")
        
        for trade in open_trades:
            # Get current market price for the position
            ltp = await self._get_contract_ltp(trade.instrument_token)
            
            # Use current_price if available, otherwise use entry price as fallback
            exit_price = ltp if ltp else (trade.current_price if trade.current_price else trade.entry_price)
            
            logger.info(f"Square-off: {trade.instrument} @ ₹{exit_price:.2f}")
            await self._exit_trade(trade, exit_price, "square_off")
        
        self._add_alert("info", f"Day end square off: {len(open_trades)} positions closed")
    
    async def _load_open_positions(self):
        """Load open positions from database"""
        open_trades = self.db.query(PaperTrade).filter(
            PaperTrade.config_id == self.config.id,
            PaperTrade.status == "open"
        ).all()
        
        for trade in open_trades:
            position_key = f"{trade.option_type}_{trade.entry_trigger}"
            self.active_positions[position_key] = trade
        
        logger.info(f"Loaded {len(open_trades)} open positions")
    
    async def _fetch_initial_data(self):
        """Fetch initial historical data for indicator calculation"""
        try:
            # Determine the reference date based on mode
            if self.is_historical_mode() and self.selected_date:
                # In historical mode, use the selected date as reference
                try:
                    reference_date = datetime.strptime(self.selected_date, '%Y-%m-%d')
                    reference_date = reference_date.replace(hour=15, minute=30)  # End of trading day
                    logger.info(f"Using selected date as reference: {reference_date.date()}")
                except ValueError:
                    logger.warning(f"Invalid selected_date format: {self.selected_date}, using current date")
                    reference_date = datetime.now()
            else:
                # In live mode or auto mode, use current date
                reference_date = datetime.now()
            
            # Fetch last 5 trading days of data for better indicator calculation
            to_date = reference_date
            from_date = reference_date - timedelta(days=7)  # Go back 7 calendar days to ensure we get 5 trading days
            
            logger.info(f"Fetching NIFTY 50 historical data from {from_date.date()} to {to_date.date()}")
            
            # Get middleware instance for centralized historical data access
            from backend.services.middleware_helper import get_middleware_instance
            middleware = get_middleware_instance(self.db)
            
            # Fetch major timeframe
            major_interval = self._map_interval(self.config.major_trend_timeframe)
            major_data = middleware.get_historical_data(
                instrument_token=256265,  # NIFTY 50
                from_date=from_date,
                to_date=to_date,
                interval=major_interval,
                use_cache=True
            )
            
            # Fetch minor timeframe  
            minor_interval = self._map_interval(self.config.minor_trend_timeframe)
            minor_data = middleware.get_historical_data(
                instrument_token=256265,
                from_date=from_date,
                to_date=to_date,
                interval=minor_interval,
                use_cache=True
            )
            
            # Populate buffers
            if major_data:
                for row in major_data:
                    self.major_candles.append({
                        'timestamp': row['date'],
                        'open': row['open'],
                        'high': row['high'],
                        'low': row['low'],
                        'close': row['close']
                    })
            
            if minor_data:
                for row in minor_data:
                    self.minor_candles.append({
                        'timestamp': row['date'],
                        'open': row['open'],
                        'high': row['high'],
                        'low': row['low'],
                        'close': row['close']
                    })
            
            logger.info(f"Loaded {len(self.major_candles)} major and {len(self.minor_candles)} minor candles for indicator calculation")
        
        except Exception as e:
            logger.error(f"Error fetching initial data: {e}")
    
    async def _find_contract(self, nifty_spot: float, option_type: str, 
                            expiry_date: datetime) -> Optional[Dict]:
        """Find appropriate option contract"""
        import math
        
        # Calculate strike
        strike_gap = self.config.min_strike_gap
        round_to = self.config.strike_round_to
        
        # Apply proper rounding based on option type
        if option_type == 'CE':
            # Call - Round UP then add gap
            base_strike = math.ceil(nifty_spot / round_to) * round_to
            strike = base_strike + strike_gap
        else:
            # Put - Round DOWN then subtract gap
            base_strike = math.floor(nifty_spot / round_to) * round_to
            strike = base_strike - strike_gap
        
        # Find contract in database
        contract = self.db.query(Instrument).filter(
            Instrument.tradingsymbol.like(f"NIFTY%{option_type}"),
            Instrument.strike == strike,
            Instrument.instrument_type == option_type
        ).order_by(Instrument.expiry).first()
        
        if contract:
            return {
                'instrument_token': contract.instrument_token,
                'tradingsymbol': contract.tradingsymbol,
                'strike': contract.strike
            }
        
        return None
    
    async def _get_contract_ltp(self, instrument_token: str) -> Optional[float]:
        """Get LTP for contract"""
        try:
            # In historical mode, fetch real historical option data from broker API
            if self.is_historical_mode():
                return await self._get_historical_option_ltp(instrument_token)
            
            # Live mode: get real quotes
            ltp_data = self.broker_data.get_ltp([instrument_token], use_cache=False)
            if ltp_data and instrument_token in ltp_data:
                return ltp_data[instrument_token]
        except Exception as e:
            logger.error(f"Error getting LTP for {instrument_token}: {e}")
        return None
    
    async def _prefetch_option_data(self, instrument_token: str, timestamp: datetime):
        """
        Pre-fetch historical data for an option contract for the simulation day
        
        This ensures data is cached before we try to get LTP during entry/exit checks
        
        Args:
            instrument_token: Option contract instrument token
            timestamp: Current simulation timestamp
        """
        try:
            if not timestamp:
                return
            
            # Define the date range for the simulation day
            from_date = timestamp.replace(hour=9, minute=15, second=0, microsecond=0)
            to_date = timestamp.replace(hour=15, minute=30, second=0, microsecond=0)
            
            # Get contract details for logging
            contract = self.db.query(Instrument).filter(
                Instrument.instrument_token == instrument_token
            ).first()
            
            contract_name = contract.tradingsymbol if contract else instrument_token
            
            logger.info(f"Pre-fetching historical data for {contract_name} (full day {from_date.date()})")
            
            # Fetch and cache the data
            historical_data = self.broker_data.get_historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval="minute",
                use_cache=True
            )
            
            if historical_data:
                logger.info(f"✓ Pre-fetched {len(historical_data)} minute candles for {contract_name}")
            else:
                logger.warning(f"⚠️ No historical data available for {contract_name} on {from_date.date()}")
                
        except Exception as e:
            logger.error(f"Error pre-fetching option data for {instrument_token}: {e}")
    
    async def _get_historical_option_ltp(self, instrument_token: str) -> Optional[float]:
        """
        Get historical LTP for option contract from broker API
        
        Fetches real historical data for the current simulation timestamp
        """
        try:
            if not self.current_timestamp:
                logger.warning("No current timestamp available for historical option data")
                return None
            
            # Get contract details
            contract = self.db.query(Instrument).filter(
                Instrument.instrument_token == instrument_token
            ).first()
            
            if not contract:
                logger.warning(f"Contract not found for token {instrument_token}")
                return None
            
            # Fetch historical data for the current day (no caching to avoid stale data)
            from_date = self.current_timestamp.replace(hour=9, minute=15, second=0, microsecond=0)
            to_date = self.current_timestamp.replace(hour=15, minute=30, second=0, microsecond=0)
            
            historical_data = self.broker_data.get_historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval="minute",
                use_cache=True  # Cache is day-specific, so OK to cache
            )
            
            if historical_data:
                # Find the candle closest to (but not after) current timestamp
                # Ensure both timestamps are timezone-aware for comparison
                import pytz
                IST = pytz.timezone('Asia/Kolkata')
                
                # Make current_timestamp timezone-aware if it isn't
                current_ts = self.current_timestamp
                if current_ts.tzinfo is None:
                    current_ts = IST.localize(current_ts)
                
                valid_candles = []
                for c in historical_data:
                    candle_dt = pd.to_datetime(c['date'])
                    # Make candle datetime timezone-aware
                    if candle_dt.tz is None:
                        candle_dt = IST.localize(candle_dt)
                    
                    if candle_dt <= current_ts:
                        valid_candles.append(c)
                
                if not valid_candles:
                    logger.debug(f"No historical data available before {current_ts} for {contract.tradingsymbol}")
                    return None
                
                # Get the most recent candle before current timestamp
                closest_candle = max(valid_candles, 
                                   key=lambda x: IST.localize(pd.to_datetime(x['date'])) if pd.to_datetime(x['date']).tz is None else pd.to_datetime(x['date']))
                ltp = closest_candle.get('close', 0.0)
                
                candle_time = pd.to_datetime(closest_candle['date'])
                if candle_time.tz is None:
                    candle_time = IST.localize(candle_time)
                logger.debug(f"Historical LTP for {contract.tradingsymbol}: ₹{ltp:.2f} at {candle_time} (simulation time: {current_ts})")
                return ltp
            else:
                logger.warning(f"No historical data available for {instrument_token}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching historical option LTP for {instrument_token}: {e}")
            return None
    
    async def _get_current_nifty_ltp(self) -> float:
        """Get current NIFTY 50 LTP"""
        # Return the LTP we already have from process_ltp_update
        return self.nifty_ltp if self.nifty_ltp else 0.0
    
    def _clear_paper_trades_for_date(self):
        """
        Clear paper trades for historical replay.
        This ensures a clean slate when replaying a specific date.
        Only called for historical mode, NOT for live trading.
        """
        try:
            # Delete all paper trades for this config
            deleted_trades = self.db.query(PaperTrade).filter(
                PaperTrade.config_id == self.config.id
            ).delete()
            
            # Delete all alerts
            deleted_alerts = self.db.query(PaperTradingAlert).filter(
                PaperTradingAlert.config_id == self.config.id
            ).delete()
            
            # Delete all market data
            deleted_market_data = self.db.query(PaperTradingMarketData).filter(
                PaperTradingMarketData.config_id == self.config.id
            ).delete()
            
            # Reset capital to initial
            self.config.current_capital = self.config.initial_capital
            
            self.db.commit()
            
            logger.info(f"Cleared {deleted_trades} trades, {deleted_alerts} alerts, {deleted_market_data} market data records for historical replay")
        
        except Exception as e:
            logger.error(f"Error clearing paper trades: {e}")
            self.db.rollback()
    
    def _add_alert(self, alert_type: str, message: str, trade_id: Optional[int] = None):
        """Add alert to database"""
        try:
            alert = PaperTradingAlert(
                config_id=self.config.id,
                alert_type=alert_type,
                message=message,
                trade_id=trade_id
            )
            self.db.add(alert)
            self.db.commit()
        except Exception as e:
            logger.error(f"Error adding alert: {e}")
            self.db.rollback()
            # Re-raise if it's a foreign key error (config doesn't exist)
            if "FOREIGN KEY constraint failed" in str(e):
                logger.error(f"Config {self.config.id} does not exist - stopping paper trading")
                # Don't re-raise, just log - the engine should stop gracefully
            else:
                raise
    
    def _timeframe_to_minutes(self, timeframe: str) -> int:
        """Convert timeframe string to minutes"""
        if timeframe.endswith('min'):
            return int(timeframe[:-3])
        elif timeframe == '1hour':
            return 60
        elif timeframe == 'day':
            return 1440
        return 1
    
    def _map_interval(self, timeframe: str) -> str:
        """Map timeframe to Kite interval"""
        mapping = {
            "1min": "minute",
            "3min": "3minute",
            "5min": "5minute",
            "10min": "10minute",
            "15min": "15minute",
            "30min": "30minute",
            "60min": "60minute",
            "day": "day"
        }
        return mapping.get(timeframe, "minute")
    
    def _determine_mode(self):
        """
        Determine the trading mode based on configuration and market hours
        
        Sets self.current_mode to either "live" or "historical"
        """
        if self.mode == "live":
            self.current_mode = "live"
            logger.info("Forced LIVE mode")
        elif self.mode == "historical":
            self.current_mode = "historical"
            logger.info("Forced HISTORICAL mode")
        else:  # auto mode
            # Check market status from exchange calendar
            market_status = get_market_status()
            if market_status['is_open']:
                self.current_mode = "live"
                logger.info("AUTO mode: Market is open - Using LIVE data")
            else:
                self.current_mode = "historical"
                logger.info(f"AUTO mode: Market is closed - Using HISTORICAL simulation")
            logger.info(f"Next trading day: {market_status.get('next_trading_day', 'Unknown')}")
    
    async def _start_historical_simulation(self):
        """
        Start historical data simulation
        
        Fetches historical data and replays it to simulate real-time trading
        """
        try:
            # Initialize historical data service with middleware
            # Get middleware instance
            from backend.services.middleware_helper import get_middleware_instance
            middleware = get_middleware_instance(self.db)
            
            self.historical_service = HistoricalDataService(middleware)
            
            # Determine days_back based on selected_date
            days_back = 1  # Default to yesterday
            if self.selected_date:
                try:
                    selected_dt = datetime.strptime(self.selected_date, '%Y-%m-%d').date()
                    today = datetime.now().date()
                    days_back = (today - selected_dt).days
                    if days_back < 0:
                        logger.warning(f"Selected date {selected_dt} is in the future, using yesterday")
                        days_back = 1
                    elif days_back == 0:
                        logger.warning("Selected date is today, using yesterday")
                        days_back = 1
                except ValueError as e:
                    logger.error(f"Invalid selected_date format: {self.selected_date}, using yesterday")
                    days_back = 1
            
            logger.info(f"Preparing historical simulation data for {days_back} days back...")
            
            logger.info(f"Creating historical service and starting replay task...")
            # Start replay in background and store the task reference
            self.replay_task = asyncio.create_task(
                self._run_historical_replay_with_completion(days_back)
            )
            logger.info(f"Replay task created: {self.replay_task}")
            
            date_desc = f" ({days_back} days ago)" if days_back > 1 else " (yesterday)"
            self._add_alert("info", f"Historical simulation started - Replaying market data{date_desc}")
            logger.info(f"Historical simulation replay started for {days_back} days back")
        
        except Exception as e:
            error_msg = f"Failed to start historical simulation: {str(e)}"
            logger.error(error_msg)
            self._add_alert("error", error_msg)
            
            # Fall back to live mode
            self.current_mode = "live"
            self._add_alert("info", "Falling back to LIVE mode due to simulation error")
    
    async def _run_historical_replay_with_completion(self, days_back: int):
        """
        Run historical replay and perform final square-off when complete
        """
        try:
            # Run the replay
            await self.historical_service.start_replay_simulation(
                callback=self.process_ltp_update,
                symbol="NIFTY 50",
                instrument_token="256265",
                days_back=days_back,
                interval="minute",
                replay_speed=self.config.replay_speed
            )
            
            logger.info("Historical replay completed - performing final square-off check")
            
            # Perform final square-off for any remaining open positions
            if self.current_timestamp:
                logger.info(f"Final timestamp: {self.current_timestamp}")
                await self._square_off_all()
            
        except Exception as e:
            logger.error(f"Error in historical replay: {e}")
            import traceback
            traceback.print_exc()
    
    def get_current_mode(self) -> str:
        """
        Get the current trading mode
        
        Returns:
            str: "live" or "historical"
        """
        return self.current_mode if self.current_mode else "unknown"
    
    def is_historical_mode(self) -> bool:
        """
        Check if engine is running in historical simulation mode
        
        Returns:
            bool: True if historical mode, False otherwise
        """
        return self.current_mode == "historical"
