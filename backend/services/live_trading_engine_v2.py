"""
Live Trading Engine V2 - Real Money Trading with Real-time Market Data
========================================================================

This module manages live trading with real broker funds:
1. Fetches real cash balance from broker
2. Enforces market hours for trading operations
3. Places actual orders through broker API
4. Tracks orders via webhook postbacks
5. Manages positions with real funds
6. Implements crash recovery with state persistence
7. Handles token expiry with auto-pause

Key Differences from Paper Trading:
- Uses real broker funds (fetched via API)
- Orders tracked via webhook postbacks (not simulated)
- Market hours strictly enforced (no historical mode)
- State persisted for crash recovery
- Token expiry handling with re-authentication

"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pytz
from sqlalchemy.orm import Session
import asyncio
from collections import deque
import json

from backend.models import (
    TradingConfig, LiveTrade, LiveTradingState, LiveTradingMarketData,
    LiveTradingAlert, LiveTradingSignal, Instrument
)
from backend.broker.base import TokenExpiredError
from backend.services.unified_broker_middleware import UnifiedBrokerMiddleware
from backend.services.market_calendar import is_market_open, get_market_status
from backend.services.trading_logic_service import TradingLogicService

logger = logging.getLogger(__name__)

IST = pytz.timezone('Asia/Kolkata')


class LiveTradingEngineV2:
    """
    Real money live trading engine with market hours enforcement and crash recovery
    """
    
    def __init__(self, middleware: UnifiedBrokerMiddleware, db: Optional[Session] = None):
        """
        Initialize live trading engine
        
        Args:
            middleware: Unified broker middleware
            db: Database session (optional, used only for initialization, engine creates its own session)
        """
        self.middleware = middleware
        
        # Create our own database session for long-running operations
        from backend.database import SessionLocal
        self.db = SessionLocal()
        
        self.config: Optional[TradingConfig] = None
        self.running = False
        self.paused = False
        
        # Initialize unified trading logic service
        self.trading_logic = TradingLogicService()
        
        # Fund management
        self.available_funds = 0.0
        self.allocated_funds = 0.0
        
        # Live data buffers (using deque for efficient FIFO operations)
        self.major_candles = deque(maxlen=100)  # Last 100 major timeframe candles
        self.minor_candles = deque(maxlen=500)  # Last 500 minor timeframe candles
        
        # Current market data
        self.nifty_ltp = 0.0
        self.positions_ltp = {}  # instrument_token: ltp (DEPRECATED - use ltp_processor)
        self.current_timestamp = None
        
        # Trend tracking
        self.major_trend = None
        self.major_trend_changed_at = None
        self.minor_trend = None
        self.minor_trend_changed_at = None
        
        # Active positions tracking
        self.active_positions: Dict[str, LiveTrade] = {}  # key: f"{option_type}_{trigger}"
        
        # Contract expiry filter
        self.contract_expiry: Optional[str] = None  # Format: "YYYY-MM-DD" or "YYMMDD"
        
        # State tracking for crash recovery
        self.state_id: Optional[int] = None
        
        # Last check time for square off
        self.last_check_time = None
        
        # Position monitoring task
        self.position_monitor_task: Optional[asyncio.Task] = None
        
        # Auto-subscription tracking for webhook
        self.subscribed_instruments: set = set()  # Track all subscribed instrument tokens
        
        logger.info("LiveTradingEngineV2 initialized with unified middleware")
    
    def load_config(self, config_id: int) -> bool:
        """
        Load live trading configuration
        
        Args:
            config_id: Trading config ID
            
        Returns:
            bool: True if config loaded successfully
        """
        try:
            # Use our own database session to load the config
            self.config = self.db.query(TradingConfig).filter(
                TradingConfig.id == config_id
            ).first()
            
            if not self.config:
                logger.error(f"Config {config_id} not found")
                return False
            
            logger.info(f"Loaded config: {self.config.name}")
            
            # Note: Broker funds will be fetched when engine starts (async)
            # Don't fetch here as this is a sync function
            
            return True
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return False
    
    async def _fetch_broker_funds(self):
        """Fetch available cash balance from broker"""
        try:
            logger.info("Fetching broker funds...")
            
            # Use middleware to get funds/margins
            funds = self.middleware.get_funds(use_cache=False)
            
            if funds and 'equity' in funds:
                available_cash = funds['equity'].get('available', {}).get('live_balance', 0.0)
                self.available_funds = available_cash
                logger.info(f"Available funds: ₹{self.available_funds:,.2f}")
            else:
                logger.warning("Could not fetch broker funds - using 0")
                self.available_funds = 0.0
                
        except TokenExpiredError:
            logger.error("Token expired while fetching broker funds")
            await self._handle_token_expiry()
            raise
        except Exception as e:
            logger.error(f"Error fetching broker funds: {e}")
            self.available_funds = 0.0
    
    async def start(self, contract_expiry: Optional[str] = None):
        """
        Start live trading engine
        
        Args:
            contract_expiry: Optional contract expiry filter (format: "YYYY-MM-DD" or "YYMMDD")
        """
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
            raise Exception(f"Cannot start live trading: {e}")
        
        # Check market hours for trading - STRICT enforcement
        market_status = get_market_status()
        if not market_status.get('is_open', False):
            reason = market_status.get('reason', 'Market is closed')
            logger.error(f"Cannot start live trading: {reason}")
            raise Exception(f"Cannot start live trading: {reason}")
        
        # Set contract expiry filter
        self.contract_expiry = contract_expiry
        if contract_expiry:
            logger.info(f"Contract expiry filter set to: {contract_expiry}")
        
        # Try to recover from previous state
        await self._load_state()
        
        # Refresh broker funds (Phase 8: with token expiry handling)
        await self._fetch_broker_funds()
        
        self.running = True
        self.paused = False
        self.config.status = "running"
        self.config.started_at = datetime.now(IST)
        self.db.commit()
        
        # Load open positions
        await self._load_open_positions()
        
        # Phase 7: Reconcile with broker after crash recovery
        state = self.db.query(LiveTradingState).filter(
            LiveTradingState.id == self.state_id
        ).first()
        if state and state.recovery_count and state.recovery_count > 0:
            logger.info("Running broker reconciliation after crash recovery...")
            reconciliation_report = await self._reconcile_broker_positions()
            
            # Log reconciliation summary
            if reconciliation_report.get('success'):
                if reconciliation_report.get('discrepancies_found'):
                    logger.warning(
                        f"⚠️ Reconciliation found discrepancies - engine auto-paused. "
                        f"Review report before resuming."
                    )
                else:
                    logger.info("✅ Reconciliation passed - no discrepancies found")
        
        # Fetch initial historical data for indicators
        await self._fetch_initial_data()
        
        # Start position monitoring task
        self.position_monitor_task = asyncio.create_task(self._monitor_positions())
        
        # Auto-subscribe to instruments for webhook (Phase: Auto-subscription)
        await self._auto_subscribe_instruments()
        
        # Middleware already handles WebSocket connection management based on market hours
        logger.info("✓ Middleware managing WebSocket connections based on market hours")
        
        # Save initial state
        await self._save_state()
        
        self._add_alert("info", f"Live trading started (Funds: ₹{self.available_funds:,.2f})")
        logger.info(f"✓ Live trading started with ₹{self.available_funds:,.2f} available funds")
    
    async def stop(self):
        """Stop live trading engine and square off all positions"""
        logger.info("Stopping live trading engine...")
        
        self.running = False
        
        # Cancel position monitoring task
        if self.position_monitor_task and not self.position_monitor_task.done():
            self.position_monitor_task.cancel()
            try:
                await self.position_monitor_task
            except asyncio.CancelledError:
                pass
        
        # Square off all open positions
        await self._square_off_all_positions()
        
        # Update config status
        self.config.status = "stopped"
        self.config.started_at = datetime.now(IST)
        self.db.commit()
        
        # Save final state
        await self._save_state()
        
        # Add alert before closing session
        self._add_alert("info", "Live trading stopped - all positions squared off")
        logger.info("Live trading stopped")
        
        # Close our database session
        self.db.close()
    
    async def pause(self):
        """Pause live trading (no new entries, existing positions continue)"""
        self.paused = True
        self.config.status = "paused"
        self.db.commit()
        
        await self._save_state()
        
        self._add_alert("warning", "Live trading paused - No new entries")
        logger.info("Live trading paused")
    
    async def resume(self):
        """Resume live trading"""
        # Check market hours before resuming
        market_status = get_market_status()
        if not market_status.get('is_open', False):
            reason = market_status.get('reason', 'Market is closed')
            logger.error(f"Cannot resume live trading: {reason}")
            raise Exception(f"Cannot resume: {reason}")
        
        self.paused = False
        self.config.status = "running"
        self.db.commit()
        
        await self._save_state()
        
        self._add_alert("info", "Live trading resumed")
        logger.info("Live trading resumed")
    
    async def _handle_token_expiry(self):
        """
        Handle token expiry by auto-pausing engine and notifying frontend
        
        Called when TokenExpiredError is caught from broker API.
        This ensures safe pause until user re-authenticates.
        """
        logger.error("🔒 Token expired - auto-pausing live trading engine")
        
        # Auto-pause engine
        self.paused = True
        self.config.status = "paused"
        self.db.commit()
        
        await self._save_state()
        
        # Add critical alert
        self._add_alert(
            "critical",
            "Token expired. Trading paused. Please re-login to continue.",
            extra_data={"requires_action": True, "action_type": "re_authenticate"}
        )
        
        # TODO Phase 8: Send WebSocket notification to frontend
        # This will trigger the login popup modal in the UI
        # websocket_manager.broadcast({
        #     "type": "token_expired",
        #     "message": "Your session has expired. Please re-login to continue trading.",
        #     "timestamp": datetime.now(IST).isoformat()
        # })
        
        logger.info("Engine auto-paused. Waiting for user re-authentication.")
    
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
    
    async def _load_state(self):
        """Load previous state for crash recovery"""
        try:
            state = self.db.query(LiveTradingState).filter(
                LiveTradingState.config_id == self.config.id
            ).first()
            
            if state:
                self.state_id = state.id
                
                # Check if we need to recover
                if state.engine_status == "running":
                    logger.warning("Detected previous crash - loading state for recovery")
                    
                    # Load funds
                    self.available_funds = state.available_funds or 0.0
                    self.allocated_funds = state.allocated_funds or 0.0
                    
                    # Load trends
                    self.major_trend = state.major_trend
                    self.minor_trend = state.minor_trend
                    self.nifty_ltp = state.last_nifty_ltp or 0.0
                    
                    # Auto-pause after recovery
                    self.paused = True
                    state.recovery_count = (state.recovery_count or 0) + 1
                    state.last_recovery_at = datetime.now(IST)
                    
                    self._add_alert("warning", f"Recovered from crash (recovery #{state.recovery_count}) - Auto-paused")
                    logger.info(f"State recovered - recovery count: {state.recovery_count}")
                else:
                    logger.info("Previous session ended cleanly")
                
                # Update state
                state.engine_status = "running"
                state.last_active_at = datetime.now(IST)
                self.db.commit()
            else:
                # Create new state record
                state = LiveTradingState(
                    config_id=self.config.id,
                    engine_status="running",
                    last_active_at=datetime.now(IST),
                    available_funds=self.available_funds,
                    allocated_funds=0.0,
                    open_position_count=0
                )
                self.db.add(state)
                self.db.commit()
                self.state_id = state.id
                logger.info("New state record created")
                
        except Exception as e:
            logger.error(f"Error loading state: {e}")
    
    async def _save_state(self):
        """Save current state for crash recovery"""
        try:
            if not self.state_id:
                return
            
            state = self.db.query(LiveTradingState).filter(
                LiveTradingState.id == self.state_id
            ).first()
            
            if state:
                # Update state
                state.last_active_at = datetime.now(IST)
                state.engine_status = "running" if self.running else "stopped"
                state.available_funds = self.available_funds
                state.allocated_funds = self.allocated_funds
                state.open_position_count = len(self.active_positions)
                state.last_nifty_ltp = self.nifty_ltp
                state.major_trend = self.major_trend
                state.minor_trend = self.minor_trend
                
                if self.major_trend_changed_at:
                    state.major_trend_changed_at = self.major_trend_changed_at
                if self.minor_trend_changed_at:
                    state.minor_trend_changed_at = self.minor_trend_changed_at
                
                # Save snapshot of critical data
                state.state_snapshot = json.dumps({
                    'positions': {k: v.id for k, v in self.active_positions.items()},
                    'contract_expiry': self.contract_expiry,
                    'paused': self.paused,
                    'timestamp': datetime.now(IST).isoformat()
                })
                
                self.db.commit()
                logger.debug("State saved successfully")
                
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    async def _load_open_positions(self):
        """Load open positions from database"""
        try:
            open_trades = self.db.query(LiveTrade).filter(
                LiveTrade.config_id == self.config.id,
                LiveTrade.status == "open"
            ).all()
            
            self.active_positions = {}
            self.allocated_funds = 0.0
            
            for trade in open_trades:
                key = f"{trade.option_type}_{trade.trigger_type}"
                self.active_positions[key] = trade
                
                # Add to allocated funds
                if trade.allocated_capital:
                    self.allocated_funds += trade.allocated_capital
            
            logger.info(f"Loaded {len(self.active_positions)} open positions (Allocated: ₹{self.allocated_funds:,.2f})")
            
        except Exception as e:
            logger.error(f"Error loading open positions: {e}")
    
    # ===========================
    # Phase 7: Crash Recovery Enhancement
    # ===========================
    
    async def _reconcile_broker_positions(self) -> Dict[str, any]:
        """
        Reconcile database positions with broker positions after crash recovery
        
        This method:
        1. Fetches current positions from broker
        2. Fetches pending/completed orders from broker
        3. Compares with database positions
        4. Identifies discrepancies (orphaned orders, missing positions)
        5. Auto-pauses engine if critical discrepancies found
        6. Returns reconciliation report
        
        Called during:
        - Startup after crash detection
        - Manual reconciliation request
        
        Returns:
            Dict with reconciliation results and discrepancy details
        """
        try:
            logger.info("🔍 Starting broker position reconciliation...")
            
            report = {
                'success': True,
                'timestamp': datetime.now(IST).isoformat(),
                'discrepancies_found': False,
                'discrepancy_details': [],
                'actions_taken': [],
                'broker_positions': [],
                'db_positions': [],
                'orphaned_orders': [],
                'missing_orders': [],
                'fund_mismatch': False
            }
            
            # 1. Fetch broker positions
            try:
                broker_positions_data = self.middleware.get_positions(use_cache=False)
                broker_net_positions = broker_positions_data.get('net', [])
                report['broker_positions'] = [
                    {
                        'tradingsymbol': pos.get('tradingsymbol'),
                        'quantity': pos.get('quantity'),
                        'product': pos.get('product'),
                        'pnl': pos.get('pnl')
                    }
                    for pos in broker_net_positions
                    if pos.get('quantity', 0) != 0  # Only non-zero positions
                ]
                logger.info(f"Found {len(report['broker_positions'])} active positions at broker")
            except TokenExpiredError:
                logger.error("Token expired during broker reconciliation")
                await self._handle_token_expiry()
                raise
            except Exception as e:
                logger.error(f"Failed to fetch broker positions: {e}")
                report['success'] = False
                report['discrepancies_found'] = True
                report['discrepancy_details'].append(f"Broker API error: {e}")
                return report
            
            # 2. Fetch broker orders (today's orders)
            try:
                broker_orders = self.middleware.get_orders(use_cache=False)
                logger.info(f"Found {len(broker_orders)} orders at broker")
            except TokenExpiredError:
                logger.error("Token expired while fetching orders")
                await self._handle_token_expiry()
                raise
            except Exception as e:
                logger.error(f"Failed to fetch broker orders: {e}")
                broker_orders = []
            
            # 3. Get database positions
            db_positions = self.db.query(LiveTrade).filter(
                LiveTrade.config_id == self.config.id,
                LiveTrade.status == 'open'
            ).all()
            
            report['db_positions'] = [
                {
                    'id': trade.id,
                    'instrument': trade.instrument,
                    'quantity': trade.quantity,
                    'broker_order_id_buy': trade.broker_order_id_buy,
                    'broker_order_id_sell': trade.broker_order_id_sell,
                    'order_status_buy': trade.order_status_buy,
                    'order_status_sell': trade.order_status_sell
                }
                for trade in db_positions
            ]
            logger.info(f"Found {len(db_positions)} open positions in database")
            
            # 4. Check for orphaned orders (in DB but not placed at broker)
            for trade in db_positions:
                buy_order_id = trade.broker_order_id_buy
                sell_order_id = trade.broker_order_id_sell
                
                # Check buy order
                if buy_order_id:
                    broker_buy_order = next(
                        (o for o in broker_orders if o.get('order_id') == buy_order_id),
                        None
                    )
                    if not broker_buy_order:
                        report['orphaned_orders'].append({
                            'trade_id': trade.id,
                            'order_id': buy_order_id,
                            'order_type': 'BUY',
                            'instrument': trade.instrument
                        })
                        report['discrepancies_found'] = True
                        logger.warning(
                            f"⚠️ Orphaned BUY order: Trade {trade.id} has order ID "
                            f"{buy_order_id} but not found at broker"
                        )
                
                # Check sell order
                if sell_order_id:
                    broker_sell_order = next(
                        (o for o in broker_orders if o.get('order_id') == sell_order_id),
                        None
                    )
                    if not broker_sell_order:
                        report['orphaned_orders'].append({
                            'trade_id': trade.id,
                            'order_id': sell_order_id,
                            'order_type': 'SELL',
                            'instrument': trade.instrument
                        })
                        report['discrepancies_found'] = True
                        logger.warning(
                            f"⚠️ Orphaned SELL order: Trade {trade.id} has order ID "
                            f"{sell_order_id} but not found at broker"
                        )
            
            # 5. Check for positions at broker not in database
            for broker_pos in report['broker_positions']:
                tradingsymbol = broker_pos['tradingsymbol']
                
                # Check if this position exists in DB
                db_trade = next(
                    (t for t in db_positions if t.instrument == tradingsymbol),
                    None
                )
                
                if not db_trade:
                    report['missing_orders'].append({
                        'tradingsymbol': tradingsymbol,
                        'quantity': broker_pos['quantity'],
                        'pnl': broker_pos['pnl']
                    })
                    report['discrepancies_found'] = True
                    logger.warning(
                        f"⚠️ Position at broker not in DB: {tradingsymbol} "
                        f"(Qty: {broker_pos['quantity']})"
                    )
            
            # 6. Verify allocated funds match reality
            calculated_allocation = sum(
                trade.allocated_capital or 0.0
                for trade in db_positions
            )
            
            if abs(calculated_allocation - self.allocated_funds) > 1.0:  # 1 rupee tolerance
                report['fund_mismatch'] = True
                report['discrepancies_found'] = True
                report['discrepancy_details'].append(
                    f"Fund mismatch: DB shows ₹{self.allocated_funds:,.2f} allocated, "
                    f"but calculated ₹{calculated_allocation:,.2f} from positions"
                )
                logger.warning(
                    f"⚠️ Fund allocation mismatch: "
                    f"Stored={self.allocated_funds:,.2f}, Calculated={calculated_allocation:,.2f}"
                )
                
                # Auto-correct allocated funds
                self.allocated_funds = calculated_allocation
                report['actions_taken'].append(
                    f"Corrected allocated_funds to ₹{calculated_allocation:,.2f}"
                )
            
            # 7. Handle critical discrepancies
            if report['discrepancies_found']:
                # Auto-pause engine
                self.paused = True
                report['actions_taken'].append("Auto-paused engine due to discrepancies")
                
                # Send alert
                discrepancy_summary = []
                if report['orphaned_orders']:
                    discrepancy_summary.append(
                        f"{len(report['orphaned_orders'])} orphaned orders"
                    )
                if report['missing_orders']:
                    discrepancy_summary.append(
                        f"{len(report['missing_orders'])} missing positions"
                    )
                if report['fund_mismatch']:
                    discrepancy_summary.append("fund allocation mismatch")
                
                alert_msg = (
                    f"🚨 RECONCILIATION ALERT: {', '.join(discrepancy_summary)}. "
                    f"Engine auto-paused. Please review before resuming."
                )
                self._add_alert('error', alert_msg)
                logger.error(alert_msg)
            else:
                logger.info("✅ Reconciliation complete - no discrepancies found")
                report['actions_taken'].append("No issues found - engine ready")
            
            # Save updated state
            await self._save_state()
            
            return report
            
        except Exception as e:
            logger.error(f"Error during reconciliation: {e}")
            return {
                'success': False,
                'timestamp': datetime.now(IST).isoformat(),
                'error': str(e),
                'discrepancies_found': True
            }
    
    async def _fetch_initial_data(self):
        """Fetch initial historical data for indicators"""
        try:
            if not self.config:
                return
            
            logger.info("Fetching initial historical data for indicators...")
            
            # Fetch major timeframe data
            major_days = self._get_days_for_candles(self.config.major_timeframe, 100)
            from_date = datetime.now(IST) - timedelta(days=major_days)
            to_date = datetime.now(IST)
            
            logger.info(f"Fetching NIFTY 50 data from {from_date.date()} to {to_date.date()} ({self.config.major_timeframe})")
            
            # Use middleware to get historical data (centralized rate limiting and caching)
            major_data_raw = self.middleware.get_historical_data(
                instrument_token=256265,  # NIFTY 50
                from_date=from_date,
                to_date=to_date,
                interval=self.config.major_timeframe,
                use_cache=True
            )
            
            if major_data_raw:
                self.major_candles.extend(major_data_raw[-100:])
                logger.info(f"Loaded {len(self.major_candles)} major timeframe candles")
            
            # Fetch minor timeframe data
            minor_days = self._get_days_for_candles(self.config.minor_timeframe, 500)
            from_date = datetime.now(IST) - timedelta(days=minor_days)
            
            logger.info(f"Fetching NIFTY 50 data from {from_date.date()} to {to_date.date()} ({self.config.minor_timeframe})")
            
            # Use middleware to get historical data (centralized rate limiting and caching)
            minor_data_raw = self.middleware.get_historical_data(
                instrument_token=256265,
                from_date=from_date,
                to_date=to_date,
                interval=self.config.minor_timeframe,
                use_cache=True
            )
            
            if minor_data_raw:
                self.minor_candles.extend(minor_data_raw[-500:])
                logger.info(f"Loaded {len(self.minor_candles)} minor timeframe candles")
            
            logger.info("Initial data fetch complete")
            
        except Exception as e:
            logger.error(f"Error fetching initial data: {e}")
    
    def _get_days_for_candles(self, timeframe: str, num_candles: int) -> int:
        """Calculate number of days needed to fetch required candles"""
        minutes_per_candle = {
            "minute": 1, "3minute": 3, "5minute": 5, "10minute": 10,
            "15minute": 15, "30minute": 30, "60minute": 60, "day": 375
        }
        
        minutes = minutes_per_candle.get(timeframe, 1)
        trading_minutes_per_day = 375  # 6.25 hours
        days_needed = (num_candles * minutes) / trading_minutes_per_day
        
        # Add buffer for weekends and holidays
        return int(days_needed * 2) + 5
    
    async def _monitor_positions(self):
        """Background task to monitor open positions"""
        logger.info("Position monitoring task started")
        
        try:
            while self.running:
                # Check market hours
                if not is_market_open():
                    logger.debug("Market closed - skipping position check")
                    await asyncio.sleep(60)
                    continue
                
                # Monitor each position
                for key, trade in list(self.active_positions.items()):
                    await self._check_position_targets(trade)
                
                # Save state periodically
                await self._save_state()
                
                # Wait before next check (every 5 seconds)
                await asyncio.sleep(5)
                
        except asyncio.CancelledError:
            logger.info("Position monitoring task cancelled")
        except Exception as e:
            logger.error(f"Error in position monitoring: {e}")
    
    async def _check_position_targets(self, trade: LiveTrade):
        """
        Check if position has hit target or stoploss
        
        This method is called when LTP updates are received via webhook.
        Uses the middleware LTP cache for < 1ms access time (HFT optimization).
        
        Args:
            trade: LiveTrade record to check
        """
        try:
            # Skip if position is not open or buy not confirmed
            if trade.status != 'open' or trade.order_status_buy != 'COMPLETE':
                return
            
            # Get current LTP from middleware (uses cache during market hours)
            ltp_data = self.middleware.get_ltp([f"NFO:{trade.instrument}"])
            ltp = ltp_data.get(f"NFO:{trade.instrument}", 0) if ltp_data else 0
            if not ltp or ltp <= 0:
                return
            
            # Update position prices
            await self._update_position_prices(trade, ltp)
            
            # Calculate unrealized P&L
            pnl = (ltp - trade.entry_price) * trade.quantity
            pnl_pct = ((ltp - trade.entry_price) / trade.entry_price) * 100
            
            # Update trade record
            trade.current_price = ltp
            trade.unrealized_pnl = pnl
            self.db.commit()
            
            # Check target hit
            if ltp >= trade.target_price:
                logger.info(
                    f"🎯 TARGET HIT: {trade.instrument} "
                    f"LTP=₹{ltp:.2f} >= Target=₹{trade.target_price:.2f} "
                    f"P&L=₹{pnl:,.2f} ({pnl_pct:.2f}%)"
                )
                await self._exit_position(
                    trade,
                    "target",
                    f"Target hit: ₹{ltp:.2f} >= ₹{trade.target_price:.2f}"
                )
                return
            
            # Check stoploss hit
            if ltp <= trade.stoploss_price:
                logger.info(
                    f"🛑 STOPLOSS HIT: {trade.instrument} "
                    f"LTP=₹{ltp:.2f} <= SL=₹{trade.stoploss_price:.2f} "
                    f"P&L=₹{pnl:,.2f} ({pnl_pct:.2f}%)"
                )
                await self._exit_position(
                    trade,
                    "stoploss",
                    f"Stoploss hit: ₹{ltp:.2f} <= ₹{trade.stoploss_price:.2f}"
                )
                return
            
        except Exception as e:
            logger.error(f"Error checking position targets for {trade.id}: {e}")
    
    async def _realtime_position_check(self, instrument_token: str, ltp: float):
        """
        Real-time position check callback (called by LTP processor every 50ms)
        
        This is the HFT-optimized path for position monitoring:
        - Called automatically when LTP updates arrive
        - Checks all positions for this instrument
        - Triggers exits immediately when target/SL hit
        - Sub-second response time
        
        Args:
            instrument_token: Instrument token with LTP update
            ltp: Current LTP
        """
        try:
            # Find all active positions for this instrument
            for trade in self.active_positions.values():
                if trade.instrument_token == instrument_token:
                    await self._check_position_targets(trade)
        except Exception as e:
            logger.error(f"Error in real-time position check: {e}")
    
    async def _square_off_all_positions(self):
        """
        Square off all open positions at end of day (15:28)
        
        This should be called at 15:28 IST to close all positions before market closes.
        Used for:
        1. End-of-day cleanup
        2. Manual stop trading
        3. Token expiry auto-pause
        """
        logger.info(f"🔴 Squaring off {len(self.active_positions)} open positions...")
        
        squared_count = 0
        failed_count = 0
        
        for key, trade in list(self.active_positions.items()):
            try:
                await self._exit_position(
                    trade,
                    "square_off",
                    f"End of day square-off at {datetime.now(IST).strftime('%H:%M')}"
                )
                squared_count += 1
            except Exception as e:
                logger.error(f"Error squaring off position {key}: {e}")
                failed_count += 1
        
        logger.info(
            f"✅ Square-off complete: {squared_count} closed, {failed_count} failed"
        )
        
        # Alert
        self._add_alert(
            'info',
            f"Day end square-off: {squared_count} positions closed"
        )
    
    async def _exit_position(self, trade: LiveTrade, exit_reason: str, comment: str):
        """
        Exit a position by placing a SELL order
        
        This is a wrapper around _execute_exit_signal() with additional checks.
        Used by:
        - Target/SL hit (_check_position_targets)
        - Manual square-off (_square_off_all_positions)
        - Opposite signal (signal detection - Phase 6+)
        
        Args:
            trade: LiveTrade record to exit
            exit_reason: Reason for exit ('target', 'stoploss', 'square_off', 'opposite_signal', etc.)
            comment: Human-readable comment for logs
        """
        try:
            logger.info(f"📤 Exiting position {trade.id}: {exit_reason} - {comment}")
            
            # Verify position is open
            if trade.status != 'open':
                logger.warning(f"Position {trade.id} is not open (status: {trade.status})")
                return
            
            # Verify buy order is confirmed
            if trade.order_status_buy != 'COMPLETE':
                logger.warning(
                    f"Position {trade.id} buy not confirmed (status: {trade.order_status_buy})"
                )
                return
            
            # Execute exit signal (places SELL order)
            await self._execute_exit_signal(trade, exit_reason)
            
            logger.info(f"✅ Exit order placed for {trade.instrument}")
            
        except Exception as e:
            logger.error(f"Error exiting position {trade.id}: {e}")
            # Alert on exit failure
            self._add_alert(
                'error',
                f"Failed to exit {trade.instrument}: {e}"
            )
    
    def _calculate_trade_quantity(self, option_premium: float, lot_size: int = 50) -> Tuple[int, float]:
        """
        Calculate trade quantity based on available broker funds and capital allocation
        
        Formula: max_lots = capital_per_trade / (ltp * lot_size), then round down
        Where: capital_per_trade = available_broker_funds * (capital_allocation_pct / 100)
        
        Args:
            option_premium: Premium price of the option (LTP)
            lot_size: Lot size of the contract (default: 50 for NIFTY)
            
        Returns:
            Tuple of (quantity, capital_required)
        """
        # Calculate capital to allocate per trade from BROKER FUNDS (not config initial_capital)
        capital_allocation_pct = self.config.capital_allocation_pct or 16.0
        capital_per_trade = self.available_funds * (capital_allocation_pct / 100)
        
        # Check if we have enough available funds
        if capital_per_trade <= 0:
            logger.warning(f"Insufficient funds: Available=₹{self.available_funds:,.2f}, Allocation={capital_allocation_pct}% = ₹{capital_per_trade:,.2f}")
            return 0, 0.0
        
        # Calculate number of lots: capital_per_trade / (ltp * lot_size), then round down
        if option_premium <= 0 or lot_size <= 0:
            logger.warning(f"Invalid parameters: premium={option_premium}, lot_size={lot_size}")
            return 0, 0.0
            
        max_lots = int(capital_per_trade / (option_premium * lot_size))
        
        if max_lots < 1:
            logger.warning(f"Insufficient fund for 1 lot: Allocated=₹{capital_per_trade:,.2f}, Required=₹{option_premium * lot_size:,.2f} per lot")
            return 0, 0.0
        
        # Calculate quantity and actual capital required
        quantity = max_lots * lot_size
        capital_required = quantity * option_premium
        
        logger.info(f"Trade calculation: Broker funds=₹{self.available_funds:,.2f}, Allocation={capital_allocation_pct}%, Per trade=₹{capital_per_trade:,.2f}")
        logger.info(f"  → {max_lots} lots x {lot_size} = {quantity} qty, Capital needed: ₹{capital_required:,.2f}")
        
        return quantity, capital_required
    
    def _validate_funds_for_entry(self, capital_required: float) -> bool:
        """
        Validate if we have sufficient funds for a new entry
        
        Args:
            capital_required: Capital required for the trade
            
        Returns:
            bool: True if sufficient funds available
        """
        if capital_required <= 0:
            logger.error("Invalid capital requirement")
            return False
        
        if self.available_funds < capital_required:
            logger.warning(
                f"Insufficient funds: Required=₹{capital_required:,.2f}, "
                f"Available=₹{self.available_funds:,.2f}"
            )
            return False
        
        # Also check if we have room within config limits
        max_positions = self.config.max_open_positions or 2
        if len(self.active_positions) >= max_positions:
            logger.warning(f"Max positions reached: {len(self.active_positions)}/{max_positions}")
            return False
        
        return True
    
    def _update_funds_on_entry(self, capital_allocated: float):
        """
        Update fund tracking when entering a new position
        
        Args:
            capital_allocated: Capital allocated to the new position
        """
        self.available_funds -= capital_allocated
        self.allocated_funds += capital_allocated
        
        logger.info(
            f"Funds updated on entry: Available=₹{self.available_funds:,.2f}, "
            f"Allocated=₹{self.allocated_funds:,.2f}"
        )
    
    def _update_funds_on_exit(self, capital_allocated: float, pnl: float):
        """
        Update fund tracking when exiting a position
        
        Args:
            capital_allocated: Capital that was allocated to the position
            pnl: Profit/Loss from the trade
        """
        # Release allocated capital
        self.allocated_funds -= capital_allocated
        
        # Add back capital + P&L to available funds
        self.available_funds += (capital_allocated + pnl)
        
        logger.info(
            f"Funds updated on exit: P&L=₹{pnl:,.2f}, "
            f"Available=₹{self.available_funds:,.2f}, "
            f"Allocated=₹{self.allocated_funds:,.2f}"
        )
    
    def _get_fund_status(self) -> Dict:
        """
        Get current fund status for display
        
        Returns:
            Dict with fund details
        """
        return {
            'available_funds': round(self.available_funds, 2),
            'allocated_funds': round(self.allocated_funds, 2),
            'total_funds': round(self.available_funds + self.allocated_funds, 2),
            'utilization_pct': round(
                (self.allocated_funds / (self.available_funds + self.allocated_funds) * 100) 
                if (self.available_funds + self.allocated_funds) > 0 else 0, 
                2
            ),
            'open_positions': len(self.active_positions)
        }
    
    async def process_ltp_update(self, instrument_token: str, ltp: float):
        """
        DEPRECATED: This method is kept for backward compatibility only.
        
        LTP updates are now handled automatically by UnifiedBrokerMiddleware
        via WebSocket during market hours. The middleware handles:
        - WebSocket connection management (9:00 AM - 3:30 PM)
        - LTP caching with < 1ms access time
        - Automatic fallback to API polling if webhook fails
        
        This method does minimal processing and will be removed in a future version.
        
        Args:
            instrument_token: Instrument token (e.g., "256265" for NIFTY 50)
            ltp: Last traded price
        """
        if not self.running:
            return
        
        # Update NIFTY LTP if this is NIFTY 50
        if instrument_token == "256265":
            self.nifty_ltp = ltp
    
    async def _process_nifty_update(self, ltp: float):
        """Process NIFTY LTP update (placeholder - will be implemented with trading logic)"""
        # This will be implemented in later phases with trend detection
        # For now, just update the LTP
        logger.debug(f"NIFTY LTP updated: {ltp}")
    
    async def process_order_update(self, order_data: Dict):
        """
        Process order status update from webhook postback (HFT-OPTIMIZED)
        
        This is the critical path for HFT trading - every millisecond counts!
        
        Optimizations:
        1. Direct database updates (no ORM overhead for critical fields)
        2. Immediate sell order placement when buy fills (no delay)
        3. Batch database commits where possible
        4. Pre-calculated order matching (O(1) lookups)
        
        Args:
            order_data: Order data from broker postback
                {
                    'order_id': '123456789',
                    'status': 'COMPLETE',
                    'filled_quantity': 50,
                    'average_price': 150.25,
                    'order_timestamp': '2025-11-02 10:30:45',
                    'transaction_type': 'BUY',
                    'tradingsymbol': 'NIFTY25NOVFUT'
                }
        """
        try:
            order_id = order_data.get('order_id')
            status = order_data.get('status')
            
            logger.info(f"⚡ Processing order update: {order_id} - Status: {status}")
            
            # Find the trade with this order ID (O(1) with proper indexing)
            trade = self.db.query(LiveTrade).filter(
                (LiveTrade.broker_order_id_buy == order_id) | 
                (LiveTrade.broker_order_id_sell == order_id)
            ).first()
            
            if not trade:
                logger.warning(f"No trade found for order ID: {order_id}")
                return
            
            # Determine if this is buy or sell order
            is_buy_order = (trade.broker_order_id_buy == order_id)
            
            # Update order status
            if is_buy_order:
                trade.order_status_buy = status
                if status == 'COMPLETE':
                    trade.buy_confirmed_at = datetime.now(IST)
                    trade.entry_price = order_data.get('average_price', trade.entry_price)
                    logger.info(f"✓ Buy order confirmed for trade {trade.id} at ₹{trade.entry_price}")
                    
                    # Update trade status
                    trade.status = 'open'
                    
                    # Middleware automatically handles real-time LTP updates via WebSocket
                    # No need to manually update LTP cache
                    
                    # Commit immediately for fast access
                    self.db.commit()
                    
                    logger.info(f"⚡ Position opened - real-time monitoring active for {trade.instrument}")
                    
                elif status == 'REJECTED':
                    trade.buy_rejection_reason = order_data.get('status_message', 'Order rejected')
                    trade.status = 'rejected'
                    
                    # Release allocated funds
                    if trade.allocated_capital:
                        self._update_funds_on_exit(trade.allocated_capital, 0.0)
                    
                    self.db.commit()
                    
                    logger.error(f"Buy order rejected for trade {trade.id}: {trade.buy_rejection_reason}")
                    self._add_alert("error", f"Buy order rejected: {trade.buy_rejection_reason}")
            else:
                trade.order_status_sell = status
                if status == 'COMPLETE':
                    trade.sell_confirmed_at = datetime.now(IST)
                    trade.exit_price = order_data.get('average_price', trade.exit_price)
                    trade.exit_time = datetime.now(IST)
                    
                    # Calculate P&L using helper method
                    pnl, pnl_pct = self._calculate_pnl(trade)
                    trade.pnl = pnl
                    trade.pnl_percentage = pnl_pct
                    trade.status = 'closed'
                    
                    # Release funds and add P&L
                    if trade.allocated_capital:
                        self._update_funds_on_exit(trade.allocated_capital, pnl)
                    
                    # Remove from active positions
                    key = f"{trade.option_type}_{trade.entry_trigger}"
                    if key in self.active_positions:
                        del self.active_positions[key]
                    
                    # Commit immediately
                    self.db.commit()
                    
                    logger.info(
                        f"✅ Sell order confirmed for trade {trade.id} - "
                        f"P&L: ₹{pnl:,.2f} ({pnl_pct:.2f}%)"
                    )
                    pnl_emoji = "🟢" if pnl >= 0 else "🔴"
                    self._add_alert(
                        "success" if pnl >= 0 else "warning",
                        f"{pnl_emoji} Position closed - P&L: ₹{pnl:,.2f} ({pnl_pct:.2f}%)"
                    )
                    
                elif status == 'REJECTED':
                    trade.sell_rejection_reason = order_data.get('status_message', 'Order rejected')
                    self.db.commit()
                    logger.error(f"Sell order rejected for trade {trade.id}: {trade.sell_rejection_reason}")
                    self._add_alert("error", f"Sell order rejected: {trade.sell_rejection_reason}")
            
            await self._save_state()
            
        except Exception as e:
            logger.error(f"Error processing order update: {e}")
            self.db.rollback()
    
    async def _subscribe_position_ltp(self, trade: LiveTrade):
        """
        Subscribe to LTP updates for a position
        
        Args:
            trade: LiveTrade record
        """
        try:
            if not trade.instrument_token:
                logger.warning(f"No instrument token for trade {trade.id}")
                return
            
            # Use middleware to subscribe to instrument for LTP updates
            logger.info(f"Subscribing to LTP updates for instrument: {trade.instrument_token}")
            
            # Subscribe via middleware
            instrument_token_int = int(trade.instrument_token)
            self.middleware.subscribe_ltp(
                instruments=[f"NFO:{trade.instrument}"],
                instrument_tokens=[instrument_token_int]
            )
            
            # Store in positions_ltp dict for tracking
            self.positions_ltp[trade.instrument_token] = trade.entry_price
            
        except Exception as e:
            logger.error(f"Error subscribing to position LTP: {e}")
    
    async def _unsubscribe_position_ltp(self, trade: LiveTrade):
        """
        Unsubscribe from LTP updates for a position
        
        Args:
            trade: LiveTrade record
        """
        try:
            if not trade.instrument_token:
                return
            
            logger.info(f"Unsubscribing from LTP updates for instrument: {trade.instrument_token}")
            
            # Remove from positions_ltp dict
            if trade.instrument_token in self.positions_ltp:
                del self.positions_ltp[trade.instrument_token]
            
        except Exception as e:
            logger.error(f"Error unsubscribing from position LTP: {e}")
    
    def _add_alert(self, alert_type: str, message: str, extra_data: Dict = None):
        """Add alert to database"""
        try:
            alert = LiveTradingAlert(
                config_id=self.config.id,
                alert_type=alert_type,
                category=alert_type,  # Map alert_type to category field
                message=message,
                timestamp=datetime.now(IST),
                alert_metadata=extra_data  # Use correct field name from model
            )
            self.db.add(alert)
            self.db.commit()
        except Exception as e:
            logger.error(f"Error adding alert: {e}")
    
    # ==================== PHASE 5: ORDER EXECUTION FLOW ====================
    
    async def _get_contract_expiry(self) -> Optional[str]:
        """
        Get contract expiry date based on config
        
        If contract_expiry is set during start, uses that.
        Otherwise defaults to nearest weekly expiry.
        
        Returns:
            Expiry date string in format "YYYY-MM-DD" or None if not found
        """
        try:
            if self.contract_expiry:
                # Already set during start
                logger.debug(f"Using configured contract expiry: {self.contract_expiry}")
                return self.contract_expiry
            
            # Get nearest weekly expiry
            # Query instruments to find next NIFTY option expiry
            next_expiry = self.db.query(Instrument.expiry).filter(
                Instrument.name == 'NIFTY',
                Instrument.instrument_type.in_(['CE', 'PE']),
                Instrument.expiry >= datetime.now(IST).date()
            ).order_by(Instrument.expiry).first()
            
            if next_expiry:
                expiry_date = next_expiry[0].strftime('%Y-%m-%d')
                logger.info(f"Selected nearest expiry: {expiry_date}")
                return expiry_date
            
            logger.error("No valid expiry dates found in instrument database")
            return None
            
        except Exception as e:
            logger.error(f"Error getting contract expiry: {e}")
            return None
    
    async def _select_strike_prices(self, nifty_ltp: float, option_type: str) -> Optional[int]:
        """
        Select strike price based on NIFTY LTP and config
        
        Logic:
        - CE (Call): Round UP to nearest strike, then ADD gap
        - PE (Put): Round DOWN to nearest strike, then SUBTRACT gap
        
        Example with NIFTY=25722, round_to=100, gap=100:
        - CE: ceil(25722/100)*100 + 100 = 25800 + 100 = 25900
        - PE: floor(25722/100)*100 - 100 = 25700 - 100 = 25600
        
        Args:
            nifty_ltp: Current NIFTY spot price
            option_type: 'CE' or 'PE'
        
        Returns:
            Strike price or None if unable to calculate
        """
        try:
            import math
            
            strike_gap = self.config.min_strike_gap
            round_to = self.config.strike_round_to
            
            # Calculate strike based on option type
            if option_type == 'CE':
                # CE: Round UP to next strike, then ADD gap
                base_strike = math.ceil(nifty_ltp / round_to) * round_to
                strike = base_strike + strike_gap
            else:  # PE
                # PE: Round DOWN to previous strike, then SUBTRACT gap
                base_strike = math.floor(nifty_ltp / round_to) * round_to
                strike = base_strike - strike_gap
            
            logger.debug(
                f"Strike selection for {option_type}: NIFTY={nifty_ltp:.2f}, "
                f"Round={round_to}, Gap={strike_gap}, Base={base_strike} → Strike={strike}"
            )
            
            return int(strike)
            
        except Exception as e:
            logger.error(f"Error selecting strike price: {e}")
            return None
    
    async def _find_contract(
        self, 
        nifty_ltp: float, 
        option_type: str,
        expiry_date: str
    ) -> Optional[Dict]:
        """
        Find appropriate option contract based on strike and expiry
        
        Args:
            nifty_ltp: Current NIFTY spot price
            option_type: 'CE' or 'PE'
            expiry_date: Target expiry date in format "YYYY-MM-DD"
        
        Returns:
            Dict with contract details or None if not found
        """
        try:
            # Calculate strike
            strike = await self._select_strike_prices(nifty_ltp, option_type)
            if not strike:
                logger.error("Failed to calculate strike price")
                return None
            
            # Convert expiry_date to date object for comparison
            from datetime import datetime
            target_expiry = datetime.strptime(expiry_date, '%Y-%m-%d').date()
            
            # Find contract in database
            contract = self.db.query(Instrument).filter(
                Instrument.name == 'NIFTY',
                Instrument.instrument_type == option_type,
                Instrument.strike == strike,
                Instrument.expiry == target_expiry
            ).first()
            
            if contract:
                logger.info(
                    f"Found contract: {contract.tradingsymbol} "
                    f"(Strike={strike}, Expiry={expiry_date})"
                )
                return {
                    'instrument_token': contract.instrument_token,
                    'tradingsymbol': contract.tradingsymbol,
                    'strike': contract.strike,
                    'expiry': contract.expiry,
                    'exchange': contract.exchange,
                    'lot_size': contract.lot_size
                }
            
            logger.warning(
                f"No contract found: {option_type} Strike={strike} "
                f"Expiry={expiry_date}"
            )
            return None
            
        except Exception as e:
            logger.error(f"Error finding contract: {e}")
            return None
    
    async def _get_contract_ltp(self, instrument_token: str) -> Optional[float]:
        """
        Get current LTP for a contract
        
        Args:
            instrument_token: Instrument token
        
        Returns:
            LTP or None if unable to fetch
        """
        try:
            ltp_data = self.middleware.get_ltp([instrument_token])
            if ltp_data and instrument_token in ltp_data:
                ltp = ltp_data[instrument_token]
                logger.debug(f"Contract LTP for {instrument_token}: ₹{ltp:.2f}")
                return ltp
            
            logger.warning(f"No LTP data available for {instrument_token}")
            return None
            
        except TokenExpiredError:
            logger.error("Token expired while fetching contract LTP")
            await self._handle_token_expiry()
            raise
        except Exception as e:
            logger.error(f"Error getting contract LTP: {e}")
            return None
    
    async def _place_order(
        self,
        trade: LiveTrade,
        order_type: str,
        quantity: int,
        price: Optional[float] = None
    ) -> Optional[str]:
        """
        Place buy or sell order through broker API
        
        Args:
            trade: LiveTrade record
            order_type: 'BUY' or 'SELL'
            quantity: Order quantity in lots
            price: Limit price (None for market order)
        
        Returns:
            Broker order ID or None if order failed
        """
        try:
            # Determine order parameters
            transaction_type = order_type  # 'BUY' or 'SELL'
            product = self.config.product_type  # MIS/NRML from config
            order_mode = 'MARKET' if price is None else 'LIMIT'
            
            logger.info(
                f"Placing {order_type} order: {trade.instrument} "
                f"Qty={quantity} Price={price or 'MARKET'} Product={product}"
            )
            
            # Place order via middleware
            order_result = self.middleware.place_order(
                tradingsymbol=trade.instrument,
                exchange=trade.exchange or 'NFO',
                transaction_type=transaction_type,
                quantity=quantity * trade.lot_size,  # Convert lots to quantity
                order_type=order_mode,
                product=product,
                price=price,
                trigger_price=None
            )
            
            if order_result and 'order_id' in order_result:
                broker_order_id = order_result['order_id']
                logger.info(
                    f"✓ Order placed successfully: {order_type} {trade.instrument} "
                    f"Order ID: {broker_order_id}"
                )
                
                # Store broker order ID in trade record
                if order_type == 'BUY':
                    trade.broker_order_id_buy = broker_order_id
                    trade.order_status_buy = 'PENDING'
                else:  # SELL
                    trade.broker_order_id_sell = broker_order_id
                    trade.order_status_sell = 'PENDING'
                
                self.db.commit()
                
                return broker_order_id
            else:
                logger.error(f"Order placement failed: {order_result}")
                return None
            
        except TokenExpiredError:
            logger.error("Token expired while placing order")
            await self._handle_token_expiry()
            raise
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            await self._handle_order_rejection(trade, order_type, str(e))
            return None
    
    async def _execute_entry_signal(
        self,
        timestamp: datetime,
        nifty_ltp: float,
        option_type: str,
        trigger: str,
        indicator_value: float
    ):
        """
        Execute entry signal - place buy order for option contract
        
        Args:
            timestamp: Signal timestamp
            nifty_ltp: Current NIFTY spot price
            option_type: 'CE' or 'PE'
            trigger: Signal trigger (e.g., '7MA', 'LBB')
            indicator_value: Indicator value at signal
        """
        try:
            logger.info(
                f"Processing entry signal: {option_type} on {trigger} "
                f"@ {indicator_value:.2f}"
            )
            
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
                return
            
            # Get contract expiry
            expiry_date = await self._get_contract_expiry()
            if not expiry_date:
                self._add_alert('error', 'Failed to determine contract expiry')
                return
            
            # Find contract
            contract = await self._find_contract(nifty_ltp, option_type, expiry_date)
            if not contract:
                msg = f"No contract found for {option_type} near {nifty_ltp} expiry {expiry_date}"
                self._add_alert('error', msg)
                logger.warning(msg)
                return
            
            # Get contract LTP
            ltp = await self._get_contract_ltp(contract['instrument_token'])
            if not ltp:
                msg = f"Failed to get LTP for {contract['tradingsymbol']}"
                self._add_alert('error', msg)
                logger.warning(msg)
                return
            
            # Calculate quantity using fund management
            quantity_lots = self._calculate_trade_quantity(ltp, contract['lot_size'])
            if quantity_lots < 1:
                msg = f"Insufficient funds for {contract['tradingsymbol']} @ ₹{ltp:.2f}"
                self._add_alert('info', msg)
                logger.info(msg)
                return
            
            # Calculate capital required
            capital_required = ltp * quantity_lots * contract['lot_size']
            
            # Validate funds
            if not self._validate_funds_for_entry(capital_required):
                msg = f"Insufficient available funds for {contract['tradingsymbol']}"
                self._add_alert('warning', msg)
                logger.warning(msg)
                return
            
            # Calculate target and stoploss
            target_pct = self.config.target_pct if trigger == '7MA' else self.config.target_pct_lbb
            sl_pct = self.config.stoploss_pct if trigger == '7MA' else self.config.stoploss_pct_lbb
            
            target_price = ltp * (1 + target_pct / 100)
            stoploss_price = ltp * (1 - sl_pct / 100)
            
            # Create trade record
            trade = LiveTrade(
                config_id=self.config.id,
                date=timestamp.date(),
                instrument=contract['tradingsymbol'],
                instrument_token=contract['instrument_token'],
                exchange=contract['exchange'],
                option_type=option_type,
                strike=contract['strike'],
                entry_time=timestamp,
                entry_price=ltp,
                entry_trigger=trigger,
                crossover_value=indicator_value,
                quantity=quantity_lots,
                lot_size=contract['lot_size'],
                target_price=target_price,
                stoploss_price=stoploss_price,
                current_price=ltp,
                status='pending',  # Will change to 'open' on buy confirmation
                # Market context
                nifty_price=nifty_ltp,
                major_trend=self.major_trend,
                minor_trend=self.minor_trend,
                # Fund tracking
                available_funds_before=self.available_funds,
                allocated_capital=capital_required,
                # Contract details
                contract_expiry=expiry_date,
                # Price tracking
                highest_price=ltp,
                lowest_price=ltp,
                max_drawdown_pct=0.0
            )
            
            self.db.add(trade)
            self.db.commit()
            self.db.refresh(trade)
            
            # Place buy order
            broker_order_id = await self._place_order(
                trade=trade,
                order_type='BUY',
                quantity=quantity_lots,
                price=None  # Market order
            )
            
            if broker_order_id:
                # Allocate funds immediately on order placement
                self._update_funds_on_entry(capital_required)
                trade.available_funds_after = self.available_funds
                self.db.commit()
                
                # Add to active positions (pending confirmation)
                self.active_positions[position_key] = trade
                
                # Immediately subscribe to this new instrument for webhook
                await self._subscribe_new_instrument(
                    trade.instrument_token,
                    trade.instrument
                )
                
                # Alert
                msg = (
                    f"🔵 BUY ORDER PLACED: {trade.instrument} @ ₹{ltp:.2f} | "
                    f"Qty: {quantity_lots} lots | Target: ₹{target_price:.2f} | "
                    f"SL: ₹{stoploss_price:.2f} | Trigger: {trigger.upper()} | "
                    f"Order ID: {broker_order_id}"
                )
                self._add_alert('entry', msg)
                logger.info(msg)
            else:
                # Order placement failed - delete trade record
                self.db.delete(trade)
                self.db.commit()
                
        except Exception as e:
            logger.error(f"Error executing entry signal: {e}")
            self._add_alert('error', f'Entry execution failed: {e}')
    
    async def _execute_exit_signal(self, trade: LiveTrade, reason: str):
        """
        Execute exit signal - place sell order for open position
        
        Args:
            trade: LiveTrade record with open position
            reason: Exit reason (e.g., 'target', 'stoploss', 'square-off')
        """
        try:
            logger.info(
                f"Processing exit signal: {trade.instrument} "
                f"Reason: {reason}"
            )
            
            # Check if buy order is confirmed
            if trade.order_status_buy != 'COMPLETE':
                logger.warning(f"Cannot exit - buy order not confirmed yet for {trade.instrument}")
                return
            
            # Check if sell order already placed
            if trade.broker_order_id_sell:
                logger.warning(f"Sell order already placed for {trade.instrument}")
                return
            
            # Get current LTP
            ltp = await self._get_contract_ltp(trade.instrument_token)
            if not ltp:
                logger.error(f"Cannot get LTP for exit: {trade.instrument}")
                return
            
            # Update trade exit details
            trade.exit_price = ltp
            trade.exit_time = datetime.now(IST)
            trade.exit_reason = reason
            
            # Place sell order
            broker_order_id = await self._place_order(
                trade=trade,
                order_type='SELL',
                quantity=trade.quantity,
                price=None  # Market order
            )
            
            if broker_order_id:
                # Alert
                pnl = (ltp - trade.entry_price) * trade.quantity * trade.lot_size
                msg = (
                    f"🔴 SELL ORDER PLACED: {trade.instrument} @ ₹{ltp:.2f} | "
                    f"Entry: ₹{trade.entry_price:.2f} | "
                    f"P&L: ₹{pnl:,.2f} | Reason: {reason.upper()} | "
                    f"Order ID: {broker_order_id}"
                )
                self._add_alert('exit', msg)
                logger.info(msg)
            else:
                # Sell order failed - log but don't remove position
                logger.error(f"Failed to place sell order for {trade.instrument}")
                
        except Exception as e:
            logger.error(f"Error executing exit signal: {e}")
            self._add_alert('error', f'Exit execution failed: {e}')
    
    async def _handle_order_rejection(
        self,
        trade: LiveTrade,
        order_type: str,
        reason: str
    ):
        """
        Handle order rejection from broker
        
        Args:
            trade: LiveTrade record
            order_type: 'BUY' or 'SELL'
            reason: Rejection reason from broker
        """
        try:
            logger.error(
                f"Order rejected: {order_type} {trade.instrument} - {reason}"
            )
            
            # Update trade record
            if order_type == 'BUY':
                trade.order_status_buy = 'REJECTED'
                trade.buy_rejection_reason = reason
                trade.status = 'rejected'
                
                # Release allocated funds
                if trade.allocated_capital > 0:
                    self._update_funds_on_exit(trade.allocated_capital, 0.0)
                
                # Remove from active positions
                position_key = f"{trade.option_type}_{trade.entry_trigger}"
                if position_key in self.active_positions:
                    del self.active_positions[position_key]
                
            else:  # SELL
                trade.order_status_sell = 'REJECTED'
                trade.sell_rejection_reason = reason
                # For sell rejection, keep position open - will retry on next check
            
            self.db.commit()
            
            # Alert
            msg = (
                f"❌ ORDER REJECTED: {order_type} {trade.instrument} - {reason}"
            )
            self._add_alert('error', msg)
            logger.error(msg)
            
        except Exception as e:
            logger.error(f"Error handling order rejection: {e}")
    
    # ===========================
    # Phase 6: Position Management Helper Methods
    # ===========================
    
    async def _update_position_prices(self, trade: LiveTrade, ltp: float):
        """
        Update position price tracking (highest, lowest, max drawdown)
        
        This method updates:
        1. current_price - Current market price
        2. highest_price - Highest price since entry
        3. lowest_price - Lowest price since entry
        4. max_profit - Maximum profit reached
        5. max_loss - Maximum loss reached
        6. max_drawdown_pct - Maximum drawdown percentage from entry
        
        Args:
            trade: LiveTrade record
            ltp: Current LTP (Last Traded Price)
        """
        try:
            # Update current price
            trade.current_price = ltp
            
            # Update highest price
            if trade.highest_price is None or ltp > trade.highest_price:
                trade.highest_price = ltp
            
            # Update lowest price
            if trade.lowest_price is None or ltp < trade.lowest_price:
                trade.lowest_price = ltp
            
            # Calculate unrealized P&L
            unrealized_pnl = (ltp - trade.entry_price) * trade.quantity
            trade.unrealized_pnl = unrealized_pnl
            
            # Update max profit
            if trade.max_profit is None or unrealized_pnl > trade.max_profit:
                trade.max_profit = unrealized_pnl
            
            # Update max loss
            if trade.max_loss is None or unrealized_pnl < trade.max_loss:
                trade.max_loss = unrealized_pnl
            
            # Calculate max drawdown percentage
            if trade.entry_price > 0:
                current_dd_pct = ((ltp - trade.entry_price) / trade.entry_price) * 100
                if trade.max_drawdown_pct is None or current_dd_pct < trade.max_drawdown_pct:
                    trade.max_drawdown_pct = current_dd_pct
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error updating position prices for {trade.id}: {e}")
    
    # ===========================
    # Phase: Auto-Subscription for Webhook
    # ===========================
    
    async def _auto_subscribe_instruments(self):
        """
        Auto-subscribe to instruments for webhook (connection starts at 9:00 AM)
        
        Subscribes to:
        1. NIFTY 50 (index)
        2. All instruments in order list (LiveTrade)
        3. All instruments in position list (open trades)
        4. Instruments expected to be bought (CE/PE contracts based on current NIFTY LTP)
        
        Note: Webhook connection time starts at 9:00 AM, 15 minutes before market opens at 9:15 AM.
        This ensures the connection is established and ready to receive data when trading begins.
        
        Called:
        - At engine start
        - When new position is opened
        - Periodically to sync with broker positions
        """
        try:
            logger.info("🔔 Auto-subscribing to instruments for webhook...")
            
            instruments_to_subscribe = set()
            
            # 1. Subscribe to NIFTY 50
            nifty_token = "256265"
            instruments_to_subscribe.add(nifty_token)
            logger.debug("Added NIFTY 50 to subscription list")
            
            # 2. Subscribe to all instruments in order list (today's trades)
            today_start = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)
            all_trades = self.db.query(LiveTrade).filter(
                LiveTrade.config_id == self.config.id,
                LiveTrade.entry_time >= today_start
            ).all()
            
            for trade in all_trades:
                if trade.instrument_token:
                    instruments_to_subscribe.add(trade.instrument_token)
            logger.debug(f"Added {len(all_trades)} instruments from order list")
            
            # 3. Subscribe to all instruments in open positions
            open_positions = self.db.query(LiveTrade).filter(
                LiveTrade.config_id == self.config.id,
                LiveTrade.status == 'open'
            ).all()
            
            for trade in open_positions:
                if trade.instrument_token:
                    instruments_to_subscribe.add(trade.instrument_token)
            logger.debug(f"Added {len(open_positions)} instruments from open positions")
            
            # 4. Subscribe to expected instruments (CE/PE contracts)
            if self.nifty_ltp > 0:
                # Get contract expiry
                expiry_date = await self._get_contract_expiry()
                if expiry_date:
                    # Find CE contract
                    ce_contract = await self._find_contract(self.nifty_ltp, 'CE', expiry_date)
                    if ce_contract and ce_contract.get('instrument_token'):
                        instruments_to_subscribe.add(ce_contract['instrument_token'])
                        logger.debug(f"Added expected CE contract: {ce_contract['tradingsymbol']}")
                    
                    # Find PE contract
                    pe_contract = await self._find_contract(self.nifty_ltp, 'PE', expiry_date)
                    if pe_contract and pe_contract.get('instrument_token'):
                        instruments_to_subscribe.add(pe_contract['instrument_token'])
                        logger.debug(f"Added expected PE contract: {pe_contract['tradingsymbol']}")
            
            # Subscribe to all instruments via middleware
            new_subscriptions = instruments_to_subscribe - self.subscribed_instruments
            if new_subscriptions:
                logger.info(f"📡 Subscribing to {len(new_subscriptions)} new instruments via middleware")
                
                # Subscribe via middleware (handles WebSocket/API based on market hours)
                # Convert tokens to instrument names for subscription
                instrument_names = []
                for token in new_subscriptions:
                    # Get instrument from database
                    instrument = self.db.query(Instrument).filter(
                        Instrument.instrument_token == str(token)
                    ).first()
                    if instrument:
                        instrument_names.append(f"{instrument.exchange}:{instrument.tradingsymbol}")
                
                if instrument_names:
                    self.middleware.subscribe_ltp(
                        instruments=instrument_names,
                        instrument_tokens=list(new_subscriptions)
                    )
                
                # Update tracking
                self.subscribed_instruments.update(new_subscriptions)
                
                # Log subscribed instruments
                logger.info(
                    f"✓ Total subscribed instruments: {len(self.subscribed_instruments)} "
                    f"(NIFTY: 1, Orders: {len(all_trades)}, Positions: {len(open_positions)}, "
                    f"Expected: 2)"
                )
            else:
                logger.debug("All instruments already subscribed")
            
            # Middleware handles WebSocket connections automatically
            # based on market hours and subscriptions
            logger.debug("Middleware managing WebSocket connections based on market hours")
            
        except Exception as e:
            logger.error(f"Error in auto-subscription: {e}")
    
    async def _subscribe_new_instrument(self, instrument_token: str, instrument_name: str):
        """
        Subscribe to a new instrument immediately when position is opened
        
        Args:
            instrument_token: Instrument token to subscribe
            instrument_name: Human-readable instrument name for logging
        """
        try:
            if instrument_token in self.subscribed_instruments:
                logger.debug(f"Already subscribed to {instrument_name}")
                return
            
            logger.info(f"📡 Immediately subscribing to new instrument: {instrument_name}")
            
            # Subscribe via middleware
            self.middleware.subscribe_ltp(
                instruments=[instrument_name],
                instrument_tokens=[int(instrument_token)]
            )
            
            # Update tracking
            self.subscribed_instruments.add(instrument_token)
            
            logger.info(f"✓ Subscribed to {instrument_name} ({instrument_token})")
            
        except Exception as e:
            logger.error(f"Error subscribing to new instrument {instrument_name}: {e}")
    
    def _calculate_pnl(self, trade: LiveTrade) -> Tuple[float, float]:
        """
        Calculate realized P&L for a trade
        
        This method calculates:
        1. Absolute P&L in rupees
        2. P&L percentage relative to entry price
        
        Called when:
        - Exit order is confirmed (webhook callback)
        - Position is closed
        - Final P&L calculation needed
        
        Args:
            trade: LiveTrade record with entry and exit prices
            
        Returns:
            Tuple of (pnl_rupees, pnl_percentage)
        """
        try:
            # Validate prices
            if not trade.entry_price or not trade.exit_price:
                logger.warning(
                    f"Cannot calculate P&L - missing prices: "
                    f"entry={trade.entry_price}, exit={trade.exit_price}"
                )
                return 0.0, 0.0
            
            # Validate quantity
            if not trade.quantity or trade.quantity <= 0:
                logger.warning(f"Cannot calculate P&L - invalid quantity: {trade.quantity}")
                return 0.0, 0.0
            
            # Calculate absolute P&L
            pnl_rupees = (trade.exit_price - trade.entry_price) * trade.quantity
            
            # Calculate P&L percentage
            pnl_percentage = ((trade.exit_price - trade.entry_price) / trade.entry_price) * 100
            
            logger.debug(
                f"P&L calculated for {trade.instrument}: "
                f"Entry=₹{trade.entry_price:.2f}, Exit=₹{trade.exit_price:.2f}, "
                f"Qty={trade.quantity}, P&L=₹{pnl_rupees:,.2f} ({pnl_percentage:.2f}%)"
            )
            
            return pnl_rupees, pnl_percentage
            
        except Exception as e:
            logger.error(f"Error calculating P&L for trade {trade.id}: {e}")
            return 0.0, 0.0

