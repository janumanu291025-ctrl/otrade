"""
Kite Connect Exception and Error Code Handling
Based on official Kite Connect API documentation
https://kite.trade/docs/connect/v3/exceptions/
"""
from typing import Optional, Dict, Any
from datetime import datetime


# ==================== Kite Connect Exception Types ====================

class KiteBaseException(Exception):
    """Base exception for all Kite Connect errors"""
    
    def __init__(
        self,
        message: str,
        error_type: str = "GeneralException",
        http_code: int = 500,
        additional_info: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_type = error_type
        self.http_code = http_code
        self.additional_info = additional_info or {}
        self.timestamp = datetime.now()
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        return {
            "status": "error",
            "message": self.message,
            "error_type": self.error_type,
            "http_code": self.http_code,
            "timestamp": self.timestamp.isoformat() + 'Z',
            **self.additional_info
        }


class TokenException(KiteBaseException):
    """
    Token expired or invalidated (403)
    
    Indicates the expiry or invalidation of an authenticated session.
    Caused by:
    - User logging out
    - Natural token expiry (daily at 3:30 PM)
    - User logging into another Kite instance
    
    Action: Clear user session and re-initiate login
    """
    
    def __init__(self, message: str = "Access token expired or invalidated", **kwargs):
        super().__init__(
            message=message,
            error_type="TokenException",
            http_code=403,
            **kwargs
        )


class UserException(KiteBaseException):
    """
    User account related errors (400/403)
    
    Examples:
    - Invalid API key
    - User account suspended
    - Insufficient permissions
    - Invalid user credentials
    """
    
    def __init__(self, message: str = "User account error", **kwargs):
        super().__init__(
            message=message,
            error_type="UserException",
            http_code=400,
            **kwargs
        )


class OrderException(KiteBaseException):
    """
    Order related errors (400/500)
    
    Examples:
    - Order placement failed
    - Insufficient funds
    - Invalid order parameters
    - Order not found
    - Order already cancelled/executed
    - Market closed
    """
    
    def __init__(self, message: str = "Order operation failed", **kwargs):
        super().__init__(
            message=message,
            error_type="OrderException",
            http_code=400,
            **kwargs
        )


class InputException(KiteBaseException):
    """
    Missing required fields or bad parameter values (400)
    
    Examples:
    - Missing required fields (symbol, quantity, etc.)
    - Invalid field values
    - Parameter type mismatch
    - Invalid date format
    """
    
    def __init__(self, message: str = "Invalid input parameters", **kwargs):
        super().__init__(
            message=message,
            error_type="InputException",
            http_code=400,
            **kwargs
        )


class MarginException(KiteBaseException):
    """
    Insufficient funds for order placement (400)
    
    Examples:
    - Insufficient margin
    - Margin blocked for existing orders
    - Margin calculation error
    """
    
    def __init__(self, message: str = "Insufficient margin", **kwargs):
        super().__init__(
            message=message,
            error_type="MarginException",
            http_code=400,
            **kwargs
        )


class HoldingException(KiteBaseException):
    """
    Insufficient holdings to place sell order (400)
    
    Examples:
    - No holdings available for sell
    - Holdings locked in other orders
    - Insufficient quantity in holdings
    """
    
    def __init__(self, message: str = "Insufficient holdings", **kwargs):
        super().__init__(
            message=message,
            error_type="HoldingException",
            http_code=400,
            **kwargs
        )


class NetworkException(KiteBaseException):
    """
    Network error - API unable to communicate with OMS (502/503/504)
    
    Examples:
    - OMS backend down
    - Network timeout
    - Connection refused
    - Gateway error
    """
    
    def __init__(self, message: str = "Network error connecting to OMS", **kwargs):
        super().__init__(
            message=message,
            error_type="NetworkException",
            http_code=502,
            **kwargs
        )


class DataException(KiteBaseException):
    """
    Internal system error - API unable to understand OMS response (500)
    
    Examples:
    - Invalid response from OMS
    - Data parsing error
    - Unexpected data format
    """
    
    def __init__(self, message: str = "Data error from OMS", **kwargs):
        super().__init__(
            message=message,
            error_type="DataException",
            http_code=500,
            **kwargs
        )


class GeneralException(KiteBaseException):
    """
    Unclassified error (500)
    
    This should only happen rarely for unexpected errors
    """
    
    def __init__(self, message: str = "General error occurred", **kwargs):
        super().__init__(
            message=message,
            error_type="GeneralException",
            http_code=500,
            **kwargs
        )


class RateLimitException(KiteBaseException):
    """
    Too many requests - Rate limiting triggered (429)
    
    Kite Connect API Rate Limits:
    - Quote: 1 req/second
    - Historical candle: 3 req/second
    - Order placement: 10 req/second
    - All other endpoints: 10 req/second
    
    Additional limits:
    - 200 orders per minute
    - 10 orders per second
    - 3000 orders per day (risk management)
    - 25 modifications per order
    """
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        endpoint: Optional[str] = None,
        limit: Optional[int] = None,
        reset_at: Optional[datetime] = None,
        **kwargs
    ):
        additional_info = {
            "endpoint": endpoint,
            "limit": limit,
            "reset_at": reset_at.isoformat() + 'Z' if reset_at else None
        }
        super().__init__(
            message=message,
            error_type="RateLimitException",
            http_code=429,
            additional_info=additional_info,
            **kwargs
        )


# ==================== HTTP Error Code Mapping ====================

HTTP_ERROR_CODES = {
    400: {
        "description": "Missing or bad request parameters or values",
        "action": "Check request parameters and values",
        "retryable": False
    },
    403: {
        "description": "Session expired or invalid. Must re-login",
        "action": "Clear session and initiate re-login",
        "retryable": False
    },
    404: {
        "description": "Requested resource was not found",
        "action": "Verify resource exists",
        "retryable": False
    },
    405: {
        "description": "Request method not allowed on the endpoint",
        "action": "Check HTTP method (GET, POST, etc.)",
        "retryable": False
    },
    410: {
        "description": "Requested resource is gone permanently",
        "action": "Resource no longer available",
        "retryable": False
    },
    429: {
        "description": "Too many requests - rate limiting",
        "action": "Reduce request frequency and implement backoff",
        "retryable": True
    },
    500: {
        "description": "Something unexpected went wrong",
        "action": "Retry after some time or contact support",
        "retryable": True
    },
    502: {
        "description": "Backend OMS is down",
        "action": "Wait for OMS to recover, retry with backoff",
        "retryable": True
    },
    503: {
        "description": "Service unavailable - API is down",
        "action": "Wait for service to recover",
        "retryable": True
    },
    504: {
        "description": "Gateway timeout - API is unreachable",
        "action": "Check network connectivity and retry",
        "retryable": True
    }
}


# ==================== Rate Limit Configuration ====================

RATE_LIMITS = {
    "quote": {
        "requests_per_second": 1,
        "requests_per_minute": 60,
        "burst": 2  # Allow small bursts
    },
    "historical": {
        "requests_per_second": 3,
        "requests_per_minute": 180,
        "burst": 5
    },
    "order_placement": {
        "requests_per_second": 10,
        "requests_per_minute": 200,  # Hard limit
        "requests_per_day": 3000,     # Risk management limit
        "burst": 15
    },
    "order_modification": {
        "max_per_order": 25,  # Maximum modifications per order
        "requests_per_second": 10
    },
    "default": {
        "requests_per_second": 10,
        "requests_per_minute": 600,
        "burst": 20
    }
}


# ==================== Exception Parsing ====================

EXCEPTION_TYPE_MAP = {
    "TokenException": TokenException,
    "UserException": UserException,
    "OrderException": OrderException,
    "InputException": InputException,
    "MarginException": MarginException,
    "HoldingException": HoldingException,
    "NetworkException": NetworkException,
    "DataException": DataException,
    "GeneralException": GeneralException,
    "RateLimitException": RateLimitException
}


def parse_kite_error(error_response: Dict[str, Any], http_code: int = 500) -> KiteBaseException:
    """
    Parse Kite Connect error response and return appropriate exception
    
    Example error response:
    {
        "status": "error",
        "message": "Error message",
        "error_type": "GeneralException"
    }
    
    Args:
        error_response: Error response dict from Kite API
        http_code: HTTP status code
    
    Returns:
        Appropriate exception instance
    """
    error_type = error_response.get("error_type", "GeneralException")
    message = error_response.get("message", "Unknown error")
    
    # Get exception class from map
    exception_class = EXCEPTION_TYPE_MAP.get(error_type, GeneralException)
    
    # Create exception instance
    return exception_class(
        message=message,
        additional_info={
            "raw_response": error_response,
            "http_code": http_code
        }
    )


def get_exception_from_http_code(http_code: int, message: str = None) -> KiteBaseException:
    """
    Get appropriate exception based on HTTP status code
    
    Args:
        http_code: HTTP status code
        message: Optional custom error message
    
    Returns:
        Appropriate exception instance
    """
    if message is None:
        error_info = HTTP_ERROR_CODES.get(http_code, {})
        message = error_info.get("description", f"HTTP {http_code} error")
    
    # Map HTTP codes to exception types
    if http_code == 403:
        return TokenException(message)
    elif http_code == 429:
        return RateLimitException(message)
    elif http_code in [502, 503, 504]:
        return NetworkException(message)
    elif http_code in [400, 404, 405, 410]:
        return InputException(message)
    else:
        return GeneralException(message)


def is_retryable_error(exception: KiteBaseException) -> bool:
    """
    Check if error is retryable
    
    Args:
        exception: Exception instance
    
    Returns:
        True if error is retryable, False otherwise
    """
    error_info = HTTP_ERROR_CODES.get(exception.http_code, {})
    return error_info.get("retryable", False)


def get_retry_delay(exception: KiteBaseException, attempt: int) -> float:
    """
    Get retry delay in seconds using exponential backoff
    
    Args:
        exception: Exception instance
        attempt: Retry attempt number (starts at 1)
    
    Returns:
        Delay in seconds
    """
    if not is_retryable_error(exception):
        return 0
    
    # Base delay depends on error type
    if isinstance(exception, RateLimitException):
        base_delay = 1.0  # Start with 1 second for rate limits
    elif isinstance(exception, NetworkException):
        base_delay = 2.0  # Start with 2 seconds for network errors
    else:
        base_delay = 1.0
    
    # Exponential backoff: delay = base * 2^(attempt - 1)
    # Max delay: 60 seconds
    delay = min(base_delay * (2 ** (attempt - 1)), 60.0)
    
    return delay


# ==================== Error Context Tracking ====================

class ErrorContext:
    """Track error context for debugging and monitoring"""
    
    def __init__(self):
        self.errors = []
        self.rate_limit_hits = {}
        self.token_expiry_count = 0
    
    def record_error(self, exception: KiteBaseException, endpoint: str = None):
        """Record error occurrence"""
        self.errors.append({
            "error_type": exception.error_type,
            "message": exception.message,
            "http_code": exception.http_code,
            "endpoint": endpoint,
            "timestamp": exception.timestamp.isoformat() + 'Z'
        })
        
        # Track specific error types
        if isinstance(exception, TokenException):
            self.token_expiry_count += 1
        elif isinstance(exception, RateLimitException):
            if endpoint:
                self.rate_limit_hits[endpoint] = \
                    self.rate_limit_hits.get(endpoint, 0) + 1
    
    def get_summary(self) -> Dict[str, Any]:
        """Get error summary statistics"""
        error_types = {}
        for error in self.errors:
            error_type = error["error_type"]
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        return {
            "total_errors": len(self.errors),
            "error_types": error_types,
            "token_expiry_count": self.token_expiry_count,
            "rate_limit_hits": self.rate_limit_hits,
            "recent_errors": self.errors[-10:]  # Last 10 errors
        }
    
    def clear(self):
        """Clear error history"""
        self.errors = []
        self.rate_limit_hits = {}
        self.token_expiry_count = 0


# Global error context instance
error_context = ErrorContext()
