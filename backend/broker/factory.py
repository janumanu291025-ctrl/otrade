"""
Broker Factory - Get broker client instance using .env configuration
"""

from backend.config import settings
from backend.broker.kite.client import KiteBroker
from backend.broker.upstox.client import UpstoxBroker


def get_broker_client(raise_exception: bool = True):
    """
    Get active broker client from .env configuration
    
    Args:
        raise_exception: If False, returns None instead of raising exception
    
    Returns:
        Broker client instance or None
    """
    broker_type = settings.BROKER_TYPE.lower()
    
    if broker_type == "kite":
        if not settings.KITE_API_KEY or not settings.KITE_API_SECRET:
            if raise_exception:
                from fastapi import HTTPException
                raise HTTPException(status_code=400, detail="Missing Kite credentials in .env")
            return None
        
        return KiteBroker(
            api_key=settings.KITE_API_KEY,
            api_secret=settings.KITE_API_SECRET,
            access_token=settings.KITE_ACCESS_TOKEN
        )
    
    elif broker_type == "upstox":
        if not settings.UPSTOX_API_KEY or not settings.UPSTOX_API_SECRET:
            if raise_exception:
                from fastapi import HTTPException
                raise HTTPException(status_code=400, detail="Missing Upstox credentials in .env")
            return None
        
        return UpstoxBroker(
            api_key=settings.UPSTOX_API_KEY,
            api_secret=settings.UPSTOX_API_SECRET,
            access_token=settings.UPSTOX_ACCESS_TOKEN
        )
    
    # Unsupported broker type
    if raise_exception:
        from fastapi import HTTPException
        error_msg = f"Unsupported broker type: {broker_type}"
        raise HTTPException(status_code=400, detail=error_msg)
    
    return None
