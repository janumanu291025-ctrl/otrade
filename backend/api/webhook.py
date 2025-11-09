"""
Webhook endpoints for broker postbacks and live market data
"""
from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import BrokerConfig, LiveTrade
from backend.config import settings
import hashlib
import json
import logging
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhook", tags=["webhook"])

# Global paper trading engine instance (will be set by main app)
paper_trading_engine = None
live_trading_engine = None


async def process_order_update_with_retry(engine, order_data: Dict, max_retries: int = 3):
    """
    Process order update with retry logic for failed webhook processing
    
    Args:
        engine: Live trading engine instance
        order_data: Order update data from webhook
        max_retries: Maximum number of retry attempts (default: 3)
    """
    for attempt in range(max_retries):
        try:
            await engine.process_order_update(order_data)
            logger.info(f"Order update processed successfully: {order_data['order_id']}")
            return
        except Exception as e:
            logger.error(f"Attempt {attempt + 1}/{max_retries} failed for order {order_data['order_id']}: {e}")
            if attempt == max_retries - 1:
                logger.error(f"All retry attempts exhausted for order {order_data['order_id']}")
                # Could add to a dead letter queue here for manual review
            else:
                # Wait before retry (exponential backoff)
                import asyncio
                await asyncio.sleep(2 ** attempt)


def set_paper_trading_engine(engine):
    """Set global paper trading engine instance"""
    global paper_trading_engine
    paper_trading_engine = engine


def set_live_trading_engine(engine):
    """Set global live trading engine instance"""
    global live_trading_engine
    live_trading_engine = engine


def verify_kite_checksum(order_id: str, order_timestamp: str, api_secret: str, checksum: str) -> bool:
    """
    Verify Kite Connect postback checksum
    
    The checksum is SHA-256 hash of (order_id + order_timestamp + api_secret)
    
    Args:
        order_id: Order ID from postback
        order_timestamp: Order timestamp from postback
        api_secret: API secret from broker config
        checksum: Checksum from postback
    
    Returns:
        True if checksum is valid, False otherwise
    """
    # Concatenate order_id + order_timestamp + api_secret
    message = f"{order_id}{order_timestamp}{api_secret}"
    
    # Calculate SHA-256 hash
    calculated_checksum = hashlib.sha256(message.encode()).hexdigest()
    
    return calculated_checksum == checksum


def map_kite_status(kite_status: str) -> str:
    """Map Kite order status to internal status"""
    status_map = {
        'COMPLETE': 'COMPLETE',
        'OPEN': 'PENDING',
        'REJECTED': 'REJECTED',
        'CANCELLED': 'CANCELLED'
    }
    return status_map.get(kite_status, 'PENDING')


@router.post("/kite-postback")
async def kite_postback(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Receive order status updates from Kite Connect postback
    
    Kite Connect sends a POST request with JSON payload when order status changes.
    The payload includes a checksum for verification.
    """
    try:
        # Read raw body
        body = await request.body()
        
        # Parse JSON
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            logger.error("Invalid JSON in postback")
            raise HTTPException(status_code=400, detail="Invalid JSON")
        
        logger.info(f"Received Kite postback: {data.get('order_id')} - {data.get('status')}")
        
        # Get broker config to verify checksum
        broker_config = db.query(BrokerConfig).filter(
            BrokerConfig.broker_type == 'kite',
            BrokerConfig.is_active == True
        ).first()
        
        if not broker_config or not broker_config.api_secret:
            logger.error("No active Kite broker config found")
            raise HTTPException(status_code=500, detail="Broker not configured")
        
        # Verify checksum
        order_id = data.get('order_id')
        order_timestamp = data.get('order_timestamp')
        checksum = data.get('checksum')
        
        if not all([order_id, order_timestamp, checksum]):
            logger.error("Missing required fields in postback")
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        is_valid = verify_kite_checksum(
            order_id,
            order_timestamp,
            broker_config.api_secret,
            checksum
        )
        
        if not is_valid:
            logger.error(f"Invalid checksum for order: {order_id}")
            raise HTTPException(status_code=400, detail="Invalid checksum")
        
        # Log the postback data
        logger.info(f"✓ Valid postback received for order: {order_id} - Status: {data.get('status')}")
        
        # Process order update in live trading engine if active
        if live_trading_engine and live_trading_engine.running:
            try:
                # Map Kite status to internal status
                internal_status = map_kite_status(data.get('status', ''))
                
                # Prepare order data for engine
                order_update = {
                    'order_id': order_id,
                    'status': internal_status,
                    'filled_quantity': data.get('filled_quantity', 0),
                    'average_price': data.get('average_price', 0.0),
                    'order_timestamp': data.get('order_timestamp'),
                    'transaction_type': data.get('transaction_type'),
                    'tradingsymbol': data.get('tradingsymbol'),
                    'status_message': data.get('status_message', '')
                }
                
                # Process in background with retry logic
                background_tasks.add_task(
                    process_order_update_with_retry,
                    live_trading_engine,
                    order_update
                )
                
                logger.info(f"Order update queued for processing with retry: {order_id}")
            except Exception as e:
                logger.error(f"Error queuing order update: {e}")
        else:
            logger.debug("No active live trading engine to process order update")
        
        return {"status": "success", "message": "Postback received"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing postback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def webhook_status(db: Session = Depends(get_db)):
    """Get webhook configuration status"""
    from backend.services.market_calendar import get_market_status
    
    market_status = get_market_status()
    
    broker_config = db.query(BrokerConfig).filter(
        BrokerConfig.is_active == True
    ).first()
    
    return {
        "market_status": market_status,
        "webhook_configured": broker_config.webhook_url if broker_config else None
    }


@router.post("/ltp")
async def receive_ltp_update(request: Request, db: Session = Depends(get_db)):
    """
    Receive live LTP updates from market data feed (OPTIMIZED FOR HFT)
    
    Expected payload:
    {
        "instrument_token": "256265",
        "ltp": 24500.50,
        "timestamp": "2025-10-31T10:30:45"
    }
    
    Or batch updates:
    {
        "updates": [
            {"instrument_token": "256265", "ltp": 24500.50},
            {"instrument_token": "12345", "ltp": 150.25}
        ],
        "timestamp": "2025-10-31T10:30:45"
    }
    
    Performance:
    - Updates processed in < 1ms (in-memory cache)
    - Middleware handles LTP caching automatically
    - Real-time WebSocket broadcast
    - Auto-subscribed instruments during live trading
    
    Note: Middleware now handles LTP updates automatically via WebSocket during market hours.
    This endpoint is kept for backward compatibility with external webhook sources.
    """
    try:
        data = await request.json()
        
        if "updates" in data:
            # Batch update
            for update in data["updates"]:
                instrument_token = str(update["instrument_token"])
                ltp = update["ltp"]
                
                # If live engine is running, update NIFTY LTP
                if live_trading_engine and live_trading_engine.running:
                    if instrument_token == "256265":
                        live_trading_engine.nifty_ltp = ltp
                        logger.debug(f"NIFTY 50 LTP updated: ₹{ltp:.2f}")
        else:
            # Single update
            instrument_token = str(data["instrument_token"])
            ltp = data["ltp"]
            
            # If live engine is running, update NIFTY LTP
            if live_trading_engine and live_trading_engine.running:
                if instrument_token == "256265":
                    live_trading_engine.nifty_ltp = ltp
                    logger.debug(f"NIFTY 50 LTP updated: ₹{ltp:.2f}")
        
        return {"status": "ok", "message": "LTP update processed"}
    
    except Exception as e:
        logger.error(f"Error processing LTP update: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/subscriptions")
async def get_webhook_subscriptions(db: Session = Depends(get_db)):
    """
    Get list of all instruments subscribed for webhook/websocket updates
    
    Returns:
        - List of subscribed instrument tokens
        - Subscription sources (NIFTY, orders, positions, expected)
        - Total subscription count
    """
    global live_trading_engine
    
    try:
        if not live_trading_engine or not live_trading_engine.running:
            return {
                "status": "engine_not_running",
                "subscribed_instruments": [],
                "subscription_count": 0,
                "sources": {}
            }
        
        # Get all subscribed instruments
        subscribed = list(live_trading_engine.subscribed_instruments)
        
        # Categorize subscriptions by source
        sources = {
            "nifty_50": [],
            "orders": [],
            "positions": [],
            "expected": []
        }
        
        # NIFTY 50
        if "256265" in subscribed:
            sources["nifty_50"] = ["256265"]
        
        # Orders (all trades today)
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        order_trades = db.query(LiveTrade).filter(
            LiveTrade.config_id == live_trading_engine.config.id,
            LiveTrade.entry_time >= today_start
        ).all()
        sources["orders"] = [t.instrument_token for t in order_trades if t.instrument_token in subscribed]
        
        # Positions (open trades)
        position_trades = db.query(LiveTrade).filter(
            LiveTrade.config_id == live_trading_engine.config.id,
            LiveTrade.status == 'open'
        ).all()
        sources["positions"] = [t.instrument_token for t in position_trades if t.instrument_token in subscribed]
        
        # Expected (CE/PE contracts)
        all_categorized = set(sources["nifty_50"] + sources["orders"] + sources["positions"])
        sources["expected"] = [token for token in subscribed if token not in all_categorized]
        
        return {
            "status": "active",
            "subscribed_instruments": subscribed,
            "subscription_count": len(subscribed),
            "sources": {
                "nifty_50": {
                    "count": len(sources["nifty_50"]),
                    "instruments": sources["nifty_50"]
                },
                "orders": {
                    "count": len(sources["orders"]),
                    "instruments": sources["orders"]
                },
                "positions": {
                    "count": len(sources["positions"]),
                    "instruments": sources["positions"]
                },
                "expected": {
                    "count": len(sources["expected"]),
                    "instruments": sources["expected"]
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting webhook subscriptions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tick")
async def receive_tick_data(request: Request, db: Session = Depends(get_db)):
    """
    Receive tick data from WebSocket feed
    
    Expected payload (Kite Connect format):
    {
        "instrument_token": 256265,
        "last_price": 24500.50,
        "ohlc": {
            "open": 24450.00,
            "high": 24520.00,
            "low": 24400.00,
            "close": 24500.50
        },
        "timestamp": "2025-10-31T10:30:45"
    }
    """
    try:
        data = await request.json()
        
        instrument_token = str(data.get("instrument_token"))
        last_price = data.get("last_price")
        
        if instrument_token and last_price and paper_trading_engine:
            await paper_trading_engine.process_ltp_update(
                instrument_token,
                last_price
            )
        
        return {"status": "ok", "message": "Tick data processed"}
    
    except Exception as e:
        logger.error(f"Error processing tick data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

