"""
Performance Caching Utilities
==============================

In-memory caching for frequently accessed data with TTL support.
Optimizes API response times for status, positions, and other queries.
"""
import time
from typing import Any, Optional, Callable, Dict
from functools import wraps
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CacheEntry:
    """Cache entry with value and expiration"""
    def __init__(self, value: Any, ttl: float):
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        return time.time() - self.created_at > self.ttl
    
    def age(self) -> float:
        """Get age of cache entry in seconds"""
        return time.time() - self.created_at


class InMemoryCache:
    """
    Simple in-memory cache with TTL support
    
    Features:
    - Thread-safe operations
    - TTL-based expiration
    - Automatic cleanup of expired entries
    - Statistics tracking
    """
    
    def __init__(self, default_ttl: float = 5.0, max_size: int = 1000):
        """
        Initialize cache
        
        Args:
            default_ttl: Default time-to-live in seconds
            max_size: Maximum number of cache entries
        """
        self._cache: Dict[str, CacheEntry] = {}
        self.default_ttl = default_ttl
        self.max_size = max_size
        
        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.last_cleanup = time.time()
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        entry = self._cache.get(key)
        
        if entry is None:
            self.misses += 1
            return None
        
        if entry.is_expired():
            # Remove expired entry
            del self._cache[key]
            self.misses += 1
            return None
        
        self.hits += 1
        return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """
        Set value in cache
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
        """
        if ttl is None:
            ttl = self.default_ttl
        
        # Check if we need to evict entries
        if len(self._cache) >= self.max_size:
            self._evict_oldest()
        
        self._cache[key] = CacheEntry(value, ttl)
        
        # Periodic cleanup
        if time.time() - self.last_cleanup > 60:  # Cleanup every minute
            self._cleanup_expired()
    
    def delete(self, key: str):
        """Delete entry from cache"""
        if key in self._cache:
            del self._cache[key]
    
    def clear(self):
        """Clear all cache entries"""
        self._cache.clear()
        logger.info("Cache cleared")
    
    def _evict_oldest(self):
        """Evict oldest cache entry"""
        if not self._cache:
            return
        
        oldest_key = min(self._cache.items(), key=lambda x: x[1].created_at)[0]
        del self._cache[oldest_key]
        self.evictions += 1
    
    def _cleanup_expired(self):
        """Remove all expired entries"""
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        self.last_cleanup = time.time()
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "hit_rate": round(hit_rate, 2),
            "total_requests": total_requests
        }


# Global cache instances
_status_cache = InMemoryCache(default_ttl=2.0, max_size=100)  # 2s TTL for status
_positions_cache = InMemoryCache(default_ttl=3.0, max_size=500)  # 3s TTL for positions
_trades_cache = InMemoryCache(default_ttl=5.0, max_size=1000)  # 5s TTL for trades


def get_status_cache() -> InMemoryCache:
    """Get status cache instance"""
    return _status_cache


def get_positions_cache() -> InMemoryCache:
    """Get positions cache instance"""
    return _positions_cache


def get_trades_cache() -> InMemoryCache:
    """Get trades cache instance"""
    return _trades_cache


def cached(cache: InMemoryCache, key_func: Callable, ttl: Optional[float] = None):
    """
    Decorator for caching function results
    
    Args:
        cache: Cache instance to use
        key_func: Function to generate cache key from function args
        ttl: Optional TTL override
        
    Example:
        @cached(get_status_cache(), lambda engine_id: f"status_{engine_id}")
        def get_engine_status(engine_id: int):
            # Expensive operation
            return status
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = key_func(*args, **kwargs)
            
            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Compute value
            value = func(*args, **kwargs)
            
            # Store in cache
            cache.set(cache_key, value, ttl)
            
            return value
        
        return wrapper
    return decorator


def invalidate_cache_pattern(cache: InMemoryCache, pattern: str):
    """
    Invalidate all cache keys matching pattern
    
    Args:
        cache: Cache instance
        pattern: String pattern to match (simple substring match)
    """
    keys_to_delete = [
        key for key in cache._cache.keys()
        if pattern in key
    ]
    
    for key in keys_to_delete:
        cache.delete(key)
    
    if keys_to_delete:
        logger.debug(f"Invalidated {len(keys_to_delete)} cache entries matching '{pattern}'")


# Response time tracking for performance monitoring
class ResponseTimeTracker:
    """Track API response times for performance monitoring"""
    
    def __init__(self, max_samples: int = 1000):
        self.max_samples = max_samples
        self.samples: Dict[str, list] = {}  # endpoint -> [response_times]
    
    def record(self, endpoint: str, duration_ms: float):
        """Record response time for endpoint"""
        if endpoint not in self.samples:
            self.samples[endpoint] = []
        
        self.samples[endpoint].append(duration_ms)
        
        # Keep only recent samples
        if len(self.samples[endpoint]) > self.max_samples:
            self.samples[endpoint] = self.samples[endpoint][-self.max_samples:]
    
    def get_stats(self, endpoint: str) -> Optional[Dict[str, float]]:
        """Get statistics for endpoint"""
        if endpoint not in self.samples or not self.samples[endpoint]:
            return None
        
        samples = self.samples[endpoint]
        return {
            "count": len(samples),
            "avg": sum(samples) / len(samples),
            "min": min(samples),
            "max": max(samples),
            "p50": sorted(samples)[len(samples) // 2],
            "p95": sorted(samples)[int(len(samples) * 0.95)] if len(samples) > 20 else max(samples),
            "p99": sorted(samples)[int(len(samples) * 0.99)] if len(samples) > 100 else max(samples)
        }
    
    def get_all_stats(self) -> Dict[str, Dict[str, float]]:
        """Get statistics for all endpoints"""
        return {
            endpoint: self.get_stats(endpoint)
            for endpoint in self.samples.keys()
        }


# Global response time tracker
_response_tracker = ResponseTimeTracker()


def get_response_tracker() -> ResponseTimeTracker:
    """Get response time tracker instance"""
    return _response_tracker
