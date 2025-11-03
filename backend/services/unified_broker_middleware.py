"""
Unified Broker Data Middleware
================================

This middleware acts as a central hub for all broker data interactions, managing:

A. Market Data Feed (LTP & Order Status):
   - During market hours (9:00 AM - 3:30 PM): WebSocket/Webhook active
   - LTP updates via webhook in real-time
   - Order status updates via webhook postback
   - Automatic fallback to API polling if webhook doesn't return data for 10 seconds
   - Fallback uses 1-second polling interval until webhook resumes

B. Off-Market Hours Data:
   - API polling at 15-minute intervals for market data
   - No webhook connections outside market hours

C. Other Data (API-based):
   - Positions: Every 1 second (market hours), Every 15 minutes (off-hours)
   - Funds: Every 1 second (market hours), Every 15 minutes (off-hours)
   - Profile: Every 15 minutes (always)
   - Orders: On-demand (when app calls them)
   - Order creation/modification/deletion: Immediate (when app calls them)

D. Instrument List:
   - Downloaded once per day (already implemented, just verify)

This service provides a uniform interface to backend endpoints and engines,
abstracting away the complexity of market-time-based data source selection.
"""

import logging
import asyncio
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Any, Callable, Set
import time as pytime
import pytz
from sqlalchemy.orm import Session

from backend.broker.base import BaseBroker, TokenExpiredError
from backend.services.market_time import MarketTimeService
from backend.models import Instrument

logger = logging.getLogger(__name__)
IST = pytz.timezone('Asia/Kolkata')


class WebhookConnectionManager:
    """
    Manages WebSocket/Webhook connections for real-time market data
    Active only during market hours (9:00 AM - 3:30 PM)
    """
    
    def __init__(self, broker: BaseBroker, market_time_service: MarketTimeService):
        self.broker = broker
        self.market_time = market_time_service
        
        # Connection state
        self.is_connected = False
        self.last_data_received = None
        self.connection_active_time = None
        
        # Subscriptions
        self.subscribed_instruments: Set[int] = set()
        self.subscription_mode = "quote"  # ltp, quote, or full
        
        # Callbacks for data
        self.ltp_callbacks: List[Callable] = []
        self.order_callbacks: List[Callable] = []
        
        # Monitoring task
        self.monitor_task: Optional[asyncio.Task] = None
        self.running = False
        
        logger.info("WebhookConnectionManager initialized")
    
    async def start(self):
        """Start the webhook connection manager"""
        if self.running:
            logger.warning("WebhookConnectionManager already running")
            return
        
        self.running = True
        
        # Check if it's webhook connection time
        if self.market_time.is_webhook_connection_time():
            await self._connect()
        
        # Start monitoring task
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("✓ WebhookConnectionManager started")
    
    async def stop(self):
        """Stop the webhook connection manager"""
        self.running = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        await self._disconnect()
        logger.info("WebhookConnectionManager stopped")
    
    async def _connect(self):
        """Establish WebSocket connection"""
        if self.is_connected:
            return
        
        try:
            # Set up tick handler
            def on_ticks(ticks):
                self._handle_ticks(ticks)
            
            # Connect WebSocket
            self.broker.connect_websocket(
                on_message_callback=on_ticks,
                instruments=list(self.subscribed_instruments),
                mode=self.subscription_mode
            )
            
            self.is_connected = True
            self.connection_active_time = datetime.now(IST)
            self.last_data_received = datetime.now(IST)
            
            logger.info(f"✓ WebSocket connected with {len(self.subscribed_instruments)} instruments")
        
        except Exception as e:
            logger.error(f"Error connecting WebSocket: {e}")
            self.is_connected = False
    
    async def _disconnect(self):
        """Disconnect WebSocket"""
        if not self.is_connected:
            return
        
        try:
            self.broker.disconnect_websocket()
            self.is_connected = False
            self.connection_active_time = None
            logger.info("WebSocket disconnected")
        
        except Exception as e:
            logger.error(f"Error disconnecting WebSocket: {e}")
    
    def _handle_ticks(self, ticks: List[Dict]):
        """Handle incoming tick data"""
        self.last_data_received = datetime.now(IST)
        
        # Process LTP updates
        for tick in ticks:
            instrument_token = tick.get('instrument_token')
            last_price = tick.get('last_price', 0.0)
            
            # Notify all LTP callbacks
            for callback in self.ltp_callbacks:
                try:
                    callback(instrument_token, last_price, tick)
                except Exception as e:
                    logger.error(f"Error in LTP callback: {e}")
    
    async def _monitor_loop(self):
        """Monitor connection and handle reconnection"""
        try:
            while self.running:
                now = datetime.now(IST)
                
                # Check if we should be connected
                should_be_connected = self.market_time.is_webhook_connection_time()
                
                if should_be_connected and not self.is_connected:
                    # Should be connected but aren't - try to connect
                    logger.info("Market hours active - establishing WebSocket connection")
                    await self._connect()
                
                elif not should_be_connected and self.is_connected:
                    # Outside market hours - disconnect
                    logger.info("Outside market hours - disconnecting WebSocket")
                    await self._disconnect()
                
                # Check for data timeout (10 seconds without data)
                if self.is_connected and self.last_data_received:
                    seconds_since_data = (now - self.last_data_received).total_seconds()
                    if seconds_since_data > 10:
                        logger.warning(
                            f"⚠️ No data received for {seconds_since_data:.1f}s - "
                            "Webhook may be inactive, API fallback will be used"
                        )
                
                await asyncio.sleep(1)  # Check every second
        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in monitor loop: {e}")
    
    def subscribe(self, instruments: List[int], mode: str = "quote"):
        """Subscribe to instruments"""
        new_instruments = [i for i in instruments if i not in self.subscribed_instruments]
        
        if new_instruments:
            self.subscribed_instruments.update(new_instruments)
            
            if self.is_connected:
                try:
                    self.broker.subscribe_instruments(new_instruments, mode)
                    logger.info(f"Subscribed to {len(new_instruments)} new instruments")
                except Exception as e:
                    logger.error(f"Error subscribing to instruments: {e}")
    
    def unsubscribe(self, instruments: List[int]):
        """Unsubscribe from instruments"""
        instruments_to_remove = [i for i in instruments if i in self.subscribed_instruments]
        
        if instruments_to_remove:
            self.subscribed_instruments.difference_update(instruments_to_remove)
            
            if self.is_connected:
                try:
                    self.broker.unsubscribe_instruments(instruments_to_remove)
                    logger.info(f"Unsubscribed from {len(instruments_to_remove)} instruments")
                except Exception as e:
                    logger.error(f"Error unsubscribing from instruments: {e}")
    
    def register_ltp_callback(self, callback: Callable):
        """Register callback for LTP updates"""
        self.ltp_callbacks.append(callback)
    
    def register_order_callback(self, callback: Callable):
        """Register callback for order updates"""
        self.order_callbacks.append(callback)
    
    def is_data_flowing(self) -> bool:
        """Check if data is flowing from webhook"""
        if not self.is_connected or not self.last_data_received:
            return False
        
        seconds_since_data = (datetime.now(IST) - self.last_data_received).total_seconds()
        return seconds_since_data < 10  # Data within last 10 seconds


class DataPollingScheduler:
    """
    Manages API polling schedules for different data types
    Adapts polling frequency based on market hours
    """
    
    def __init__(self, broker: BaseBroker, market_time_service: MarketTimeService):
        self.broker = broker
        self.market_time = market_time_service
        
        # Polling tasks
        self.position_task: Optional[asyncio.Task] = None
        self.fund_task: Optional[asyncio.Task] = None
        self.profile_task: Optional[asyncio.Task] = None
        self.ltp_fallback_task: Optional[asyncio.Task] = None
        
        # Data cache
        self.positions_cache: Optional[Dict] = None
        self.funds_cache: Optional[Dict] = None
        self.profile_cache: Optional[Dict] = None
        self.ltp_cache: Dict[str, float] = {}
        
        # Cache timestamps
        self.positions_cache_time: Optional[datetime] = None
        self.funds_cache_time: Optional[datetime] = None
        self.profile_cache_time: Optional[datetime] = None
        
        # Data callbacks
        self.position_callbacks: List[Callable] = []
        self.fund_callbacks: List[Callable] = []
        self.ltp_fallback_callbacks: List[Callable] = []
        
        # Control flags
        self.running = False
        self.ltp_fallback_active = False
        
        logger.info("DataPollingScheduler initialized")
    
    async def start(self):
        """Start all polling tasks"""
        if self.running:
            return
        
        self.running = True
        
        # Start polling tasks
        self.position_task = asyncio.create_task(self._poll_positions())
        self.fund_task = asyncio.create_task(self._poll_funds())
        self.profile_task = asyncio.create_task(self._poll_profile())
        
        logger.info("✓ DataPollingScheduler started")
    
    async def stop(self):
        """Stop all polling tasks"""
        self.running = False
        
        tasks = [
            self.position_task,
            self.fund_task,
            self.profile_task,
            self.ltp_fallback_task
        ]
        
        for task in tasks:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        logger.info("DataPollingScheduler stopped")
    
    async def _poll_positions(self):
        """Poll positions at adaptive intervals"""
        try:
            while self.running:
                try:
                    # Fetch positions
                    positions = self.broker.get_positions()
                    self.positions_cache = positions
                    self.positions_cache_time = datetime.now(IST)
                    
                    # Notify callbacks
                    for callback in self.position_callbacks:
                        try:
                            callback(positions)
                        except Exception as e:
                            logger.error(f"Error in position callback: {e}")
                    
                    logger.debug("Positions fetched via API")
                
                except TokenExpiredError:
                    logger.error("Token expired while fetching positions")
                    # Don't continue polling if token expired
                    break
                except Exception as e:
                    logger.error(f"Error polling positions: {e}")
                
                # Determine wait interval based on market hours
                if self.market_time.is_market_open():
                    await asyncio.sleep(1)  # 1 second during market hours
                else:
                    await asyncio.sleep(900)  # 15 minutes outside market hours
        
        except asyncio.CancelledError:
            pass
    
    async def _poll_funds(self):
        """Poll funds at adaptive intervals"""
        try:
            while self.running:
                try:
                    # Fetch funds
                    funds = self.broker.get_funds()
                    self.funds_cache = funds
                    self.funds_cache_time = datetime.now(IST)
                    
                    # Notify callbacks
                    for callback in self.fund_callbacks:
                        try:
                            callback(funds)
                        except Exception as e:
                            logger.error(f"Error in fund callback: {e}")
                    
                    logger.debug("Funds fetched via API")
                
                except TokenExpiredError:
                    logger.error("Token expired while fetching funds")
                    break
                except Exception as e:
                    logger.error(f"Error polling funds: {e}")
                
                # Determine wait interval
                if self.market_time.is_market_open():
                    await asyncio.sleep(1)  # 1 second during market hours
                else:
                    await asyncio.sleep(900)  # 15 minutes outside market hours
        
        except asyncio.CancelledError:
            pass
    
    async def _poll_profile(self):
        """Poll profile every 15 minutes"""
        try:
            while self.running:
                try:
                    # Fetch profile
                    profile = self.broker.get_profile()
                    self.profile_cache = profile
                    self.profile_cache_time = datetime.now(IST)
                    
                    logger.debug("Profile fetched via API")
                
                except TokenExpiredError:
                    logger.error("Token expired while fetching profile")
                    break
                except Exception as e:
                    logger.error(f"Error polling profile: {e}")
                
                await asyncio.sleep(900)  # 15 minutes always
        
        except asyncio.CancelledError:
            pass
    
    async def start_ltp_fallback(self, instruments: List[str]):
        """Start LTP fallback polling (when webhook is not flowing)"""
        if self.ltp_fallback_active:
            return
        
        self.ltp_fallback_active = True
        self.ltp_fallback_task = asyncio.create_task(self._poll_ltp_fallback(instruments))
        logger.info(f"✓ LTP fallback polling started for {len(instruments)} instruments")
    
    async def stop_ltp_fallback(self):
        """Stop LTP fallback polling"""
        self.ltp_fallback_active = False
        
        if self.ltp_fallback_task:
            self.ltp_fallback_task.cancel()
            try:
                await self.ltp_fallback_task
            except asyncio.CancelledError:
                pass
            self.ltp_fallback_task = None
        
        logger.info("LTP fallback polling stopped")
    
    async def _poll_ltp_fallback(self, instruments: List[str]):
        """Poll LTP via API when webhook is not working"""
        try:
            while self.ltp_fallback_active and self.running:
                try:
                    # Fetch LTP for all instruments
                    ltp_data = self.broker.get_ltp(instruments)
                    
                    # Update cache
                    for instrument, data in ltp_data.items():
                        if isinstance(data, dict):
                            ltp = data.get('last_price', 0.0)
                        else:
                            ltp = data
                        
                        self.ltp_cache[instrument] = ltp
                        
                        # Notify callbacks
                        for callback in self.ltp_fallback_callbacks:
                            try:
                                # Extract instrument token from "EXCHANGE:SYMBOL" format
                                callback(instrument, ltp, data)
                            except Exception as e:
                                logger.error(f"Error in LTP fallback callback: {e}")
                    
                    logger.debug(f"LTP fallback: Fetched {len(ltp_data)} instruments via API")
                
                except TokenExpiredError:
                    logger.error("Token expired while fetching LTP")
                    break
                except Exception as e:
                    logger.error(f"Error in LTP fallback polling: {e}")
                
                # Wait 1 second before next poll (during market hours)
                # Outside market hours, use 15 minute interval
                if self.market_time.is_market_open():
                    await asyncio.sleep(1)
                else:
                    await asyncio.sleep(900)
        
        except asyncio.CancelledError:
            pass
    
    def register_position_callback(self, callback: Callable):
        """Register callback for position updates"""
        self.position_callbacks.append(callback)
    
    def register_fund_callback(self, callback: Callable):
        """Register callback for fund updates"""
        self.fund_callbacks.append(callback)
    
    def register_ltp_fallback_callback(self, callback: Callable):
        """Register callback for LTP fallback updates"""
        self.ltp_fallback_callbacks.append(callback)
    
    def get_cached_positions(self) -> Optional[Dict]:
        """Get cached positions"""
        return self.positions_cache
    
    def get_cached_funds(self) -> Optional[Dict]:
        """Get cached funds"""
        return self.funds_cache
    
    def get_cached_profile(self) -> Optional[Dict]:
        """Get cached profile"""
        return self.profile_cache


class UnifiedBrokerMiddleware:
    """
    Unified middleware for all broker data interactions
    Manages webhook connections, API polling, and data aggregation
    """
    
    def __init__(self, broker: BaseBroker, db: Session):
        self.broker = broker
        self.db = db
        
        # Initialize market time service
        self.market_time = MarketTimeService(db)
        
        # Initialize sub-components
        self.webhook_manager = WebhookConnectionManager(broker, self.market_time)
        self.polling_scheduler = DataPollingScheduler(broker, self.market_time)
        
        # Data aggregator state
        self.running = False
        self.subscribed_instruments_for_ltp: List[str] = []
        
        # Callback for unified LTP updates (webhook + API fallback)
        self.ltp_update_callbacks: List[Callable] = []
        
        # Monitoring task
        self.monitor_task: Optional[asyncio.Task] = None
        
        logger.info("UnifiedBrokerMiddleware initialized")
        
        # Wire up callbacks
        self._setup_callbacks()
    
    def _setup_callbacks(self):
        """Set up callback connections between components"""
        
        # LTP updates from webhook
        self.webhook_manager.register_ltp_callback(self._handle_webhook_ltp)
        
        # LTP fallback from API polling
        self.polling_scheduler.register_ltp_fallback_callback(self._handle_fallback_ltp)
    
    def _handle_webhook_ltp(self, instrument_token: int, ltp: float, tick_data: Dict):
        """Handle LTP update from webhook"""
        # Notify all registered callbacks
        for callback in self.ltp_update_callbacks:
            try:
                callback(str(instrument_token), ltp, tick_data, source="webhook")
            except Exception as e:
                logger.error(f"Error in LTP update callback: {e}")
    
    def _handle_fallback_ltp(self, instrument: str, ltp: float, data: Dict):
        """Handle LTP update from API fallback"""
        # Notify all registered callbacks
        for callback in self.ltp_update_callbacks:
            try:
                callback(instrument, ltp, data, source="api_fallback")
            except Exception as e:
                logger.error(f"Error in LTP fallback callback: {e}")
    
    async def start(self):
        """Start the unified middleware"""
        if self.running:
            logger.warning("UnifiedBrokerMiddleware already running")
            return
        
        self.running = True
        
        # Start sub-components
        await self.webhook_manager.start()
        await self.polling_scheduler.start()
        
        # Start monitoring task
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        
        logger.info("✅ UnifiedBrokerMiddleware started")
    
    async def stop(self):
        """Stop the unified middleware"""
        self.running = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        # Stop sub-components
        await self.webhook_manager.stop()
        await self.polling_scheduler.stop()
        
        logger.info("UnifiedBrokerMiddleware stopped")
    
    async def _monitor_loop(self):
        """Monitor webhook status and activate fallback if needed"""
        try:
            while self.running:
                # Check if webhook data is flowing
                webhook_active = self.webhook_manager.is_data_flowing()
                
                # Check if we're in market hours
                in_market_hours = self.market_time.is_webhook_connection_time()
                
                # Determine if we need LTP fallback
                if in_market_hours and not webhook_active and self.subscribed_instruments_for_ltp:
                    # Webhook not flowing during market hours - activate fallback
                    if not self.polling_scheduler.ltp_fallback_active:
                        logger.warning("⚠️ Webhook not flowing - activating API fallback for LTP")
                        await self.polling_scheduler.start_ltp_fallback(
                            self.subscribed_instruments_for_ltp
                        )
                
                elif webhook_active and self.polling_scheduler.ltp_fallback_active:
                    # Webhook resumed - deactivate fallback
                    logger.info("✓ Webhook data resumed - deactivating API fallback")
                    await self.polling_scheduler.stop_ltp_fallback()
                
                await asyncio.sleep(2)  # Check every 2 seconds
        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in monitor loop: {e}")
    
    # ==================== Public API ====================
    
    def subscribe_ltp(self, instruments: List[str], instrument_tokens: List[int]):
        """
        Subscribe to LTP updates for instruments
        
        Args:
            instruments: List of instruments in "EXCHANGE:SYMBOL" format (for API)
            instrument_tokens: List of instrument tokens (for WebSocket)
        """
        self.subscribed_instruments_for_ltp = instruments
        
        # Subscribe via webhook
        self.webhook_manager.subscribe(instrument_tokens)
        
        logger.info(f"Subscribed to LTP for {len(instruments)} instruments")
    
    def unsubscribe_ltp(self, instrument_tokens: List[int]):
        """Unsubscribe from LTP updates"""
        self.webhook_manager.unsubscribe(instrument_tokens)
        
        # Update subscribed list
        # Note: This is simplified - in production you'd track per-instrument subscriptions
        logger.info(f"Unsubscribed from {len(instrument_tokens)} instruments")
    
    def register_ltp_callback(self, callback: Callable):
        """
        Register callback for LTP updates
        
        Callback signature: callback(instrument: str, ltp: float, data: Dict, source: str)
        """
        self.ltp_update_callbacks.append(callback)
    
    def register_position_callback(self, callback: Callable):
        """Register callback for position updates"""
        self.polling_scheduler.register_position_callback(callback)
    
    def register_fund_callback(self, callback: Callable):
        """Register callback for fund updates"""
        self.polling_scheduler.register_fund_callback(callback)
    
    # ==================== Data Access Methods ====================
    
    def get_ltp(self, instruments: List[str]) -> Dict[str, float]:
        """
        Get LTP for instruments (uses cache or API)
        
        Args:
            instruments: List of instruments in "EXCHANGE:SYMBOL" format
        
        Returns:
            Dict mapping instrument to LTP
        """
        # During market hours with webhook active, use webhook cache
        if self.webhook_manager.is_data_flowing():
            # TODO: Implement webhook cache lookup
            pass
        
        # Otherwise, use API
        try:
            return self.broker.get_ltp(instruments)
        except Exception as e:
            logger.error(f"Error getting LTP: {e}")
            return {}
    
    def get_quote(self, instruments: List[str], use_cache: bool = True) -> Dict[str, Any]:
        """
        Get full quote data for instruments (includes OHLC, LTP, volume, etc.)
        
        Args:
            instruments: List of instruments in "EXCHANGE:SYMBOL" format
            use_cache: Whether to use cached data (currently not cached, always fresh)
        
        Returns:
            Dict mapping instrument to quote data with OHLC, LTP, volume, etc.
        """
        # Currently pass-through to broker as quotes are lightweight and frequently needed fresh
        # TODO: Could implement short-lived cache (5-10 seconds) for frequently accessed quotes
        try:
            return self.broker.get_quote(instruments)
        except Exception as e:
            logger.error(f"Error getting quote: {e}")
            return {}
    
    def get_positions(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get positions (uses cache if available and fresh)
        
        Args:
            use_cache: Whether to use cached data
        
        Returns:
            Positions data
        """
        if use_cache:
            cached = self.polling_scheduler.get_cached_positions()
            if cached:
                return cached
        
        # Fetch fresh data
        try:
            return self.broker.get_positions()
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return {'net': [], 'day': []}
    
    def get_funds(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get funds (uses cache if available and fresh)
        
        Args:
            use_cache: Whether to use cached data
        
        Returns:
            Funds data
        """
        if use_cache:
            cached = self.polling_scheduler.get_cached_funds()
            if cached:
                return cached
        
        # Fetch fresh data
        try:
            return self.broker.get_funds()
        except Exception as e:
            logger.error(f"Error getting funds: {e}")
            return {}
    
    def get_profile(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get profile (uses cache if available and fresh)
        
        Args:
            use_cache: Whether to use cached data
        
        Returns:
            Profile data
        """
        if use_cache:
            cached = self.polling_scheduler.get_cached_profile()
            if cached:
                return cached
        
        # Fetch fresh data
        try:
            return self.broker.get_profile()
        except Exception as e:
            logger.error(f"Error getting profile: {e}")
            return {}
    
    # ==================== Order Operations (Pass-through) ====================
    
    def place_order(self, **kwargs) -> Dict[str, Any]:
        """Place order (immediate, no caching)"""
        return self.broker.place_order(**kwargs)
    
    def modify_order(self, order_id: str, **kwargs) -> Dict[str, Any]:
        """Modify order (immediate, no caching)"""
        return self.broker.modify_order(order_id, **kwargs)
    
    def cancel_order(self, order_id: str, **kwargs) -> Dict[str, Any]:
        """Cancel order (immediate, no caching)"""
        return self.broker.cancel_order(order_id, **kwargs)
    
    def get_orders(self, use_cache: bool = False) -> List[Dict[str, Any]]:
        """Get orders (typically no caching for orders)"""
        return self.broker.get_orders()
    
    def get_order_history(self, order_id: str) -> List[Dict[str, Any]]:
        """Get order history (no caching)"""
        return self.broker.get_order_history(order_id)
    
    # ==================== Instrument Operations ====================
    
    def get_instruments(self, exchange: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get instruments (should be called once per day, managed externally)"""
        return self.broker.get_instruments(exchange=exchange)
    
    def get_historical_data(self, **kwargs) -> List[Dict[str, Any]]:
        """Get historical data (pass-through, no special handling)"""
        return self.broker.get_historical_data(**kwargs)
    
    # ==================== Status Methods ====================
    
    def get_status(self) -> Dict[str, Any]:
        """Get middleware status"""
        return {
            "running": self.running,
            "market_hours_active": self.market_time.is_market_open(),
            "webhook_connection_time": self.market_time.is_webhook_connection_time(),
            "webhook_connected": self.webhook_manager.is_connected,
            "webhook_data_flowing": self.webhook_manager.is_data_flowing(),
            "ltp_fallback_active": self.polling_scheduler.ltp_fallback_active,
            "subscribed_instruments": len(self.webhook_manager.subscribed_instruments),
            "polling_active": self.polling_scheduler.running
        }


# ==================== Factory Function ====================

_middleware_instance: Optional[UnifiedBrokerMiddleware] = None


def get_unified_broker_middleware(broker: BaseBroker, db: Session) -> UnifiedBrokerMiddleware:
    """
    Get or create UnifiedBrokerMiddleware instance
    
    Args:
        broker: Broker client
        db: Database session
    
    Returns:
        UnifiedBrokerMiddleware instance
    """
    global _middleware_instance
    
    if _middleware_instance is None:
        _middleware_instance = UnifiedBrokerMiddleware(broker, db)
    
    return _middleware_instance


def reset_middleware():
    """Reset middleware instance (for testing)"""
    global _middleware_instance
    _middleware_instance = None
