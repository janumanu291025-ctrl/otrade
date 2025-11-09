from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Boolean, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.database import Base


class TradingConfig(Base):
    """
    Unified Trading Configuration
    Used by Paper Trading and Live Trading
    """
    __tablename__ = "trading_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True, unique=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, index=True)  # Only one config can be active at a time
    
    # Capital
    initial_capital = Column(Float, nullable=False, default=100000.0)
    current_capital = Column(Float, nullable=False, default=100000.0)  # For paper/live trading tracking
    
    # Trading control (for paper/live trading)
    suspend_ce = Column(Boolean, default=False)  # Suspend CE entries
    suspend_pe = Column(Boolean, default=False)  # Suspend PE entries
    status = Column(String(20), nullable=False, default="stopped")  # running, paused, stopped
    started_at = Column(DateTime, nullable=True)  # When trading was started
    stopped_at = Column(DateTime, nullable=True)  # When trading was stopped
    
    # Historical simulation settings (for paper trading)
    replay_speed = Column(Float, nullable=False, default=1.0)  # Speed multiplier for historical replay
    
    # MA settings
    ma_short_period = Column(Integer, nullable=False, default=7)
    ma_long_period = Column(Integer, nullable=False, default=20)
    
    # Timeframe configuration
    major_trend_timeframe = Column(String(10), nullable=False, default="15min")
    minor_trend_timeframe = Column(String(10), nullable=False, default="1min")
    
    # Multi-trigger settings for 7MA
    buy_7ma_enabled = Column(Boolean, nullable=False, default=True)
    buy_7ma_percentage_below = Column(Float, nullable=False, default=0.0)
    buy_7ma_target_percentage = Column(Float, nullable=False, default=2.5)
    buy_7ma_stoploss_percentage = Column(Float, nullable=False, default=99.0)
    
    # Multi-trigger settings for 20MA
    buy_20ma_enabled = Column(Boolean, nullable=False, default=True)
    buy_20ma_percentage_below = Column(Float, nullable=False, default=0.0)
    buy_20ma_target_percentage = Column(Float, nullable=False, default=2.5)
    buy_20ma_stoploss_percentage = Column(Float, nullable=False, default=99.0)
    
    # Multi-trigger settings for LBB
    buy_lbb_enabled = Column(Boolean, nullable=False, default=True)
    buy_lbb_percentage_below = Column(Float, nullable=False, default=0.0)
    buy_lbb_target_percentage = Column(Float, nullable=False, default=2.5)
    buy_lbb_stoploss_percentage = Column(Float, nullable=False, default=99.0)
    
    # Position sizing
    capital_allocation_pct = Column(Float, nullable=False, default=16.0)  # % of capital per trade
    lot_size = Column(Integer, nullable=False, default=75)
    
    # Strike selection
    min_strike_gap = Column(Integer, nullable=False, default=100)
    strike_round_to = Column(Integer, nullable=False, default=100)
    
    # Day end square off
    square_off_time = Column(String(10), nullable=False, default="15:20")
    square_off_enabled = Column(Boolean, nullable=False, default=True)
    
    # Contract selection
    exclude_expiry_day_contracts = Column(Boolean, nullable=False, default=True)
    
    # Signal reversal option
    reverse_signals = Column(Boolean, nullable=False, default=False)
    
    # NIFTY options settings
    lots_per_trade = Column(Integer, nullable=False, default=1)
    tick_size = Column(Float, nullable=False, default=0.05)
    
    # Expiry selection
    expiry_offset_days = Column(Integer, nullable=False, default=0)  # 0 = nearest, 1 = next week, etc.
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    # Paper trading relationships with CASCADE delete
    paper_trades = relationship("PaperTrade", back_populates="config", cascade="all, delete-orphan")
    paper_market_data = relationship("PaperTradingMarketData", back_populates="config", cascade="all, delete-orphan")
    paper_alerts = relationship("PaperTradingAlert", back_populates="config", cascade="all, delete-orphan")
    # Live trading relationships with CASCADE delete
    live_trades = relationship("LiveTrade", back_populates="config", cascade="all, delete-orphan")
    live_market_data = relationship("LiveTradingMarketData", back_populates="config", cascade="all, delete-orphan")
    live_alerts = relationship("LiveTradingAlert", back_populates="config", cascade="all, delete-orphan")
    live_signals = relationship("LiveTradingSignal", back_populates="config", cascade="all, delete-orphan")


class BrokerConfig(Base):
    __tablename__ = "broker_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    broker_type = Column(String(20), nullable=False, unique=True)
    
    api_key = Column(String(200), nullable=True)
    api_secret = Column(String(200), nullable=True)
    access_token = Column(String(500), nullable=True)
    user_id = Column(String(100), nullable=True)
    
    is_active = Column(Boolean, default=False)
    token_expires_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Instrument(Base):
    __tablename__ = "instruments"
    
    id = Column(Integer, primary_key=True, index=True)
    instrument_token = Column(String(50), nullable=False, index=True)
    exchange_token = Column(String(50), nullable=True)
    tradingsymbol = Column(String(100), nullable=False, index=True)
    name = Column(String(200), nullable=True)
    last_price = Column(Float, default=0.0)
    expiry = Column(String(50), nullable=True)
    strike = Column(Float, nullable=True)
    tick_size = Column(Float, nullable=True)
    lot_size = Column(Integer, nullable=True)
    instrument_type = Column(String(20), nullable=True, index=True)
    segment = Column(String(50), nullable=True, index=True)
    exchange = Column(String(20), nullable=False, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class InstrumentDownloadLog(Base):
    """Track instrument downloads to prevent duplicate downloads"""
    __tablename__ = "instrument_download_log"
    
    id = Column(Integer, primary_key=True, index=True)
    download_date = Column(DateTime, nullable=False, index=True)  # Date when instruments were downloaded
    instrument_count = Column(Integer, nullable=False)
    download_type = Column(String(20), nullable=False, default="auto")  # auto or manual
    source = Column(String(50), nullable=False, default="broker_api")  # broker_api, file, etc.
    status = Column(String(20), nullable=False, default="completed")  # completed, failed, partial
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class SchemaMigration(Base):
    """Track applied database schema migrations"""
    __tablename__ = "schema_migrations"
    
    id = Column(Integer, primary_key=True, index=True)
    version = Column(String(50), nullable=False, unique=True, index=True)  # Migration version identifier
    description = Column(Text, nullable=True)  # Description of what the migration does
    applied_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    status = Column(String(20), nullable=False, default="applied")  # applied, failed, rolled_back
    execution_time_ms = Column(Integer, nullable=True)  # Time taken to apply migration in milliseconds
    error_message = Column(Text, nullable=True)


# ============================================================================
# PAPER TRADING MODELS (using unified TradingConfig)
# ============================================================================

class PaperTrade(Base):
    """
    Individual paper trade using unified TradingConfig
    """
    __tablename__ = "paper_trades"
    __table_args__ = (
        Index('idx_paper_trades_config_status', 'config_id', 'status'),
        Index('idx_paper_trades_config_entry_time', 'config_id', 'entry_time'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, ForeignKey("trading_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Trade identification
    date = Column(DateTime, nullable=False, index=True)
    instrument = Column(String(100), nullable=False)
    instrument_token = Column(String(50), nullable=False)
    option_type = Column(String(10), nullable=False, index=True)  # CE or PE
    strike = Column(Float, nullable=False)
    
    # Entry details
    entry_time = Column(DateTime, nullable=False, index=True)
    entry_price = Column(Float, nullable=False)
    entry_trigger = Column(String(20), nullable=False, index=True)  # 7ma, 20ma, lbb
    crossover_value = Column(Float, nullable=True)
    quantity = Column(Integer, nullable=False)
    target_price = Column(Float, nullable=False)
    stoploss_price = Column(Float, nullable=False)
    
    # Exit details
    exit_time = Column(DateTime, nullable=True)
    exit_price = Column(Float, nullable=True)
    exit_reason = Column(String(50), nullable=True, index=True)  # target, stoploss, square_off
    
    # Performance metrics
    pnl = Column(Float, nullable=False, default=0.0)
    pnl_percentage = Column(Float, nullable=False, default=0.0)
    current_price = Column(Float, nullable=True)  # Last known price for open positions
    unrealized_pnl = Column(Float, nullable=False, default=0.0)
    max_loss = Column(Float, nullable=False, default=0.0)
    max_profit = Column(Float, nullable=False, default=0.0)
    
    # Market context at entry
    nifty_price = Column(Float, nullable=True)  # NIFTY price at entry
    cash_after_buy = Column(Float, nullable=True)  # Cash remaining after buy
    major_trend = Column(String(20), nullable=True)  # Major trend at entry
    minor_trend = Column(String(20), nullable=True)  # Minor trend at entry
    major_7ma = Column(Float, nullable=True)  # Major 7MA at entry
    major_20ma = Column(Float, nullable=True)  # Major 20MA at entry
    minor_7ma = Column(Float, nullable=True)  # Minor 7MA at entry
    minor_20ma = Column(Float, nullable=True)  # Minor 20MA at entry
    
    # Price tracking
    highest_price = Column(Float, nullable=True)  # Highest price reached
    lowest_price = Column(Float, nullable=True)  # Lowest price reached
    max_drawdown_pct = Column(Float, nullable=True)  # Max drawdown percentage
    
    # Entry explanation
    entry_comment = Column(Text, nullable=True)  # Human-readable explanation of entry
    
    # Status
    status = Column(String(20), nullable=False, default="open", index=True)  # open, closed
    
    # Relationship
    config = relationship("TradingConfig", back_populates="paper_trades")
    alerts = relationship("PaperTradingAlert", back_populates="trade")


class PaperTradingMarketData(Base):
    """
    Live market data feed for paper trading using unified TradingConfig
    """
    __tablename__ = "paper_trading_market_data"
    
    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, ForeignKey("trading_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Timestamp
    timestamp = Column(DateTime, nullable=False, index=True)
    
    # NIFTY 50 data
    nifty_ltp = Column(Float, nullable=False)
    nifty_change_percent = Column(Float, nullable=True)
    
    # Indicator values for major timeframe
    major_ma7 = Column(Float, nullable=True)
    major_ma20 = Column(Float, nullable=True)
    major_lbb = Column(Float, nullable=True)
    major_ubb = Column(Float, nullable=True)
    major_trend = Column(String(20), nullable=True)
    major_trend_changed_at = Column(DateTime, nullable=True)
    
    # Indicator values for minor timeframe
    minor_ma7 = Column(Float, nullable=True)
    minor_ma20 = Column(Float, nullable=True)
    minor_lbb = Column(Float, nullable=True)
    minor_ubb = Column(Float, nullable=True)
    minor_trend = Column(String(20), nullable=True)
    minor_trend_changed_at = Column(DateTime, nullable=True)
    
    # Active positions LTP (JSON: {instrument_token: ltp})
    positions_ltp = Column(JSON, nullable=True)
    
    # Relationship
    config = relationship("TradingConfig", back_populates="paper_market_data")


class PaperTradingAlert(Base):
    """
    Trade alerts/notifications using unified TradingConfig
    """
    __tablename__ = "paper_trading_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, ForeignKey("trading_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    alert_type = Column(String(20), nullable=False, index=True)  # entry, exit, error, info
    message = Column(Text, nullable=False)
    trade_id = Column(Integer, ForeignKey("paper_trades.id", ondelete="SET NULL"), nullable=True)
    
    # Relationships
    config = relationship("TradingConfig", back_populates="paper_alerts")
    trade = relationship("PaperTrade", back_populates="alerts")


# ========================
# Live Trading Models
# ========================

class LiveTrade(Base):
    """Live trading records using unified TradingConfig - REBUILD V2"""
    __tablename__ = "live_trades"
    __table_args__ = (
        Index('idx_live_trades_config_status', 'config_id', 'status'),
        Index('idx_live_trades_config_entry_time', 'config_id', 'entry_time'),
        Index('idx_live_trades_order_status', 'order_status_buy', 'order_status_sell'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, ForeignKey("trading_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Trade identification
    date = Column(DateTime, nullable=True, index=True)
    instrument = Column(String(100), nullable=False)  # Trading symbol
    instrument_token = Column(String(50), nullable=False, index=True)  # For webhook tracking
    option_type = Column(String(10), nullable=False, index=True)  # CE or PE
    strike = Column(Float, nullable=False)
    contract_expiry = Column(String(20), nullable=True)  # Selected expiry date
    lot_size = Column(Integer, nullable=False, default=50)
    
    # Entry details
    entry_time = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    entry_price = Column(Float, nullable=False)
    entry_trigger = Column(String(20), nullable=False, index=True)  # 7ma, 20ma, lbb
    crossover_value = Column(Float, nullable=True)
    quantity = Column(Integer, nullable=False)
    target_price = Column(Float, nullable=False)
    stoploss_price = Column(Float, nullable=False)
    
    # Broker order tracking - BUY
    broker_order_id_buy = Column(String(100), nullable=True, index=True)  # Buy order ID from broker
    order_status_buy = Column(String(20), nullable=True, index=True)  # PENDING, COMPLETE, REJECTED, CANCELLED
    buy_confirmed_at = Column(DateTime, nullable=True)  # When buy order was confirmed
    buy_rejection_reason = Column(Text, nullable=True)  # If buy order rejected
    
    # Broker order tracking - SELL
    broker_order_id_sell = Column(String(100), nullable=True, index=True)  # Sell order ID from broker
    order_status_sell = Column(String(20), nullable=True, index=True)  # PENDING, COMPLETE, REJECTED, CANCELLED
    sell_confirmed_at = Column(DateTime, nullable=True)  # When sell order was confirmed
    sell_rejection_reason = Column(Text, nullable=True)  # If sell order rejected
    
    # Exit details
    exit_time = Column(DateTime, nullable=True, index=True)
    exit_price = Column(Float, nullable=True)
    exit_reason = Column(String(50), nullable=True, index=True)  # target, stoploss, square_off, manual
    
    # Fund management
    available_funds_before = Column(Float, nullable=True)  # Available funds before trade
    available_funds_after = Column(Float, nullable=True)  # Available funds after trade allocation
    allocated_capital = Column(Float, nullable=True)  # Capital allocated for this position
    
    # P&L tracking
    pnl = Column(Float, default=0.0)
    pnl_percentage = Column(Float, default=0.0)
    current_price = Column(Float, nullable=True)  # Last known price for open positions
    unrealized_pnl = Column(Float, nullable=False, default=0.0)
    max_loss = Column(Float, nullable=False, default=0.0)
    max_profit = Column(Float, nullable=False, default=0.0)
    highest_price = Column(Float, nullable=True)  # Highest price reached
    lowest_price = Column(Float, nullable=True)  # Lowest price reached
    max_drawdown_pct = Column(Float, nullable=True)  # Max drawdown percentage
    
    # Market context at entry
    nifty_price = Column(Float, nullable=True)  # NIFTY price at entry
    major_trend = Column(String(20), nullable=True)  # Major trend at entry
    minor_trend = Column(String(20), nullable=True)  # Minor trend at entry
    major_ma7 = Column(Float, nullable=True)  # Major 7MA at entry
    major_ma20 = Column(Float, nullable=True)  # Major 20MA at entry
    minor_ma7 = Column(Float, nullable=True)  # Minor 7MA at entry
    minor_ma20 = Column(Float, nullable=True)  # Minor 20MA at entry
    
    # Entry explanation
    entry_comment = Column(Text, nullable=True)  # Human-readable explanation
    
    # Status tracking
    status = Column(String(20), default="pending", index=True)  # pending, open, closed, error
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    config = relationship("TradingConfig", back_populates="live_trades")
    alerts = relationship("LiveTradingAlert", back_populates="trade", cascade="all, delete-orphan")


class LiveTradingState(Base):
    """
    Live trading engine state for crash recovery
    Stores the last known state of the trading engine for recovery after restart
    """
    __tablename__ = "live_trading_state"
    
    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, ForeignKey("trading_configs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    # State tracking
    last_active_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    engine_status = Column(String(20), nullable=False, default="stopped")  # running, paused, stopped
    
    # Fund tracking
    available_funds = Column(Float, nullable=False, default=0.0)  # Last known available funds
    allocated_funds = Column(Float, nullable=False, default=0.0)  # Sum of all open position allocations
    open_position_count = Column(Integer, nullable=False, default=0)
    
    # Market state
    last_nifty_ltp = Column(Float, nullable=True)
    major_trend = Column(String(20), nullable=True)
    minor_trend = Column(String(20), nullable=True)
    major_trend_changed_at = Column(DateTime, nullable=True)
    minor_trend_changed_at = Column(DateTime, nullable=True)
    
    # Full state snapshot (JSON)
    state_snapshot = Column(JSON, nullable=True)  # Complete state backup
    # Example: {
    #     'subscribed_instruments': ['256265', '12345'],
    #     'active_positions': {'CE_7ma': 1, 'PE_20ma': 2},
    #     'candle_buffer_sizes': {'major': 50, 'minor': 200},
    #     'last_signal_time': '2025-11-02T15:20:00',
    #     'square_off_pending': false
    # }
    
    # Recovery metadata
    recovery_count = Column(Integer, nullable=False, default=0)  # How many times recovered
    last_recovery_at = Column(DateTime, nullable=True)  # Last recovery timestamp
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LiveTradingMarketData(Base):
    """Live trading market data snapshots using unified TradingConfig"""
    __tablename__ = "live_trading_market_data"
    
    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, ForeignKey("trading_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Timestamp
    timestamp = Column(DateTime, nullable=False, index=True)
    
    # NIFTY 50 data
    nifty_ltp = Column(Float, nullable=False)
    
    # Indicator values for major timeframe
    major_ma7 = Column(Float, nullable=True)
    major_ma20 = Column(Float, nullable=True)
    major_lbb = Column(Float, nullable=True)
    major_ubb = Column(Float, nullable=True)
    major_trend = Column(String(20), nullable=True)
    
    # Indicator values for minor timeframe
    minor_ma7 = Column(Float, nullable=True)
    minor_ma20 = Column(Float, nullable=True)
    minor_lbb = Column(Float, nullable=True)
    minor_ubb = Column(Float, nullable=True)
    minor_trend = Column(String(20), nullable=True)
    
    # Active positions LTP (JSON: {instrument_token: ltp})
    positions_ltp = Column(JSON, nullable=True)
    
    # NOTE: Model matches database - no 'symbol' column
    
    # Relationships
    config = relationship("TradingConfig", back_populates="live_market_data")


class LiveTradingAlert(Base):
    """Live trading alerts and notifications using unified TradingConfig"""
    __tablename__ = "live_trading_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, ForeignKey("trading_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    alert_type = Column(String(20), nullable=False, index=True)  # entry, exit, error, info
    category = Column(String(20), nullable=True)  # Additional categorization
    message = Column(Text, nullable=False)
    trade_id = Column(Integer, ForeignKey("live_trades.id", ondelete="SET NULL"), nullable=True)
    alert_metadata = Column(JSON, nullable=True)  # Additional alert data
    
    # NOTE: Model now matches actual database schema
    # Added: category, alert_metadata
    
    # Relationships
    config = relationship("TradingConfig", back_populates="live_alerts")
    trade = relationship("LiveTrade", back_populates="alerts")


class LiveTradingSignal(Base):
    """Live trading signals and analysis using unified TradingConfig"""
    __tablename__ = "live_trading_signals"
    
    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, ForeignKey("trading_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Timestamp
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Market data at signal time - using actual database columns
    nifty_50_value = Column(Float, nullable=False)
    instrument = Column(String(100), nullable=True)  # Option contract symbol
    instrument_price = Column(Float, nullable=True)  # LTP of instrument
    
    # Market state trends
    major_trend = Column(String(20), nullable=False)
    minor_trend = Column(String(20), nullable=False)
    
    # Major timeframe indicators
    major_ma7 = Column(Float, nullable=True)
    major_ma20 = Column(Float, nullable=True)
    major_lbb = Column(Float, nullable=True)
    major_ubb = Column(Float, nullable=True)
    
    # Minor timeframe indicators
    minor_ma7 = Column(Float, nullable=True)
    minor_ma20 = Column(Float, nullable=True)
    minor_lbb = Column(Float, nullable=True)
    minor_ubb = Column(Float, nullable=True)
    
    # Signal details
    signal_type = Column(String(20), nullable=True)  # BUY or SELL
    trigger = Column(String(20), nullable=True)  # Signal trigger type
    decision_reason = Column(Text, nullable=False)  # Why this signal was generated
    
    # NOTE: Model now matches actual database schema (19 columns)
    # Database has individual indicator columns, not JSON fields
    
    # Relationships
    config = relationship("TradingConfig", back_populates="live_signals")






