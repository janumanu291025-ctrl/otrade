"""Order management endpoints - Centralized order operations using middleware"""
from fastapi import APIRouter, HTTPException, Body
from typing import Optional, Dict, Any
from backend.services.middleware_helper import get_middleware_instance
from backend.broker.base import TokenExpiredError, OrderError
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/orders", tags=["orders"])


# ========== CONSOLIDATED ORDER APIS (Kite Connect v3 Compatible) ==========

@router.get("")
@router.get("/")
async def get_orders() -> Dict[str, Any]:
    """
    Retrieve the list of all orders (open and executed) for the day
    GET /orders
    
    This endpoint fetches orders directly from the broker via middleware.
    Returns comprehensive order information including status, prices, quantities, and timestamps.
    
    Reference: https://kite.trade/docs/connect/v3/orders/#retrieving-orders
    
    Returns:
        {
            "status": "success",
            "data": [list of order objects],
            "count": number of orders
        }
    """
    try:
        # Get middleware instance (no database needed)
        middleware = get_middleware_instance()
        
        # Fetch orders from broker via middleware
        orders = middleware.get_orders(use_cache=False)
        
        return {
            "status": "success",
            "data": orders,
            "count": len(orders)
        }
        
    except TokenExpiredError as e:
        logger.error(f"Token expired while fetching orders: {e}")
        raise HTTPException(
            status_code=401,
            detail="Access token expired. Please re-authenticate with your broker."
        )
    except Exception as e:
        logger.error(f"Error fetching orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{variety}")
async def place_order(
    variety: str,
    tradingsymbol: str = Body(...),
    exchange: str = Body(...),
    transaction_type: str = Body(...),
    quantity: int = Body(...),
    order_type: str = Body(...),
    product: str = Body("MIS"),
    price: Optional[float] = Body(None),
    trigger_price: Optional[float] = Body(None),
    disclosed_quantity: Optional[int] = Body(None),
    validity: str = Body("DAY"),
    validity_ttl: Optional[int] = Body(None),
    iceberg_legs: Optional[int] = Body(None),
    iceberg_quantity: Optional[int] = Body(None),
    auction_number: Optional[str] = Body(None),
    market_protection: Optional[int] = Body(None),
    autoslice: Optional[bool] = Body(None),
    tag: Optional[str] = Body(None)
) -> Dict[str, Any]:
    """
    Place an order of a particular variety
    POST /orders/:variety
    
    Variety can be: regular, amo, co, iceberg, auction
    
    Reference: https://kite.trade/docs/connect/v3/orders/#placing-orders
    
    Args:
        variety: Order variety (regular, amo, co, iceberg, auction)
        tradingsymbol: Exchange tradingsymbol (e.g., "INFY", "NIFTY2410016000CE")
        exchange: Exchange code (NSE, BSE, NFO, BFO, CDS, MCX, BCD)
        transaction_type: BUY or SELL
        quantity: Quantity to transact
        order_type: MARKET, LIMIT, SL, SL-M
        product: CNC, NRML, MIS, MTF (margin product)
        price: Price for LIMIT orders
        trigger_price: Trigger price for SL/SL-M orders
        disclosed_quantity: Quantity to disclose publicly (equity only)
        validity: DAY, IOC, TTL
        validity_ttl: Order life in minutes (for TTL validity)
        iceberg_legs: Number of legs for iceberg orders (2-10)
        iceberg_quantity: Split quantity per iceberg leg
        auction_number: Unique identifier for auction
        market_protection: 0 (no protection), 0-100 (custom %), -1 (auto)
        autoslice: Enable automatic order slicing for freeze quantities
        tag: Optional tag to identify order (alphanumeric, max 20 chars)
    
    Returns:
        {"status": "success", "data": {"order_id": "151220000000000"}}
    """
    try:
        # Get middleware instance (no database needed)
        middleware = get_middleware_instance()
        
        # Place order via middleware
        result = middleware.place_order(
            tradingsymbol=tradingsymbol,
            exchange=exchange,
            transaction_type=transaction_type,
            quantity=quantity,
            order_type=order_type,
            product=product,
            variety=variety,
            price=price,
            trigger_price=trigger_price,
            disclosed_quantity=disclosed_quantity,
            validity=validity,
            validity_ttl=validity_ttl,
            iceberg_legs=iceberg_legs,
            iceberg_quantity=iceberg_quantity,
            auction_number=auction_number,
            market_protection=market_protection,
            autoslice=autoslice,
            tag=tag
        )
        
        logger.info(f"Order placed successfully: {result}")
        
        return {
            "status": "success",
            "data": result
        }
        
    except TokenExpiredError as e:
        logger.error(f"Token expired while placing order: {e}")
        raise HTTPException(
            status_code=401,
            detail="Access token expired. Please re-authenticate with your broker."
        )
    except OrderError as e:
        logger.error(f"Order placement failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error placing order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{variety}/{order_id}")
async def modify_order(
    variety: str,
    order_id: str,
    quantity: Optional[int] = Body(None),
    price: Optional[float] = Body(None),
    trigger_price: Optional[float] = Body(None),
    order_type: Optional[str] = Body(None),
    disclosed_quantity: Optional[int] = Body(None),
    validity: Optional[str] = Body(None),
    validity_ttl: Optional[int] = Body(None)
) -> Dict[str, Any]:
    """
    Modify an open or pending order
    PUT /orders/:variety/:order_id
    
    Reference: https://kite.trade/docs/connect/v3/orders/#modifying-orders
    
    Args:
        variety: Order variety (regular, amo, co, iceberg, auction)
        order_id: Unique order ID
        quantity: New quantity
        price: New price
        trigger_price: New trigger price
        order_type: New order type (MARKET, LIMIT, SL, SL-M)
        disclosed_quantity: New disclosed quantity
        validity: New validity (DAY, IOC, TTL)
        validity_ttl: New validity TTL
    
    Returns:
        {"status": "success", "data": {"order_id": "151220000000000"}}
    """
    try:
        # Get middleware instance (no database needed)
        middleware = get_middleware_instance()
        
        # Modify order via middleware
        result = middleware.modify_order(
            order_id=order_id,
            variety=variety,
            quantity=quantity,
            price=price,
            trigger_price=trigger_price,
            order_type=order_type,
            disclosed_quantity=disclosed_quantity,
            validity=validity,
            validity_ttl=validity_ttl
        )
        
        logger.info(f"Order modified successfully: {result}")
        
        return {
            "status": "success",
            "data": result
        }
        
    except TokenExpiredError as e:
        logger.error(f"Token expired while modifying order: {e}")
        raise HTTPException(
            status_code=401,
            detail="Access token expired. Please re-authenticate with your broker."
        )
    except OrderError as e:
        logger.error(f"Order modification failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error modifying order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{variety}/{order_id}")
async def cancel_order(
    variety: str,
    order_id: str
) -> Dict[str, Any]:
    """
    Cancel an open or pending order
    DELETE /orders/:variety/:order_id
    
    Reference: https://kite.trade/docs/connect/v3/orders/#cancelling-orders
    
    Args:
        variety: Order variety (regular, amo, co, iceberg, auction)
        order_id: Unique order ID
    
    Returns:
        {"status": "success", "data": {"order_id": "151220000000000"}}
    """
    try:
        # Get middleware instance (no database needed)
        middleware = get_middleware_instance()
        
        # Cancel order via middleware
        result = middleware.cancel_order(
            order_id=order_id,
            variety=variety
        )
        
        logger.info(f"Order cancelled successfully: {result}")
        
        return {
            "status": "success",
            "data": result
        }
        
    except TokenExpiredError as e:
        logger.error(f"Token expired while cancelling order: {e}")
        raise HTTPException(
            status_code=401,
            detail="Access token expired. Please re-authenticate with your broker."
        )
    except OrderError as e:
        logger.error(f"Order cancellation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error cancelling order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== LEGACY/HELPER ENDPOINTS (DISABLED) ==========
# These endpoints were using the old Order model which has been deprecated.
# All order operations now go directly through the broker middleware.
# If you need local order tracking, implement a new Order model first.
