"""
Middleware Helper - Direct Access to UnifiedBrokerMiddleware

This module provides direct access to the UnifiedBrokerMiddleware singleton
for use by endpoints and services throughout the application.
"""

from typing import Optional
from fastapi import HTTPException

from backend.broker.factory import get_broker_client
from backend.services.unified_broker_middleware import (
    UnifiedBrokerMiddleware,
    get_unified_broker_middleware
)


def get_middleware_instance() -> UnifiedBrokerMiddleware:
    """
    Get UnifiedBrokerMiddleware instance directly (no database needed)
    
    This creates or retrieves the singleton middleware instance
    and ensures it's properly initialized using JSON configuration.
    
    Returns:
        UnifiedBrokerMiddleware instance
    
    Raises:
        HTTPException if broker is not configured or authenticated
    """
    try:
        # Get broker client from JSON config
        broker = get_broker_client(raise_exception=True)
        
        # Get or create middleware (no database needed)
        middleware = get_unified_broker_middleware(broker, db=None)
        
        return middleware
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Broker not configured or authenticated: {str(e)}")
