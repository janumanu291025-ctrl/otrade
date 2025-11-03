"""
Unified Trading Configuration API Endpoints
Manages configuration used by Backtest, Paper Trading, and Live Trading
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import logging

from backend.database import get_db
from backend.models import TradingConfig

router = APIRouter(prefix="/api/config", tags=["config"])
logger = logging.getLogger(__name__)


@router.get("/")
async def get_all_configs(db: Session = Depends(get_db)):
    """Get all trading configurations"""
    try:
        configs = db.query(TradingConfig).order_by(
            TradingConfig.is_active.desc(),
            TradingConfig.updated_at.desc()
        ).all()
        
        return {
            "configs": [
                {
                    "id": c.id,
                    "name": c.name,
                    "description": c.description,
                    "is_active": c.is_active,
                    "initial_capital": c.initial_capital,
                    "ma_short_period": c.ma_short_period,
                    "ma_long_period": c.ma_long_period,
                    "major_trend_timeframe": c.major_trend_timeframe,
                    "minor_trend_timeframe": c.minor_trend_timeframe,
                    "buy_7ma_enabled": c.buy_7ma_enabled,
                    "buy_7ma_percentage_below": c.buy_7ma_percentage_below,
                    "buy_7ma_target_percentage": c.buy_7ma_target_percentage,
                    "buy_7ma_stoploss_percentage": c.buy_7ma_stoploss_percentage,
                    "buy_20ma_enabled": c.buy_20ma_enabled,
                    "buy_20ma_percentage_below": c.buy_20ma_percentage_below,
                    "buy_20ma_target_percentage": c.buy_20ma_target_percentage,
                    "buy_20ma_stoploss_percentage": c.buy_20ma_stoploss_percentage,
                    "buy_lbb_enabled": c.buy_lbb_enabled,
                    "buy_lbb_percentage_below": c.buy_lbb_percentage_below,
                    "buy_lbb_target_percentage": c.buy_lbb_target_percentage,
                    "buy_lbb_stoploss_percentage": c.buy_lbb_stoploss_percentage,
                    "capital_allocation_pct": c.capital_allocation_pct,
                    "lot_size": c.lot_size,
                    "min_strike_gap": c.min_strike_gap,
                    "strike_round_to": c.strike_round_to,
                    "square_off_time": c.square_off_time,
                    "square_off_enabled": c.square_off_enabled,
                    "exclude_expiry_day_contracts": c.exclude_expiry_day_contracts,
                    "reverse_signals": c.reverse_signals,
                    "lots_per_trade": c.lots_per_trade,
                    "tick_size": c.tick_size,
                    "expiry_offset_days": c.expiry_offset_days,
                    "created_at": c.created_at.isoformat(),
                    "updated_at": c.updated_at.isoformat()
                }
                for c in configs
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching configs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active")
async def get_active_config(db: Session = Depends(get_db)):
    """Get the active trading configuration"""
    try:
        config = db.query(TradingConfig).filter(
            TradingConfig.is_active == True
        ).first()
        
        if not config:
            raise HTTPException(status_code=404, detail="No active configuration found")
        
        return {
            "id": config.id,
            "name": config.name,
            "description": config.description,
            "is_active": config.is_active,
            "initial_capital": config.initial_capital,
            "ma_short_period": config.ma_short_period,
            "ma_long_period": config.ma_long_period,
            "major_trend_timeframe": config.major_trend_timeframe,
            "minor_trend_timeframe": config.minor_trend_timeframe,
            "buy_7ma_enabled": config.buy_7ma_enabled,
            "buy_7ma_percentage_below": config.buy_7ma_percentage_below,
            "buy_7ma_target_percentage": config.buy_7ma_target_percentage,
            "buy_7ma_stoploss_percentage": config.buy_7ma_stoploss_percentage,
            "buy_20ma_enabled": config.buy_20ma_enabled,
            "buy_20ma_percentage_below": config.buy_20ma_percentage_below,
            "buy_20ma_target_percentage": config.buy_20ma_target_percentage,
            "buy_20ma_stoploss_percentage": config.buy_20ma_stoploss_percentage,
            "buy_lbb_enabled": config.buy_lbb_enabled,
            "buy_lbb_percentage_below": config.buy_lbb_percentage_below,
            "buy_lbb_target_percentage": config.buy_lbb_target_percentage,
            "buy_lbb_stoploss_percentage": config.buy_lbb_stoploss_percentage,
            "capital_allocation_pct": config.capital_allocation_pct,
            "lot_size": config.lot_size,
            "min_strike_gap": config.min_strike_gap,
            "strike_round_to": config.strike_round_to,
            "square_off_time": config.square_off_time,
            "square_off_enabled": config.square_off_enabled,
            "exclude_expiry_day_contracts": config.exclude_expiry_day_contracts,
            "reverse_signals": config.reverse_signals,
            "lots_per_trade": config.lots_per_trade,
            "tick_size": config.tick_size,
            "expiry_offset_days": config.expiry_offset_days,
            "created_at": config.created_at.isoformat(),
            "updated_at": config.updated_at.isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching active config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{config_id}")
async def get_config(config_id: int, db: Session = Depends(get_db)):
    """Get a specific trading configuration"""
    try:
        config = db.query(TradingConfig).filter(TradingConfig.id == config_id).first()
        
        if not config:
            raise HTTPException(status_code=404, detail="Configuration not found")
        
        return {
            "id": config.id,
            "name": config.name,
            "description": config.description,
            "is_active": config.is_active,
            "initial_capital": config.initial_capital,
            "ma_short_period": config.ma_short_period,
            "ma_long_period": config.ma_long_period,
            "major_trend_timeframe": config.major_trend_timeframe,
            "minor_trend_timeframe": config.minor_trend_timeframe,
            "buy_7ma_enabled": config.buy_7ma_enabled,
            "buy_7ma_percentage_below": config.buy_7ma_percentage_below,
            "buy_7ma_target_percentage": config.buy_7ma_target_percentage,
            "buy_7ma_stoploss_percentage": config.buy_7ma_stoploss_percentage,
            "buy_20ma_enabled": config.buy_20ma_enabled,
            "buy_20ma_percentage_below": config.buy_20ma_percentage_below,
            "buy_20ma_target_percentage": config.buy_20ma_target_percentage,
            "buy_20ma_stoploss_percentage": config.buy_20ma_stoploss_percentage,
            "buy_lbb_enabled": config.buy_lbb_enabled,
            "buy_lbb_percentage_below": config.buy_lbb_percentage_below,
            "buy_lbb_target_percentage": config.buy_lbb_target_percentage,
            "buy_lbb_stoploss_percentage": config.buy_lbb_stoploss_percentage,
            "capital_allocation_pct": config.capital_allocation_pct,
            "lot_size": config.lot_size,
            "min_strike_gap": config.min_strike_gap,
            "strike_round_to": config.strike_round_to,
            "square_off_time": config.square_off_time,
            "square_off_enabled": config.square_off_enabled,
            "exclude_expiry_day_contracts": config.exclude_expiry_day_contracts,
            "reverse_signals": config.reverse_signals,
            "lots_per_trade": config.lots_per_trade,
            "tick_size": config.tick_size,
            "expiry_offset_days": config.expiry_offset_days,
            "created_at": config.created_at.isoformat(),
            "updated_at": config.updated_at.isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching config {config_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
async def create_config(data: dict, db: Session = Depends(get_db)):
    """Create a new trading configuration"""
    try:
        # Check if name already exists
        existing = db.query(TradingConfig).filter(TradingConfig.name == data.get("name")).first()
        if existing:
            raise HTTPException(status_code=400, detail="Configuration with this name already exists")
        
        # If this is set as active, deactivate all others
        if data.get("is_active", False):
            db.query(TradingConfig).update({"is_active": False})
        
        config = TradingConfig(
            name=data.get("name"),
            description=data.get("description"),
            is_active=data.get("is_active", False),
            initial_capital=data.get("initial_capital", 100000.0),
            ma_short_period=data.get("ma_short_period", 7),
            ma_long_period=data.get("ma_long_period", 20),
            major_trend_timeframe=data.get("major_trend_timeframe", "15min"),
            minor_trend_timeframe=data.get("minor_trend_timeframe", "1min"),
            buy_7ma_enabled=data.get("buy_7ma_enabled", True),
            buy_7ma_percentage_below=data.get("buy_7ma_percentage_below", 0.0),
            buy_7ma_target_percentage=data.get("buy_7ma_target_percentage", 2.5),
            buy_7ma_stoploss_percentage=data.get("buy_7ma_stoploss_percentage", 15.0),
            buy_20ma_enabled=data.get("buy_20ma_enabled", True),
            buy_20ma_percentage_below=data.get("buy_20ma_percentage_below", 0.0),
            buy_20ma_target_percentage=data.get("buy_20ma_target_percentage", 3.0),
            buy_20ma_stoploss_percentage=data.get("buy_20ma_stoploss_percentage", 15.0),
            buy_lbb_enabled=data.get("buy_lbb_enabled", True),
            buy_lbb_percentage_below=data.get("buy_lbb_percentage_below", 0.0),
            buy_lbb_target_percentage=data.get("buy_lbb_target_percentage", 5.0),
            buy_lbb_stoploss_percentage=data.get("buy_lbb_stoploss_percentage", 15.0),
            capital_allocation_pct=data.get("capital_allocation_pct", 50.0),
            lot_size=data.get("lot_size", 75),
            min_strike_gap=data.get("min_strike_gap", 100),
            strike_round_to=data.get("strike_round_to", 100),
            square_off_time=data.get("square_off_time", "15:28"),
            square_off_enabled=data.get("square_off_enabled", True),
            exclude_expiry_day_contracts=data.get("exclude_expiry_day_contracts", True),
            reverse_signals=data.get("reverse_signals", False),
            lots_per_trade=data.get("lots_per_trade", 1),
            tick_size=data.get("tick_size", 0.05),
            expiry_offset_days=data.get("expiry_offset_days", 0)
        )
        
        db.add(config)
        db.commit()
        db.refresh(config)
        
        logger.info(f"Created config: {config.name} (ID: {config.id})")
        
        return {
            "id": config.id,
            "name": config.name,
            "description": config.description,
            "is_active": config.is_active,
            "message": "Configuration created successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{config_id}")
async def update_config(config_id: int, data: dict, db: Session = Depends(get_db)):
    """Update an existing trading configuration"""
    try:
        config = db.query(TradingConfig).filter(TradingConfig.id == config_id).first()
        
        if not config:
            raise HTTPException(status_code=404, detail="Configuration not found")
        
        # If setting this config as active, deactivate all others
        if data.get("is_active", False) and not config.is_active:
            db.query(TradingConfig).filter(TradingConfig.id != config_id).update({"is_active": False})
        
        # Update fields
        for key, value in data.items():
            if hasattr(config, key) and key not in ["id", "created_at", "updated_at"]:
                setattr(config, key, value)
        
        config.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(config)
        
        logger.info(f"Updated config: {config.name} (ID: {config.id})")
        
        return {
            "id": config.id,
            "name": config.name,
            "description": config.description,
            "is_active": config.is_active,
            "message": "Configuration updated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating config {config_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{config_id}/activate")
async def activate_config(config_id: int, db: Session = Depends(get_db)):
    """Activate a trading configuration (deactivates all others)"""
    try:
        config = db.query(TradingConfig).filter(TradingConfig.id == config_id).first()
        
        if not config:
            raise HTTPException(status_code=404, detail="Configuration not found")
        
        # Deactivate all configs
        db.query(TradingConfig).update({"is_active": False})
        
        # Activate this one
        config.is_active = True
        config.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Activated config: {config.name} (ID: {config.id})")
        
        return {
            "id": config.id,
            "name": config.name,
            "is_active": True,
            "message": "Configuration activated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error activating config {config_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{config_id}")
async def delete_config(config_id: int, db: Session = Depends(get_db)):
    """Delete a trading configuration"""
    try:
        config = db.query(TradingConfig).filter(TradingConfig.id == config_id).first()
        
        if not config:
            raise HTTPException(status_code=404, detail="Configuration not found")
        
        # Don't allow deleting the active config if it's the only one
        if config.is_active:
            other_configs = db.query(TradingConfig).filter(TradingConfig.id != config_id).count()
            if other_configs == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot delete the only configuration. Create another one first."
                )
        
        name = config.name
        db.delete(config)
        db.commit()
        
        logger.info(f"Deleted config: {name} (ID: {config_id})")
        
        return {
            "message": f"Configuration '{name}' deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting config {config_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
