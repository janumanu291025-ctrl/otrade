"""WebSocket endpoint for real-time updates"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.services.middleware_helper import get_middleware_instance
from typing import List
import json
import logging
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections with per-API-key and per-connection limits.

    Behavior changes (backward compatible):
    - Clients must send a registration message immediately after connecting:
      {"type": "register", "api_key": "YOUR_KEY"}
    - Each API key may have up to 3 active WebSocket connections.
    - Each connection may subscribe to up to 3000 instruments. Subscribe
      requests that would exceed the limit are rejected with a clear error.
    """

    MAX_CONNECTIONS_PER_KEY = 3
    MAX_SUBSCRIPTIONS_PER_CONNECTION = 3000

    def __init__(self):
        # All active websockets (flat list)
        self.active_connections: List[WebSocket] = []

        # Map API key -> list of WebSocket objects
        self.api_key_connections = {}

        # Map websocket id -> metadata (api_key, subscriptions set)
        self._ws_meta = {}

    async def connect(self, websocket: WebSocket):
        """Accept connection and expect an immediate registration message.

        Returns True if connection accepted and registered, False otherwise.
        """
        await websocket.accept()

        # Expect a registration/auth message within a short timeout
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=8)
        except asyncio.TimeoutError:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "Registration required: send {\"type\": \"register\", \"api_key\": \"...\"} immediately after connecting"
            }))
            await websocket.close()
            return False

        try:
            msg = json.loads(raw)
            if msg.get("type") not in ("register", "auth"):
                raise ValueError("invalid registration type")

            api_key = msg.get("api_key") or msg.get("token")
            if not api_key:
                raise ValueError("missing api_key")
        except Exception:
            await websocket.send_text(json.dumps({"type": "error", "message": "Invalid registration message"}))
            await websocket.close()
            return False

        # Enforce per-API-key connection limit
        conns = self.api_key_connections.get(api_key, [])
        if len(conns) >= self.MAX_CONNECTIONS_PER_KEY:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"API key has reached maximum websocket connections ({self.MAX_CONNECTIONS_PER_KEY})"
            }))
            await websocket.close()
            return False

        # Register connection
        conns.append(websocket)
        self.api_key_connections[api_key] = conns
        self.active_connections.append(websocket)
        self._ws_meta[id(websocket)] = {
            "websocket": websocket,
            "api_key": api_key,
            "subscriptions": set()
        }

        logger.info(
            f"WebSocket connected for api_key={api_key}. Total connections: {len(self.active_connections)} (api_key connections={len(conns)})"
        )
        return True

    def disconnect(self, websocket: WebSocket):
        meta = self._ws_meta.pop(id(websocket), None)
        if websocket in self.active_connections:
            try:
                self.active_connections.remove(websocket)
            except ValueError:
                pass

        if meta:
            api_key = meta.get("api_key")
            conns = self.api_key_connections.get(api_key, [])
            try:
                conns.remove(websocket)
            except ValueError:
                pass
            if not conns:
                self.api_key_connections.pop(api_key, None)

        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_text(json.dumps(message))

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        for connection in list(self.active_connections):
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error broadcasting to client: {str(e)}")

    def get_meta(self, websocket: WebSocket):
        return self._ws_meta.get(id(websocket))


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates.

    Expects an immediate registration message from client. Afterwards,
    clients can send 'ping', 'subscribe', and 'unsubscribe' messages.
    """
    connected = await manager.connect(websocket)
    if not connected:
        return

    try:
        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                logger.error("Invalid JSON received from websocket client")
                await manager.send_personal_message({"type": "error", "message": "Invalid JSON"}, websocket)
                continue

            message_type = message.get("type")

            if message_type == "ping":
                await manager.send_personal_message({"type": "pong", "timestamp": message.get("timestamp")}, websocket)

            elif message_type == "subscribe":
                # Expect instruments list under 'instruments' or 'data'
                instruments = message.get("instruments") or message.get("data") or []
                if not isinstance(instruments, list):
                    await manager.send_personal_message({"type": "error", "message": "Invalid subscribe payload - should be a list of instruments"}, websocket)
                    continue

                meta = manager.get_meta(websocket)
                if not meta:
                    await manager.send_personal_message({"type": "error", "message": "Connection metadata missing"}, websocket)
                    continue

                current_subs = meta.get("subscriptions")
                new_set = set(instruments) - current_subs
                if len(current_subs) + len(new_set) > manager.MAX_SUBSCRIPTIONS_PER_CONNECTION:
                    await manager.send_personal_message({
                        "type": "error",
                        "message": f"Subscription limit exceeded. Max {manager.MAX_SUBSCRIPTIONS_PER_CONNECTION} instruments per connection"
                    }, websocket)
                    continue

                # Update local subscription set
                current_subs.update(new_set)

                # Notify middleware about subscriptions (best-effort)
                try:
                    middleware = get_middleware_instance()
                    # middleware.subscribe_ltp expects (instruments, instrument_tokens)
                    # We pass instrument strings and leave token list empty; middleware will handle mapping if needed.
                    middleware.subscribe_ltp(list(current_subs), [])
                except Exception as e:
                    logger.debug(f"Middleware subscribe failed (non-fatal): {e}")

                await manager.send_personal_message({"type": "subscribed", "count": len(current_subs)}, websocket)

            elif message_type == "unsubscribe":
                instruments = message.get("instruments") or message.get("data") or []
                if not isinstance(instruments, list):
                    await manager.send_personal_message({"type": "error", "message": "Invalid unsubscribe payload - should be a list of instruments"}, websocket)
                    continue

                meta = manager.get_meta(websocket)
                if not meta:
                    await manager.send_personal_message({"type": "error", "message": "Connection metadata missing"}, websocket)
                    continue

                current_subs = meta.get("subscriptions")
                remove_set = set(instruments) & current_subs
                if remove_set:
                    current_subs.difference_update(remove_set)
                    try:
                        middleware = get_middleware_instance()
                        middleware.unsubscribe_ltp(list(remove_set))
                    except Exception as e:
                        logger.debug(f"Middleware unsubscribe failed (non-fatal): {e}")

                await manager.send_personal_message({"type": "unsubscribed", "count": len(current_subs)}, websocket)

            else:
                logger.warning(f"Unknown message type: {message_type}")

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
async def get_websocket_status():
    """Get WebSocket connection status - now shows middleware status"""
    
    try:
        middleware = get_middleware_instance()
        status = middleware.get_status()
        # Build per-api_key connection summary
        api_keys_summary = {k: len(v) for k, v in manager.api_key_connections.items()}

        # Per-connection subscription counts
        conn_subs = []
        for meta in manager._ws_meta.values():
            conn_subs.append({
                "api_key": meta.get("api_key"),
                "subscriptions": len(meta.get("subscriptions", []))
            })

        return {
            "status": "ok",
            "connected": status["webhook_connected"],
            "active_connections": len(manager.active_connections),
            "api_key_connections": api_keys_summary,
            "connections": conn_subs,
            "subscribed_instruments (middleware)": status["subscribed_instruments"],
            "middleware_running": status["running"]
        }
    except Exception as e:
        logger.error(f"Error getting WebSocket status: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.post("/ws/reconnect")
async def reconnect_websocket():
    """Reconnect WebSocket for market data (handled by middleware based on market hours)"""
    from backend.services.market_calendar import is_market_open
    
    # Check if it's market hours
    if not is_market_open():
        return {
            "status": "error",
            "message": "WebSocket connection only available during market hours (9:15 AM - 3:30 PM)"
        }
    
    try:
        middleware = get_middleware_instance()
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
