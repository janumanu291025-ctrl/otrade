"""
Middleware Helper - Direct Access to UnifiedBrokerMiddleware
==============================================================

This module provides direct access to the UnifiedBrokerMiddleware singleton
for use by endpoints and services throughout the application.

Usage in endpoints:
    from backend.services.middleware_helper import get_middleware_instance
    
    @router.get("/some-endpoint")
    async def some_endpoint(db: Session = Depends(get_db)):
        # Get middleware instance directly
        middleware = get_middleware_instance(db)
        positions = middleware.get_positions()
        funds = middleware.get_funds()
        ...
"""

from typing import Optional
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.broker.factory import get_broker_client
from backend.services.unified_broker_middleware import (
    UnifiedBrokerMiddleware,
    get_unified_broker_middleware
)


def get_middleware_instance(db: Session) -> UnifiedBrokerMiddleware:
    """
    Get UnifiedBrokerMiddleware instance directly (no dependency injection)
    
    This creates or retrieves the singleton middleware instance
    and ensures it's properly initialized.
    
    Args:
        db: Database session
    
    Returns:
        UnifiedBrokerMiddleware instance
    
    Raises:
        HTTPException if broker is not configured or authenticated
    """
    try:
        # Get broker client
        broker = get_broker_client(db, raise_exception=True)
        
        # Get or create middleware
        middleware = get_unified_broker_middleware(broker, db)
        
        return middleware
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Broker not configured or authenticated: {str(e)}")


# Legacy dependency injection support (deprecated)
def get_middleware(db: Session = Depends(get_db)) -> UnifiedBrokerMiddleware:
    """
    DEPRECATED: Use get_middleware_instance() directly instead
    
    Legacy dependency injection for UnifiedBrokerMiddleware
    """
    return get_middleware_instance(db)
