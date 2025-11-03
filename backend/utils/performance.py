"""
Performance Monitoring Middleware
==================================

Middleware to track API response times and provide performance insights.
"""
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.utils.cache import get_response_tracker

logger = logging.getLogger(__name__)


class PerformanceMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track API response times
    
    Logs slow requests and provides performance metrics.
    """
    
    def __init__(self, app, slow_threshold_ms: float = 500):
        """
        Initialize middleware
        
        Args:
            app: FastAPI application
            slow_threshold_ms: Threshold for logging slow requests (milliseconds)
        """
        super().__init__(app)
        self.slow_threshold_ms = slow_threshold_ms
        self.tracker = get_response_tracker()
    
    async def dispatch(self, request: Request, call_next):
        """Process request and track timing"""
        # Skip for health checks and static files
        if request.url.path in ["/health", "/", "/docs", "/openapi.json"]:
            return await call_next(request)
        
        start_time = time.time()
        
        try:
            response = await call_next(request)
        except Exception as e:
            # Track failed requests too
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Request failed: {request.method} {request.url.path} - {duration_ms:.2f}ms - {e}")
            raise
        
        duration_ms = (time.time() - start_time) * 1000
        
        # Track response time
        endpoint = f"{request.method} {request.url.path}"
        self.tracker.record(endpoint, duration_ms)
        
        # Log slow requests
        if duration_ms > self.slow_threshold_ms:
            logger.warning(
                f"Slow request: {endpoint} - {duration_ms:.2f}ms "
                f"(threshold: {self.slow_threshold_ms}ms)"
            )
        
        # Add performance header
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        
        return response
