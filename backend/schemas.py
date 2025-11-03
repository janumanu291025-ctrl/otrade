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
class MarketHoursConfig(BaseModel):
    """Market hours configuration response"""
    id: int
    start_time: str
    end_time: str
    webhook_start_time: str
    order_placement_start_time: str
    order_placement_end_time: str
    square_off_time: str
    trading_days: List[int]
    webhook_url: Optional[str] = None
    polling_interval_seconds: int
    
    class Config:
        from_attributes = True


class MarketHoursUpdate(BaseModel):
    """Market hours configuration update request"""
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    webhook_start_time: Optional[str] = None
    order_placement_start_time: Optional[str] = None
    order_placement_end_time: Optional[str] = None
    square_off_time: Optional[str] = None
    trading_days: Optional[List[int]] = None
    webhook_url: Optional[str] = None
    polling_interval_seconds: Optional[int] = None


class HolidayCreate(BaseModel):
    """Holiday creation request"""
    date: str  # YYYY-MM-DD
    name: str
    description: Optional[str] = None


class HolidayResponse(BaseModel):
    """Holiday response"""
    id: int
    date: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class MarketStatusResponse(BaseModel):
    """Market status response"""
    is_open: bool
    is_active: bool
    is_trading_day: bool
    is_webhook_connection_time: bool
    is_order_placement_time: bool
    is_square_off_time: bool
    current_time: str
    current_day: str
    market_open_time: str
    market_close_time: str
    webhook_start_time: str
    order_placement_start_time: str
    order_placement_end_time: str
    square_off_time: str
    trading_days: List[str]
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


