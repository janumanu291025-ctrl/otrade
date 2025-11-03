"""Portfolio and fund management endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Fund, BrokerConfig
from backend.schemas import Fund as FundSchema
from backend.services.fund_manager import FundManager
from backend.services.middleware_helper import get_middleware
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/fund", response_model=FundSchema)
def get_current_fund(db: Session = Depends(get_db)):
    """Get current fund information"""
    today = date.today()
    fund = db.query(Fund).filter(
        Fund.date >= datetime.combine(today, datetime.min.time()),
        Fund.date < datetime.combine(today, datetime.max.time())
    ).first()
    
    if not fund:
        # Return default fund if not initialized
        return Fund(
            id=0,
            date=datetime.now(),
            opening_balance=0,
            available_balance=0,
            updated_at=datetime.now()
        )
    
    return fund


@router.get("/fund/summary")
def get_fund_summary(broker_type: str = "kite", db: Session = Depends(get_db)):
    """Get comprehensive fund summary"""
    broker_config = db.query(BrokerConfig).filter(
        BrokerConfig.broker_type == broker_type,
        BrokerConfig.is_active == True
    ).first()
    
    if not broker_config or not broker_config.access_token:
        raise HTTPException(
            status_code=401,
            detail="Broker not connected. Please authenticate first."
        )
    
    try:
        middleware = get_middleware(db)
        fund_manager = FundManager(db, middleware.broker)
        summary = fund_manager.get_fund_summary(middleware.broker)
        return summary
    except Exception as e:
        logger.error(f"Error getting fund summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fund/sync")
def sync_fund_with_broker(broker_type: str = "kite", db: Session = Depends(get_db)):
    """Sync fund information with broker"""
    broker_config = db.query(BrokerConfig).filter(
        BrokerConfig.broker_type == broker_type,
        BrokerConfig.is_active == True
    ).first()
    
    if not broker_config or not broker_config.access_token:
        raise HTTPException(
            status_code=401,
            detail="Broker not connected. Please authenticate first."
        )
    
    try:
        middleware = get_middleware(db)
        fund_manager = FundManager(db, middleware.broker)
        fund = fund_manager.update_fund_from_broker()
        return {
            "status": "success",
            "fund": fund
        }
    except Exception as e:
        logger.error(f"Error syncing fund: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/holdings")
def get_holdings(broker_type: str = "kite", db: Session = Depends(get_db)):
    """Get holdings from broker"""
    broker_config = db.query(BrokerConfig).filter(
        BrokerConfig.broker_type == broker_type,
        BrokerConfig.is_active == True
    ).first()
    
    if not broker_config or not broker_config.access_token:
        raise HTTPException(
            status_code=401,
            detail="Broker not connected. Please authenticate first."
        )
    
    try:
        middleware = get_middleware(db)
        holdings = middleware.broker.get_holdings()
        return holdings
    except Exception as e:
        logger.error(f"Error getting holdings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions")
def get_positions(broker_type: str = "kite", db: Session = Depends(get_db)):
    """Get current positions from broker"""
    broker_config = db.query(BrokerConfig).filter(
        BrokerConfig.broker_type == broker_type,
        BrokerConfig.is_active == True
    ).first()
    
    if not broker_config or not broker_config.access_token:
        raise HTTPException(
            status_code=401,
            detail="Broker not connected. Please authenticate first."
        )
    
    try:
        middleware = get_middleware(db)
        positions = middleware.get_positions(use_cache=False)
        
        # Flatten net and day positions into a single list
        all_positions = []
        if positions and 'net' in positions:
            all_positions.extend(positions['net'])
        if positions and 'day' in positions:
            # Add day positions that aren't duplicates
            day_symbols = {p['tradingsymbol'] for p in all_positions}
            for pos in positions['day']:
                if pos['tradingsymbol'] not in day_symbols:
                    all_positions.append(pos)
        
        return {"status": "success", "data": all_positions}
    except Exception as e:
        logger.error(f"Error getting positions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
