"""Broker connection and authentication endpoints"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import BrokerConfig, Instrument
from backend.schemas import BrokerConfigCreate, BrokerConfigUpdate, BrokerConfig as BrokerConfigSchema, BrokerAuthURL
from backend.broker.kite.client import KiteBroker
from backend.broker.upstox.client import UpstoxBroker
from backend.config import settings
from backend.services.market_time import is_market_open, get_market_time_service
from backend.services.middleware_helper import get_middleware_instance
from datetime import datetime, timedelta, time
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/broker", tags=["broker"])


def get_broker_client(broker_config: BrokerConfig):
    """Get broker client instance"""
    if broker_config.broker_type == "kite":
        return KiteBroker(
            api_key=broker_config.api_key,
            api_secret=broker_config.api_secret,
            access_token=broker_config.access_token
        )
    elif broker_config.broker_type == "upstox":
        return UpstoxBroker(
            api_key=broker_config.api_key,
            api_secret=broker_config.api_secret,
            access_token=broker_config.access_token
        )
    else:
        raise ValueError(f"Unsupported broker type: {broker_config.broker_type}")


@router.get("/status/{broker_type}")
def get_broker_status_by_type(broker_type: str, db: Session = Depends(get_db)):
    """
    Get broker connection and market hours status for specific broker type
    Returns:
        - configured: bool (whether broker credentials are set)
        - connected: bool (whether broker is connected with valid token)
        - token_expired: bool (whether access token has expired)
        - token_expires_at: str (ISO timestamp of token expiry)
        - market_active: bool
        - status: "active" | "market_closed" | "broker_disconnected" | "both_inactive"
        - remark: str
        - seconds_to_close: int
    """
    from backend.broker.kite.exceptions import TokenException
    
    # Check broker configuration
    broker_config = db.query(BrokerConfig).filter(
        BrokerConfig.broker_type == broker_type
    ).first()
    
    configured = bool(broker_config and broker_config.api_key and broker_config.api_secret)
    connected = False
    token_expired = False
    token_expires_at = None
    
    if broker_config and broker_config.access_token:
        # IMMEDIATE token expiry check (database level)
        if broker_config.token_expires_at:
            token_expires_at = broker_config.token_expires_at.isoformat() + 'Z'
            if broker_config.token_expires_at < datetime.now():
                logger.warning(f"Token expired at {token_expires_at}")
                token_expired = True
                connected = False
            else:
                # Token not expired in database, verify with API
                try:
                    broker = get_broker_client(broker_config)
                    # Quick lightweight check - get profile
                    profile = broker.get_profile()
                    connected = True
                    logger.debug(f"Broker connected: {profile.get('user_name', 'Unknown')}")
                except TokenException as e:
                    logger.warning(f"Token validation failed: {e.message}")
                    token_expired = True
                    connected = False
                    # Update database to reflect expired token
                    broker_config.token_expires_at = datetime.now()
                    broker_config.is_active = False
                    db.commit()
                except Exception as e:
                    logger.error(f"Broker connection check failed: {e}")
                    connected = False
        else:
            # No expiry set - assume token doesn't expire (for debugging/development)
            # Still verify with API
            try:
                broker = get_broker_client(broker_config)
                profile = broker.get_profile()
                connected = True
            except TokenException as e:
                logger.warning(f"Token validation failed: {e.message}")
                token_expired = True
                connected = False
            except Exception as e:
                logger.error(f"Broker connection check failed: {e}")
                connected = False
    
    # Check market hours
    market_active = is_market_open(db)
    market_service = get_market_time_service(db)
    market_config = market_service.get_config()
    
    # Calculate seconds to market close
    seconds_to_close = None
    if market_active:
        time_info = market_service.time_until_market_close()
        seconds_to_close = time_info['seconds']
    
    # Determine status and remark
    if connected and market_active:
        status = "active"
        hours = seconds_to_close // 3600
        minutes = (seconds_to_close % 3600) // 60
        seconds = seconds_to_close % 60
        remark = f"Market closes in {hours:02d}:{minutes:02d}:{seconds:02d}"
    elif not connected and not market_active:
        status = "both_inactive"
        if token_expired:
            remark = "Market closed / Token expired - Re-authenticate required"
        else:
            remark = "Market closed / Broker disconnected"
    elif not connected:
        status = "broker_disconnected"
        if token_expired:
            remark = "Token expired - Re-authenticate required"
        elif not configured:
            remark = "Broker not configured"
        else:
            remark = "Broker disconnected"
    else:  # not market_active
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
            "start_time": market_config.start_time,
            "end_time": market_config.end_time
        }
    }


@router.get("/nifty50")
def get_nifty50_data(db: Session = Depends(get_db)):
    """
    Get Nifty 50 index live data (uses middleware for market-time-aware data fetching)
    Returns:
        - instrument_token: int
        - symbol: str
        - ltp: float (last traded price)
        - change: float (absolute change from previous close)
        - change_percent: float (percentage change)
        - volume: int
        - timestamp: datetime
    """
    # Nifty 50 symbol for Kite Connect
    NIFTY_SYMBOL = "NSE:NIFTY 50"
    NIFTY_TOKEN = 256265
    
    # Get active broker config
    broker_config = db.query(BrokerConfig).filter(
        BrokerConfig.is_active == True
    ).first()
    
    if not broker_config or not broker_config.access_token:
        return {
            "instrument_token": NIFTY_TOKEN,
            "symbol": "NIFTY 50",
            "ltp": 0,
            "change": 0,
            "change_percent": 0,
            "volume": 0,
            "error": "Broker not connected"
        }
    
    try:
        # Use middleware for market-time-aware data fetching
        middleware = get_middleware_instance(db)
        
        # Get quote for Nifty 50 (contains LTP + OHLC data)
        quote_data = middleware.get_quote([NIFTY_SYMBOL], use_cache=True)
        
        if not quote_data or NIFTY_SYMBOL not in quote_data:
            return {
                "instrument_token": NIFTY_TOKEN,
                "symbol": "NIFTY 50",
                "ltp": 0,
                "change": 0,
                "change_percent": 0,
                "volume": 0,
                "error": "No data available"
            }
        
        nifty_data = quote_data[NIFTY_SYMBOL]
        ohlc = nifty_data.get('ohlc', {})
        last_price = nifty_data.get('last_price', 0)
        prev_close = ohlc.get('close', 0) or last_price  # Use last_price if close is 0
        
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
            "change": 0,
            "change_percent": 0,
            "volume": 0,
            "error": str(e)
        }


@router.post("/config", response_model=BrokerConfigSchema)
def create_broker_config(config: BrokerConfigCreate, db: Session = Depends(get_db)):
    """Create or update broker configuration"""
    # Check if config exists
    existing = db.query(BrokerConfig).filter(
        BrokerConfig.broker_type == config.broker_type
    ).first()
    
    if existing:
        # Update existing
        existing.api_key = config.api_key
        existing.api_secret = config.api_secret
        existing.user_id = config.user_id
        existing.updated_at = datetime.now()
        db.commit()
        db.refresh(existing)
        return existing
    
    # Create new
    db_config = BrokerConfig(**config.dict())
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config


@router.get("/config/{broker_type}", response_model=BrokerConfigSchema)
def get_broker_config(broker_type: str, db: Session = Depends(get_db)):
    """Get broker configuration"""
    config = db.query(BrokerConfig).filter(
        BrokerConfig.broker_type == broker_type
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Broker config not found")
    
    return config


@router.get("/auth-url/{broker_type}", response_model=BrokerAuthURL)
def get_auth_url(broker_type: str, db: Session = Depends(get_db)):
    """Generate broker authentication URL"""
    config = db.query(BrokerConfig).filter(
        BrokerConfig.broker_type == broker_type
    ).first()
    
    if not config or not config.api_key or not config.api_secret:
        raise HTTPException(
            status_code=400,
            detail="Broker configuration incomplete. Please set API Key and Secret first."
        )
    
    try:
        broker = get_broker_client(config)
        auth_url = broker.generate_auth_url()
        return {"auth_url": auth_url}
    except Exception as e:
        logger.error(f"Error generating auth URL: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/callback")
def auth_callback(
    request_token: str = Query(...),
    action: str = Query(None),
    type: str = Query(None),
    status: str = Query(None),
    broker_type: str = Query("kite"),
    db: Session = Depends(get_db)
):
    """Handle OAuth callback and exchange for access token"""
    logger.info(f"Callback received - request_token: {request_token}, status: {status}, broker_type: {broker_type}")
    
    config = db.query(BrokerConfig).filter(
        BrokerConfig.broker_type == broker_type
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Broker config not found")
    
    try:
        broker = get_broker_client(config)
        token_data = broker.get_access_token(request_token)
        
        # Update config with access token
        config.access_token = token_data.get("access_token")
        config.is_active = True
        config.updated_at = datetime.now()
        
        # Set expiry if provided
        if "expires_in" in token_data:
            expires_in = token_data["expires_in"]
            config.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
        
        db.commit()
        
        logger.info(f"Authentication successful for {broker_type}")
        
        # Redirect to frontend settings page with success message
        return RedirectResponse(
            url=f"http://127.0.0.1:5174/settings?auth=success&broker={broker_type}",
            status_code=302
        )
    except Exception as e:
        logger.error(f"Error in auth callback: {str(e)}")
        # Redirect to frontend with error
        return RedirectResponse(
            url=f"http://127.0.0.1:5174/settings?auth=error&message={str(e)}",
            status_code=302
        )


@router.get("/profile/{broker_type}")
def get_profile(broker_type: str, db: Session = Depends(get_db)):
    """Get broker profile/user information"""
    config = db.query(BrokerConfig).filter(
        BrokerConfig.broker_type == broker_type
    ).first()
    
    if not config or not config.access_token:
        raise HTTPException(status_code=401, detail="Not authenticated with broker")
    
    try:
        broker = get_broker_client(config)
        profile = broker.get_profile()
        return profile
    except Exception as e:
        logger.error(f"Error getting profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/funds/{broker_type}")
def get_funds(broker_type: str, db: Session = Depends(get_db)):
    """Get available funds and margins (uses middleware)"""
    from backend.services.middleware_helper import get_middleware
    
    config = db.query(BrokerConfig).filter(
        BrokerConfig.broker_type == broker_type
    ).first()
    
    if not config or not config.access_token:
        raise HTTPException(status_code=401, detail="Not authenticated with broker")
    
    try:
        middleware = get_middleware(db)
        funds = middleware.get_funds(use_cache=True)
        return funds
    except Exception as e:
        logger.error(f"Error getting funds: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/available-margin/{broker_type}")
def get_available_margin(broker_type: str, segment: str = "equity", db: Session = Depends(get_db)):
    """
    Get available margin for trading (uses middleware)
    Returns the raw cash balance available for trading
    """
    from backend.services.middleware_helper import get_middleware
    
    config = db.query(BrokerConfig).filter(
        BrokerConfig.broker_type == broker_type
    ).first()
    
    if not config or not config.access_token:
        raise HTTPException(status_code=401, detail="Not authenticated with broker")
    
    try:
        middleware = get_middleware(db)
        funds = middleware.get_funds(use_cache=True)
        
        # Extract equity segment data
        equity_data = funds.get("equity", {})
        
        # Get available cash for trading (includes intraday_payin)
        available_cash = equity_data.get("available", {}).get("cash", 0)
        net_balance = equity_data.get("net", 0)
        
        return {
            "status": "success",
            "segment": segment,
            "available_cash": available_cash,
            "net_balance": net_balance,
            "enabled": equity_data.get("enabled", False),
            "utilised": equity_data.get("utilised", {}),
            "details": equity_data
        }
    except Exception as e:
        logger.error(f"Error getting available margin: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/instruments/{broker_type}")
def get_instruments(
    broker_type: str,
    exchange: str = Query("NFO"),
    db: Session = Depends(get_db)
):
    """Get available instruments"""
    config = db.query(BrokerConfig).filter(
        BrokerConfig.broker_type == broker_type
    ).first()
    
    if not config or not config.access_token:
        raise HTTPException(status_code=401, detail="Not authenticated with broker")
    
    try:
        broker = get_broker_client(config)
        instruments = broker.get_instruments(exchange)
        
        # Filter for Nifty instruments
        nifty_instruments = [
            inst for inst in instruments
            if "NIFTY" in inst.get("name", "").upper() or 
               "NIFTY" in inst.get("tradingsymbol", "").upper()
        ]
        
        return nifty_instruments
    except Exception as e:
        logger.error(f"Error getting instruments: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disconnect/{broker_type}")
def disconnect_broker(broker_type: str, db: Session = Depends(get_db)):
    """Disconnect broker (clear access token)"""
    config = db.query(BrokerConfig).filter(
        BrokerConfig.broker_type == broker_type
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Broker config not found")
    
    config.access_token = None
    config.is_active = False
    config.updated_at = datetime.now()
    db.commit()
    
    return {"status": "success", "message": "Broker disconnected"}


# Removed duplicate - using first get_broker_status endpoint at line 22


@router.post("/init/{broker_type}")
def init_broker_from_env(broker_type: str, db: Session = Depends(get_db)):
    """Initialize broker configuration from environment variables"""
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
        raise HTTPException(
            status_code=400,
            detail=f"Missing {broker_type.upper()} credentials in environment variables"
        )
    
    # Check if config exists
    config = db.query(BrokerConfig).filter(
        BrokerConfig.broker_type == broker_type
    ).first()
    
    if config:
        # Update existing
        config.api_key = api_key
        config.api_secret = api_secret
        config.user_id = user_id
        config.updated_at = datetime.now()
    else:
        # Create new
        config = BrokerConfig(
            broker_type=broker_type,
            api_key=api_key,
            api_secret=api_secret,
            user_id=user_id
        )
        db.add(config)
    
    db.commit()
    db.refresh(config)
    
    return {
        "status": "success",
        "message": f"{broker_type.capitalize()} configuration initialized",
        "broker_type": broker_type,
        "configured": True
    }


@router.get("/env-config/{broker_type}")
def get_env_config(broker_type: str):
    """Get broker configuration from environment variables"""
    if broker_type == "kite":
        return {
            "broker_type": broker_type,
            "api_key": settings.KITE_API_KEY or "",
            "api_secret": settings.KITE_API_SECRET or "",
            "redirect_url": settings.KITE_REDIRECT_URL or "",
            "postback_url": settings.KITE_POSTBACK_URL or "",
            "user_id": settings.KITE_USER_ID or ""
        }
    elif broker_type == "upstox":
        return {
            "broker_type": broker_type,
            "api_key": settings.UPSTOX_API_KEY or "",
            "api_secret": settings.UPSTOX_API_SECRET or "",
            "user_id": settings.UPSTOX_USER_ID or ""
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
    
    # Update or add configuration
    if broker_type == "kite":
        updates = {
            'KITE_API_KEY': config_data.get('api_key', ''),
            'KITE_API_SECRET': config_data.get('api_secret', ''),
            'KITE_REDIRECT_URL': config_data.get('redirect_url', ''),
            'KITE_POSTBACK_URL': config_data.get('postback_url', ''),
            'KITE_USER_ID': config_data.get('user_id', '')
        }
    elif broker_type == "upstox":
        updates = {
            'UPSTOX_API_KEY': config_data.get('api_key', ''),
            'UPSTOX_API_SECRET': config_data.get('api_secret', ''),
            'UPSTOX_USER_ID': config_data.get('user_id', '')
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


@router.get("/orders/{broker_type}")
def get_broker_orders(broker_type: str, db: Session = Depends(get_db)):
    """Get all orders from broker for the day (uses middleware)"""
    from backend.services.middleware_helper import get_middleware
    
    config = db.query(BrokerConfig).filter(
        BrokerConfig.broker_type == broker_type
    ).first()
    
    if not config or not config.access_token:
        raise HTTPException(status_code=401, detail="Not authenticated with broker")
    
    try:
        middleware = get_middleware(db)
        orders = middleware.get_orders(use_cache=False)
        return orders
    except Exception as e:
        logger.error(f"Error getting orders: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trades/{broker_type}")
def get_broker_trades(broker_type: str, db: Session = Depends(get_db)):
    """Get all executed trades from broker for the day"""
    config = db.query(BrokerConfig).filter(
        BrokerConfig.broker_type == broker_type
    ).first()
    
    if not config or not config.access_token:
        raise HTTPException(status_code=401, detail="Not authenticated with broker")
    
    try:
        broker = get_broker_client(config)
        trades = broker.get_trades()
        return trades
    except Exception as e:
        logger.error(f"Error getting trades: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions/{broker_type}")
def get_broker_positions(broker_type: str, db: Session = Depends(get_db)):
    """Get all positions from broker (uses middleware)"""
    from backend.services.middleware_helper import get_middleware
    
    config = db.query(BrokerConfig).filter(
        BrokerConfig.broker_type == broker_type
    ).first()
    
    if not config or not config.access_token:
        raise HTTPException(status_code=401, detail="Not authenticated with broker")
    
    try:
        middleware = get_middleware(db)
        positions = middleware.get_positions(use_cache=True)
        return positions
    except Exception as e:
        logger.error(f"Error getting positions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/instruments/status/{broker_type}")
def get_instruments_status(
    broker_type: str,
    db: Session = Depends(get_db)
):
    """Get instrument download status"""
    from datetime import date
    from sqlalchemy import func
    
    try:
        # Get count and last updated time
        result = db.query(
            func.count(Instrument.id).label('count'),
            func.max(Instrument.updated_at).label('last_download')
        ).first()
        
        count = result.count if result.count else 0
        last_download = result.last_download
        
        # Check if downloaded today
        downloaded_today = False
        if last_download:
            downloaded_today = last_download.date() == date.today()
        
        return {
            "count": count,
            "last_download": last_download.isoformat() + 'Z' if last_download else None,
            "downloaded_today": downloaded_today
        }
    except Exception as e:
        logger.error(f"Error getting instrument status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/instruments/download/{broker_type}")
def download_instruments(
    broker_type: str,
    exchange: str = Query(None, description="Filter by exchange (NSE, BSE, NFO, etc.)"),
    db: Session = Depends(get_db)
):
    """Download instruments from broker and store in database
    
    This will fetch the latest instruments list from the broker API and store/update in the database.
    Warning: This operation can take time as it processes thousands of instruments.
    """
    from backend.models import InstrumentDownloadLog
    from datetime import datetime
    
    config = db.query(BrokerConfig).filter(
        BrokerConfig.broker_type == broker_type
    ).first()
    
    if not config or not config.access_token:
        raise HTTPException(status_code=401, detail="Not authenticated with broker")
    
    download_start = datetime.now()
    
    try:
        broker = get_broker_client(config)
        instruments_data = broker.get_instruments(exchange)
        
        # Clear existing instruments if no exchange filter (full refresh)
        if not exchange:
            db.query(Instrument).delete()
        else:
            # Clear only instruments from the specified exchange
            db.query(Instrument).filter(Instrument.exchange == exchange).delete()
        
        # Batch insert new instruments
        instruments_to_add = []
        for inst_data in instruments_data:
            instrument = Instrument(
                instrument_token=str(inst_data.get("instrument_token")),
                exchange_token=str(inst_data.get("exchange_token")) if inst_data.get("exchange_token") else None,
                tradingsymbol=inst_data.get("tradingsymbol"),
                name=inst_data.get("name"),
                last_price=inst_data.get("last_price", 0.0),
                expiry=str(inst_data.get("expiry")) if inst_data.get("expiry") else None,
                strike=inst_data.get("strike"),
                tick_size=inst_data.get("tick_size"),
                lot_size=inst_data.get("lot_size"),
                instrument_type=inst_data.get("instrument_type"),
                segment=inst_data.get("segment"),
                exchange=inst_data.get("exchange")
            )
            instruments_to_add.append(instrument)
        
        db.bulk_save_objects(instruments_to_add)
        
        # Record manual download in log
        download_log = InstrumentDownloadLog(
            download_date=download_start,
            instrument_count=len(instruments_to_add),
            download_type="manual",
            source="broker_api",
            status="completed"
        )
        db.add(download_log)
        db.commit()
        
        count = len(instruments_to_add)
        duration = (datetime.now() - download_start).total_seconds()
        logger.info(f"Downloaded and stored {count} instruments in {duration:.2f}s")
        
        return {
            "status": "success",
            "message": f"Downloaded and stored {count} instruments in {duration:.2f} seconds",
            "count": count,
            "exchange": exchange or "all",
            "duration_seconds": round(duration, 2)
        }
    except Exception as e:
        db.rollback()
        
        # Record failed download in log
        download_log = InstrumentDownloadLog(
            download_date=download_start,
            instrument_count=0,
            download_type="manual",
            source="broker_api",
            status="failed",
            error_message=str(e)
        )
        db.add(download_log)
        db.commit()
        
        logger.error(f"Error downloading instruments: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/instruments")
def get_instruments(
    exchange: str = Query(None, description="Filter by exchange"),
    instrument_type: str = Query(None, description="Filter by instrument type"),
    segment: str = Query(None, description="Filter by segment"),
    search: str = Query(None, description="Search by symbol or name"),
    strike_min: float = Query(None, description="Minimum strike price"),
    strike_max: float = Query(None, description="Maximum strike price"),
    limit: int = Query(10000, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination"),
    db: Session = Depends(get_db)
):
    """Get instruments from database with filters"""
    try:
        query = db.query(Instrument)
        
        # Apply filters
        if exchange:
            query = query.filter(Instrument.exchange == exchange)
        if instrument_type:
            query = query.filter(Instrument.instrument_type == instrument_type)
        if segment:
            query = query.filter(Instrument.segment == segment)
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (Instrument.tradingsymbol.ilike(search_term)) |
                (Instrument.name.ilike(search_term))
            )
        if strike_min is not None:
            query = query.filter(Instrument.strike >= strike_min)
        if strike_max is not None:
            query = query.filter(Instrument.strike <= strike_max)
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination
        instruments = query.offset(offset).limit(limit).all()
        
        # Convert to dict
        instruments_data = [
            {
                "instrument_token": inst.instrument_token,
                "exchange_token": inst.exchange_token,
                "tradingsymbol": inst.tradingsymbol,
                "name": inst.name,
                "last_price": inst.last_price,
                "expiry": inst.expiry,
                "strike": inst.strike,
                "tick_size": inst.tick_size,
                "lot_size": inst.lot_size,
                "instrument_type": inst.instrument_type,
                "segment": inst.segment,
                "exchange": inst.exchange
            }
            for inst in instruments
        ]
        
        return {
            "data": instruments_data,
            "count": len(instruments_data),
            "total": total_count,
            "offset": offset,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error getting instruments from database: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/instruments/stats")
def get_instruments_stats(db: Session = Depends(get_db)):
    """Get statistics about stored instruments"""
    try:
        total = db.query(Instrument).count()
        
        # Count by exchange
        from sqlalchemy import func
        by_exchange = db.query(
            Instrument.exchange,
            func.count(Instrument.id).label('count')
        ).group_by(Instrument.exchange).all()
        
        # Count by instrument type
        by_type = db.query(
            Instrument.instrument_type,
            func.count(Instrument.id).label('count')
        ).group_by(Instrument.instrument_type).all()
        
        # Get unique segments
        segments = db.query(Instrument.segment).distinct().filter(
            Instrument.segment.isnot(None)
        ).order_by(Instrument.segment).all()
        
        # Get last update time
        last_updated = db.query(func.max(Instrument.updated_at)).scalar()
        
        return {
            "total": total,
            "by_exchange": {ex: count for ex, count in by_exchange},
            "by_type": {typ: count for typ, count in by_type if typ},
            "segments": [seg[0] for seg in segments if seg[0]],
            "last_updated": last_updated.isoformat() + 'Z' if last_updated else None
        }
    except Exception as e:
        logger.error(f"Error getting positions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quote/{broker_type}")
def get_market_quote(
    broker_type: str,
    instruments: str = Query(..., description="Comma-separated list of instruments (e.g., NSE:INFY,NSE:SBIN)"),
    db: Session = Depends(get_db)
):
    """Get full market quotes for instruments (max 500) - uses middleware"""
    from backend.services.middleware_helper import get_middleware
    
    config = db.query(BrokerConfig).filter(
        BrokerConfig.broker_type == broker_type
    ).first()
    
    if not config or not config.access_token:
        raise HTTPException(status_code=401, detail="Not authenticated with broker")
    
    try:
        middleware = get_middleware(db)
        instrument_list = [i.strip() for i in instruments.split(",")]
        
        if len(instrument_list) > 500:
            raise HTTPException(status_code=400, detail="Maximum 500 instruments allowed")
        
        quotes = middleware.get_quote(instrument_list, use_cache=True)
        return quotes
    except Exception as e:
        logger.error(f"Error getting quotes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/orders/{variety}/{order_id}")
def cancel_order(
    variety: str,
    order_id: str,
    db: Session = Depends(get_db)
):
    """Cancel an open or pending order
    
    Args:
        variety: Order variety (regular, amo, co, iceberg, auction)
        order_id: Unique order ID to cancel
    """
    # Get active broker config
    config = db.query(BrokerConfig).filter(
        BrokerConfig.is_active == True
    ).first()
    
    if not config or not config.access_token:
        raise HTTPException(status_code=401, detail="Not authenticated with broker")
    
    try:
        # Use middleware to cancel order
        middleware = get_middleware_instance(db)
        result = middleware.cancel_order(order_id=order_id, variety=variety)
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Error cancelling order: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/orders/{variety}/{order_id}")
def modify_order(
    variety: str,
    order_id: str,
    order_type: str = None,
    quantity: int = None,
    price: float = None,
    trigger_price: float = None,
    disclosed_quantity: int = None,
    validity: str = None,
    db: Session = Depends(get_db)
):
    """Modify an open or pending order
    
    Args:
        variety: Order variety (regular, amo, co, iceberg, auction)
        order_id: Unique order ID to modify
        order_type: Order type (MARKET, LIMIT, SL, SL-M)
        quantity: New quantity
        price: New limit price (for LIMIT orders)
        trigger_price: New trigger price (for SL orders)
        disclosed_quantity: New disclosed quantity
        validity: Order validity (DAY, IOC, TTL)
    """
    # Get active broker config
    config = db.query(BrokerConfig).filter(
        BrokerConfig.is_active == True
    ).first()
    
    if not config or not config.access_token:
        raise HTTPException(status_code=401, detail="Not authenticated with broker")
    
    try:
        # Use middleware to modify order
        middleware = get_middleware_instance(db)
        
        # Build params dict with only provided values
        params = {}
        if order_type is not None:
            params['order_type'] = order_type
        if quantity is not None:
            params['quantity'] = quantity
        if price is not None:
            params['price'] = price
        if trigger_price is not None:
            params['trigger_price'] = trigger_price
        if disclosed_quantity is not None:
            params['disclosed_quantity'] = disclosed_quantity
        if validity is not None:
            params['validity'] = validity
        
        result = middleware.modify_order(order_id=order_id, variety=variety, **params)
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Error modifying order: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/positions/close")
def close_position(
    tradingsymbol: str,
    exchange: str,
    transaction_type: str = None,
    quantity: int = None,
    product: str = "MIS",
    db: Session = Depends(get_db)
):
    """Close/square off an open position
    
    This places a reverse order to close the position.
    
    Args:
        tradingsymbol: Trading symbol of the position
        exchange: Exchange (NSE, NFO, etc.)
        transaction_type: BUY or SELL (optional, will be determined from position)
        quantity: Quantity to close (optional, will close full position if not specified)
        product: Product type (MIS, NRML, CNC)
    """
    # Get active broker config
    config = db.query(BrokerConfig).filter(
        BrokerConfig.is_active == True
    ).first()
    
    if not config or not config.access_token:
        raise HTTPException(status_code=401, detail="Not authenticated with broker")
    
    try:
        # Get middleware instance
        middleware = get_middleware_instance(db)
        
        # Get current positions via middleware (uses cached data)
        positions = middleware.get_positions(use_cache=True)
        
        # Find the position
        position = None
        for pos in positions.get('net', []):
            if pos.get('tradingsymbol') == tradingsymbol and pos.get('exchange') == exchange:
                position = pos
                break
        
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")
        
        # Determine reverse transaction type
        current_qty = position.get('quantity', 0)
        if current_qty == 0:
            raise HTTPException(status_code=400, detail="Position quantity is zero")
        
        # Determine transaction type for closing
        if not transaction_type:
            transaction_type = 'SELL' if current_qty > 0 else 'BUY'
        
        # Use absolute quantity
        close_qty = abs(quantity) if quantity else abs(current_qty)
        
        # Place market order to close position via middleware
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
        return {"status": "success", "data": result, "message": f"Position close order placed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error closing position: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orders/place")
def place_manual_order(
    tradingsymbol: str,
    exchange: str,
    transaction_type: str,
    quantity: int,
    order_type: str,
    product: str = "MIS",
    variety: str = "regular",
    price: float = None,
    trigger_price: float = None,
    validity: str = "DAY",
    tag: str = None,
    db: Session = Depends(get_db)
):
    """Place a manual order
    
    This endpoint allows placing orders manually with full control over all parameters.
    
    Args:
        tradingsymbol: Trading symbol (e.g., "NIFTY2411118000CE")
        exchange: Exchange code (NSE, BSE, NFO, BFO, CDS, MCX, BCD)
        transaction_type: BUY or SELL
        quantity: Quantity to transact
        order_type: MARKET, LIMIT, SL, SL-M
        product: CNC (Cash), NRML (Normal), MIS (Intraday), MTF (Margin)
        variety: regular, amo, co, iceberg, auction
        price: Limit price (required for LIMIT orders)
        trigger_price: Trigger price (required for SL/SL-M orders)
        validity: DAY, IOC, TTL
        tag: Optional tag to identify the order
    
    Returns:
        {"status": "success", "order_id": "...", "message": "..."}
    """
    # Get active broker config
    config = db.query(BrokerConfig).filter(
        BrokerConfig.is_active == True
    ).first()
    
    if not config or not config.access_token:
        raise HTTPException(status_code=401, detail="Not authenticated with broker")
    
    # Validate required fields
    if order_type == "LIMIT" and price is None:
        raise HTTPException(status_code=400, detail="Price is required for LIMIT orders")
    
    if order_type in ["SL", "SL-M"] and trigger_price is None:
        raise HTTPException(status_code=400, detail="Trigger price is required for SL/SL-M orders")
    
    try:
        # Use middleware to place order
        middleware = get_middleware_instance(db)
        
        # Build order parameters
        order_params = {
            'tradingsymbol': tradingsymbol,
            'exchange': exchange,
            'transaction_type': transaction_type.upper(),
            'quantity': quantity,
            'order_type': order_type.upper(),
            'product': product.upper(),
            'variety': variety,
            'validity': validity.upper()
        }
        
        # Add optional parameters
        if price is not None:
            order_params['price'] = price
        if trigger_price is not None:
            order_params['trigger_price'] = trigger_price
        if tag:
            order_params['tag'] = tag
        
        # Place the order via middleware
        result = middleware.place_order(**order_params)
        
        logger.info(f"Manual order placed: {transaction_type} {quantity} {tradingsymbol} @ {price or 'MARKET'}")
        
        return {
            "status": "success",
            "data": result,
            "message": f"Order placed successfully: {transaction_type} {quantity} {tradingsymbol}"
        }
    except Exception as e:
        logger.error(f"Error placing manual order: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

