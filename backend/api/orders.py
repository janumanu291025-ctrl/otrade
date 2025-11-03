"""Order management endpoints"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from backend.database import get_db
from backend.models import Order, BrokerConfig
from backend.schemas import Order as OrderSchema
from backend.services.middleware_helper import get_middleware
from backend.services.order_sync import OrderSyncService
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("/", response_model=List[OrderSchema])
def list_orders(
    skip: int = 0,
    limit: int = 100,
    status: str = Query(None),
    order_type: str = Query(None),
    db: Session = Depends(get_db)
):
    """Get list of orders"""
    query = db.query(Order)
    
    if status:
        query = query.filter(Order.status == status)
    
    if order_type:
        query = query.filter(Order.order_type == order_type)
    
    orders = query.order_by(Order.placed_at.desc()).offset(skip).limit(limit).all()
    logger.info(f"Retrieved {len(orders)} orders (status={status})")
    return orders


@router.get("/sync-status")
async def get_sync_status(db: Session = Depends(get_db)):
    """
    Get order sync status and strategy based on market hours
    """
    try:
        # Get active broker config
        broker_config = db.query(BrokerConfig).filter(
            BrokerConfig.broker_type == 'kite',
            BrokerConfig.is_active == True
        ).first()
        
        if not broker_config:
            return {
                "configured": False,
                "message": "No active broker configured",
                "sync_strategy": {
                    "method": "manual",
                    "market_status": {
                        "is_active": False
                    }
                }
            }
        
        # Initialize broker middleware and sync service
        try:
            middleware = get_middleware(db)
            
            sync_service = OrderSyncService(db, middleware.broker)
            sync_strategy = sync_service.get_sync_strategy()
            
            # Count pending orders
            pending_orders = db.query(Order).filter(Order.status == "open").count()
            
            return {
                "configured": True,
                "sync_strategy": sync_strategy,
                "pending_orders": pending_orders,
                "last_checked": None  # Can be implemented with a cache
            }
        except Exception as broker_error:
            logger.error(f"Error initializing broker/sync service: {broker_error}")
            # Return a safe default response
            return {
                "configured": True,
                "sync_strategy": {
                    "method": "manual",
                    "market_status": {
                        "is_active": False
                    }
                },
                "pending_orders": 0,
                "error": str(broker_error)
            }
        
    except Exception as e:
        logger.error(f"Error getting sync status: {e}", exc_info=True)
        # Return safe default instead of raising exception
        return {
            "configured": False,
            "sync_strategy": {
                "method": "manual",
                "market_status": {
                    "is_active": False
                }
            },
            "pending_orders": 0,
            "error": str(e)
        }


@router.get("/{order_id}", response_model=OrderSchema)
def get_order(order_id: int, db: Session = Depends(get_db)):
    """Get a specific order"""
    order = db.query(Order).filter(Order.id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return order


@router.get("/open/all", response_model=List[OrderSchema])
def get_open_orders(db: Session = Depends(get_db)):
    """Get all open (pending) orders"""
    orders = db.query(Order).filter(
        Order.status.in_(['open', 'pending'])
    ).order_by(Order.placed_at.desc()).all()
    
    logger.info(f"Retrieved {len(orders)} open orders")
    return orders


@router.get("/completed/all", response_model=List[OrderSchema])
def get_completed_orders(db: Session = Depends(get_db)):
    """Get all completed orders"""
    orders = db.query(Order).filter(
        Order.status.in_(['completed', 'rejected', 'cancelled'])
    ).order_by(Order.filled_at.desc()).all()
    
    logger.info(f"Retrieved {len(orders)} completed orders")
    return orders


@router.post("/sync-open")
async def sync_open_orders(db: Session = Depends(get_db)):
    """
    Sync only open orders from broker
    More efficient than syncing all orders
    """
    try:
        # Get active broker config
        broker_config = db.query(BrokerConfig).filter(
            BrokerConfig.broker_type == 'kite',
            BrokerConfig.is_active == True
        ).first()
        
        if not broker_config:
            raise HTTPException(status_code=400, detail="No active broker configured")
        
        # Initialize broker middleware and sync service
        middleware = get_middleware(db)
        
        sync_service = OrderSyncService(db, middleware.broker)
        result = await sync_service.sync_open_orders()
        
        return result
        
    except Exception as e:
        logger.error(f"Error syncing open orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))
