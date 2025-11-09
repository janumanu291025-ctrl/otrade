from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime, time


# Broker Schemas
class BrokerConfigBase(BaseModel):
    broker_type: str
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    user_id: Optional[str] = None


class BrokerConfigCreate(BrokerConfigBase):
    pass


class BrokerConfigUpdate(BaseModel):
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    access_token: Optional[str] = None
    user_id: Optional[str] = None


class BrokerConfig(BrokerConfigBase):
    id: int
    access_token: Optional[str] = None
    is_active: bool
    token_expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Market Data Schemas
class MarketQuote(BaseModel):
    instrument_token: str
    symbol: str
    last_price: float
    open: float
    high: float
    low: float
    close: float
    volume: int
    change: float
    change_percentage: float


class MarketDepth(BaseModel):
    buy: List[Dict[str, float]]
    sell: List[Dict[str, float]]


# WebSocket Message Schemas
class WSMessage(BaseModel):
    type: str
    data: Dict


# Authentication Schemas
class BrokerAuthURL(BaseModel):
    auth_url: str
    
    
class BrokerAuthCallback(BaseModel):
    request_token: str
    broker_type: str


# Market Time Schemas
class HolidayResponse(BaseModel):
    """Holiday response from exchange calendar"""
    date: str
    name: str
    description: Optional[str] = None


class MarketStatusResponse(BaseModel):
    """Market status response"""
    is_open: bool
    is_trading_day: bool
    current_time: str
    current_day: str
    market_open_time: Optional[str] = None
    market_close_time: Optional[str] = None
    exchange: str
    next_trading_day: Optional[str] = None


class TimeUntilResponse(BaseModel):
    """Time until market open/close response"""
    is_open: bool
    seconds: int
    formatted: str
    opens_at: Optional[str] = None
    closes_at: Optional[str] = None


# Unified Broker Middleware Schemas
class MiddlewareStatus(BaseModel):
    """Unified broker middleware status"""
    running: bool
    market_hours_active: bool
    webhook_connection_time: bool
    webhook_connected: bool
    webhook_data_flowing: bool
    ltp_fallback_active: bool
    subscribed_instruments: int
    polling_active: bool


