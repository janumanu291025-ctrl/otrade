"""
Live Trading V2 API Endpoints
==============================

REST API endpoints for Live Trading Engine V2 with enhanced features:
- Real broker fund management
- Token expiry handling
- Crash recovery with reconciliation
- Contract expiry filtering
- Comprehensive status reporting
- Trade and position management
"""
from fastapi import APIRouter, HTTPException, Depends, Body, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
import pytz
import pandas as pd

from backend.database import get_db
from backend.models import (
    TradingConfig, LiveTrade, LiveTradingAlert, LiveTradingState,
    LiveTradingMarketData, LiveTradingSignal, Instrument
)
from backend.broker.base import TokenExpiredError
from backend.config import settings
from backend.services.live_trading_engine_v2 import LiveTradingEngineV2
from backend.services.middleware_helper import get_middleware_instance
from backend.utils.cache import (
    get_status_cache, get_positions_cache, get_trades_cache,
    invalidate_cache_pattern
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/live-trading-v2", tags=["live_trading_v2"])

# Global engine instance
_engine_instance: Optional[LiveTradingEngineV2] = None


def get_engine() -> Optional[LiveTradingEngineV2]:
    """Get current live trading V2 engine instance"""
    return _engine_instance


@router.post("/start")
async def start_live_trading(
    config_id: int = Query(..., description="Trading config ID"),
    contract_expiry: Optional[str] = Query(None, description="Contract expiry filter (YYYY-MM-DD or YYMMDD)"),
    db: Session = Depends(get_db)
) -> Dict:
    """
    Start live trading engine V2
    
    Args:
        config_id: Trading configuration ID
        contract_expiry: Optional contract expiry filter for option contracts
        
    Returns:
        Status, config details, and initial funds info
        
    Raises:
        401: Token expired (user must re-authenticate)
        404: Config not found
        500: Market closed or other startup error
    """
    global _engine_instance
    
    try:
        # Check if already running
        if _engine_instance and _engine_instance.running:
            return {
                "status": "already_running",
                "message": "Live trading engine is already running",
                "config_id": _engine_instance.config.id,
                "paused": _engine_instance.paused
            }
        
        # Load config
        config = db.query(TradingConfig).filter(
            TradingConfig.id == config_id
        ).first()
        
        if not config:
            raise HTTPException(status_code=404, detail=f"Config {config_id} not found")
        
        # Get unified broker middleware
        middleware = get_middleware_instance()
        if not middleware:
            raise HTTPException(status_code=500, detail="Broker not configured. Please authenticate first.")
        
        # Create and start engine
        _engine_instance = LiveTradingEngineV2(
            middleware=middleware,
            db=db
        )
        
        if not _engine_instance.load_config(config_id):
            raise HTTPException(status_code=500, detail="Failed to load config")
        
        # Start engine with contract expiry filter
        await _engine_instance.start(contract_expiry=contract_expiry)
        
        # Invalidate status cache on start
        invalidate_cache_pattern(get_status_cache(), f"status_{config_id}")
        
        # Register with webhook for live updates
        from backend.api.webhook import set_live_trading_engine
        set_live_trading_engine(_engine_instance)
        
        return {
            "status": "started",
            "message": "Live trading engine started successfully",
            "config_id": config.id,
            "config_name": config.name,
            "contract_expiry": contract_expiry or "auto-detect",
            "funds": {
                "available": _engine_instance.available_funds,
                "allocated": _engine_instance.allocated_funds,
                "utilization_pct": (
                    (_engine_instance.allocated_funds / _engine_instance.available_funds * 100)
                    if _engine_instance.available_funds > 0 else 0
                )
            },
            "started_at": config.started_at.isoformat() if config.started_at else None
        }
        
    except TokenExpiredError:
        # Token expired - return 401 to trigger frontend re-authentication
        raise HTTPException(
            status_code=401,
            detail="Access token expired. Please re-authenticate with your broker."
        )
    except Exception as e:
        logger.error(f"Error starting live trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_live_trading(
    db: Session = Depends(get_db)
) -> Dict:
    """
    Stop live trading engine and square off all positions
    
    Returns:
        Status and square-off summary
        
    Raises:
        404: Engine not running
        401: Token expired during square-off
    """
    global _engine_instance
    
    try:
        if not _engine_instance or not _engine_instance.running:
            raise HTTPException(status_code=404, detail="Live trading engine is not running")
        
        # Stop engine (squares off all positions)
        await _engine_instance.stop()
        
        config_id = _engine_instance.config.id if _engine_instance.config else None
        
        # Invalidate all caches for this config
        if config_id:
            invalidate_cache_pattern(get_status_cache(), f"status_{config_id}")
            invalidate_cache_pattern(get_positions_cache(), f"positions_{config_id}")
            invalidate_cache_pattern(get_trades_cache(), f"trades_{config_id}")
        
        # Clear instance
        _engine_instance = None
        
        # Unregister from webhook
        from backend.api.webhook import set_live_trading_engine
        set_live_trading_engine(None)
        
        return {
            "status": "stopped",
            "message": "Live trading engine stopped and all positions squared off",
            "config_id": config_id,
            "stopped_at": datetime.now().isoformat()
        }
        
    except TokenExpiredError:
        raise HTTPException(
            status_code=401,
            detail="Access token expired during stop operation. Positions may still be open at broker."
        )
    except Exception as e:
        logger.error(f"Error stopping live trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pause")
async def pause_live_trading(
    db: Session = Depends(get_db)
) -> Dict:
    """
    Pause live trading (stops new entries but keeps monitoring positions)
    
    Returns:
        Status confirmation
        
    Raises:
        404: Engine not running
    """
    global _engine_instance
    
    try:
        if not _engine_instance or not _engine_instance.running:
            raise HTTPException(status_code=404, detail="Live trading engine is not running")
        
        if _engine_instance.paused:
            return {
                "status": "already_paused",
                "message": "Live trading is already paused"
            }
        
        await _engine_instance.pause()
        
        # Invalidate status cache
        invalidate_cache_pattern(get_status_cache(), f"status_{_engine_instance.config.id}")
        
        return {
            "status": "paused",
            "message": "Live trading paused. No new entries will be made.",
            "paused_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error pausing live trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resume")
async def resume_live_trading(
    db: Session = Depends(get_db)
) -> Dict:
    """
    Resume live trading after pause or token expiry
    
    Returns:
        Status confirmation with current funds
        
    Raises:
        404: Engine not running
        401: Token still expired
        500: Market closed
    """
    global _engine_instance
    
    try:
        if not _engine_instance or not _engine_instance.running:
            raise HTTPException(status_code=404, detail="Live trading engine is not running")
        
        if not _engine_instance.paused:
            return {
                "status": "already_running",
                "message": "Live trading is already running (not paused)"
            }
        
        # Resume (includes market hours check)
        await _engine_instance.resume()
        
        # Invalidate status cache
        invalidate_cache_pattern(get_status_cache(), f"status_{_engine_instance.config.id}")
        
        return {
            "status": "resumed",
            "message": "Live trading resumed successfully",
            "funds": {
                "available": _engine_instance.available_funds,
                "allocated": _engine_instance.allocated_funds,
                "utilization_pct": (
                    (_engine_instance.allocated_funds / _engine_instance.available_funds * 100)
                    if _engine_instance.available_funds > 0 else 0
                )
            },
            "resumed_at": datetime.now().isoformat()
        }
        
    except TokenExpiredError:
        raise HTTPException(
            status_code=401,
            detail="Access token still expired. Please re-authenticate with your broker."
        )
    except Exception as e:
        logger.error(f"Error resuming live trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_live_trading_status() -> Dict:
    """
    Get current live trading status with comprehensive details
    
    Returns:
        Engine status, funds, positions, trades, statistics, market data and trends
        
    Note: Response is cached for 2 seconds to optimize performance
    During off-market hours, fetches data from middleware with adaptive polling
    """
    from backend.services.market_calendar import get_market_status
    
    global _engine_instance
    
    try:
        # Get middleware instance
        middleware = get_middleware_instance()
        
        # Check market status
        market_status = get_market_status()
        is_market_open = market_status.get("is_open", False)
        
        if not _engine_instance:
            # Engine not running - always try to fetch data from middleware
            # This ensures frontend gets market data even when engine is stopped
            access_token = None
            broker_type = settings.BROKER_TYPE.lower()
            
            if broker_type == "kite":
                access_token = settings.KITE_ACCESS_TOKEN
            elif broker_type == "upstox":
                access_token = settings.UPSTOX_ACCESS_TOKEN
            
            if not access_token:
                # No broker authentication - return minimal status
                return {
                    "running": False,
                    "message": "Live trading engine not initialized (broker not authenticated)"
                }
            
            try:
                # Fetch comprehensive data via middleware (handles market-time-aware data fetching)
                # Middleware adapts polling based on market hours (1s during market, 15min off-market)
                
                # Fetch funds via middleware (uses cached data with adaptive polling)
                funds = middleware.get_funds(use_cache=True)
                equity_funds = funds.get("equity", {})
                available_funds = equity_funds.get("available", {}).get("live_balance", 0)
                
                # Fetch positions via middleware
                positions = middleware.get_positions(use_cache=True)
                net_positions = positions.get("net", [])
                open_position_count = len([p for p in net_positions if p.get("quantity", 0) != 0])
                
                # Fetch orders via middleware (always fresh for accuracy)
                orders = middleware.get_orders(use_cache=False)
                # Count only completed/executed orders
                completed_orders = [o for o in orders if o.get("status") == "COMPLETE"]
                today_orders = len(completed_orders)
                
                # Get Nifty LTP via middleware
                quotes = middleware.get_quote(["NSE:NIFTY 50"], use_cache=True)
                nifty_quote = quotes.get("NSE:NIFTY 50", {})
                nifty_ltp = nifty_quote.get("last_price", 0)
                ohlc = nifty_quote.get("ohlc", {})
                prev_close = ohlc.get("close", 0)
                nifty_change = nifty_ltp - prev_close if prev_close else 0
                nifty_change_pct = (nifty_change / prev_close * 100) if prev_close else 0
                
                # Get saved market data for trends - skip database lookup, will calculate below
                latest_market_data = None
                
                # If no saved data, try to calculate from historical candles
                major_trend = None
                major_ma7 = None
                major_ma20 = None
                major_lbb = None
                major_ubb = None
                major_trend_changed_at = None
                minor_trend = None
                minor_ma7 = None
                minor_ma20 = None
                minor_lbb = None
                minor_ubb = None
                minor_trend_changed_at = None
                
                if latest_market_data:
                    major_trend = latest_market_data.major_trend
                    major_ma7 = latest_market_data.major_ma7
                    major_ma20 = latest_market_data.major_ma20
                    minor_trend = latest_market_data.minor_trend
                    minor_ma7 = latest_market_data.minor_ma7
                    minor_ma20 = latest_market_data.minor_ma20
                    # Note: LBB/UBB not stored in LiveTradingMarketData, will calculate from historical
                else:
                    # Fetch historical data and calculate indicators
                    try:
                        from datetime import timedelta
                        from collections import deque
                        from backend.services.trading_logic_service import TradingLogicService
                        
                        # Get NIFTY 50 token
                        nifty_token = 256265  # NSE NIFTY 50
                        
                        # Fetch 15min candles for major trend (last 30 candles = 7.5 hours)
                        now = datetime.now()
                        # Go back to last trading day if it's weekend or after market hours
                        # Saturday=5, Sunday=6, Friday=4
                        while now.weekday() > 4:  # Go back to Friday or earlier
                            now -= timedelta(days=1)
                        
                        # If it's before market open, go back to previous day
                        if now.hour < 9 or (now.hour == 9 and now.minute < 15):
                            now -= timedelta(days=1)
                            while now.weekday() > 4:  # Make sure it's a weekday
                                now -= timedelta(days=1)
                        
                        end_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
                        start_time = end_time - timedelta(hours=12)
                        
                        major_candles = middleware.get_historical_data(
                            instrument_token=nifty_token,
                            from_date=start_time,
                            to_date=end_time,
                            interval="15minute"
                        )
                        
                        # Fetch 1min candles for minor trend (last 30 candles = 30 minutes)
                        minor_candles = middleware.get_historical_data(
                            instrument_token=nifty_token,
                            from_date=end_time - timedelta(hours=1),
                            to_date=end_time,
                            interval="minute"
                        )
                        
                        trading_logic = TradingLogicService()
                        
                        if major_candles and len(major_candles) >= 20:
                            major_ind = trading_logic.calculate_indicators_from_deque(deque(major_candles))
                            if major_ind:
                                major_trend = major_ind.get('trend')
                                major_ma7 = major_ind.get('ma7')
                                major_ma20 = major_ind.get('ma20')
                                major_lbb = major_ind.get('lbb')
                                major_ubb = major_ind.get('ubb')
                        
                        if minor_candles and len(minor_candles) >= 20:
                            minor_ind = trading_logic.calculate_indicators_from_deque(deque(minor_candles))
                            if minor_ind:
                                minor_trend = minor_ind.get('trend')
                                minor_ma7 = minor_ind.get('ma7')
                                minor_ma20 = minor_ind.get('ma20')
                                minor_lbb = minor_ind.get('lbb')
                                minor_ubb = minor_ind.get('ubb')
                    except Exception as e:
                        logger.warning(f"Could not calculate indicators from historical data: {e}")
                
                # Calculate allocated funds for next trade
                # Default allocation percentage (16% per trade)
                capital_allocation_pct = 16.0
                allocated_per_trade = available_funds * (capital_allocation_pct / 100.0)
                
                # Calculate how much is locked in open positions
                locked_in_positions = sum(p.get("value", 0) for p in net_positions if p.get("quantity", 0) != 0)
                
                # Remaining available = total available - locked
                remaining_available = available_funds - abs(locked_in_positions)
                
                return {
                    "running": False,
                    "message": "Live trading engine not running (data from broker via middleware)",
                    "market_open": is_market_open,
                    "funds": {
                        "available": round(available_funds, 2),
                        "allocated": round(allocated_per_trade, 2),
                        "remaining": round(remaining_available, 2),
                        "utilization_pct": round((abs(locked_in_positions) / available_funds * 100) if available_funds > 0 else 0, 2)
                    },
                    "positions": {
                        "open": open_position_count,
                        "max_allowed": 2
                    },
                    "trades": {
                        "today": today_orders,
                        "total": 0
                    },
                    "pnl": {
                        "realized": 0,
                        "unrealized": 0,
                        "total": 0
                    },
                    "nifty_ltp": round(nifty_ltp, 2),
                    "nifty_change": round(nifty_change, 2),
                    "nifty_change_pct": round(nifty_change_pct, 2),
                    "major_trend": major_trend,
                    "major_ma7": round(major_ma7, 2) if major_ma7 else None,
                    "major_ma20": round(major_ma20, 2) if major_ma20 else None,
                    "major_lbb": round(major_lbb, 2) if major_lbb else None,
                    "major_ubb": round(major_ubb, 2) if major_ubb else None,
                    "major_trend_changed_at": major_trend_changed_at,
                    "minor_trend": minor_trend,
                    "minor_ma7": round(minor_ma7, 2) if minor_ma7 else None,
                    "minor_ma20": round(minor_ma20, 2) if minor_ma20 else None,
                    "minor_lbb": round(minor_lbb, 2) if minor_lbb else None,
                    "minor_ubb": round(minor_ubb, 2) if minor_ubb else None,
                    "minor_trend_changed_at": minor_trend_changed_at,
                    "major_timeframe": "15min",
                    "minor_timeframe": "1min",
                    "recent_alerts": [],
                    "_cached": False
                }
            except Exception as e:
                logger.error(f"Error fetching data from broker via middleware: {e}")
                # Return minimal status on error
                return {
                    "running": False,
                    "message": f"Live trading engine not initialized (error: {str(e)})"
                }
        
        # Try cache first (2 second TTL)
        cache = get_status_cache()
        cache_key = f"status_{_engine_instance.config.id}"
        cached_status = cache.get(cache_key)
        
        if cached_status is not None:
            # Add cache hit header for monitoring
            cached_status["_cached"] = True
            return cached_status
        
        # Get open positions count - use middleware instead of database
        open_positions = len([p for p in net_positions if p.get("quantity", 0) != 0])
        
        # Get today's trades - use fixed count from engine if available
        trades_today = 0
        
        # Get today's P&L - initialize to 0 without database
        realized_pnl = 0
        
        # Get unrealized P&L - calculate from positions
        unrealized_pnl = sum(p.get("pnl", 0) for p in net_positions if p.get("quantity", 0) != 0)
        
        # Get recent alerts - initialize empty
        recent_alerts = []
        
        # Get latest market data and indicators from trading logic
        major_indicators = None
        minor_indicators = None
        
        if len(_engine_instance.major_candles) > 0:
            # Convert deque to list for trading logic service
            major_candles_list = list(_engine_instance.major_candles)
            if major_candles_list:
                major_indicators = _engine_instance.trading_logic.get_latest_indicators(
                    major_candles_list, 
                    _engine_instance.config.major_trend_timeframe
                )
        
        if len(_engine_instance.minor_candles) > 0:
            # Convert deque to list for trading logic service
            minor_candles_list = list(_engine_instance.minor_candles)
            if minor_candles_list:
                minor_indicators = _engine_instance.trading_logic.get_latest_indicators(
                    minor_candles_list, 
                    _engine_instance.config.minor_trend_timeframe
                )
        
        status_data = {
            "running": _engine_instance.running,
            "paused": _engine_instance.paused,
            "config_id": _engine_instance.config.id,
            "config_name": _engine_instance.config.name,
            "contract_expiry": _engine_instance.contract_expiry,
            "started_at": _engine_instance.config.started_at.isoformat() if _engine_instance.config.started_at else None,
            "funds": {
                "available": round(_engine_instance.available_funds, 2),
                "allocated": round(_engine_instance.allocated_funds, 2),
                "remaining": round(_engine_instance.available_funds - _engine_instance.allocated_funds, 2),
                "utilization_pct": round(
                    (_engine_instance.allocated_funds / _engine_instance.available_funds * 100)
                    if _engine_instance.available_funds > 0 else 0,
                    2
                )
            },
            "positions": {
                "open": open_positions,
                "max_allowed": 2  # Max 2 positions (1 CE + 1 PE)
            },
            "trades": {
                "today": trades_today,
                "total": trades_today  # Use same value, no database
            },
            "pnl": {
                "realized": round(realized_pnl, 2),
                "unrealized": round(unrealized_pnl, 2),
                "total": round(realized_pnl + unrealized_pnl, 2)
            },
            # Market data and trends
            "nifty_ltp": round(_engine_instance.nifty_ltp, 2) if _engine_instance.nifty_ltp else 0,
            "major_trend": _engine_instance.major_trend or (major_indicators.get('trend') if major_indicators else None),
            "major_ma7": round(major_indicators.get('ma7'), 2) if major_indicators and major_indicators.get('ma7') else None,
            "major_ma20": round(major_indicators.get('ma20'), 2) if major_indicators and major_indicators.get('ma20') else None,
            "major_lbb": round(major_indicators.get('lbb'), 2) if major_indicators and major_indicators.get('lbb') else None,
            "major_ubb": round(major_indicators.get('ubb'), 2) if major_indicators and major_indicators.get('ubb') else None,
            "major_trend_changed_at": _engine_instance.major_trend_changed_at.isoformat() if _engine_instance.major_trend_changed_at else None,
            "minor_trend": _engine_instance.minor_trend or (minor_indicators.get('trend') if minor_indicators else None),
            "minor_ma7": round(minor_indicators.get('ma7'), 2) if minor_indicators and minor_indicators.get('ma7') else None,
            "minor_ma20": round(minor_indicators.get('ma20'), 2) if minor_indicators and minor_indicators.get('ma20') else None,
            "minor_lbb": round(minor_indicators.get('lbb'), 2) if minor_indicators and minor_indicators.get('lbb') else None,
            "minor_ubb": round(minor_indicators.get('ubb'), 2) if minor_indicators and minor_indicators.get('ubb') else None,
            "minor_trend_changed_at": _engine_instance.minor_trend_changed_at.isoformat() if _engine_instance.minor_trend_changed_at else None,
            "major_timeframe": _engine_instance.config.major_trend_timeframe,
            "minor_timeframe": _engine_instance.config.minor_trend_timeframe,
            "suspend_ce": _engine_instance.config.suspend_ce or False,
            "suspend_pe": _engine_instance.config.suspend_pe or False,
            "recent_alerts": [
                {
                    "severity": alert.severity,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat()
                }
                for alert in recent_alerts
            ],
            "system": {
                "state_id": _engine_instance.state_id,
                "recovery_count": 0  # Skip database lookup
            },
            "_cached": False
        }
        
        # Cache the result (2 second TTL)
        cache.set(cache_key, status_data, ttl=2.0)
        
        return status_data
        
    except Exception as e:
        logger.error(f"Error getting live trading status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/instruments/{config_id}")
async def get_available_instruments(config_id: int, db: Session = Depends(get_db)) -> Dict:
    """
    Get list of available instruments based on current NIFTY 50 LTP and trading signals
    
    Returns instruments that would be traded if signals are generated, including:
    - Index (NIFTY 50)
    - CE/PE contracts based on strike selection logic
    - LTP values
    - Lot sizes
    - Expected quantities
    - Cash balance after position (if initiated)
    - Subscription status (whether subscribed to webhook/websocket)
    """
    global _engine_instance
    
    try:
        # Get config
        config = db.query(TradingConfig).filter(TradingConfig.id == config_id).first()
        if not config:
            raise HTTPException(status_code=404, detail="Config not found")
        
        instruments = []
        
        # Get current NIFTY 50 LTP
        nifty_ltp = 0.0
        if _engine_instance and _engine_instance.running:
            nifty_ltp = _engine_instance.nifty_ltp
        
        # If no live data, try to get from broker via middleware
        if nifty_ltp == 0.0:
            try:
                middleware = get_middleware_instance()
                if middleware:
                    ltp_data = middleware.get_ltp(["NSE:NIFTY 50"])
                    if ltp_data and "NSE:NIFTY 50" in ltp_data:
                        # LTP data is a dict with 'last_price' key
                        nifty_ltp_value = ltp_data["NSE:NIFTY 50"]
                        if isinstance(nifty_ltp_value, dict):
                            nifty_ltp = nifty_ltp_value.get('last_price', 0.0)
                        else:
                            nifty_ltp = nifty_ltp_value
            except Exception as e:
                logger.warning(f"Could not fetch NIFTY 50 LTP: {e}")
        
        # Check if engine is running for subscription status
        is_subscribed = lambda token: (
            _engine_instance and _engine_instance.running and 
            token in _engine_instance.subscribed_instruments
        )
        
        # Add NIFTY 50 index
        index_instrument = {
            "type": "INDEX",
            "symbol": "NIFTY 50",
            "tradingsymbol": "NIFTY 50",
            "instrument_token": "256265",
            "strike": None,
            "ltp": nifty_ltp,
            "lot_size": None,
            "expected_quantity": None,
            "position_value": None,
            "cash_balance_after": None,
            "entry_triggers": [],
            "subscribed": is_subscribed("256265")
        }
        instruments.append(index_instrument)
        
        ce_instrument = None
        pe_instrument = None
        
        # Calculate strikes for CE and PE based on config
        if nifty_ltp > 0:
            import math
            
            strike_gap = config.min_strike_gap
            round_to = config.strike_round_to
            
            # Get lot size from config
            lot_size = config.lot_size or 50  # Use config lot_size, fallback to 50
            
            # Calculate quantity based on capital allocation
            # For LIVE trading: use broker available funds (not config initial_capital)
            if _engine_instance and _engine_instance.running:
                # Use actual broker funds from running engine
                available_capital = _engine_instance.available_funds
            else:
                # Engine not running - try to fetch broker funds via middleware
                try:
                    middleware = get_middleware_instance()
                    if middleware:
                        funds = middleware.get_funds(use_cache=True)
                        if funds and 'equity' in funds:
                            available_capital = funds['equity'].get('available', {}).get('live_balance', 0.0)
                        else:
                            available_capital = config.initial_capital  # Fallback to config
                    else:
                        available_capital = config.initial_capital  # Fallback to config
                except Exception as e:
                    logger.warning(f"Could not fetch broker funds, using config initial_capital: {e}")
                    available_capital = config.initial_capital
            
            max_capital_per_trade = available_capital * (config.capital_allocation_pct / 100)
            
            # Calculate CE strike: Round UP + Add gap
            ce_base_strike = math.ceil(nifty_ltp / round_to) * round_to
            ce_strike = ce_base_strike + strike_gap
            
            # Find CE contract
            ce_contract = db.query(Instrument).filter(
                Instrument.tradingsymbol.like(f"NIFTY%CE"),
                Instrument.strike == ce_strike,
                Instrument.instrument_type == "CE"
            ).order_by(Instrument.expiry).first()
            
            if ce_contract:
                # Get CE LTP
                ce_ltp = 0.0
                try:
                    if _engine_instance and _engine_instance.running:
                        ce_ltp = await _engine_instance._get_contract_ltp(ce_contract.instrument_token)
                    
                    if not ce_ltp:
                        middleware = get_middleware_instance()
                        if middleware:
                            ltp_data = middleware.get_ltp([f"NFO:{ce_contract.tradingsymbol}"])
                            if ltp_data and f"NFO:{ce_contract.tradingsymbol}" in ltp_data:
                                ce_ltp_value = ltp_data[f"NFO:{ce_contract.tradingsymbol}"]
                                if isinstance(ce_ltp_value, dict):
                                    ce_ltp = ce_ltp_value.get('last_price', 0.0)
                                else:
                                    ce_ltp = ce_ltp_value
                except Exception as e:
                    logger.warning(f"Could not fetch CE LTP: {e}")
                
                # Calculate expected quantity
                expected_quantity = 0
                position_value = 0.0
                cash_balance_after = available_capital  # Use broker funds, not config
                
                if ce_ltp > 0 and lot_size > 0:
                    # Calculate number of lots: available_fund / (ltp * lot_size), then round down
                    max_lots = int(max_capital_per_trade / (ce_ltp * lot_size))
                    if max_lots > 0:
                        expected_quantity = max_lots * lot_size
                        position_value = expected_quantity * ce_ltp  # Total position value = qty × ltp
                        cash_balance_after = available_capital - position_value
                
                # Determine entry triggers (CE is for uptrend in normal mode)
                entry_triggers = []
                if not config.reverse_signals:
                    if not config.suspend_ce:
                        entry_triggers = ["7MA", "20MA", "LBB"]
                    else:
                        entry_triggers = ["SUSPENDED"]
                else:
                    # In reverse mode, CE is for downtrend
                    if not config.suspend_ce:
                        entry_triggers = ["7MA", "20MA", "LBB"]
                    else:
                        entry_triggers = ["SUSPENDED"]
                
                ce_instrument = {
                    "type": "CE",
                    "symbol": ce_contract.name,
                    "tradingsymbol": ce_contract.tradingsymbol,
                    "instrument_token": ce_contract.instrument_token,
                    "strike": ce_contract.strike,
                    "ltp": ce_ltp,
                    "lot_size": lot_size,
                    "expected_quantity": expected_quantity,
                    "position_value": position_value,  # Already calculated as qty × ltp
                    "cash_balance_after": cash_balance_after,
                    "entry_triggers": entry_triggers,
                    "subscribed": is_subscribed(ce_contract.instrument_token)
                }
                instruments.append(ce_instrument)
            
            # Calculate PE strike: Round DOWN - Subtract gap
            pe_base_strike = math.floor(nifty_ltp / round_to) * round_to
            pe_strike = pe_base_strike - strike_gap
            
            # Find PE contract
            pe_contract = db.query(Instrument).filter(
                Instrument.tradingsymbol.like(f"NIFTY%PE"),
                Instrument.strike == pe_strike,
                Instrument.instrument_type == "PE"
            ).order_by(Instrument.expiry).first()
            
            if pe_contract:
                # Get PE LTP
                pe_ltp = 0.0
                try:
                    if _engine_instance and _engine_instance.running:
                        pe_ltp = await _engine_instance._get_contract_ltp(pe_contract.instrument_token)
                    
                    if not pe_ltp:
                        middleware = get_middleware_instance()
                        if middleware:
                            ltp_data = middleware.get_ltp([f"NFO:{pe_contract.tradingsymbol}"])
                            if ltp_data and f"NFO:{pe_contract.tradingsymbol}" in ltp_data:
                                pe_ltp_value = ltp_data[f"NFO:{pe_contract.tradingsymbol}"]
                                if isinstance(pe_ltp_value, dict):
                                    pe_ltp = pe_ltp_value.get('last_price', 0.0)
                                else:
                                    pe_ltp = pe_ltp_value
                except Exception as e:
                    logger.warning(f"Could not fetch PE LTP: {e}")
                
                # Calculate expected quantity
                expected_quantity = 0
                position_value = 0.0
                cash_balance_after = available_capital  # Use broker funds, not config
                
                if pe_ltp > 0 and lot_size > 0:
                    # Calculate number of lots: available_fund / (ltp * lot_size), then round down
                    max_lots = int(max_capital_per_trade / (pe_ltp * lot_size))
                    if max_lots > 0:
                        expected_quantity = max_lots * lot_size
                        position_value = expected_quantity * pe_ltp  # Total position value = qty × ltp
                        cash_balance_after = available_capital - position_value
                
                # Determine entry triggers (PE is for downtrend in normal mode)
                entry_triggers = []
                if not config.reverse_signals:
                    if not config.suspend_pe:
                        entry_triggers = ["7MA", "20MA", "LBB"]
                    else:
                        entry_triggers = ["SUSPENDED"]
                else:
                    # In reverse mode, PE is for uptrend
                    if not config.suspend_pe:
                        entry_triggers = ["7MA", "20MA", "LBB"]
                    else:
                        entry_triggers = ["SUSPENDED"]
                
                pe_instrument = {
                    "type": "PE",
                    "symbol": pe_contract.name,
                    "tradingsymbol": pe_contract.tradingsymbol,
                    "instrument_token": pe_contract.instrument_token,
                    "strike": pe_contract.strike,
                    "ltp": pe_ltp,
                    "lot_size": lot_size,
                    "expected_quantity": expected_quantity,
                    "position_value": position_value,  # Already calculated as qty × ltp
                    "cash_balance_after": cash_balance_after,
                    "entry_triggers": entry_triggers,
                    "subscribed": is_subscribed(pe_contract.instrument_token)
                }
                instruments.append(pe_instrument)
        
        # Add subscription summary
        total_subscribed = sum(1 for inst in instruments if inst.get("subscribed", False))
        
        return {
            "status": "success",
            "instruments": instruments,
            "count": len(instruments),
            "subscription_info": {
                "total_instruments": len(instruments),
                "subscribed_count": total_subscribed,
                "unsubscribed_count": len(instruments) - total_subscribed,
                "engine_running": _engine_instance is not None and _engine_instance.running
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching instruments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trades")
async def get_live_trades(
    limit: int = Query(50, description="Number of trades to return"),
    status: Optional[str] = Query(None, description="Filter by status: open, closed, rejected"),
    db: Session = Depends(get_db)
) -> Dict:
    """
    Get live trades with optional filtering
    
    Args:
        limit: Maximum number of trades to return
        status: Optional status filter (open, closed, rejected)
        
    Returns:
        List of trades with details
    """
    global _engine_instance
    
    try:
        # Get config_id - try from engine first, otherwise get latest config
        config_id = None
        if _engine_instance and _engine_instance.config:
            config_id = _engine_instance.config.id
        else:
            # If engine not running, get the active config
            config = db.query(TradingConfig).filter(
                TradingConfig.is_active == True
            ).first()
            if config:
                config_id = config.id
            else:
                # No active config, return empty
                return {
                    "trades": [],
                    "count": 0,
                    "config_id": None
                }
        
        # Build query
        query = db.query(LiveTrade).filter(
            LiveTrade.config_id == config_id
        )
        
        if status:
            query = query.filter(LiveTrade.status == status.upper())
        
        trades = query.order_by(desc(LiveTrade.entry_time)).limit(limit).all()
        
        return {
            "trades": [
                {
                    "id": trade.id,
                    "instrument": trade.instrument,
                    "option_type": trade.option_type,
                    "strike": trade.strike,
                    "status": trade.status,
                    "entry_time": trade.entry_time.isoformat() if trade.entry_time else None,
                    "exit_time": trade.exit_time.isoformat() if trade.exit_time else None,
                    "entry_price": round(trade.entry_price, 2) if trade.entry_price else None,
                    "exit_price": round(trade.exit_price, 2) if trade.exit_price else None,
                    "quantity": trade.quantity,
                    "target_price": round(trade.target_price, 2) if trade.target_price else None,
                    "stoploss_price": round(trade.stoploss_price, 2) if trade.stoploss_price else None,
                    "pnl": round(trade.pnl, 2) if trade.pnl else None,
                    "exit_reason": trade.exit_reason,
                    "trigger_type": trade.trigger_type,
                    "broker_order_id": trade.broker_order_id,
                }
                for trade in trades
            ],
            "count": len(trades),
            "config_id": config_id
        }
        
    except Exception as e:
        logger.error(f"Error getting live trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions")
async def get_live_positions(
    db: Session = Depends(get_db)
) -> Dict:
    """
    Get currently open positions with live P&L
    
    NOTE: For off-market positions, use GET /api/portfolio/positions instead
    This endpoint is for live trading engine positions only
    
    Returns:
        List of open positions with current prices and P&L
    """
    global _engine_instance
    
    try:
        if not _engine_instance:
            # Engine not running - redirect to portfolio API
            raise HTTPException(
                status_code=404,
                detail="Live trading engine not running. Use GET /api/portfolio/positions for broker positions."
            )
        
        # Get open positions
        positions = db.query(LiveTrade).filter(
            LiveTrade.config_id == _engine_instance.config.id,
            LiveTrade.status == 'open'
        ).order_by(LiveTrade.entry_time).all()
        
        return {
            "positions": [
                {
                    "id": trade.id,
                    "instrument": trade.instrument,
                    "option_type": trade.option_type,
                    "strike_price": trade.strike_price,
                    "entry_time": trade.entry_time.isoformat() if trade.entry_time else None,
                    "entry_price": round(trade.entry_price, 2),
                    "current_price": round(trade.current_price, 2) if trade.current_price else None,
                    "quantity": trade.quantity,
                    "target_price": round(trade.target_price, 2),
                    "stoploss_price": round(trade.stoploss_price, 2),
                    "unrealized_pnl": round(trade.unrealized_pnl, 2) if trade.unrealized_pnl else 0,
                    "unrealized_pnl_pct": round(
                        ((trade.current_price - trade.entry_price) / trade.entry_price * 100)
                        if trade.current_price and trade.entry_price else 0,
                        2
                    ),
                    "highest_price": round(trade.highest_price, 2) if trade.highest_price else None,
                    "lowest_price": round(trade.lowest_price, 2) if trade.lowest_price else None,
                    "max_drawdown_pct": round(trade.max_drawdown_pct, 2) if trade.max_drawdown_pct else None,
                    "allocated_capital": round(trade.allocated_capital, 2),
                    "order_status_buy": trade.order_status_buy,
                    "ltp_available": trade.instrument_token in _engine_instance.positions_ltp
                }
                for trade in positions
            ],
            "count": len(positions),
            "total_allocated": round(sum(trade.allocated_capital or 0 for trade in positions), 2),
            "total_unrealized_pnl": round(sum(trade.unrealized_pnl or 0 for trade in positions), 2)
        }
        
    except Exception as e:
        logger.error(f"Error getting live positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders")
async def get_live_orders() -> Dict:
    """
    Get today's orders
    
    Returns:
        List of orders with status and details
    During off-market hours, fetches from middleware with adaptive polling
    """
    from backend.services.market_calendar import get_market_status
    
    global _engine_instance
    
    try:
        # Get middleware instance
        middleware = get_middleware_instance()
        
        # Check market status
        market_status = get_market_status()
        is_market_open = market_status.get("is_open", False)
        
        # Fetch from middleware (works both when engine is running or not during off-market)
        if not is_market_open or not _engine_instance:
            access_token = None
            broker_type = settings.BROKER_TYPE.lower()
            
            if broker_type == "kite":
                access_token = settings.KITE_ACCESS_TOKEN
            elif broker_type == "upstox":
                access_token = settings.UPSTOX_ACCESS_TOKEN
            
            if access_token:
                try:
                    orders = middleware.get_orders(use_cache=False)
                    
                    return {
                        "orders": [
                            {
                                "order_id": order.get("order_id"),
                                "exchange_order_id": order.get("exchange_order_id"),
                                "tradingsymbol": order.get("tradingsymbol"),
                                "exchange": order.get("exchange"),
                                "transaction_type": order.get("transaction_type"),
                                "quantity": order.get("quantity"),
                                "filled_quantity": order.get("filled_quantity"),
                                "pending_quantity": order.get("pending_quantity"),
                                "price": round(order.get("price", 0), 2),
                                "average_price": round(order.get("average_price", 0), 2),
                                "status": order.get("status"),
                                "product": order.get("product"),
                                "order_type": order.get("order_type"),
                                "order_timestamp": order.get("order_timestamp"),
                                "exchange_timestamp": order.get("exchange_timestamp"),
                                "status_message": order.get("status_message"),
                            }
                            for order in orders
                        ],
                        "count": len(orders),
                        "source": "broker_api"
                    }
                except Exception as e:
                    logger.error(f"Error fetching orders from broker: {e}")
                    raise HTTPException(status_code=500, detail=f"Failed to fetch orders: {str(e)}")
        
        # If engine is running, get from database
        if _engine_instance:
            # Get today's trades and return their orders
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            # Skip database lookup - return empty trades
            trades = []
            
            return {
                "orders": [],
                "count": 0,
                "source": "database"
            }
        
        raise HTTPException(status_code=404, detail="No data source available")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def get_live_alerts(
    limit: int = Query(100, description="Number of alerts to return"),
    alert_type: Optional[str] = Query(None, description="Filter by alert_type: entry, exit, error, info"),
    db: Session = Depends(get_db)
) -> Dict:
    """
    Get live trading alerts
    
    Args:
        limit: Maximum number of alerts to return
        alert_type: Optional alert_type filter
        
    Returns:
        List of alerts with timestamps
    """
    global _engine_instance
    
    try:
        # Get config_id - try from engine first, otherwise get latest config
        config_id = None
        if _engine_instance and _engine_instance.config:
            config_id = _engine_instance.config.id
        else:
            # If engine not running, get the active config
            config = db.query(TradingConfig).filter(
                TradingConfig.is_active == True
            ).first()
            if config:
                config_id = config.id
            else:
                # No active config, return empty
                return {
                    "alerts": [],
                    "count": 0
                }
        
        # Build query
        query = db.query(LiveTradingAlert).filter(
            LiveTradingAlert.config_id == config_id
        )
        
        if alert_type:
            query = query.filter(LiveTradingAlert.alert_type == alert_type)
        
        alerts = query.order_by(desc(LiveTradingAlert.timestamp)).limit(limit).all()
        
        return {
            "alerts": [
                {
                    "id": alert.id,
                    "alert_type": alert.alert_type,
                    "category": alert.category,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat(),
                    "trade_id": alert.trade_id,
                    "alert_metadata": alert.alert_metadata
                }
                for alert in alerts
            ],
            "count": len(alerts),
            "config_id": config_id
        }
        
    except Exception as e:
        logger.error(f"Error getting live alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals")
async def get_live_signals(
    limit: int = Query(50, description="Number of signals to return"),
    db: Session = Depends(get_db)
) -> Dict:
    """
    Get recent trading signals
    
    Args:
        limit: Maximum number of signals to return
        
    Returns:
        List of signals with timestamps and values
    """
    global _engine_instance
    
    try:
        # Get config_id - try from engine first, otherwise get latest config
        config_id = None
        if _engine_instance and _engine_instance.config:
            config_id = _engine_instance.config.id
        else:
            # If engine not running, get the active config
            config = db.query(TradingConfig).filter(
                TradingConfig.is_active == True
            ).first()
            if config:
                config_id = config.id
            else:
                # No active config, return empty
                return {
                    "signals": [],
                    "count": 0
                }
        
        signals = db.query(LiveTradingSignal).filter(
            LiveTradingSignal.config_id == config_id
        ).order_by(desc(LiveTradingSignal.timestamp)).limit(limit).all()
        
        return {
            "signals": [
                {
                    "id": signal.id,
                    "signal_type": signal.signal_type,
                    "option_type": signal.option_type,
                    "trigger": signal.trigger,
                    "nifty_price": round(signal.nifty_price, 2) if signal.nifty_price else None,
                    "indicator_value": round(signal.indicator_value, 2) if signal.indicator_value else None,
                    "timestamp": signal.timestamp.isoformat(),
                    "executed": signal.executed,
                    "reason": signal.reason
                }
                for signal in signals
            ],
            "count": len(signals),
            "config_id": config_id
        }
        
    except Exception as e:
        logger.error(f"Error getting live signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/close-position")
async def close_position_manually(
    trade_id: int = Body(..., embed=True, description="Trade ID to close"),
    reason: str = Body("manual_close", embed=True, description="Reason for closing"),
    db: Session = Depends(get_db)
) -> Dict:
    """
    Manually close an open position
    
    Args:
        trade_id: ID of the trade to close
        reason: Reason for manual closure
        
    Returns:
        Closure confirmation with P&L
        
    Raises:
        404: Trade not found or not open
        401: Token expired
    """
    global _engine_instance
    
    try:
        if not _engine_instance or not _engine_instance.running:
            raise HTTPException(status_code=404, detail="Live trading engine is not running")
        
        # Get trade
        trade = db.query(LiveTrade).filter(
            LiveTrade.id == trade_id,
            LiveTrade.config_id == _engine_instance.config.id
        ).first()
        
        if not trade:
            raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")
        
        if trade.status != 'open':
            raise HTTPException(
                status_code=400,
                detail=f"Trade {trade_id} is not open (status: {trade.status})"
            )
        
        # Exit position
        await _engine_instance._exit_position(trade, "manual", reason)
        
        return {
            "status": "closed",
            "message": f"Position closed manually: {trade.instrument}",
            "trade_id": trade_id,
            "exit_price": round(trade.current_price, 2) if trade.current_price else None,
            "pnl": round(trade.unrealized_pnl, 2) if trade.unrealized_pnl else None,
            "closed_at": datetime.now().isoformat()
        }
        
    except TokenExpiredError:
        raise HTTPException(
            status_code=401,
            detail="Access token expired while closing position. Position may still be open."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error closing position manually: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reconcile")
async def trigger_reconciliation(
    db: Session = Depends(get_db)
) -> Dict:
    """
    Manually trigger broker position reconciliation
    
    Useful after suspected crash or discrepancies.
    Engine will auto-pause if issues are found.
    
    Returns:
        Detailed reconciliation report
        
    Raises:
        404: Engine not running
        401: Token expired
    """
    global _engine_instance
    
    try:
        if not _engine_instance or not _engine_instance.running:
            raise HTTPException(status_code=404, detail="Live trading engine is not running")
        
        logger.info("Manual reconciliation triggered via API")
        
        # Run reconciliation
        report = await _engine_instance._reconcile_broker_positions()
        
        return {
            "status": "completed",
            "reconciliation": report,
            "timestamp": datetime.now().isoformat()
        }
        
    except TokenExpiredError:
        raise HTTPException(
            status_code=401,
            detail="Access token expired during reconciliation."
        )
    except Exception as e:
        logger.error(f"Error during reconciliation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suspend-ce")
async def suspend_ce_entries(
    suspend: bool = Body(..., embed=True, description="True to suspend, False to resume"),
    db: Session = Depends(get_db)
) -> Dict:
    """
    Suspend or resume CE (Call) entries
    
    Args:
        suspend: True to suspend CE entries, False to resume
        
    Returns:
        Status confirmation
    """
    global _engine_instance
    
    if not _engine_instance or not _engine_instance.running:
        raise HTTPException(status_code=404, detail="Live trading engine is not running")
    
    try:
        _engine_instance.suspend_ce(suspend)
        
        return {
            "status": "updated",
            "ce_suspended": suspend,
            "message": "CE entries suspended" if suspend else "CE entries resumed"
        }
        
    except Exception as e:
        logger.error(f"Error updating CE suspension: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suspend-pe")
async def suspend_pe_entries(
    suspend: bool = Body(..., embed=True, description="True to suspend, False to resume"),
    db: Session = Depends(get_db)
) -> Dict:
    """
    Suspend or resume PE (Put) entries
    
    Args:
        suspend: True to suspend PE entries, False to resume
        
    Returns:
        Status confirmation
    """
    global _engine_instance
    
    if not _engine_instance or not _engine_instance.running:
        raise HTTPException(status_code=404, detail="Live trading engine is not running")
    
    try:
        _engine_instance.suspend_pe(suspend)
        
        return {
            "status": "updated",
            "pe_suspended": suspend,
            "message": "PE entries suspended" if suspend else "PE entries resumed"
        }
        
    except Exception as e:
        logger.error(f"Error updating PE suspension: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance")
async def get_performance_metrics(
    db: Session = Depends(get_db)
) -> Dict:
    """
    Get API performance metrics and cache statistics
    
    Returns:
        Response time statistics and cache hit rates
    """
    from backend.utils.cache import get_response_tracker
    
    try:
        tracker = get_response_tracker()
        status_cache = get_status_cache()
        positions_cache = get_positions_cache()
        trades_cache = get_trades_cache()
        
        return {
            "response_times": tracker.get_all_stats(),
            "caches": {
                "status": status_cache.get_stats(),
                "positions": positions_cache.get_stats(),
                "trades": trades_cache.get_stats()
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market-data")
async def get_market_data() -> Dict:
    """
    Get current market data (Nifty LTP, trends, indicators)
    Works both during and after market hours
    
    Returns:
        - Nifty 50 LTP and day change
        - Major and Minor trend indicators (if engine is running)
        - Market status (open/closed)
        
    Note: This endpoint works even when live trading engine is stopped
    """
    from backend.services.market_calendar import get_market_status
    
    global _engine_instance
    
    try:
        # Get middleware instance
        middleware = get_middleware_instance()
        
        # Get market status
        market_status = get_market_status()
        
        # Get broker config to validate authentication
        access_token = None
        broker_type = settings.BROKER_TYPE.lower()
        
        if broker_type == "kite":
            access_token = settings.KITE_ACCESS_TOKEN
        elif broker_type == "upstox":
            access_token = settings.UPSTOX_ACCESS_TOKEN
        
        if not access_token:
            return {
                "available": False,
                "reason": "Broker not authenticated"
            }
        
        # Get NIFTY 50 quotes via middleware
        try:
            quotes = middleware.get_quote(["NSE:NIFTY 50"], use_cache=True)
            nifty_quote = quotes.get("NSE:NIFTY 50", {})
            nifty_ltp = nifty_quote.get("last_price", 0)
            ohlc = nifty_quote.get("ohlc", {})
            prev_close = ohlc.get("close", 0)
            
            # Get exchange timestamp (if available)
            exchange_timestamp = nifty_quote.get("last_trade_time")
            if not exchange_timestamp:
                exchange_timestamp = nifty_quote.get("timestamp")
            
            # Calculate change
            nifty_change = nifty_ltp - prev_close if prev_close else 0
            nifty_change_pct = (nifty_change / prev_close * 100) if prev_close else 0
        except Exception as e:
            logger.warning(f"Could not fetch Nifty quotes: {e}")
            nifty_ltp = 0
            nifty_change = 0
            nifty_change_pct = 0
            prev_close = 0
            exchange_timestamp = None
        
        # Get trend indicators from engine if running
        major_indicators = None
        minor_indicators = None
        
        if _engine_instance and _engine_instance.running:
            # Get indicators from running engine
            try:
                if len(_engine_instance.major_candles) > 0:
                    major_candles_list = list(_engine_instance.major_candles)
                    if major_candles_list:
                        major_ind = _engine_instance.trading_logic.get_latest_indicators(
                            major_candles_list,
                            _engine_instance.config.major_trend_timeframe
                        )
                        if major_ind:
                            major_indicators = {
                                "trend": major_ind.get('trend'),
                                "ma7": major_ind.get('ma7'),
                                "ma20": major_ind.get('ma20')
                            }
                
                if len(_engine_instance.minor_candles) > 0:
                    minor_candles_list = list(_engine_instance.minor_candles)
                    if minor_candles_list:
                        minor_ind = _engine_instance.trading_logic.get_latest_indicators(
                            minor_candles_list,
                            _engine_instance.config.minor_trend_timeframe
                        )
                        if minor_ind:
                            minor_indicators = {
                                "trend": minor_ind.get('trend'),
                                "ma7": minor_ind.get('ma7'),
                                "ma20": minor_ind.get('ma20')
                            }
            except Exception as e:
                logger.warning(f"Could not fetch indicators from engine: {e}")
        
        # If engine not running, try to get latest saved market data - skip database
        if not major_indicators or not minor_indicators:
            try:
                latest_market_data = None  # Skip database lookup
                
                if latest_market_data:
                    if not major_indicators:
                        major_indicators = {
                            "trend": latest_market_data.major_trend,
                            "ma7": latest_market_data.major_ma7,
                            "ma20": latest_market_data.major_ma20
                        }
                    if not minor_indicators:
                        minor_indicators = {
                            "trend": latest_market_data.minor_trend,
                            "ma7": latest_market_data.minor_ma7,
                            "ma20": latest_market_data.minor_ma20
                        }
                else:
                    # No saved data, calculate from historical candles
                    try:
                        from datetime import timedelta
                        from collections import deque
                        from backend.services.trading_logic_service import TradingLogicService
                        
                        # Get NIFTY 50 token
                        nifty_token = 256265  # NSE NIFTY 50
                        
                        # Fetch 15min candles for major trend
                        end_time = datetime.now()
                        # Go back to last trading day if it's weekend
                        while end_time.weekday() >= 5:
                            end_time -= timedelta(days=1)
                        end_time = end_time.replace(hour=15, minute=30, second=0, microsecond=0)
                        start_time = end_time - timedelta(hours=12)
                        
                        major_candles = middleware.get_historical_data(
                            instrument_token=nifty_token,
                            from_date=start_time,
                            to_date=end_time,
                            interval="15minute"
                        )
                        
                        # Fetch 1min candles for minor trend
                        minor_candles = middleware.get_historical_data(
                            instrument_token=nifty_token,
                            from_date=end_time - timedelta(hours=1),
                            to_date=end_time,
                            interval="minute"
                        )
                        
                        trading_logic = TradingLogicService()
                        
                        if major_candles and len(major_candles) >= 20:
                            major_ind = trading_logic.calculate_indicators_from_deque(deque(major_candles))
                            if major_ind:
                                major_indicators = {
                                    "trend": major_ind.get('trend'),
                                    "ma7": major_ind.get('ma7'),
                                    "ma20": major_ind.get('ma20')
                                }
                        
                        if minor_candles and len(minor_candles) >= 20:
                            minor_ind = trading_logic.calculate_indicators_from_deque(deque(minor_candles))
                            if minor_ind:
                                minor_indicators = {
                                    "trend": minor_ind.get('trend'),
                                    "ma7": minor_ind.get('ma7'),
                                    "ma20": minor_ind.get('ma20')
                                }
                    except Exception as e:
                        logger.warning(f"Could not calculate indicators from historical data: {e}")
            except Exception as e:
                logger.warning(f"Could not fetch saved market data: {e}")
        
        return {
            "available": True,
            "market_status": market_status,
            "nifty": {
                "ltp": round(nifty_ltp, 2),
                "change": round(nifty_change, 2),
                "change_pct": round(nifty_change_pct, 2),
                "prev_close": round(prev_close, 2),
                "exchange_timestamp": exchange_timestamp.isoformat() if exchange_timestamp else None
            },
            "trends": {
                "major": {
                    "timeframe": "15min",
                    "trend": major_indicators.get("trend") if major_indicators else None,
                    "ma7": round(major_indicators.get("ma7"), 2) if major_indicators and major_indicators.get("ma7") else None,
                    "ma20": round(major_indicators.get("ma20"), 2) if major_indicators and major_indicators.get("ma20") else None,
                } if major_indicators else None,
                "minor": {
                    "timeframe": "1min",
                    "trend": minor_indicators.get("trend") if minor_indicators else None,
                    "ma7": round(minor_indicators.get("ma7"), 2) if minor_indicators and minor_indicators.get("ma7") else None,
                    "ma20": round(minor_indicators.get("ma20"), 2) if minor_indicators and minor_indicators.get("ma20") else None,
                } if minor_indicators else None
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except TokenExpiredError:
        raise HTTPException(
            status_code=401,
            detail="Access token expired. Please re-authenticate with your broker."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting market data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/candles")
async def get_candles(
    timeframe: str = "15minute",  # "minute" or "15minute"
    limit: int = 100,
    before: Optional[int] = None  # Unix timestamp for pagination
) -> Dict:
    """
    Get historical candlestick data for NIFTY 50
    
    Parameters:
        - timeframe: "minute" for 1-minute candles, "15minute" for 15-minute candles
        - limit: Number of candles to return (default 100)
        - before: Optional Unix timestamp to fetch data before this time (for pagination)
        
    Returns:
        - List of OHLC candles with timestamp
        - Calculated indicators (7MA, 20MA, Bollinger Bands)
    """
    from backend.services.trading_logic_service import TradingLogicService
    from collections import deque
    
    try:
        # Get middleware instance
        middleware = get_middleware_instance()
        
        # Get broker config to validate authentication
        access_token = None
        broker_type = settings.BROKER_TYPE.lower()
        
        if broker_type == "kite":
            access_token = settings.KITE_ACCESS_TOKEN
        elif broker_type == "upstox":
            access_token = settings.UPSTOX_ACCESS_TOKEN
        
        if not access_token:
            raise HTTPException(
                status_code=401,
                detail="Broker not authenticated"
            )
        
        # NIFTY 50 token
        nifty_token = 256265
        
        # Calculate time range
        now = datetime.now()
        
        # If 'before' timestamp is provided, use it as end time
        if before:
            now = datetime.fromtimestamp(before)
        
        # Go back to last trading day if it's weekend
        while now.weekday() > 4:  # Saturday=5, Sunday=6
            now -= timedelta(days=1)
        
        # If it's before market open, go back to previous day
        if now.hour < 9 or (now.hour == 9 and now.minute < 15):
            now -= timedelta(days=1)
            while now.weekday() > 4:
                now -= timedelta(days=1)
        
        # Calculate time range based on interval
        if timeframe == "minute":
            # For 1-minute candles, fetch last trading day's data (more reliable)
            # If paginating, go back further
            if before:
                end_time = now
                start_time = end_time - timedelta(days=1)
            else:
                end_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
                start_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
        else:  # 15minute and other timeframes
            # For other timeframes, fetch appropriate range
            if before:
                end_time = now
                start_time = end_time - timedelta(days=3)
            else:
                end_time = now
                start_time = end_time - timedelta(days=2)
        
        # Fetch historical data via middleware
        candles = middleware.get_historical_data(
            instrument_token=nifty_token,
            from_date=start_time,
            to_date=end_time,
            interval=timeframe
        )
        
        if not candles:
            return {
                "status": "success",
                "timeframe": timeframe,
                "candles": [],
                "indicators": None
            }
        
        # Limit the number of candles returned
        candles = candles[-limit:] if len(candles) > limit else candles
        
        # Normalize candle structure - broker returns 'date' but we need consistent keys
        normalized_candles = []
        for candle in candles:
            normalized_candles.append({
                "timestamp": candle.get("date"),
                "date": candle.get("date"),  # Keep for compatibility
                "open": candle.get("open"),
                "high": candle.get("high"),
                "low": candle.get("low"),
                "close": candle.get("close"),
                "volume": candle.get("volume", 0)
            })
        
        # Calculate indicators
        trading_logic = TradingLogicService()
        indicators_data = []
        
        if len(normalized_candles) >= 20:
            # Calculate indicators for each candle position
            for i in range(20, len(normalized_candles) + 1):
                candle_subset = deque(normalized_candles[:i])
                ind = trading_logic.calculate_indicators_from_deque(candle_subset)
                if ind and ind.get("ma7") is not None:
                    indicators_data.append({
                        "timestamp": normalized_candles[i-1].get("date"),
                        "ma7": round(ind.get("ma7"), 2) if ind.get("ma7") else None,
                        "ma20": round(ind.get("ma20"), 2) if ind.get("ma20") else None,
                        "lbb": round(ind.get("lbb"), 2) if ind.get("lbb") else None,
                        "ubb": round(ind.get("ubb"), 2) if ind.get("ubb") else None
                    })
        
        # Format candles for response
        formatted_candles = []
        for candle in normalized_candles:
            formatted_candles.append({
                "timestamp": candle.get("date").isoformat() if isinstance(candle.get("date"), datetime) else str(candle.get("date")),
                "open": round(candle.get("open"), 2),
                "high": round(candle.get("high"), 2),
                "low": round(candle.get("low"), 2),
                "close": round(candle.get("close"), 2),
                "volume": candle.get("volume", 0)
            })
        
        return {
            "status": "success",
            "timeframe": timeframe,
            "candles": formatted_candles,
            "indicators": indicators_data
        }
        
    except TokenExpiredError:
        raise HTTPException(
            status_code=401,
            detail="Access token expired. Please re-authenticate with your broker."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching candle data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chart-data")
async def get_chart_data(
    timeframe: str = "15minute",
    limit: int = 5000
) -> Dict:
    """
    Get chart data formatted for frontend charts
    
    Fetches historical OHLC data via the unified middleware which provides:
    - Centralized rate limiting (3 req/sec)
    - Redis caching for performance
    - Automatic error handling and retries
    
    Data ranges by timeframe:
    - minute: Last 30 days (~15,000+ candles)
    - 3-30minute: Last 200 days (~5,000+ candles, Kite API limit)
    - 60minute: Last 200 days (~2,500+ candles, Kite API limit)
    - day: Last 5 years (~1,250+ candles)
    
    Returns data formatted for chart components:
    - candles: Array of OHLC data with timestamps
    - ma7: Moving average 7 data points
    - ma20: Moving average 20 data points  
    - bb_upper: Bollinger Band upper band
    - bb_lower: Bollinger Band lower band
    
    Args:
        timeframe: Candle interval ('minute', '3minute', '5minute', '15minute', 
                  '30minute', '60minute', 'day')
        limit: Maximum number of candles to return (default: 5000, fetches all available data)
    
    Returns:
        Dict with candles and indicator data formatted for frontend
    """
    from backend.services.trading_logic_service import TradingLogicService
    from collections import deque
    
    # Validate timeframe parameter BEFORE try block so validation errors return 400, not 500
    valid_timeframes = ['minute', '3minute', '5minute', '10minute', '15minute', 
                       '30minute', '60minute', 'day']
    if timeframe not in valid_timeframes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe '{timeframe}'. Valid options: {', '.join(valid_timeframes)}"
        )
    
    try:
        # Get middleware instance (centralized broker data access)
        middleware = get_middleware_instance()
        
        # Validate broker authentication via .env config
        access_token = None
        broker_type = settings.BROKER_TYPE.lower()
        
        if broker_type == "kite":
            access_token = settings.KITE_ACCESS_TOKEN
        elif broker_type == "upstox":
            access_token = settings.UPSTOX_ACCESS_TOKEN
        
        if not access_token:
            raise HTTPException(
                status_code=401,
                detail="Broker not authenticated"
            )
        
        # NIFTY 50 token
        nifty_token = 256265
        
        # Calculate time range based on current time in IST
        IST = pytz.timezone('Asia/Kolkata')
        now = datetime.now(IST)
        
        # Adjust for weekends
        while now.weekday() > 4:  # Saturday=5, Sunday=6
            now -= timedelta(days=1)
        
        # Adjust for before market open
        if now.hour < 9 or (now.hour == 9 and now.minute < 15):
            now -= timedelta(days=1)
            while now.weekday() > 4:
                now -= timedelta(days=1)
        
        # Set time range based on timeframe
        if timeframe == "minute":
            # For 1-minute candles, fetch last 30 days
            end_time = now
            start_time = end_time - timedelta(days=30)
        elif timeframe in ["3minute", "5minute", "10minute", "15minute", "30minute"]:
            # For intraday intervals, fetch last 200 days (Kite API limit)
            end_time = now
            start_time = end_time - timedelta(days=200)
        elif timeframe == "60minute":
            # For hourly, fetch last 200 days (Kite API limit)
            end_time = now
            start_time = end_time - timedelta(days=200)
        else:  # "day"
            # For daily, fetch last 5 years
            end_time = now
            start_time = end_time - timedelta(days=1825)
        
        # Fetch historical data via middleware (centralized rate limiting, caching, error handling)
        candles = middleware.get_historical_data(
            instrument_token=nifty_token,
            from_date=start_time,
            to_date=end_time,
            interval=timeframe,
            use_cache=True
        )
        
        if not candles:
            return {
                "candles": [],
                "ma7": [],
                "ma20": [],
                "bb_upper": [],
                "bb_lower": []
            }
        
        # Limit candles to requested amount
        candles = candles[-limit:] if len(candles) > limit else candles
        
        # Normalize candle structure for frontend
        normalized_candles = []
        for candle in candles:
            normalized_candles.append({
                "timestamp": candle.get("date"),
                "open": candle.get("open"),
                "high": candle.get("high"),
                "low": candle.get("low"),
                "close": candle.get("close"),
            })
        
        # Calculate technical indicators using efficient pandas calculation
        trading_logic = TradingLogicService()
        ma7_data = []
        ma20_data = []
        bb_upper_data = []
        bb_lower_data = []
        
        if len(normalized_candles) >= 20:
            # Convert to DataFrame for efficient calculation
            df = pd.DataFrame(normalized_candles)
            
            # Calculate all indicators at once using optimized pandas operations
            df_with_indicators = trading_logic.calculate_indicators_from_df(df)
            
            # Extract indicator values for each valid position
            for idx in range(19, len(df_with_indicators)):  # Start from index 19 (20th candle, 0-indexed)
                row = df_with_indicators.iloc[idx]
                timestamp = row.get("timestamp")
                
                if pd.notna(row.get("ma7")):
                    ma7_data.append({
                        "timestamp": timestamp,
                        "value": round(row.get("ma7"), 2)
                    })
                if pd.notna(row.get("ma20")):
                    ma20_data.append({
                        "timestamp": timestamp,
                        "value": round(row.get("ma20"), 2)
                    })
                if pd.notna(row.get("bb_upper")):
                    bb_upper_data.append({
                        "timestamp": timestamp,
                        "value": round(row.get("bb_upper"), 2)
                    })
                if pd.notna(row.get("bb_lower")):
                    bb_lower_data.append({
                        "timestamp": timestamp,
                        "value": round(row.get("bb_lower"), 2)
                    })
        
        # Format candles for response (convert datetime to timestamp)
        formatted_candles = []
        for candle in normalized_candles:
            date_obj = candle.get("timestamp")
            if isinstance(date_obj, datetime):
                timestamp = int(date_obj.timestamp() * 1000)  # Convert to milliseconds
            else:
                timestamp = date_obj
            
            formatted_candles.append({
                "timestamp": timestamp,
                "open": round(candle.get("open"), 2) if candle.get("open") else 0,
                "high": round(candle.get("high"), 2) if candle.get("high") else 0,
                "low": round(candle.get("low"), 2) if candle.get("low") else 0,
                "close": round(candle.get("close"), 2) if candle.get("close") else 0,
            })
        
        # Format indicator data
        def format_indicator_data(data_list):
            formatted = []
            for item in data_list:
                ts = item.get("timestamp")
                if isinstance(ts, datetime):
                    ts = int(ts.timestamp() * 1000)
                formatted.append({
                    "timestamp": ts,
                    "value": item.get("value", 0)
                })
            return formatted
        
        return {
            "candles": formatted_candles,
            "ma7": format_indicator_data(ma7_data),
            "ma20": format_indicator_data(ma20_data),
            "bb_upper": format_indicator_data(bb_upper_data),
            "bb_lower": format_indicator_data(bb_lower_data)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching chart data: {e}")
        raise HTTPException(status_code=500, detail=str(e))
