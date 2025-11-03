"""
Middleware Status API Endpoints
================================

REST API endpoints for monitoring the unified broker middleware status.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas import MiddlewareStatus
from backend.services.middleware_helper import get_middleware

router = APIRouter(prefix="/api/middleware", tags=["middleware"])


@router.get("/status", response_model=MiddlewareStatus)
async def get_middleware_status(middleware = Depends(get_middleware)):
    """
    Get current status of the unified broker middleware
    
    Returns:
        - running: Whether middleware is running
        - market_hours_active: Whether market is currently open
        - webhook_connection_time: Whether it's webhook connection time (9:00 AM - 3:30 PM)
        - webhook_connected: Whether WebSocket/webhook is connected
        - webhook_data_flowing: Whether data is flowing from webhook
        - ltp_fallback_active: Whether API fallback is active for LTP
        - subscribed_instruments: Number of subscribed instruments
        - polling_active: Whether API polling is active
    """
    try:
        status = middleware.get_status()
        return MiddlewareStatus(**status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting middleware status: {str(e)}")
