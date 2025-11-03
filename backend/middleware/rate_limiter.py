"""
Rate Limiter Middleware for Kite Connect API
Implements rate limiting based on official Kite Connect API limits
"""
from typing import Dict, Optional, Callable
from datetime import datetime, timedelta
from collections import deque
import time
import asyncio
import logging
from functools import wraps

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter for Kite Connect API
    
    Implements rate limits:
    - Per second limits
    - Per minute limits
    - Per day limits (for orders)
    - Per order modification limits
    """
    
    def __init__(
        self,
        requests_per_second: float = 10.0,
        requests_per_minute: Optional[int] = None,
        requests_per_day: Optional[int] = None,
        burst: int = 20
    ):
        """
        Initialize rate limiter
        
        Args:
            requests_per_second: Requests allowed per second
            requests_per_minute: Requests allowed per minute (None = no limit)
            requests_per_day: Requests allowed per day (None = no limit)
            burst: Maximum burst capacity (tokens in bucket)
        """
        self.rate = requests_per_second
        self.burst = burst
        self.requests_per_minute = requests_per_minute
        self.requests_per_day = requests_per_day
        
        # Token bucket for per-second rate limiting
        self.tokens = float(burst)
        self.last_update = time.time()
        
        # Request history for per-minute limiting
        self.minute_requests = deque()
        
        # Request history for per-day limiting
        self.day_requests = deque()
        
        # Per-order modification tracking
        self.order_modifications: Dict[str, int] = {}
        
        # Lock for thread safety
        self.lock = asyncio.Lock()
    
    async def acquire(self, endpoint: str = "default", order_id: Optional[str] = None) -> bool:
        """
        Acquire permission to make a request
        
        Args:
            endpoint: API endpoint being called (for endpoint-specific limits)
            order_id: Order ID (for modification limit tracking)
        
        Returns:
            True if request is allowed, False if rate limited
        """
        async with self.lock:
            now = time.time()
            
            # Refill token bucket
            elapsed = now - self.last_update
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            # Check token bucket (per-second limit)
            if self.tokens < 1.0:
                logger.warning(f"Rate limit: Per-second limit exceeded for {endpoint}")
                return False
            
            # Check per-minute limit
            if self.requests_per_minute:
                # Remove requests older than 1 minute
                cutoff = now - 60
                while self.minute_requests and self.minute_requests[0] < cutoff:
                    self.minute_requests.popleft()
                
                if len(self.minute_requests) >= self.requests_per_minute:
                    logger.warning(f"Rate limit: Per-minute limit exceeded for {endpoint}")
                    return False
            
            # Check per-day limit
            if self.requests_per_day:
                # Remove requests older than 24 hours
                cutoff = now - 86400
                while self.day_requests and self.day_requests[0] < cutoff:
                    self.day_requests.popleft()
                
                if len(self.day_requests) >= self.requests_per_day:
                    logger.warning(f"Rate limit: Per-day limit exceeded for {endpoint}")
                    return False
            
            # Check order modification limit
            if order_id and endpoint == "modify_order":
                modifications = self.order_modifications.get(order_id, 0)
                if modifications >= 25:
                    logger.warning(f"Rate limit: Order {order_id} has reached max 25 modifications")
                    return False
            
            # Allow request - consume token and record
            self.tokens -= 1.0
            
            if self.requests_per_minute:
                self.minute_requests.append(now)
            
            if self.requests_per_day:
                self.day_requests.append(now)
            
            if order_id and endpoint == "modify_order":
                self.order_modifications[order_id] = modifications + 1
            
            return True
    
    async def wait_for_capacity(
        self,
        endpoint: str = "default",
        order_id: Optional[str] = None,
        max_wait: float = 10.0
    ) -> bool:
        """
        Wait until capacity is available (with timeout)
        
        Args:
            endpoint: API endpoint being called
            order_id: Order ID (for modification tracking)
            max_wait: Maximum wait time in seconds
        
        Returns:
            True if capacity acquired, False if timed out
        """
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            if await self.acquire(endpoint, order_id):
                return True
            
            # Wait a bit before retrying
            await asyncio.sleep(0.1)
        
        logger.error(f"Rate limit: Timed out waiting for capacity on {endpoint}")
        return False
    
    def get_stats(self) -> Dict[str, any]:
        """Get rate limiter statistics"""
        now = time.time()
        
        # Count requests in last minute
        cutoff_minute = now - 60
        minute_count = sum(1 for t in self.minute_requests if t >= cutoff_minute)
        
        # Count requests in last day
        cutoff_day = now - 86400
        day_count = sum(1 for t in self.day_requests if t >= cutoff_day)
        
        return {
            "tokens_available": self.tokens,
            "rate_per_second": self.rate,
            "burst_capacity": self.burst,
            "requests_last_minute": minute_count,
            "requests_last_day": day_count,
            "order_modifications": len(self.order_modifications),
            "orders_at_max_modifications": sum(
                1 for count in self.order_modifications.values() if count >= 25
            )
        }
    
    def reset_order_modifications(self):
        """Reset order modification counts (call at end of day)"""
        self.order_modifications.clear()
    
    def reset_daily_limits(self):
        """Reset daily limits (call at end of trading day)"""
        self.day_requests.clear()
        self.order_modifications.clear()


class KiteRateLimitManager:
    """
    Manages rate limiters for different Kite Connect endpoints
    """
    
    def __init__(self):
        """Initialize rate limiters for each endpoint category"""
        # Quote endpoint: 1 req/sec
        self.quote_limiter = RateLimiter(
            requests_per_second=1.0,
            requests_per_minute=60,
            burst=2
        )
        
        # Historical data: 3 req/sec
        self.historical_limiter = RateLimiter(
            requests_per_second=3.0,
            requests_per_minute=180,
            burst=5
        )
        
        # Order placement: 10 req/sec, 200/min, 3000/day
        self.order_placement_limiter = RateLimiter(
            requests_per_second=10.0,
            requests_per_minute=200,
            requests_per_day=3000,
            burst=15
        )
        
        # Order modification: 10 req/sec, 25 per order
        self.order_modification_limiter = RateLimiter(
            requests_per_second=10.0,
            requests_per_minute=200,
            burst=15
        )
        
        # Default (other endpoints): 10 req/sec
        self.default_limiter = RateLimiter(
            requests_per_second=10.0,
            requests_per_minute=600,
            burst=20
        )
        
        # Endpoint mapping
        self.endpoint_map = {
            "quote": self.quote_limiter,
            "get_quote": self.quote_limiter,
            "get_ohlc": self.quote_limiter,
            "get_ltp": self.quote_limiter,
            "historical": self.historical_limiter,
            "get_historical_data": self.historical_limiter,
            "place_order": self.order_placement_limiter,
            "modify_order": self.order_modification_limiter,
            "cancel_order": self.default_limiter,
        }
    
    def get_limiter(self, endpoint: str) -> RateLimiter:
        """Get appropriate rate limiter for endpoint"""
        return self.endpoint_map.get(endpoint, self.default_limiter)
    
    async def acquire(self, endpoint: str, order_id: Optional[str] = None) -> bool:
        """Acquire permission for endpoint request"""
        limiter = self.get_limiter(endpoint)
        return await limiter.acquire(endpoint, order_id)
    
    async def wait_for_capacity(
        self,
        endpoint: str,
        order_id: Optional[str] = None,
        max_wait: float = 10.0
    ) -> bool:
        """Wait for capacity on endpoint"""
        limiter = self.get_limiter(endpoint)
        return await limiter.wait_for_capacity(endpoint, order_id, max_wait)
    
    def get_all_stats(self) -> Dict[str, Dict[str, any]]:
        """Get statistics for all limiters"""
        return {
            "quote": self.quote_limiter.get_stats(),
            "historical": self.historical_limiter.get_stats(),
            "order_placement": self.order_placement_limiter.get_stats(),
            "order_modification": self.order_modification_limiter.get_stats(),
            "default": self.default_limiter.get_stats()
        }
    
    def reset_daily_limits(self):
        """Reset all daily limits (call at end of trading day)"""
        self.order_placement_limiter.reset_daily_limits()
        self.order_modification_limiter.reset_order_modifications()


# Global rate limit manager
rate_limit_manager = KiteRateLimitManager()


def rate_limited(endpoint: str = "default"):
    """
    Decorator for rate limiting async functions
    
    Usage:
        @rate_limited("place_order")
        async def place_order(...):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract order_id if present in kwargs
            order_id = kwargs.get('order_id')
            
            # Wait for capacity (with 10 second timeout)
            if not await rate_limit_manager.wait_for_capacity(endpoint, order_id, max_wait=10.0):
                from backend.broker.kite.exceptions import RateLimitException
                raise RateLimitException(
                    message=f"Rate limit exceeded for {endpoint}",
                    endpoint=endpoint
                )
            
            # Call the original function
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def rate_limited_sync(endpoint: str = "default"):
    """
    Decorator for rate limiting synchronous functions
    
    Usage:
        @rate_limited_sync("get_quote")
        def get_quote(...):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Run async acquire in sync context
            loop = None
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            order_id = kwargs.get('order_id')
            
            # Wait for capacity
            if not loop.run_until_complete(
                rate_limit_manager.wait_for_capacity(endpoint, order_id, max_wait=10.0)
            ):
                from backend.broker.kite.exceptions import RateLimitException
                raise RateLimitException(
                    message=f"Rate limit exceeded for {endpoint}",
                    endpoint=endpoint
                )
            
            # Call the original function
            return func(*args, **kwargs)
        
        return wrapper
    return decorator
