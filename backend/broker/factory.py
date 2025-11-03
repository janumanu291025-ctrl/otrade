"""
Broker Factory - Get broker client instance
"""
from sqlalchemy.orm import Session
from backend.models import BrokerConfig
from backend.broker.kite.client import KiteBroker


def get_broker_client(db: Session, raise_exception: bool = True):
    """
    Get active broker client
    
    Args:
        db: Database session
        raise_exception: If False, returns None instead of raising exception
    
    Returns:
        Broker client instance or None
    """
    broker_config = db.query(BrokerConfig).filter(
        BrokerConfig.is_active == True
    ).first()
    
    if not broker_config:
        if raise_exception:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="No active broker connection")
        return None
    
    if broker_config.broker_type == "kite":
        return KiteBroker(
            api_key=broker_config.api_key,
            api_secret=broker_config.api_secret,
            access_token=broker_config.access_token
        )
    
    # Unsupported broker type
    if raise_exception:
        from fastapi import HTTPException
        error_msg = f"Unsupported broker type: {broker_config.broker_type}"
        raise HTTPException(status_code=400, detail=error_msg)
    
    return None
