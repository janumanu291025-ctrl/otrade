"""
Paper Trading API Endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Body, Query
from sqlalchemy.orm import Session
from typing import Dict, Optional
from datetime import datetime
import logging
import asyncio
from pydantic import BaseModel

from backend.database import get_db
from backend.models import TradingConfig, PaperTrade, PaperTradingAlert, PaperTradingMarketData, Instrument
from backend.services.paper_trading_engine import PaperTradingEngine
from backend.services.broker_data_service import get_broker_data_service
from backend.api.webhook import set_paper_trading_engine
from backend.services.market_time import get_market_status as get_mkt_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/paper-trading", tags=["paper_trading"])


class StartPaperTradingRequest(BaseModel):
    """Request model for starting paper trading"""
    config_id: int
    historical_mode: bool = False
    replay_speed: float = 1.0
    selected_date: Optional[str] = None

# Global engine instance
_engine_instance: Optional[PaperTradingEngine] = None
_engine_callback = None  # Store callback reference for removal
_engine_config_id: Optional[int] = None  # Store config ID separately to avoid session issues


def get_engine() -> Optional[PaperTradingEngine]:
    """Get current paper trading engine instance"""
    return _engine_instance


@router.post("/start")
async def start_paper_trading(
    request: StartPaperTradingRequest,
    db: Session = Depends(get_db)
) -> Dict:
    """
    Start paper trading engine for a config
    
    Args:
        request: Request containing config_id, historical_mode, replay_speed, selected_date
    """
    global _engine_instance, _engine_callback, _engine_config_id
    
    try:
        # Check if already running
        if _engine_instance and _engine_instance.running:
            return {
                "status": "already_running",
                "message": "Paper trading engine is already running",
                "config_id": _engine_config_id,
                "mode": _engine_instance.get_current_mode()
            }
        
        # Load config
        config = db.query(TradingConfig).filter(
            TradingConfig.id == request.config_id
        ).first()
        
        if not config:
            raise HTTPException(status_code=404, detail="Config not found")
        
        # Update replay speed if provided
        if request.replay_speed != config.replay_speed:
            config.replay_speed = request.replay_speed
            db.commit()
            logger.info(f"Updated replay speed to {request.replay_speed}x for config {request.config_id}")
        
        # Get broker data service
        broker_data_service = get_broker_data_service(db, mode='paper', enable_cache=True)
        
        # Determine mode
        mode = "historical" if request.historical_mode else "auto"
        
        # Create and start engine
        _engine_instance = PaperTradingEngine(broker_data_service=broker_data_service, mode=mode, selected_date=request.selected_date)
        if not _engine_instance.load_config(request.config_id):
            raise HTTPException(status_code=500, detail="Failed to load config")
        
        # Store config_id to avoid session issues
        _engine_config_id = request.config_id
        
        await _engine_instance.start()
        
        # Get the actual mode being used
        actual_mode = _engine_instance.get_current_mode()
        
        # Register with webhook for live updates (only if in live mode)
        if actual_mode == "live":
            set_paper_trading_engine(_engine_instance)
            # Note: Paper trading now relies on webhook LTP updates via /api/webhook/tick
            # instead of direct WebSocket subscriptions
            logger.info("Paper trading registered for webhook LTP updates")
        else:
            logger.info("Historical mode active - Using simulated data instead of live stream")
        
        logger.info(f"Paper trading engine started for config {request.config_id} in {actual_mode.upper()} mode")
        
        return {
            "status": "started",
            "message": f"Paper trading engine started successfully in {actual_mode.upper()} mode",
            "config_id": request.config_id,
            "mode": actual_mode,
            "initial_capital": float(config.initial_capital),
            "started_at": config.started_at.isoformat() if config.started_at else None
        }
        
    except Exception as e:
        logger.error(f"Error starting paper trading engine: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_paper_trading(db: Session = Depends(get_db)) -> Dict:
    """Stop paper trading engine"""
    global _engine_instance, _engine_callback, _engine_config_id
    
    try:
        if not _engine_instance:
            return {
                "status": "not_running",
                "message": "Paper trading engine is not running"
            }
        
        config_id = _engine_config_id
        
        # Paper trading cleanup (no WebSocket unsubscribe needed)
        if _engine_callback:
            _engine_callback = None
        
        await _engine_instance.stop()
        
        # Clear engine instance
        _engine_instance = None
        _engine_config_id = None
        set_paper_trading_engine(None)
        
        logger.info(f"Paper trading engine stopped for config {config_id}")
        
        return {
            "status": "stopped",
            "message": "Paper trading engine stopped successfully",
            "config_id": config_id
        }
        
    except Exception as e:
        logger.error(f"Error stopping paper trading engine: {e}")
        # Clear the instance even on error
        _engine_instance = None
        _engine_config_id = None
        set_paper_trading_engine(None)
        
        # If it's a session error, don't raise - just return stopped status
        if "rolled back" in str(e).lower() or "session" in str(e).lower():
            logger.warning("Session error during stop - engine cleared anyway")
            return {
                "status": "stopped",
                "message": "Paper trading engine stopped (with session errors)",
                "config_id": config_id if 'config_id' in locals() else None
            }
        
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pause")
async def pause_paper_trading(db: Session = Depends(get_db)) -> Dict:
    """Pause paper trading (no new entries)"""
    global _engine_instance
    
    if not _engine_instance or not _engine_instance.running:
        raise HTTPException(status_code=400, detail="Engine not running")
    
    try:
        await _engine_instance.pause()
        return {
            "status": "paused",
            "message": "Paper trading paused - No new entries",
            "config_id": _engine_instance.config.id
        }
    except Exception as e:
        logger.error(f"Error pausing paper trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resume")
async def resume_paper_trading(db: Session = Depends(get_db)) -> Dict:
    """Resume paper trading"""
    global _engine_instance
    
    if not _engine_instance:
        raise HTTPException(status_code=400, detail="Engine not running")
    
    try:
        await _engine_instance.resume()
        return {
            "status": "running",
            "message": "Paper trading resumed",
            "config_id": _engine_instance.config.id
        }
    except Exception as e:
        logger.error(f"Error resuming paper trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_status(db: Session = Depends(get_db)) -> Dict:
    """Get paper trading engine status"""
    global _engine_instance, _engine_config_id
    
    if not _engine_instance or not _engine_config_id:
        return {
            "running": False,
            "status": "stopped",
            "mode": "none",
            "message": "No paper trading engine running"
        }
    
    # Reload config from current database session to avoid session binding issues
    config = db.query(TradingConfig).filter(
        TradingConfig.id == _engine_config_id
    ).first()
    
    if not config:
        logger.error("Config not found in database")
        return {
            "running": False,
            "status": "error",
            "mode": "none",
            "message": "Configuration not found"
        }
    
    # Get latest market data
    latest_data = db.query(PaperTradingMarketData).filter(
        PaperTradingMarketData.config_id == config.id
    ).order_by(PaperTradingMarketData.timestamp.desc()).first()
    
    # Get active trades
    active_trades = db.query(PaperTrade).filter(
        PaperTrade.config_id == config.id,
        PaperTrade.status == "open"
    ).count()
    
    # Get current mode
    current_mode = _engine_instance.get_current_mode()
    is_historical = _engine_instance.is_historical_mode()
    
    # Get current simulation timestamp from engine
    current_simulation_time = _engine_instance.current_timestamp
    
    return {
        "running": _engine_instance.running,
        "status": config.status,
        "mode": current_mode,
        "is_historical_mode": is_historical,
        "config_id": config.id,
        "initial_capital": float(config.initial_capital),
        "current_capital": float(config.current_capital),
        "started_at": config.started_at.isoformat() if config.started_at else None,
        "active_positions": active_trades,
        "nifty_ltp": float(latest_data.nifty_ltp) if latest_data else None,
        "major_trend": latest_data.major_trend if latest_data else None,
        "major_ma7": float(latest_data.major_ma7) if latest_data and latest_data.major_ma7 else None,
        "major_ma20": float(latest_data.major_ma20) if latest_data and latest_data.major_ma20 else None,
        "major_trend_changed_at": latest_data.major_trend_changed_at.isoformat() if latest_data and latest_data.major_trend_changed_at else None,
        "minor_trend": latest_data.minor_trend if latest_data else None,
        "minor_ma7": float(latest_data.minor_ma7) if latest_data and latest_data.minor_ma7 else None,
        "minor_ma20": float(latest_data.minor_ma20) if latest_data and latest_data.minor_ma20 else None,
        "minor_trend_changed_at": latest_data.minor_trend_changed_at.isoformat() if latest_data and latest_data.minor_trend_changed_at else None,
        "last_update": latest_data.timestamp.isoformat() if latest_data else None,
        "current_simulation_time": current_simulation_time.isoformat() if current_simulation_time else None,
        "suspend_ce": config.suspend_ce,
        "suspend_pe": config.suspend_pe
    }


@router.get("/market-status")
async def get_market_status(db: Session = Depends(get_db)) -> Dict:
    """
    Get current market status (open/closed, trading hours, holidays)
    """
    try:
        status = get_mkt_status(db)
        return {
            "status": "success",
            "data": status
        }
    except Exception as e:
        logger.error(f"Error getting market status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trades/{config_id}")
async def get_trades(config_id: int, limit: int = 100, db: Session = Depends(get_db)) -> Dict:
    """Get trades for a config"""
    try:
        trades = db.query(PaperTrade).filter(
            PaperTrade.config_id == config_id
        ).order_by(PaperTrade.entry_time.desc()).limit(limit).all()
        
        return {
            "trades": [
                {
                    "id": t.id,
                    "date": t.date.isoformat(),
                    "instrument": t.instrument,
                    "instrument_token": t.instrument_token,
                    "option_type": t.option_type,
                    "strike": float(t.strike),
                    "entry_time": t.entry_time.isoformat(),
                    "entry_price": float(t.entry_price),
                    "entry_trigger": t.entry_trigger,
                    "quantity": t.quantity,
                    "target_price": float(t.target_price),
                    "stoploss_price": float(t.stoploss_price),
                    "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                    "exit_price": float(t.exit_price) if t.exit_price else None,
                    "exit_reason": t.exit_reason,
                    "pnl": float(t.pnl),
                    "pnl_percentage": float(t.pnl_percentage),
                    "current_price": float(t.current_price) if t.current_price else None,
                    "unrealized_pnl": float(t.unrealized_pnl),
                    "status": t.status
                }
                for t in trades
            ]
        }
        
    except Exception as e:
        logger.error(f"Error fetching trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/{config_id}")
async def get_alerts(config_id: int, limit: int = 100, db: Session = Depends(get_db)) -> Dict:
    """Get alerts for a config"""
    try:
        alerts = db.query(PaperTradingAlert).filter(
            PaperTradingAlert.config_id == config_id
        ).order_by(PaperTradingAlert.timestamp.desc()).limit(limit).all()
        
        return {
            "alerts": [
                {
                    "id": a.id,
                    "timestamp": a.timestamp.isoformat(),
                    "alert_type": a.alert_type,
                    "message": a.message,
                    "trade_id": a.trade_id
                }
                for a in alerts
            ]
        }
        
    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market-data/{config_id}")
async def get_market_data(config_id: int, limit: int = 100, db: Session = Depends(get_db)) -> Dict:
    """Get market data snapshots for a config"""
    try:
        data = db.query(PaperTradingMarketData).filter(
            PaperTradingMarketData.config_id == config_id
        ).order_by(PaperTradingMarketData.timestamp.desc()).limit(limit).all()
        
        return {
            "market_data": [
                {
                    "id": d.id,
                    "timestamp": d.timestamp.isoformat(),
                    "nifty_ltp": float(d.nifty_ltp),
                    "major_ma7": float(d.major_ma7) if d.major_ma7 else None,
                    "major_ma20": float(d.major_ma20) if d.major_ma20 else None,
                    "major_lbb": float(d.major_lbb) if d.major_lbb else None,
                    "major_trend": d.major_trend,
                    "minor_ma7": float(d.minor_ma7) if d.minor_ma7 else None,
                    "minor_ma20": float(d.minor_ma20) if d.minor_ma20 else None,
                    "minor_lbb": float(d.minor_lbb) if d.minor_lbb else None,
                    "minor_trend": d.minor_trend
                }
                for d in data
            ]
        }
        
    except Exception as e:
        logger.error(f"Error fetching market data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/close-position/{trade_id}")
async def close_position(trade_id: int, db: Session = Depends(get_db)) -> Dict:
    """Manually close an active position"""
    global _engine_instance
    
    if not _engine_instance or not _engine_instance.running:
        raise HTTPException(status_code=400, detail="Engine not running")
    
    try:
        trade = db.query(PaperTrade).filter(
            PaperTrade.id == trade_id,
            PaperTrade.status == "open"
        ).first()
        
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found or already closed")
        
        # Call engine to close the trade
        await _engine_instance._exit_trade(trade, "Manual Close")
        
        return {
            "status": "success",
            "message": "Position closed successfully",
            "trade_id": trade_id
        }
        
    except Exception as e:
        logger.error(f"Error closing position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suspend-ce")
async def suspend_ce(suspend: bool = Query(...), db: Session = Depends(get_db)) -> Dict:
    """
    Suspend/Resume Call Entry (CE) trades
    Updates the active config's suspend_ce field
    """
    global _engine_instance, _engine_config_id
    
    if not _engine_instance or not _engine_instance.running:
        raise HTTPException(status_code=400, detail="Engine not running")
    
    try:
        config = db.query(TradingConfig).filter(
            TradingConfig.id == _engine_config_id
        ).first()
        
        if not config:
            raise HTTPException(status_code=404, detail="Config not found")
        
        config.suspend_ce = suspend
        db.commit()
        
        # Update engine config
        _engine_instance.config.suspend_ce = suspend
        
        return {
            "status": "success",
            "message": f"CE entries {'suspended' if suspend else 'resumed'}",
            "suspend_ce": suspend
        }
        
    except Exception as e:
        logger.error(f"Error updating CE suspension: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suspend-pe")
async def suspend_pe(suspend: bool = Query(...), db: Session = Depends(get_db)) -> Dict:
    """
    Suspend/Resume Put Entry (PE) trades
    Updates the active config's suspend_pe field
    """
    global _engine_instance, _engine_config_id
    
    if not _engine_instance or not _engine_instance.running:
        raise HTTPException(status_code=400, detail="Engine not running")
    
    try:
        config = db.query(TradingConfig).filter(
            TradingConfig.id == _engine_config_id
        ).first()
        
        if not config:
            raise HTTPException(status_code=404, detail="Config not found")
        
        config.suspend_pe = suspend
        db.commit()
        
        # Update engine config
        _engine_instance.config.suspend_pe = suspend
        
        return {
            "status": "success",
            "message": f"PE entries {'suspended' if suspend else 'resumed'}",
            "suspend_pe": suspend
        }
        
    except Exception as e:
        logger.error(f"Error updating PE suspension: {e}")
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
        
        # If no live data, try to get from broker
        if nifty_ltp == 0.0:
            try:
                broker_data_service = get_broker_data_service(db, mode='paper', enable_cache=True)
                ltp_data = broker_data_service.get_ltp(["256265"], use_cache=False)
                if ltp_data and "256265" in ltp_data:
                    nifty_ltp = ltp_data["256265"]
            except Exception as e:
                logger.warning(f"Could not fetch NIFTY 50 LTP: {e}")
        
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
            "entry_triggers": []
        }
        
        ce_instrument = None
        pe_instrument = None
        
        # Calculate strikes for CE and PE based on config
        if nifty_ltp > 0:
            import math
            
            strike_gap = config.min_strike_gap
            round_to = config.strike_round_to
            
            # Get lot size for NIFTY options (typically 25 or 50)
            lot_size = 50  # Default NIFTY lot size
            
            # Calculate quantity based on capital allocation
            max_capital_per_trade = config.initial_capital * (config.capital_allocation_pct / 100)
            
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
                        broker_data_service = get_broker_data_service(db, mode='paper', enable_cache=True)
                        ltp_data = broker_data_service.get_ltp([ce_contract.instrument_token], use_cache=False)
                        if ltp_data and ce_contract.instrument_token in ltp_data:
                            ce_ltp = ltp_data[ce_contract.instrument_token]
                except Exception as e:
                    logger.warning(f"Could not fetch CE LTP: {e}")
                
                # Calculate expected quantity
                expected_quantity = 0
                position_value = 0.0
                cash_balance_after = config.current_capital
                
                if ce_ltp > 0 and lot_size > 0:
                    # Calculate number of lots: available_fund / (ltp * lot_size), then round down
                    max_lots = int(max_capital_per_trade / (ce_ltp * lot_size))
                    if max_lots > 0:
                        expected_quantity = max_lots * lot_size
                        position_value = expected_quantity * ce_ltp
                        cash_balance_after = config.current_capital - position_value
                
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
                    "position_value": position_value,
                    "cash_balance_after": cash_balance_after,
                    "entry_triggers": entry_triggers
                }
            
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
                        broker_data_service = get_broker_data_service(db, mode='paper', enable_cache=True)
                        ltp_data = broker_data_service.get_ltp([pe_contract.instrument_token], use_cache=False)
                        if ltp_data and pe_contract.instrument_token in ltp_data:
                            pe_ltp = ltp_data[pe_contract.instrument_token]
                except Exception as e:
                    logger.warning(f"Could not fetch PE LTP: {e}")
                
                # Calculate expected quantity
                expected_quantity = 0
                position_value = 0.0
                cash_balance_after = config.current_capital
                
                if pe_ltp > 0 and lot_size > 0:
                    # Calculate number of lots: available_fund / (ltp * lot_size), then round down
                    max_lots = int(max_capital_per_trade / (pe_ltp * lot_size))
                    if max_lots > 0:
                        expected_quantity = max_lots * lot_size
                        position_value = expected_quantity * pe_ltp
                        cash_balance_after = config.current_capital - position_value
                
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
                    "position_value": position_value,
                    "cash_balance_after": cash_balance_after,
                    "entry_triggers": entry_triggers
                }
        
        # Append instruments in order: CE, INDEX, PE
        if ce_instrument:
            instruments.append(ce_instrument)
        instruments.append(index_instrument)
        if pe_instrument:
            instruments.append(pe_instrument)
        
        return {
            "status": "success",
            "config_id": config_id,
            "nifty_ltp": nifty_ltp,
            "current_capital": float(config.current_capital),
            "capital_allocation_pct": config.capital_allocation_pct,
            "instruments": instruments
        }
        
    except Exception as e:
        logger.error(f"Error fetching instruments: {e}")
        raise HTTPException(status_code=500, detail=str(e))
