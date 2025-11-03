"""Position management endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from backend.database import get_db
from backend.models import Position, BrokerConfig
from backend.schemas import Position as PositionSchema
from backend.services.middleware_helper import get_middleware
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/positions", tags=["positions"])


@router.get("/", response_model=List[PositionSchema])
def list_positions(
    skip: int = 0,
    limit: int = 100,
    open_only: bool = True,
    db: Session = Depends(get_db)
):
    """Get list of positions"""
    query = db.query(Position)
    
    if open_only:
        query = query.filter(Position.closed_at.is_(None))
    
    positions = query.order_by(Position.opened_at.desc()).offset(skip).limit(limit).all()
    return positions


@router.get("/{position_id}", response_model=PositionSchema)
def get_position(position_id: int, db: Session = Depends(get_db)):
    """Get a specific position"""
    position = db.query(Position).filter(Position.id == position_id).first()
    
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    
    return position


@router.get("/summary/all")
def get_positions_summary(db: Session = Depends(get_db)):
    """Get summary of all positions"""
    open_positions = db.query(Position).filter(Position.closed_at.is_(None)).all()
    closed_positions = db.query(Position).filter(Position.closed_at.isnot(None)).all()
    
    total_open_pnl = sum(p.pnl for p in open_positions)
    total_closed_pnl = sum(p.pnl for p in closed_positions)
    
    return {
        "open_positions_count": len(open_positions),
        "closed_positions_count": len(closed_positions),
        "open_pnl": total_open_pnl,
        "closed_pnl": total_closed_pnl,
        "total_pnl": total_open_pnl + total_closed_pnl
    }


@router.get("/live/broker/{broker_type}")
def get_live_positions(broker_type: str, db: Session = Depends(get_db)):
    """
    Get live positions from broker with real-time P&L
    Automatically subscribes to WebSocket streaming for position instruments
    """
    # Get broker config
    broker_config = db.query(BrokerConfig).filter(
        BrokerConfig.broker_type == broker_type,
        BrokerConfig.is_active == True
    ).first()
    
    if not broker_config:
        raise HTTPException(status_code=404, detail="Active broker configuration not found")
    
    if not broker_config.access_token:
        raise HTTPException(status_code=400, detail="Broker not authenticated")
    
    try:
        # Get unified broker middleware
        middleware = get_middleware(db)
        
        # Fetch live positions
        positions = middleware.get_positions(use_cache=False)
        
        # Extract instrument tokens from positions for subscription
        instrument_tokens = []
        for position in positions.get("net", []):
            if position.get("quantity") != 0:  # Only active positions
                instrument_token = position.get("instrument_token")
                if instrument_token:
                    instrument_tokens.append(instrument_token)
        
        # Subscribe to middleware for these instruments (middleware handles WebSocket/API)
        if instrument_tokens:
            middleware.subscribe_instruments(instrument_tokens)
            logger.info(f"Subscribed to {len(instrument_tokens)} position instruments via middleware")
        
        return positions
        
    except Exception as e:
        logger.error(f"Error fetching live positions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch live positions: {str(e)}")
