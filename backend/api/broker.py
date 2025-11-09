"""Broker connection and authentication endpoints - Configuration via .env"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from backend.broker.kite.client import KiteBroker
from backend.broker.upstox.client import UpstoxBroker
from backend.config import settings
from backend.services.market_calendar import is_market_open, get_market_calendar
from backend.services.middleware_helper import get_middleware_instance
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/broker", tags=["broker"])


def get_broker_settings_config():
    """Get broker config from .env settings"""
    broker_type = settings.BROKER_TYPE.lower()
    
    if broker_type == "kite":
        return {
            "broker_type": broker_type,
            "api_key": settings.KITE_API_KEY,
            "api_secret": settings.KITE_API_SECRET,
            "access_token": settings.KITE_ACCESS_TOKEN,
            "user_id": settings.KITE_USER_ID
        }
    elif broker_type == "upstox":
        return {
            "broker_type": broker_type,
            "api_key": settings.UPSTOX_API_KEY,
            "api_secret": settings.UPSTOX_API_SECRET,
            "access_token": settings.UPSTOX_ACCESS_TOKEN,
            "user_id": settings.UPSTOX_USER_ID
        }
    else:
        return {}


def get_broker_client(broker_config: dict):
    """Get broker client instance"""
    broker_type = broker_config.get("broker_type")
    if broker_type == "kite":
        return KiteBroker(
            api_key=broker_config.get("api_key"),
            api_secret=broker_config.get("api_secret"),
            access_token=broker_config.get("access_token")
        )
    elif broker_type == "upstox":
        return UpstoxBroker(
            api_key=broker_config.get("api_key"),
            api_secret=broker_config.get("api_secret"),
            access_token=broker_config.get("access_token")
        )
    else:
        raise ValueError(f"Unsupported broker type: {broker_type}")


@router.get("/status/{broker_type}")
def get_broker_status_by_type(broker_type: str):
    """Get broker connection and market hours status"""
    from backend.broker.kite.exceptions import TokenException
    
    broker_config = get_broker_settings_config()
    
    if not broker_config or broker_config.get("broker_type") != broker_type:
        return {
            "configured": False,
            "connected": False,
            "token_expired": False,
            "token_expires_at": None,
            "broker_type": broker_type,
            "market_active": False,
            "status": "broker_disconnected",
            "remark": "Broker not configured",
            "seconds_to_close": None,
            "market_hours": {"start_time": "09:15", "end_time": "15:30"}
        }
    
    configured = bool(broker_config.get("api_key") and broker_config.get("api_secret"))
    connected = False
    token_expired = False
    token_expires_at = None
    
    if broker_config.get("access_token"):
        try:
            broker = get_broker_client(broker_config)
            profile = broker.get_profile()
            connected = True
        except TokenException as e:
            token_expired = True
            connected = False
        except Exception as e:
            logger.error(f"Broker connection check failed: {e}")
            connected = False
    
    market_active = is_market_open()
    market_service = get_market_calendar()
    market_times = market_service.get_market_open_close()
    
    seconds_to_close = None
    if market_active:
        time_info = market_service.time_until_market_close()
        seconds_to_close = time_info['seconds']
    
    if connected and market_active:
        status = "active"
        hours = seconds_to_close // 3600
        minutes = (seconds_to_close % 3600) // 60
        seconds = seconds_to_close % 60
        remark = f"Market closes in {hours:02d}:{minutes:02d}:{seconds:02d}"
    elif not connected and not market_active:
        status = "both_inactive"
        remark = "Market closed / Broker disconnected" if not token_expired else "Market closed / Token expired"
    elif not connected:
        status = "broker_disconnected"
        remark = "Token expired" if token_expired else "Broker disconnected"
    else:
        status = "market_closed"
        remark = "Market closed"
    
    return {
        "configured": configured,
        "connected": connected,
        "token_expired": token_expired,
        "token_expires_at": token_expires_at,
        "broker_type": broker_type,
        "market_active": market_active,
        "status": status,
        "remark": remark,
        "seconds_to_close": seconds_to_close,
        "market_hours": {
            "start_time": market_times['open'].strftime('%H:%M') if market_times['open'] else "09:15",
            "end_time": market_times['close'].strftime('%H:%M') if market_times['close'] else "15:30"
        }
    }


@router.get("/nifty50")
def get_nifty50_data():
    """Get Nifty 50 index live data"""
    NIFTY_SYMBOL = "NSE:NIFTY 50"
    NIFTY_TOKEN = 256265
    
    broker_config = get_broker_settings_config()
    
    if not broker_config or not broker_config.get("access_token"):
        return {
            "instrument_token": NIFTY_TOKEN,
            "symbol": "NIFTY 50",
            "ltp": 0,
            "error": "Broker not connected"
        }
    
    try:
        middleware = get_middleware_instance()
        quote_data = middleware.get_quote([NIFTY_SYMBOL], use_cache=True)
        
        if not quote_data or NIFTY_SYMBOL not in quote_data:
            return {
                "instrument_token": NIFTY_TOKEN,
                "symbol": "NIFTY 50",
                "ltp": 0,
                "error": "No data available"
            }
        
        nifty_data = quote_data[NIFTY_SYMBOL]
        ohlc = nifty_data.get('ohlc', {})
        last_price = nifty_data.get('last_price', 0)
        prev_close = ohlc.get('close', 0) or last_price
        
        change = last_price - prev_close if prev_close else 0
        change_percent = (change / prev_close * 100) if prev_close else 0
        
        return {
            "instrument_token": nifty_data.get('instrument_token', NIFTY_TOKEN),
            "symbol": "NIFTY 50",
            "ltp": last_price,
            "open": ohlc.get('open', 0),
            "high": ohlc.get('high', 0),
            "low": ohlc.get('low', 0),
            "close": prev_close,
            "change": round(change, 2),
            "change_percent": round(change_percent, 2),
            "volume": nifty_data.get('volume', 0),
            "timestamp": datetime.now().isoformat() + 'Z'
        }
    except Exception as e:
        logger.error(f"Error fetching Nifty 50 data: {e}")
        return {
            "instrument_token": NIFTY_TOKEN,
            "symbol": "NIFTY 50",
            "ltp": 0,
            "error": str(e)
        }


@router.post("/config")
def create_broker_config(config: dict):
    """Create or update broker configuration (stored in .env)"""
    try:
        # Note: Direct updates to .env are handled by /env-config endpoint
        # This endpoint is kept for compatibility but returns current config from .env
        return {
            "status": "success",
            "message": "Use /env-config to update broker configuration in .env",
            "broker_type": settings.BROKER_TYPE
        }
    except Exception as e:
        logger.error(f"Error updating broker config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config/{broker_type}")
def get_broker_config(broker_type: str):
    """Get broker configuration from .env"""
    try:
        config = get_broker_settings_config()
        
        if not config or config.get("broker_type") != broker_type:
            raise HTTPException(status_code=404, detail="Broker config not found")
        
        return {
            "broker_type": config.get("broker_type"),
            "user_id": config.get("user_id"),
            "is_active": bool(config.get("access_token")),
            "authenticated": bool(config.get("access_token"))
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting broker config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth-url/{broker_type}")
def get_auth_url(broker_type: str):
    """Generate broker authentication URL"""
    try:
        config = get_broker_settings_config()
        
        if not config or not config.get("api_key") or not config.get("api_secret"):
            raise HTTPException(
                status_code=400,
                detail="Broker configuration incomplete. Please set API Key and Secret in .env first."
            )
        
        broker = get_broker_client(config)
        auth_url = broker.generate_auth_url()
        return {"auth_url": auth_url}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating auth URL: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/callback")
def auth_callback(
    request_token: str = Query(...),
    action: str = Query(None),
    type: str = Query(None),
    status: str = Query(None),
    broker_type: str = Query("kite")
):
    """Handle OAuth callback and exchange for access token"""
    logger.info(f"Callback received - request_token: {request_token}")
    
    try:
        config = get_broker_settings_config()
        
        if not config:
            raise HTTPException(status_code=404, detail="Broker config not found")
        
        broker = get_broker_client(config)
        token_data = broker.get_access_token(request_token)
        
        access_token = token_data.get("access_token")
        
        # Update .env file with new access token
        from pathlib import Path
        env_path = Path(__file__).parent.parent.parent / '.env'
        
        if env_path.exists():
            with open(env_path, 'r') as f:
                lines = f.readlines()
            
            new_lines = []
            found_token = False
            key_prefix = f"{broker_type.upper()}_ACCESS_TOKEN"
            
            for line in lines:
                if line.strip().startswith(f'{key_prefix}='):
                    new_lines.append(f"{key_prefix}={access_token}\n")
                    found_token = True
                else:
                    new_lines.append(line)
            
            if not found_token:
                new_lines.append(f"\n{key_prefix}={access_token}\n")
            
            with open(env_path, 'w') as f:
                f.writelines(new_lines)
            
            # Reload settings
            from dotenv import load_dotenv
            load_dotenv(override=True)
        
        logger.info(f"Authentication successful for {broker_type}")
        
        return RedirectResponse(
            url=f"http://127.0.0.1:5173/settings?auth=success&broker={broker_type}",
            status_code=302
        )
    except Exception as e:
        logger.error(f"Error in auth callback: {str(e)}")
        return RedirectResponse(
            url=f"http://127.0.0.1:5173/settings?auth=error&message={str(e)}",
            status_code=302
        )


@router.get("/profile/{broker_type}")
def get_profile(broker_type: str):
    """Get broker profile/user information"""
    try:
        config = get_broker_settings_config()
        
        if not config or not config.get("access_token"):
            raise HTTPException(status_code=401, detail="Not authenticated with broker")
        
        broker = get_broker_client(config)
        profile = broker.get_profile()
        return profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/funds/{broker_type}")
def get_funds(broker_type: str):
    """Get available funds and margins"""
    try:
        middleware = get_middleware_instance()
        funds = middleware.get_funds(use_cache=True)
        return funds
    except Exception as e:
        logger.error(f"Error getting funds: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/available-margin/{broker_type}")
def get_available_margin(broker_type: str, segment: str = "equity"):
    """Get available margin for trading"""
    try:
        middleware = get_middleware_instance()
        funds = middleware.get_funds(use_cache=True)
        equity_data = funds.get("equity", {})
        available_cash = equity_data.get("available", {}).get("cash", 0)
        net_balance = equity_data.get("net", 0)
        
        return {
            "status": "success",
            "segment": segment,
            "available_cash": available_cash,
            "net_balance": net_balance,
            "enabled": equity_data.get("enabled", False),
            "details": equity_data
        }
    except Exception as e:
        logger.error(f"Error getting available margin: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/instruments/{broker_type}")
def get_instruments(broker_type: str, exchange: str = Query("NFO")):
    """Get available instruments"""
    try:
        config = get_broker_settings_config()
        
        if not config or not config.get("access_token"):
            raise HTTPException(status_code=401, detail="Not authenticated with broker")
        
        broker = get_broker_client(config)
        instruments = broker.get_instruments(exchange)
        
        nifty_instruments = [
            inst for inst in instruments
            if "NIFTY" in inst.get("name", "").upper() or 
               "NIFTY" in inst.get("tradingsymbol", "").upper()
        ]
        
        return nifty_instruments
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting instruments: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disconnect/{broker_type}")
def disconnect_broker(broker_type: str):
    """Disconnect broker (clear access token from .env)"""
    try:
        # Note: To disconnect, manually update .env file or use /env-config endpoint
        # This endpoint is kept for compatibility
        from pathlib import Path
        env_path = Path(__file__).parent.parent.parent / '.env'
        
        if env_path.exists():
            with open(env_path, 'r') as f:
                lines = f.readlines()
            
            new_lines = []
            key_prefix = f"{broker_type.upper()}_ACCESS_TOKEN"
            
            for line in lines:
                if line.strip().startswith(f'{key_prefix}='):
                    new_lines.append(f"{key_prefix}=\n")
                else:
                    new_lines.append(line)
            
            with open(env_path, 'w') as f:
                f.writelines(new_lines)
            
            # Reload settings
            from dotenv import load_dotenv
            load_dotenv(override=True)
        
        return {"status": "success", "message": "Broker disconnected"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disconnecting broker: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/init/{broker_type}")
def init_broker_from_env(broker_type: str):
    """Initialize broker configuration from environment variables"""
    try:
        if broker_type == "kite":
            api_key = settings.KITE_API_KEY
            api_secret = settings.KITE_API_SECRET
            user_id = settings.KITE_USER_ID
        elif broker_type == "upstox":
            api_key = settings.UPSTOX_API_KEY
            api_secret = settings.UPSTOX_API_SECRET
            user_id = settings.UPSTOX_USER_ID
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported broker type: {broker_type}")
        
        if not api_key or not api_secret:
            raise HTTPException(status_code=400, detail=f"Missing {broker_type.upper()} credentials in .env")
        
        return {
            "status": "success",
            "message": f"{broker_type.capitalize()} configuration loaded from .env",
            "broker_type": broker_type,
            "configured": True
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initializing broker from env: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/env-config/{broker_type}")
def get_env_config(broker_type: str):
    """Get broker configuration from environment variables"""
    if broker_type == "kite":
        return {
            "broker_type": broker_type,
            "api_key": settings.KITE_API_KEY or "",
            "api_secret": settings.KITE_API_SECRET or "",
            "access_token": settings.KITE_ACCESS_TOKEN or "",
            "user_id": settings.KITE_USER_ID or "",
            "password": settings.KITE_PASSWORD or "",
            "redirect_url": settings.KITE_REDIRECT_URL or "",
            "postback_url": settings.KITE_POSTBACK_URL or ""
        }
    elif broker_type == "upstox":
        return {
            "broker_type": broker_type,
            "api_key": settings.UPSTOX_API_KEY or "",
            "api_secret": settings.UPSTOX_API_SECRET or "",
            "access_token": settings.UPSTOX_ACCESS_TOKEN or "",
            "user_id": settings.UPSTOX_USER_ID or "",
            "password": settings.UPSTOX_PASSWORD or ""
        }
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported broker type: {broker_type}")


@router.post("/env-config/{broker_type}")
def update_env_config(broker_type: str, config_data: dict):
    """Update broker configuration in .env file"""
    import os
    from pathlib import Path
    
    # Get the .env file path
    env_path = Path(__file__).parent.parent.parent / '.env'
    
    if not env_path.exists():
        raise HTTPException(status_code=404, detail=".env file not found")
    
    # Read existing .env content
    with open(env_path, 'r') as f:
        lines = f.readlines()
    
    # Map config data to .env keys based on broker type
    if broker_type == "kite":
        updates = {
            'KITE_API_KEY': config_data.get('api_key', ''),
            'KITE_API_SECRET': config_data.get('api_secret', ''),
            'KITE_REDIRECT_URL': config_data.get('redirect_url', ''),
            'KITE_POSTBACK_URL': config_data.get('postback_url', ''),
            'KITE_USER_ID': config_data.get('user_id', ''),
            'KITE_PASSWORD': config_data.get('password', '')
        }
    elif broker_type == "upstox":
        updates = {
            'UPSTOX_API_KEY': config_data.get('api_key', ''),
            'UPSTOX_API_SECRET': config_data.get('api_secret', ''),
            'UPSTOX_USER_ID': config_data.get('user_id', ''),
            'UPSTOX_PASSWORD': config_data.get('password', '')
        }
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported broker type: {broker_type}")
    
    # Update lines
    updated_keys = set()
    new_lines = []
    
    for line in lines:
        line_stripped = line.strip()
        if line_stripped and not line_stripped.startswith('#'):
            key = line_stripped.split('=')[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                updated_keys.add(key)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    
    # Add missing keys
    for key, value in updates.items():
        if key not in updated_keys:
            new_lines.append(f"\n{key}={value}\n")
    
    # Write back to .env
    with open(env_path, 'w') as f:
        f.writelines(new_lines)
    
    # Reload settings
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    return {
        "status": "success",
        "message": f"{broker_type.capitalize()} configuration updated in .env file"
    }


@router.get("/quote/{broker_type}")
def get_market_quote(
    broker_type: str,
    instruments: str = Query(..., description="Comma-separated instruments")
):
    """Get full market quotes for instruments"""
    try:
        middleware = get_middleware_instance()
        instrument_list = [i.strip() for i in instruments.split(",")]
        
        if len(instrument_list) > 500:
            raise HTTPException(status_code=400, detail="Maximum 500 instruments allowed")
        
        quotes = middleware.get_quote(instrument_list, use_cache=True)
        return quotes
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting quotes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/positions/close")
def close_position(
    tradingsymbol: str,
    exchange: str,
    transaction_type: str = None,
    quantity: int = None,
    product: str = "MIS"
):
    """Close an open position"""
    try:
        middleware = get_middleware_instance()
        positions = middleware.get_positions(use_cache=True)
        
        position = None
        for pos in positions.get('net', []):
            if pos.get('tradingsymbol') == tradingsymbol and pos.get('exchange') == exchange:
                position = pos
                break
        
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")
        
        current_qty = position.get('quantity', 0)
        if current_qty == 0:
            raise HTTPException(status_code=400, detail="Position quantity is zero")
        
        if not transaction_type:
            transaction_type = 'SELL' if current_qty > 0 else 'BUY'
        
        close_qty = abs(quantity) if quantity else abs(current_qty)
        
        order_params = {
            'tradingsymbol': tradingsymbol,
            'exchange': exchange,
            'transaction_type': transaction_type,
            'order_type': 'MARKET',
            'quantity': close_qty,
            'product': product,
            'validity': 'DAY'
        }
        
        result = middleware.place_order(**order_params)
        return {"status": "success", "data": result, "message": "Position close order placed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error closing position: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
