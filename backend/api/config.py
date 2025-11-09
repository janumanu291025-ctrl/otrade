"""Trading configuration endpoints"""
from fastapi import APIRouter, HTTPException
from config.manager import ConfigManager
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/config", tags=["config"])
config_manager = ConfigManager()


@router.get("/")
async def get_configs():
    """Get all trading configurations"""
    try:
        config = config_manager.load_trading_config()
        return {
            "status": "success",
            "configs": [config] if config else [],
            "message": "Configuration loaded from JSON file"
        }
    except Exception as e:
        logger.error(f"Error fetching configs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{config_id}")
async def get_config(config_id: str):
    """Get a specific trading configuration"""
    try:
        config = config_manager.load_trading_config()
        return {
            "status": "success",
            "configs": [config] if config else [],
            "message": "Configuration loaded from JSON file"
        }
    except Exception as e:
        logger.error(f"Error fetching config {config_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
async def create_config(data: dict):
    """Create/Update trading configuration"""
    try:
        success = config_manager.save_trading_config(data)
        if success:
            return {
                "status": "success",
                "message": "Configuration saved successfully",
                "config": data
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to save configuration")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{config_id}")
async def update_config(config_id: str, data: dict):
    """Update trading configuration"""
    try:
        config = config_manager.load_trading_config()
        if not config:
            config = {}
        
        config.update(data)
        success = config_manager.save_trading_config(config)
        
        if success:
            return {
                "status": "success",
                "message": "Configuration updated successfully",
                "config": config
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to update configuration")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{config_id}")
async def delete_config(config_id: str):
    """Delete trading configuration"""
    try:
        # In JSON-based system, we clear the config
        config_manager.save_trading_config({})
        return {
            "status": "success",
            "message": "Configuration deleted successfully"
        }
    except Exception as e:
        logger.error(f"Error deleting config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
