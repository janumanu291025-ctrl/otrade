"""
Error Handling Middleware for FastAPI
Provides consistent error responses across all API endpoints
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from backend.broker.kite.exceptions import (
    KiteBaseException,
    TokenException,
    RateLimitException,
    error_context
)
import logging
from typing import Union
from datetime import datetime

logger = logging.getLogger(__name__)


async def kite_exception_handler(request: Request, exc: KiteBaseException) -> JSONResponse:
    """
    Handle Kite Connect exceptions
    
    Returns consistent error response format:
    {
        "status": "error",
        "message": "Error message",
        "error_type": "TokenException",
        "http_code": 403,
        "timestamp": "2025-11-03T10:30:00Z",
        ...additional_info
    }
    """
    # Log the error
    logger.error(
        f"Kite API Error: {exc.error_type} - {exc.message} "
        f"(HTTP {exc.http_code}) - Path: {request.url.path}"
    )
    
    # Record error in context
    error_context.record_error(exc, endpoint=request.url.path)
    
    # Return JSON response
    return JSONResponse(
        status_code=exc.http_code,
        content=exc.to_dict()
    )


async def token_exception_handler(request: Request, exc: TokenException) -> JSONResponse:
    """
    Handle token expiry/invalidation
    
    Returns special response that frontend can detect:
    {
        "status": "error",
        "message": "Access token expired",
        "error_type": "TokenException",
        "http_code": 403,
        "token_expired": true,
        "action_required": "re-authenticate",
        "timestamp": "..."
    }
    """
    logger.warning(f"Token expired - Path: {request.url.path}")
    
    # Record token expiry
    error_context.record_error(exc, endpoint=request.url.path)
    
    response_data = exc.to_dict()
    response_data.update({
        "token_expired": True,
        "action_required": "re-authenticate"
    })
    
    return JSONResponse(
        status_code=403,
        content=response_data
    )


async def rate_limit_exception_handler(request: Request, exc: RateLimitException) -> JSONResponse:
    """
    Handle rate limit exceeded
    
    Returns response with retry information:
    {
        "status": "error",
        "message": "Rate limit exceeded",
        "error_type": "RateLimitException",
        "http_code": 429,
        "endpoint": "/api/orders/place",
        "limit": 10,
        "reset_at": "2025-11-03T10:31:00Z",
        "retry_after": 5,
        "timestamp": "..."
    }
    """
    logger.warning(
        f"Rate limit exceeded - Path: {request.url.path} "
        f"- Endpoint: {exc.additional_info.get('endpoint')}"
    )
    
    # Record rate limit hit
    error_context.record_error(exc, endpoint=request.url.path)
    
    response_data = exc.to_dict()
    
    # Add retry-after header
    retry_after = 5  # Default 5 seconds
    
    return JSONResponse(
        status_code=429,
        content=response_data,
        headers={"Retry-After": str(retry_after)}
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    Handle standard HTTP exceptions
    """
    logger.error(f"HTTP {exc.status_code}: {exc.detail} - Path: {request.url.path}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": exc.detail,
            "error_type": "HTTPException",
            "http_code": exc.status_code,
            "timestamp": datetime.now().isoformat() + 'Z'
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handle request validation errors (422)
    """
    logger.error(f"Validation error - Path: {request.url.path} - Errors: {exc.errors()}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "message": "Validation error",
            "error_type": "ValidationError",
            "http_code": 422,
            "errors": exc.errors(),
            "timestamp": datetime.now().isoformat() + 'Z'
        }
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unexpected exceptions
    """
    logger.exception(f"Unexpected error - Path: {request.url.path}")
    
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Internal server error",
            "error_type": "InternalError",
            "http_code": 500,
            "detail": str(exc) if logger.level <= logging.DEBUG else None,
            "timestamp": datetime.now().isoformat() + 'Z'
        }
    )


def register_error_handlers(app):
    """
    Register all error handlers with FastAPI app
    
    Usage:
        from backend.middleware.error_handler import register_error_handlers
        
        app = FastAPI()
        register_error_handlers(app)
    """
    # Kite Connect exceptions
    app.add_exception_handler(TokenException, token_exception_handler)
    app.add_exception_handler(RateLimitException, rate_limit_exception_handler)
    app.add_exception_handler(KiteBaseException, kite_exception_handler)
    
    # Standard exceptions
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    
    logger.info("Error handlers registered")


class ErrorResponse:
    """
    Helper class for creating error responses
    """
    
    @staticmethod
    def success(message: str, data: dict = None):
        """Create success response"""
        response = {
            "status": "success",
            "message": message,
            "timestamp": datetime.now().isoformat() + 'Z'
        }
        if data:
            response["data"] = data
        return response
    
    @staticmethod
    def error(
        message: str,
        error_type: str = "GeneralError",
        http_code: int = 500,
        **kwargs
    ):
        """Create error response"""
        response = {
            "status": "error",
            "message": message,
            "error_type": error_type,
            "http_code": http_code,
            "timestamp": datetime.now().isoformat() + 'Z'
        }
        response.update(kwargs)
        return response
    
    @staticmethod
    def token_expired():
        """Create token expired response"""
        return {
            "status": "error",
            "message": "Access token expired. Please re-authenticate.",
            "error_type": "TokenException",
            "http_code": 403,
            "token_expired": True,
            "action_required": "re-authenticate",
            "timestamp": datetime.now().isoformat() + 'Z'
        }
    
    @staticmethod
    def rate_limited(endpoint: str = None, retry_after: int = 5):
        """Create rate limit response"""
        return {
            "status": "error",
            "message": "Rate limit exceeded. Please slow down your requests.",
            "error_type": "RateLimitException",
            "http_code": 429,
            "endpoint": endpoint,
            "retry_after": retry_after,
            "timestamp": datetime.now().isoformat() + 'Z'
        }
    
    @staticmethod
    def insufficient_funds(required: float, available: float):
        """Create insufficient funds response"""
        return {
            "status": "error",
            "message": f"Insufficient funds. Required: ₹{required:.2f}, Available: ₹{available:.2f}",
            "error_type": "MarginException",
            "http_code": 400,
            "required": required,
            "available": available,
            "shortfall": required - available,
            "timestamp": datetime.now().isoformat() + 'Z'
        }
    
    @staticmethod
    def order_failed(reason: str, order_details: dict = None):
        """Create order failure response"""
        response = {
            "status": "error",
            "message": f"Order failed: {reason}",
            "error_type": "OrderException",
            "http_code": 400,
            "timestamp": datetime.now().isoformat() + 'Z'
        }
        if order_details:
            response["order_details"] = order_details
        return response
    
    @staticmethod
    def market_closed():
        """Create market closed response"""
        return {
            "status": "error",
            "message": "Market is closed. Trading is not allowed outside market hours.",
            "error_type": "OrderException",
            "http_code": 400,
            "market_status": "closed",
            "timestamp": datetime.now().isoformat() + 'Z'
        }
