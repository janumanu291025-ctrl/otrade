"""WebSocket endpoint for real-time updates"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.services.middleware_helper import get_middleware
from typing import List
import json
import logging
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_text(json.dumps(message))
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error broadcasting to client: {str(e)}")


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates (simplified - middleware handles broker data)"""
    await manager.connect(websocket)
    
    try:
        while True:
            # Receive data from client
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                message_type = message.get("type")
                
                if message_type == "ping":
                    await manager.send_personal_message(
                        {"type": "pong", "timestamp": message.get("timestamp")},
                        websocket
                    )
                
                elif message_type == "subscribe":
                    # Legacy subscription handling
                    await manager.send_personal_message(
                        {"type": "subscribed", "data": message.get("data")},
                        websocket
                    )
                
                else:
                    logger.warning(f"Unknown message type: {message_type}")
                
            except json.JSONDecodeError:
                logger.error("Invalid JSON received")
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        manager.disconnect(websocket)


async def broadcast_order_update(order_data: dict):
    """Broadcast order update to all connected clients"""
    message = {
        "type": "order_update",
        "data": order_data
    }
    await manager.broadcast(message)


async def broadcast_position_update(position_data: dict):
    """Broadcast position update to all connected clients"""
    message = {
        "type": "position_update",
        "data": position_data
    }
    await manager.broadcast(message)


async def broadcast_market_data(market_data: dict):
    """Broadcast market data update to all connected clients"""
    message = {
        "type": "market_data",
        "data": market_data
    }
    await manager.broadcast(message)


async def broadcast_fund_update(fund_data: dict):
    """Broadcast fund update to all connected clients"""
    message = {
        "type": "fund_update",
        "data": fund_data
    }
    await manager.broadcast(message)


async def broadcast_notification(notification_data: dict):
    """Broadcast notification to all connected clients"""
    message = {
        "type": "notification",
        "data": notification_data
    }
    await manager.broadcast(message)


@router.get("/ws/status")
async def get_websocket_status(db: Session = Depends(get_db)):
    """Get WebSocket connection status - now shows middleware status"""
    from backend.services.middleware_helper import get_middleware
    
    try:
        middleware = get_middleware(db)
        status = middleware.get_status()
        
        return {
            "status": "ok",
            "connected": status["webhook_connected"],
            "active_connections": len(manager.active_connections),
            "subscribed_instruments": status["subscribed_instruments"],
            "middleware_running": status["running"]
        }
    except Exception as e:
        logger.error(f"Error getting WebSocket status: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.post("/ws/reconnect")
async def reconnect_websocket(db: Session = Depends(get_db)):
    """Reconnect WebSocket for market data (handled by middleware based on market hours)"""
    from backend.services.market_calendar import is_market_open
    from backend.services.middleware_helper import get_middleware
    
    # Check if it's market hours
    if not is_market_open():
        return {
            "status": "error",
            "message": "WebSocket connection only available during market hours (9:15 AM - 3:30 PM)"
        }
    
    try:
        middleware = get_middleware(db)
        # Middleware automatically manages WebSocket connections
        # Just return current status
        status = middleware.get_status()
        
        return {
            "status": "success",
            "connected": status["webhook_connected"],
            "subscribed_instruments": status["subscribed_instruments"]
        }
    except Exception as e:
        logger.error(f"Error reconnecting WebSocket: {e}")
        return {
            "status": "error",
            "message": str(e)
        }
