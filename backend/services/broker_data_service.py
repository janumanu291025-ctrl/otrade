"""
Unified Broker Data Service
===========================

This service consolidates all broker data access across backtesting, paper trading, and live trading.
It provides a unified interface for:
- Historical data (OHLC, candles)
- Live market data (LTP, quotes, market depth)
- Instruments (symbols, contracts)
- Orders (placement, modification, cancellation, tracking)
- Positions (current positions, holdings)
- Funds (available balance, margins)
- User profile

Features:
- Unified caching mechanism
- Error handling and retry logic
- Mode-aware data fetching (historical vs live)
- Websocket integration for real-time data
"""

from typing import Dict, List, Optional, Any, Literal
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import logging
import asyncio
from functools import lru_cache
import time

from backend.broker.base import BaseBroker, BrokerError, TokenExpiredError
from backend.broker.factory import get_broker_client

logger = logging.getLogger(__name__)


class BrokerDataCache:
    """Thread-safe cache for broker data with TTL"""
    
    def __init__(self):
        self._cache = {}
        self._cache_timestamps = {}
        self._default_ttl = {
            'instruments': 3600,      # 1 hour - instruments don't change often
            'profile': 3600,          # 1 hour
            'funds': 60,              # 1 minute
            'positions': 30,          # 30 seconds
            'orders': 10,             # 10 seconds
            'ltp': 1,                 # 1 second
            'quote': 2,               # 2 seconds
            'historical_minute': 60,  # 1 minute for minute candles
            'historical_day': 3600,   # 1 hour for day candles
        }
    
    def get(self, key: str, ttl: Optional[int] = None) -> Optional[Any]:
        """Get cached value if not expired"""
        if key not in self._cache:
            return None
        
        # Check if expired
        cache_time = self._cache_timestamps.get(key, 0)
        if ttl is None:
            # Auto-detect TTL from key prefix
            ttl = self._get_ttl_from_key(key)
        
        if time.time() - cache_time > ttl:
            # Expired
            self._cache.pop(key, None)
            self._cache_timestamps.pop(key, None)
            return None
        
        return self._cache[key]
    
    def set(self, key: str, value: Any):
        """Set cached value"""
        self._cache[key] = value
        self._cache_timestamps[key] = time.time()
    
    def invalidate(self, key: str):
        """Invalidate specific cache key"""
        self._cache.pop(key, None)
        self._cache_timestamps.pop(key, None)
    
    def invalidate_pattern(self, pattern: str):
        """Invalidate all keys matching pattern"""
        keys_to_remove = [k for k in self._cache.keys() if pattern in k]
        for key in keys_to_remove:
            self._cache.pop(key, None)
            self._cache_timestamps.pop(key, None)
    
    def clear(self):
        """Clear entire cache"""
        self._cache.clear()
        self._cache_timestamps.clear()
    
    def _get_ttl_from_key(self, key: str) -> int:
        """Get TTL based on key prefix"""
        for prefix, ttl in self._default_ttl.items():
            if key.startswith(prefix):
                return ttl
        return 60  # Default 60 seconds


class BrokerDataService:
    """
    Unified broker data service
    
    This service abstracts all broker interactions and provides:
    - Consistent data access for backtest, paper trading, and live trading
    - Intelligent caching to reduce API calls
    - Error handling and retry logic
    - Mode-aware data fetching
    """
    
    def __init__(
        self,
        broker: BaseBroker,
        mode: Literal['backtest', 'paper', 'live'] = 'live',
        enable_cache: bool = True
    ):
        """
        Initialize broker data service
        
        Args:
            broker: Broker client instance
            mode: Trading mode - 'backtest', 'paper', or 'live'
            enable_cache: Whether to enable caching
        """
        self.broker = broker
        self.mode = mode
        self.cache = BrokerDataCache() if enable_cache else None
        self._websocket_active = False
        self._websocket_callbacks = []
        
        logger.info(f"BrokerDataService initialized in '{mode}' mode")
    
    # ========== User Profile & Authentication ==========
    
    def get_profile(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get user profile
        
        Args:
            use_cache: Whether to use cached data
            
        Returns:
            Dict with user_id, user_name, email, broker, exchanges, etc.
        """
        cache_key = 'profile'
        
        if use_cache and self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug("Profile retrieved from cache")
                return cached
        
        try:
            profile = self.broker.get_profile()
            if self.cache:
                self.cache.set(cache_key, profile)
            logger.info(f"Profile fetched for user: {profile.get('user_id')}")
            return profile
        except TokenExpiredError:
            # Re-raise token expiry errors to propagate to engine
            raise

        except Exception as e:
            logger.error(f"Error fetching profile: {e}")
            raise BrokerError(f"Failed to fetch profile: {e}")
    
    # ========== Funds & Margins ==========
    
    def get_funds(self, segment: Optional[str] = None, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get available funds and margins
        
        Args:
            segment: Optional segment ('equity' or 'commodity')
            use_cache: Whether to use cached data
            
        Returns:
            Dict with enabled, net, available, utilised margins
        """
        cache_key = f'funds_{segment or "all"}'
        
        if use_cache and self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug("Funds retrieved from cache")
                return cached
        
        try:
            funds = self.broker.get_funds(segment=segment)
            if self.cache:
                self.cache.set(cache_key, funds)
            logger.info(f"Funds fetched: {funds}")
            return funds
        except TokenExpiredError:
            # Re-raise token expiry errors to propagate to engine
            raise

        except Exception as e:
            logger.error(f"Error fetching funds: {e}")
            raise BrokerError(f"Failed to fetch funds: {e}")
    
    # ========== Instruments ==========
    
    def get_instruments(
        self,
        exchange: Optional[str] = None,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get all tradeable instruments
        
        Args:
            exchange: Optional exchange filter (NSE, BSE, NFO, etc.)
            use_cache: Whether to use cached data
            
        Returns:
            List of instruments with token, symbol, expiry, strike, etc.
        """
        cache_key = f'instruments_{exchange or "all"}'
        
        if use_cache and self.cache:
            cached = self.cache.get(cache_key, ttl=3600)  # 1 hour cache
            if cached:
                logger.debug(f"Instruments retrieved from cache for {exchange or 'all'}")
                return cached
        
        try:
            instruments = self.broker.get_instruments(exchange=exchange)
            if self.cache:
                self.cache.set(cache_key, instruments)
            logger.info(f"Fetched {len(instruments)} instruments for {exchange or 'all exchanges'}")
            return instruments
        except TokenExpiredError:
            # Re-raise token expiry errors to propagate to engine
            raise

        except Exception as e:
            logger.error(f"Error fetching instruments: {e}")
            raise BrokerError(f"Failed to fetch instruments: {e}")
    
    def search_instruments(
        self,
        search_term: str,
        exchange: Optional[str] = None,
        instrument_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for instruments by symbol/name
        
        Args:
            search_term: Search string
            exchange: Optional exchange filter
            instrument_type: Optional type filter (EQ, CE, PE, FUT)
            
        Returns:
            List of matching instruments
        """
        instruments = self.get_instruments(exchange=exchange)
        
        # Filter by search term
        search_term = search_term.upper()
        results = [
            inst for inst in instruments
            if search_term in inst.get('tradingsymbol', '').upper()
            or search_term in inst.get('name', '').upper()
        ]
        
        # Filter by instrument type
        if instrument_type:
            results = [
                inst for inst in results
                if inst.get('instrument_type') == instrument_type
            ]
        
        logger.debug(f"Found {len(results)} instruments matching '{search_term}'")
        return results
    
    # ========== Market Data - Live ==========
    
    def get_ltp(
        self,
        instruments: List[str],
        use_cache: bool = False
    ) -> Dict[str, float]:
        """
        Get last traded price for instruments
        
        Args:
            instruments: List of instrument symbols in "EXCHANGE:SYMBOL" format
            use_cache: Whether to use cached data (default False for live prices)
            
        Returns:
            Dict mapping instrument to LTP
        """
        cache_key = f'ltp_{"_".join(instruments)}'
        
        if use_cache and self.cache:
            cached = self.cache.get(cache_key, ttl=1)
            if cached:
                logger.debug("LTP retrieved from cache")
                return cached
        
        try:
            ltp_data = self.broker.get_ltp(instruments)
            
            # Extract just the LTP values
            result = {}
            for inst, data in ltp_data.items():
                if isinstance(data, dict):
                    result[inst] = data.get('last_price', 0.0)
                else:
                    result[inst] = data
            
            if self.cache:
                self.cache.set(cache_key, result)
            
            logger.debug(f"Fetched LTP for {len(instruments)} instruments")
            return result
        except TokenExpiredError:
            # Re-raise token expiry errors to propagate to engine
            raise

        except Exception as e:
            logger.error(f"Error fetching LTP: {e}")
            raise BrokerError(f"Failed to fetch LTP: {e}")
    
    def get_quote(
        self,
        instruments: List[str],
        use_cache: bool = False
    ) -> Dict[str, Any]:
        """
        Get full market quotes
        
        Args:
            instruments: List of instrument symbols
            use_cache: Whether to use cached data
            
        Returns:
            Dict with complete quote data including OHLC, depth, etc.
        """
        cache_key = f'quote_{"_".join(instruments)}'
        
        if use_cache and self.cache:
            cached = self.cache.get(cache_key, ttl=2)
            if cached:
                logger.debug("Quote retrieved from cache")
                return cached
        
        try:
            quotes = self.broker.get_quote(instruments)
            if self.cache:
                self.cache.set(cache_key, quotes)
            logger.debug(f"Fetched quotes for {len(instruments)} instruments")
            return quotes
        except TokenExpiredError:
            # Re-raise token expiry errors to propagate to engine
            raise

        except Exception as e:
            logger.error(f"Error fetching quotes: {e}")
            raise BrokerError(f"Failed to fetch quotes: {e}")
    
    def get_ohlc(
        self,
        instruments: List[str],
        use_cache: bool = False
    ) -> Dict[str, Any]:
        """
        Get OHLC data for instruments
        
        Args:
            instruments: List of instrument symbols
            use_cache: Whether to use cached data
            
        Returns:
            Dict with OHLC data
        """
        try:
            ohlc_data = self.broker.get_ohlc(instruments)
            logger.debug(f"Fetched OHLC for {len(instruments)} instruments")
            return ohlc_data
        except TokenExpiredError:
            # Re-raise token expiry errors to propagate to engine
            raise

        except Exception as e:
            logger.error(f"Error fetching OHLC: {e}")
            raise BrokerError(f"Failed to fetch OHLC: {e}")
    
    # ========== Historical Data ==========
    
    def get_historical_data(
        self,
        instrument_token: str,
        from_date: datetime,
        to_date: datetime,
        interval: str = "minute",
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get historical OHLC candle data
        
        Args:
            instrument_token: Instrument token
            from_date: Start date
            to_date: End date
            interval: Candle interval (minute, 3minute, 5minute, 15minute, 30minute, 60minute, day)
            use_cache: Whether to use cached data
            
        Returns:
            List of candles with date, open, high, low, close, volume
        """
        # Create cache key
        cache_key = f'historical_{interval}_{instrument_token}_{from_date.date()}_{to_date.date()}'
        
        if use_cache and self.cache:
            ttl = 3600 if interval == 'day' else 60  # Day data cached longer
            cached = self.cache.get(cache_key, ttl=ttl)
            if cached:
                logger.debug(f"Historical data retrieved from cache for {instrument_token}")
                return cached
        
        try:
            candles = self.broker.get_historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval=interval
            )
            
            if self.cache:
                self.cache.set(cache_key, candles)
            
            logger.info(
                f"Fetched {len(candles)} {interval} candles for {instrument_token} "
                f"from {from_date.date()} to {to_date.date()}"
            )
            return candles
        except TokenExpiredError:
            # Re-raise token expiry errors to propagate to engine
            raise

        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            raise BrokerError(f"Failed to fetch historical data: {e}")
    
    def get_historical_data_with_retry(
        self,
        instrument_token: str,
        from_date: datetime,
        to_date: datetime,
        interval: str = "minute",
        max_retries: int = 3,
        retry_delay: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Get historical data with retry logic
        
        Args:
            instrument_token: Instrument token
            from_date: Start date
            to_date: End date
            interval: Candle interval
            max_retries: Maximum retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            List of candles
        """
        for attempt in range(max_retries):
            try:
                return self.get_historical_data(
                    instrument_token=instrument_token,
                    from_date=from_date,
                    to_date=to_date,
                    interval=interval,
                    use_cache=True
                )
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Attempt {attempt + 1} failed for historical data, "
                        f"retrying in {retry_delay}s: {e}"
                    )
                    time.sleep(retry_delay)
                else:
                    logger.error(f"All {max_retries} attempts failed for historical data")
                    raise
    
    # ========== Orders ==========
    
    def place_order(
        self,
        tradingsymbol: str,
        exchange: str,
        transaction_type: str,
        quantity: int,
        order_type: str,
        product: str = "MIS",
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Place an order
        
        Args:
            tradingsymbol: Trading symbol
            exchange: Exchange (NSE, NFO, etc.)
            transaction_type: BUY or SELL
            quantity: Order quantity
            order_type: MARKET, LIMIT, SL, SL-M
            product: CNC, NRML, MIS
            price: Limit price (for LIMIT orders)
            trigger_price: Trigger price (for SL orders)
            **kwargs: Additional parameters
            
        Returns:
            Dict with order_id and status
        """
        # In backtest/paper mode, this would be simulated
        if self.mode in ['backtest', 'paper']:
            logger.warning(f"Simulated order in {self.mode} mode")
            return {
                'order_id': f'SIM_{int(time.time())}',
                'status': 'success',
                'message': f'Simulated order in {self.mode} mode'
            }
        
        try:
            result = self.broker.place_order(
                tradingsymbol=tradingsymbol,
                exchange=exchange,
                transaction_type=transaction_type,
                quantity=quantity,
                order_type=order_type,
                product=product,
                price=price,
                trigger_price=trigger_price,
                **kwargs
            )
            
            # Invalidate orders cache
            if self.cache:
                self.cache.invalidate_pattern('orders')
            
            logger.info(
                f"Order placed: {transaction_type} {quantity} {tradingsymbol} @ "
                f"{price or 'MARKET'} - Order ID: {result.get('order_id')}"
            )
            return result
        except TokenExpiredError:
            # Re-raise token expiry errors to propagate to engine
            raise

        except Exception as e:
            logger.error(f"Error placing order: {e}")
            raise BrokerError(f"Failed to place order: {e}")
    
    def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        order_type: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Modify an existing order
        
        Args:
            order_id: Order ID to modify
            quantity: New quantity
            price: New price
            order_type: New order type
            **kwargs: Additional parameters
            
        Returns:
            Dict with order_id and status
        """
        if self.mode in ['backtest', 'paper']:
            logger.warning(f"Simulated order modification in {self.mode} mode")
            return {'order_id': order_id, 'status': 'modified', 'message': 'Simulated'}
        
        try:
            result = self.broker.modify_order(
                order_id=order_id,
                quantity=quantity,
                price=price,
                order_type=order_type,
                **kwargs
            )
            
            # Invalidate cache
            if self.cache:
                self.cache.invalidate_pattern('orders')
            
            logger.info(f"Order {order_id} modified")
            return result
        except TokenExpiredError:
            # Re-raise token expiry errors to propagate to engine
            raise

        except Exception as e:
            logger.error(f"Error modifying order: {e}")
            raise BrokerError(f"Failed to modify order: {e}")
    
    def cancel_order(self, order_id: str, **kwargs) -> Dict[str, Any]:
        """
        Cancel an order
        
        Args:
            order_id: Order ID to cancel
            **kwargs: Additional parameters
            
        Returns:
            Dict with order_id and status
        """
        if self.mode in ['backtest', 'paper']:
            logger.warning(f"Simulated order cancellation in {self.mode} mode")
            return {'order_id': order_id, 'status': 'cancelled', 'message': 'Simulated'}
        
        try:
            result = self.broker.cancel_order(order_id=order_id, **kwargs)
            
            # Invalidate cache
            if self.cache:
                self.cache.invalidate_pattern('orders')
            
            logger.info(f"Order {order_id} cancelled")
            return result
        except TokenExpiredError:
            # Re-raise token expiry errors to propagate to engine
            raise

        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            raise BrokerError(f"Failed to cancel order: {e}")
    
    def get_orders(self, use_cache: bool = False) -> List[Dict[str, Any]]:
        """
        Get all orders for the day
        
        Args:
            use_cache: Whether to use cached data
            
        Returns:
            List of orders
        """
        cache_key = 'orders_all'
        
        if use_cache and self.cache:
            cached = self.cache.get(cache_key, ttl=10)
            if cached:
                logger.debug("Orders retrieved from cache")
                return cached
        
        try:
            orders = self.broker.get_orders()
            if self.cache:
                self.cache.set(cache_key, orders)
            logger.debug(f"Fetched {len(orders)} orders")
            return orders
        except TokenExpiredError:
            # Re-raise token expiry errors to propagate to engine
            raise

        except Exception as e:
            logger.error(f"Error fetching orders: {e}")
            raise BrokerError(f"Failed to fetch orders: {e}")
    
    def get_order_history(self, order_id: str) -> List[Dict[str, Any]]:
        """
        Get order history
        
        Args:
            order_id: Order ID
            
        Returns:
            List of order state changes
        """
        try:
            history = self.broker.get_order_history(order_id)
            logger.debug(f"Fetched history for order {order_id}")
            return history
        except TokenExpiredError:
            # Re-raise token expiry errors to propagate to engine
            raise

        except Exception as e:
            logger.error(f"Error fetching order history: {e}")
            raise BrokerError(f"Failed to fetch order history: {e}")
    
    # ========== Positions ==========
    
    def get_positions(self, use_cache: bool = False) -> Dict[str, Any]:
        """
        Get current positions
        
        Args:
            use_cache: Whether to use cached data
            
        Returns:
            Dict with 'net' and 'day' positions
        """
        cache_key = 'positions'
        
        if use_cache and self.cache:
            cached = self.cache.get(cache_key, ttl=30)
            if cached:
                logger.debug("Positions retrieved from cache")
                return cached
        
        try:
            positions = self.broker.get_positions()
            if self.cache:
                self.cache.set(cache_key, positions)
            
            net_count = len(positions.get('net', []))
            day_count = len(positions.get('day', []))
            logger.debug(f"Fetched {net_count} net positions and {day_count} day positions")
            return positions
        except TokenExpiredError:
            # Re-raise token expiry errors to propagate to engine
            raise

        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            raise BrokerError(f"Failed to fetch positions: {e}")
    
    def get_holdings(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Get holdings (long-term positions)
        
        Args:
            use_cache: Whether to use cached data
            
        Returns:
            List of holdings
        """
        cache_key = 'holdings'
        
        if use_cache and self.cache:
            cached = self.cache.get(cache_key, ttl=300)
            if cached:
                logger.debug("Holdings retrieved from cache")
                return cached
        
        try:
            holdings = self.broker.get_holdings()
            if self.cache:
                self.cache.set(cache_key, holdings)
            logger.debug(f"Fetched {len(holdings)} holdings")
            return holdings
        except TokenExpiredError:
            # Re-raise token expiry errors to propagate to engine
            raise

        except Exception as e:
            logger.error(f"Error fetching holdings: {e}")
            raise BrokerError(f"Failed to fetch holdings: {e}")
    
    # ========== WebSocket ==========
    
    def connect_websocket(
        self,
        instruments: List[int],
        on_tick_callback,
        mode: str = "full"
    ):
        """
        Connect to websocket for real-time data (only during webhook connection time: 9:00 AM - 3:30 PM)
        
        Args:
            instruments: List of instrument tokens
            on_tick_callback: Callback function for tick data
            mode: Streaming mode ('ltp', 'quote', 'full')
        """
        if self.mode == 'backtest':
            logger.warning("WebSocket not available in backtest mode")
            return
        
        # Check if it's webhook connection time before connecting
        from backend.database import SessionLocal
        from backend.services.market_time import is_webhook_connection_time
        
        db = SessionLocal()
        try:
            webhook_time_active = is_webhook_connection_time(db)
            if not webhook_time_active:
                logger.info("Outside webhook connection hours (9:00 AM - 3:30 PM) - WebSocket connection deferred")
                return
        finally:
            db.close()
        
        try:
            self.broker.connect_websocket(
                on_message_callback=on_tick_callback,
                instruments=instruments,
                mode=mode
            )
            self._websocket_active = True
            logger.info(f"✓ WebSocket connected for {len(instruments)} instruments in {mode} mode")
        except TokenExpiredError:
            # Re-raise token expiry errors to propagate to engine
            raise

        except Exception as e:
            logger.error(f"Error connecting websocket: {e}")
            raise BrokerError(f"Failed to connect websocket: {e}")
    
    def disconnect_websocket(self):
        """Disconnect websocket"""
        if not self._websocket_active:
            return
        
        try:
            self.broker.disconnect_websocket()
            self._websocket_active = False
            logger.info("WebSocket disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting websocket: {e}")
    
    # ========== Cache Management ==========
    
    def clear_cache(self):
        """Clear all cached data"""
        if self.cache:
            self.cache.clear()
            logger.info("Cache cleared")
    
    def invalidate_cache(self, pattern: str):
        """Invalidate cache entries matching pattern"""
        if self.cache:
            self.cache.invalidate_pattern(pattern)
            logger.debug(f"Invalidated cache for pattern: {pattern}")


def get_broker_data_service(
    db: Session,
    mode: Literal['backtest', 'paper', 'live'] = 'live',
    enable_cache: bool = True
) -> BrokerDataService:
    """
    Factory function to get BrokerDataService instance
    
    Args:
        db: Database session
        mode: Trading mode
        enable_cache: Whether to enable caching
        
    Returns:
        BrokerDataService instance
    """
    broker = get_broker_client(db, raise_exception=True)
    return BrokerDataService(broker=broker, mode=mode, enable_cache=enable_cache)
