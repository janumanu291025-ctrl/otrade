"""
Database models (deprecated - using JSON-based configuration)
This file is kept for backward compatibility with existing imports
but all functionality has been migrated to config.manager
"""

# Stub classes to prevent import errors
class BrokerConfig:
    is_active = None
    broker_type = None
    api_key = None
    api_secret = None
    access_token = None
    token_expires_at = None
    user_id = None

class Instrument:
    id = None
    instrument_token = None
    exchange = None
    tradingsymbol = None
    name = None
    updated_at = None

class Order:
    id = None
    order_id = None
    status = None

class Fund:
    available = 0
    used = 0

class Position:
    symbol = None
    quantity = 0
    average_price = 0

class TradingConfig:
    is_active = None
    updated_at = None

class LiveTradingSignal:
    id = None
    signal_id = None

class PaperTrade:
    id = None

class PaperTradingAlert:
    id = None

class PaperTradingMarketData:
    id = None

class LiveTradingAlert:
    id = None

class LiveTrade:
    id = None
    trade_id = None

class InstrumentDownloadLog:
    id = None
    download_date = None
    instrument_count = 0
    download_type = None
    source = None
    status = None
    error_message = None

# Empty SessionLocal for backward compatibility
SessionLocal = None

class LiveTradingState:
    id = None
    state = None

class LiveTradingMarketData:
    id = None
    data = None
