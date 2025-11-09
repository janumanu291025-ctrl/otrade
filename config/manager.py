"""
JSON-based Configuration Manager - HFT Optimized
===============================================

Uses orjson for 10x faster JSON processing than standard library.
Provides persistent configuration storage without database dependency.
"""

import orjson
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone


class ConfigManager:
    """
    High-performance JSON configuration manager using orjson.

    Features:
    - 10x faster than standard json library
    - Automatic config file creation with defaults
    - Type-safe configuration loading
    - Error handling for missing/corrupted files
    """

    def __init__(self, config_dir: str = "config"):
        """
        Initialize configuration manager.

        Args:
            config_dir: Directory to store config files (default: 'config')
        """
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)

    def load_trading_config(self) -> Dict[str, Any]:
        """
        Load trading configuration from JSON file.

        Returns:
            Dict containing trading configuration
        """
        config_file = self.config_dir / "trading_config.json"

        try:
            if config_file.exists():
                # Use orjson for 10x faster loading
                with open(config_file, 'rb') as f:
                    return orjson.loads(f.read())
            else:
                # Create default config
                default_config = self._get_default_trading_config()
                self.save_trading_config(default_config)
                return default_config

        except Exception as e:
            print(f"Error loading trading config: {e}")
            return self._get_default_trading_config()

    def load_instruments(self) -> Dict[str, Dict]:
        """
        Load instruments data from JSON file.

        Returns:
            Dict mapping instrument_token to instrument data
        """
        instruments_file = self.config_dir / "instruments.json"

        try:
            if instruments_file.exists():
                with open(instruments_file, 'rb') as f:
                    data = orjson.loads(f.read())
                    instruments = data.get('instruments', [])

                    # Create token -> instrument mapping for O(1) lookups
                    return {inst['instrument_token']: inst for inst in instruments}
            else:
                # Return empty dict - will be populated by broker API
                return {}

        except Exception as e:
            print(f"Error loading instruments: {e}")
            return {}

    def save_trading_config(self, config: Dict[str, Any]) -> bool:
        """
        Save trading configuration to JSON file.

        Args:
            config: Configuration dictionary to save

        Returns:
            bool: True if saved successfully
        """
        try:
            config_file = self.config_dir / "trading_config.json"

            # Use orjson with pretty printing
            with open(config_file, 'wb') as f:
                f.write(orjson.dumps(config, option=orjson.OPT_INDENT_2))

            return True

        except Exception as e:
            print(f"Error saving trading config: {e}")
            return False

    def save_instruments(self, instruments: Dict[str, Dict]) -> bool:
        """
        Save instruments data to JSON file.

        Args:
            instruments: Dict mapping token to instrument data

        Returns:
            bool: True if saved successfully
        """
        try:
            instruments_file = self.config_dir / "instruments.json"

            # Convert to list format for JSON storage
            data = {
                'instruments': list(instruments.values()),
                'last_updated': datetime.now(timezone.utc).isoformat(),
                'download_type': 'api'
            }

            with open(instruments_file, 'wb') as f:
                f.write(orjson.dumps(data, option=orjson.OPT_INDENT_2))

            return True

        except Exception as e:
            print(f"Error saving instruments: {e}")
            return False

    def save_broker_config(self, config: Dict[str, Any]) -> bool:
        """
        Save broker configuration to JSON file.
        
        DEPRECATED: Broker configuration should be stored in .env file, not JSON.
        Use backend.config.settings instead.

        Args:
            config: Broker configuration dictionary

        Returns:
            bool: True if saved successfully
        """
        try:
            broker_file = self.config_dir / "broker_config.json"

            with open(broker_file, 'wb') as f:
                f.write(orjson.dumps(config, option=orjson.OPT_INDENT_2))

            return True

        except Exception as e:
            print(f"Error saving broker config: {e}")
            return False

    def _get_default_trading_config(self) -> Dict[str, Any]:
        """
        Get default trading configuration.

        Returns:
            Dict with default trading parameters
        """
        return {
            "name": "Live Trading Bot",
            "description": "HFT Bracket Order System",
            "is_active": True,
            "capital_allocation_pct": 16.0,
            "initial_capital": 100000.0,
            "suspend_ce": False,
            "suspend_pe": False,
            "status": "stopped",
            "replay_speed": 1.0,
            "ma_short_period": 7,
            "ma_long_period": 20,
            "major_timeframe": "15min",
            "minor_timeframe": "1min",
            "buy_7ma_enabled": True,
            "buy_7ma_percentage_below": 0.5,
            "buy_7ma_target_percentage": 2.5,
            "buy_7ma_stoploss_percentage": 99.0,
            "buy_20ma_enabled": True,
            "buy_20ma_percentage_below": 0.0,
            "buy_20ma_target_percentage": 2.5,
            "buy_20ma_stoploss_percentage": 99.0,
            "buy_lbb_enabled": True,
            "buy_lbb_percentage_below": 0.0,
            "buy_lbb_target_percentage": 2.5,
            "buy_lbb_stoploss_percentage": 99.0,
            "capital_allocation_pct": 16.0,
            "lot_size": 75,
            "min_strike_gap": 100,
            "strike_round_to": 100,
            "square_off_time": "15:20",
            "square_off_enabled": True,
            "exclude_expiry_day_contracts": True,
            "reverse_signals": False,
            "lots_per_trade": 1,
            "tick_size": 0.05,
            "product_type": "NRML",
            "expiry_offset_days": 0
        }

    def _get_template_broker_config(self) -> Dict[str, Any]:
        """
        Get template broker configuration.
        
        DEPRECATED: Broker configuration should be stored in .env file, not JSON.

        Returns:
            Dict with broker config template
        """
        return {
            "broker_type": "kite",  # Use BROKER_TYPE from .env
            "api_key": "your_api_key_here",  # Use KITE_API_KEY from .env
            "api_secret": "your_api_secret_here",  # Use KITE_API_SECRET from .env
            "access_token": "your_access_token_here",  # Use KITE_ACCESS_TOKEN from .env
            "user_id": "your_user_id_here",  # Use KITE_USER_ID from .env
            "is_active": False,
            "token_expires_at": None
        }
