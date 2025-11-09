"""
JSON-based Data Models - Database-Free
=====================================

Pure Python classes for configuration data.
No SQLAlchemy dependencies - just simple data containers.
"""

from typing import Dict, Any, Optional
from datetime import datetime


class TradingConfig:
    """
    Trading configuration loaded from JSON.

    Replaces SQLAlchemy TradingConfig model with pure Python class.
    """

    def __init__(self, data: Dict[str, Any]):
        """
        Initialize from JSON data.

        Args:
            data: Dictionary containing configuration values
        """
        # Basic info
        self.name = data.get('name', 'Live Trading Bot')
        self.description = data.get('description', '')
        self.is_active = data.get('is_active', True)

        # Capital
        self.initial_capital = data.get('initial_capital', 100000.0)
        self.capital_allocation_pct = data.get('capital_allocation_pct', 16.0)

        # Trading controls
        self.suspend_ce = data.get('suspend_ce', False)
        self.suspend_pe = data.get('suspend_pe', False)
        self.status = data.get('status', 'stopped')

        # Historical replay (for paper trading)
        self.replay_speed = data.get('replay_speed', 1.0)

        # MA settings
        self.ma_short_period = data.get('ma_short_period', 7)
        self.ma_long_period = data.get('ma_long_period', 20)

        # Timeframes
        self.major_timeframe = data.get('major_timeframe', '15min')
        self.minor_timeframe = data.get('minor_timeframe', '1min')

        # 7MA settings
        self.buy_7ma_enabled = data.get('buy_7ma_enabled', True)
        self.buy_7ma_percentage_below = data.get('buy_7ma_percentage_below', 0.0)
        self.buy_7ma_target_percentage = data.get('buy_7ma_target_percentage', 2.5)
        self.buy_7ma_stoploss_percentage = data.get('buy_7ma_stoploss_percentage', 99.0)

        # 20MA settings
        self.buy_20ma_enabled = data.get('buy_20ma_enabled', True)
        self.buy_20ma_percentage_below = data.get('buy_20ma_percentage_below', 0.0)
        self.buy_20ma_target_percentage = data.get('buy_20ma_target_percentage', 2.5)
        self.buy_20ma_stoploss_percentage = data.get('buy_20ma_stoploss_percentage', 99.0)

        # LBB settings
        self.buy_lbb_enabled = data.get('buy_lbb_enabled', True)
        self.buy_lbb_percentage_below = data.get('buy_lbb_percentage_below', 0.0)
        self.buy_lbb_target_percentage = data.get('buy_lbb_target_percentage', 2.5)
        self.buy_lbb_stoploss_percentage = data.get('buy_lbb_stoploss_percentage', 99.0)

        # Position sizing
        self.lot_size = data.get('lot_size', 75)

        # Strike selection
        self.min_strike_gap = data.get('min_strike_gap', 100)
        self.strike_round_to = data.get('strike_round_to', 100)

        # Day end square off
        self.square_off_time = data.get('square_off_time', '15:20')
        self.square_off_enabled = data.get('square_off_enabled', True)

        # Contract selection
        self.exclude_expiry_day_contracts = data.get('exclude_expiry_day_contracts', True)

        # Signal settings
        self.reverse_signals = data.get('reverse_signals', False)

        # NIFTY options settings
        self.lots_per_trade = data.get('lots_per_trade', 1)
        self.tick_size = data.get('tick_size', 0.05)
        self.product_type = data.get('product_type', 'NRML')

        # Expiry selection
        self.expiry_offset_days = data.get('expiry_offset_days', 0)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for JSON serialization.

        Returns:
            Dict representation of config
        """
        return {
            'name': self.name,
            'description': self.description,
            'is_active': self.is_active,
            'capital_allocation_pct': self.capital_allocation_pct,
            'initial_capital': self.initial_capital,
            'suspend_ce': self.suspend_ce,
            'suspend_pe': self.suspend_pe,
            'status': self.status,
            'replay_speed': self.replay_speed,
            'ma_short_period': self.ma_short_period,
            'ma_long_period': self.ma_long_period,
            'major_timeframe': self.major_timeframe,
            'minor_timeframe': self.minor_timeframe,
            'buy_7ma_enabled': self.buy_7ma_enabled,
            'buy_7ma_percentage_below': self.buy_7ma_percentage_below,
            'buy_7ma_target_percentage': self.buy_7ma_target_percentage,
            'buy_7ma_stoploss_percentage': self.buy_7ma_stoploss_percentage,
            'buy_20ma_enabled': self.buy_20ma_enabled,
            'buy_20ma_percentage_below': self.buy_20ma_percentage_below,
            'buy_20ma_target_percentage': self.buy_20ma_target_percentage,
            'buy_20ma_stoploss_percentage': self.buy_20ma_stoploss_percentage,
            'buy_lbb_enabled': self.buy_lbb_enabled,
            'buy_lbb_percentage_below': self.buy_lbb_percentage_below,
            'buy_lbb_target_percentage': self.buy_lbb_target_percentage,
            'buy_lbb_stoploss_percentage': self.buy_lbb_stoploss_percentage,
            'lot_size': self.lot_size,
            'min_strike_gap': self.min_strike_gap,
            'strike_round_to': self.strike_round_to,
            'square_off_time': self.square_off_time,
            'square_off_enabled': self.square_off_enabled,
            'exclude_expiry_day_contracts': self.exclude_expiry_day_contracts,
            'reverse_signals': self.reverse_signals,
            'lots_per_trade': self.lots_per_trade,
            'tick_size': self.tick_size,
            'product_type': self.product_type,
            'expiry_offset_days': self.expiry_offset_days
        }


class Instrument:
    """
    Instrument data loaded from JSON.

    Replaces SQLAlchemy Instrument model with pure Python class.
    """

    def __init__(self, data: Dict[str, Any]):
        """
        Initialize from JSON data.

        Args:
            data: Dictionary containing instrument values
        """
        self.instrument_token = data.get('instrument_token')
        self.exchange_token = data.get('exchange_token')
        self.tradingsymbol = data.get('tradingsymbol')
        self.name = data.get('name')
        self.last_price = data.get('last_price', 0.0)
        self.expiry = data.get('expiry')
        self.strike = data.get('strike')
        self.tick_size = data.get('tick_size', 0.05)
        self.lot_size = data.get('lot_size', 50)
        self.instrument_type = data.get('instrument_type')
        self.segment = data.get('segment')
        self.exchange = data.get('exchange')

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for JSON serialization.

        Returns:
            Dict representation of instrument
        """
        return {
            'instrument_token': self.instrument_token,
            'exchange_token': self.exchange_token,
            'tradingsymbol': self.tradingsymbol,
            'name': self.name,
            'last_price': self.last_price,
            'expiry': self.expiry,
            'strike': self.strike,
            'tick_size': self.tick_size,
            'lot_size': self.lot_size,
            'instrument_type': self.instrument_type,
            'segment': self.segment,
            'exchange': self.exchange
        }


class BrokerConfig:
    """
    Broker API configuration loaded from JSON.

    Replaces SQLAlchemy BrokerConfig model with pure Python class.
    """

    def __init__(self, data: Dict[str, Any]):
        """
        Initialize from JSON data.

        Args:
            data: Dictionary containing broker config values
        """
        self.broker_type = data.get('broker_type', 'zerodha')
        self.api_key = data.get('api_key')
        self.api_secret = data.get('api_secret')
        self.access_token = data.get('access_token')
        self.user_id = data.get('user_id')
        self.is_active = data.get('is_active', False)
        self.token_expires_at = data.get('token_expires_at')

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for JSON serialization.

        Returns:
            Dict representation of broker config
        """
        return {
            'broker_type': self.broker_type,
            'api_key': self.api_key,
            'api_secret': self.api_secret,
            'access_token': self.access_token,
            'user_id': self.user_id,
            'is_active': self.is_active,
            'token_expires_at': self.token_expires_at
        }


class Position:
    """
    In-memory position tracking.

    Replaces database-stored positions with pure Python objects.
    """

    def __init__(self,
                 symbol: str,
                 quantity: int,
                 entry_price: float,
                 target_price: Optional[float] = None,
                 stoploss_price: Optional[float] = None):
        """
        Initialize position.

        Args:
            symbol: Trading symbol
            quantity: Position quantity
            entry_price: Entry price
            target_price: Target price for bracket orders
            stoploss_price: Stoploss price
        """
        self.symbol = symbol
        self.quantity = quantity
        self.entry_price = entry_price
        self.target_price = target_price
        self.stoploss_price = stoploss_price
        self.current_price = entry_price
        self.status = 'pending'  # pending, open, closed
        self.entry_time = datetime.now()
        self.exit_time = None
        self.exit_price = None
        self.pnl = 0.0
        self.instrument_token = None
        self.order_id_buy = None
        self.order_id_sell = None

    def update_price(self, price: float):
        """
        Update current price and calculate unrealized P&L.

        Args:
            price: Current market price
        """
        self.current_price = price
        if self.status == 'open':
            self.pnl = (price - self.entry_price) * self.quantity

    def close(self, exit_price: float, exit_reason: str = 'manual'):
        """
        Close position.

        Args:
            exit_price: Exit price
            exit_reason: Reason for closing
        """
        self.exit_price = exit_price
        self.exit_time = datetime.now()
        self.status = 'closed'
        self.pnl = (exit_price - self.entry_price) * self.quantity

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary.

        Returns:
            Dict representation of position
        """
        return {
            'symbol': self.symbol,
            'quantity': self.quantity,
            'entry_price': self.entry_price,
            'target_price': self.target_price,
            'stoploss_price': self.stoploss_price,
            'current_price': self.current_price,
            'status': self.status,
            'entry_time': self.entry_time.isoformat() if self.entry_time else None,
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'exit_price': self.exit_price,
            'pnl': self.pnl,
            'instrument_token': self.instrument_token,
            'order_id_buy': self.order_id_buy,
            'order_id_sell': self.order_id_sell
        }
