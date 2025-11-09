"""Portfolio and fund management endpoints - Centralized positions and holdings"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
from backend.database import get_db
from backend.models import BrokerConfig
from backend.services.middleware_helper import get_middleware_instance
from backend.broker.base import TokenExpiredError
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


# ========== CONSOLIDATED PORTFOLIO API (Kite Connect v3 Compatible) ==========

@router.get("/positions")
async def get_portfolio_positions(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Retrieve the list of short term positions
    GET /portfolio/positions
    
    Positions contain the user's portfolio of short to medium term derivatives 
    (futures and options contracts) and intraday equity stocks. Instruments in the 
    positions portfolio remain there until they're sold, or until expiry, which, 
    for derivatives, is typically three months. Equity positions carried overnight 
    move to the holdings portfolio the next day.
    
    The positions API returns two sets of positions:
    - net: The actual, current net position portfolio
    - day: A snapshot of the buying and selling activity for that particular day
      (useful for computing intraday profits and losses for trading strategies)
    
    Reference: https://kite.trade/docs/connect/v3/portfolio/#positions
    
    Returns:
        {
            "status": "success",
            "data": {
                "net": [...],  # Current net positions (F&O and intraday equity)
                "day": [...]   # Day's trading snapshot
            }
        }
    """
    try:
        # Get middleware instance
        middleware = get_middleware_instance(db)
        
        if not middleware:
            raise HTTPException(
                status_code=401,
                detail="Broker not authenticated. Please login first."
            )
        
        # Fetch positions from broker via middleware (short-term only)
        positions = middleware.get_positions(use_cache=False)
        
        return {
            "status": "success",
            "data": positions
        }
        
    except TokenExpiredError as e:
        logger.error(f"Token expired while fetching positions: {e}")
        raise HTTPException(
            status_code=401,
            detail="Access token expired. Please re-authenticate with your broker."
        )
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))
