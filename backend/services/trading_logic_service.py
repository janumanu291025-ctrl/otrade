"""
Unified Trading Logic Service
===============================

This service consolidates all common trading logic used across:
- Backtesting (historical simulation)
- Paper Trading (live/historical with virtual money)
- Live Trading (real-time execution with broker)

Key Features:
- Indicator calculation (MA, Bollinger Bands)
- Crossover detection
- Trend determination
- Signal generation with unified decision matrix
- Contract selection helpers
- Position sizing calculation

All modules use this service to ensure consistent trading behavior.
"""
import logging
from typing import Dict, List, Optional, Tuple, Union
from collections import deque
import pandas as pd
import numpy as np
from numba import jit
from datetime import datetime

logger = logging.getLogger(__name__)


# ===== OPTIMIZED NUMBA FUNCTIONS =====

@jit(nopython=True)
def calculate_sma_numba(data: np.ndarray, period: int) -> np.ndarray:
    """Calculate Simple Moving Average using numba for performance"""
    result = np.empty_like(data)
    result[:period-1] = np.nan
    
    for i in range(period-1, len(data)):
        result[i] = np.mean(data[i-period+1:i+1])
    
    return result


@jit(nopython=True)
def calculate_bollinger_bands_numba(data: np.ndarray, period: int, std_dev: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Calculate Bollinger Bands using numba for performance"""
    sma = calculate_sma_numba(data, period)
    upper = np.empty_like(data)
    lower = np.empty_like(data)
    
    upper[:period-1] = np.nan
    lower[:period-1] = np.nan
    
    for i in range(period-1, len(data)):
        std = np.std(data[i-period+1:i+1])
        upper[i] = sma[i] + (std_dev * std)
        lower[i] = sma[i] - (std_dev * std)
    
    return sma, upper, lower


class TradingLogicService:
    """
    Unified trading logic service used by all trading modules.
    
    This service encapsulates the core trading strategy logic:
    1. Technical indicator calculations
    2. Trend determination
    3. Crossover detection
    4. Signal generation with decision matrix
    5. Position sizing and contract selection helpers
    """
    
    def __init__(self, ma_short_period: int = 7, ma_long_period: int = 20):
        """
        Initialize trading logic service
        
        Args:
            ma_short_period: Short moving average period (default 7)
            ma_long_period: Long moving average period (default 20)
        """
        self.ma_short_period = ma_short_period
        self.ma_long_period = ma_long_period
        self.bb_period = ma_long_period  # Use long MA period for BB
        self.bb_std = 2.0
    
    # ===== INDICATOR CALCULATION =====
    
    def calculate_indicators_from_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators from pandas DataFrame (for backtest)
        
        Args:
            df: DataFrame with OHLC data (must have 'close' column)
        
        Returns:
            DataFrame with added indicator columns: ma7, ma20, bb_lower, bb_upper
        """
        if df.empty or len(df) < self.ma_long_period:
            return df
        
        # Calculate Moving Averages
        df['ma7'] = df['close'].rolling(window=self.ma_short_period).mean()
        df['ma20'] = df['close'].rolling(window=self.ma_long_period).mean()
        
        # Calculate Bollinger Bands
        df['bb_middle'] = df['close'].rolling(window=self.bb_period).mean()
        bb_std_dev = df['close'].rolling(window=self.bb_period).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std_dev * self.bb_std)
        df['bb_lower'] = df['bb_middle'] - (bb_std_dev * self.bb_std)
        
        return df
    
    def calculate_indicators_from_deque(self, candles: deque) -> Dict:
        """
        Calculate indicators from deque of candles (for paper trading)
        
        Args:
            candles: Deque of candle dicts with keys: timestamp, open, high, low, close
        
        Returns:
            Dict with keys: ma7, ma20, lbb, ubb, trend
        """
        if len(candles) < self.ma_long_period:
            return {
                'ma7': None, 'ma20': None,
                'lbb': None, 'ubb': None,
                'trend': 'neutral'
            }
        
        # Convert to DataFrame for calculation
        df = pd.DataFrame(list(candles))
        
        # Calculate MAs
        df['ma7'] = df['close'].rolling(window=self.ma_short_period).mean()
        df['ma20'] = df['close'].rolling(window=self.ma_long_period).mean()
        
        # Calculate Bollinger Bands
        rolling_std = df['close'].rolling(window=self.bb_period).std()
        df['lbb'] = df['ma20'] - (self.bb_std * rolling_std)
        df['ubb'] = df['ma20'] + (self.bb_std * rolling_std)
        
        # Get last values
        last = df.iloc[-1]
        
        # Determine trend
        trend = self.determine_trend_from_values(
            float(last['ma7']) if pd.notna(last['ma7']) else None,
            float(last['ma20']) if pd.notna(last['ma20']) else None
        )
        
        return {
            'ma7': float(last['ma7']) if pd.notna(last['ma7']) else None,
            'ma20': float(last['ma20']) if pd.notna(last['ma20']) else None,
            'lbb': float(last['lbb']) if pd.notna(last['lbb']) else None,
            'ubb': float(last['ubb']) if pd.notna(last['ubb']) else None,
            'trend': trend
        }
    
    def calculate_indicators_from_array(self, close_prices: np.ndarray) -> Dict:
        """
        Calculate indicators from numpy array (for live trading with numba optimization)
        
        Args:
            close_prices: Numpy array of close prices
        
        Returns:
            Dict with keys: ma7, ma20, lbb, ubb, trend, close
        """
        if len(close_prices) < self.ma_long_period:
            return {
                'close': None, 'ma7': None, 'ma20': None,
                'lbb': None, 'ubb': None, 'trend': 'neutral'
            }
        
        # Calculate using optimized numba functions
        ma7 = calculate_sma_numba(close_prices, self.ma_short_period)
        ma20 = calculate_sma_numba(close_prices, self.ma_long_period)
        bb_sma, ubb, lbb = calculate_bollinger_bands_numba(close_prices, self.bb_period, self.bb_std)
        
        # Get latest values
        latest_idx = -1
        latest_close = close_prices[latest_idx]
        
        indicators = {
            'close': latest_close,
            'ma7': ma7[latest_idx] if not np.isnan(ma7[latest_idx]) else None,
            'ma20': ma20[latest_idx] if not np.isnan(ma20[latest_idx]) else None,
            'lbb': lbb[latest_idx] if not np.isnan(lbb[latest_idx]) else None,
            'ubb': ubb[latest_idx] if not np.isnan(ubb[latest_idx]) else None,
            'trend': self.determine_trend_from_values(
                ma7[latest_idx] if not np.isnan(ma7[latest_idx]) else None,
                ma20[latest_idx] if not np.isnan(ma20[latest_idx]) else None
            )
        }
        
        return indicators
    
    # ===== TREND DETERMINATION =====
    
    def determine_trend_from_values(self, ma7: Optional[float], ma20: Optional[float]) -> str:
        """
        Determine trend from MA values
        
        Args:
            ma7: 7-period moving average value
            ma20: 20-period moving average value
        
        Returns:
            'uptrend', 'downtrend', or 'neutral'
        """
        if ma7 is None or ma20 is None:
            return 'neutral'
        
        if np.isnan(ma7) or np.isnan(ma20):
            return 'neutral'
        
        if ma7 > ma20:
            return 'uptrend'
        elif ma7 < ma20:
            return 'downtrend'
        else:
            return 'neutral'
    
    def determine_trend_from_df(self, df: pd.DataFrame) -> str:
        """
        Determine trend from DataFrame (uses last row)
        
        Args:
            df: DataFrame with ma7 and ma20 columns
        
        Returns:
            'uptrend', 'downtrend', or 'neutral'
        """
        if df.empty or len(df) < 1:
            return 'neutral'
        
        last_row = df.iloc[-1]
        
        if pd.isna(last_row.get('ma7')) or pd.isna(last_row.get('ma20')):
            return 'neutral'
        
        return self.determine_trend_from_values(
            float(last_row['ma7']),
            float(last_row['ma20'])
        )
    
    # ===== CROSSOVER DETECTION =====
    
    def detect_crossovers_in_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect price crossovers with MA and BB levels in DataFrame
        
        Adds boolean columns for each crossover type:
        - cross_below_ma7, cross_above_ma7
        - cross_below_ma20, cross_above_ma20
        - cross_below_lbb
        - cross_above_ubb
        
        Args:
            df: DataFrame with OHLC and indicator data
        
        Returns:
            DataFrame with crossover columns added
        """
        if df.empty or len(df) < 2:
            return df
        
        # Initialize all crossover columns to False
        df['cross_below_ma7'] = False
        df['cross_below_ma20'] = False
        df['cross_below_lbb'] = False
        df['cross_above_ma7'] = False
        df['cross_above_ma20'] = False
        df['cross_above_ubb'] = False
        
        # Detect crossovers (compare current with previous candle)
        for i in range(1, len(df)):
            prev = df.iloc[i-1]
            curr = df.iloc[i]
            
            # Skip if any data is NaN
            if pd.isna(prev['close']) or pd.isna(curr['close']):
                continue
            if pd.isna(curr['low']) or pd.isna(curr['high']):
                continue
            
            # MA7 crossovers - use LOW for cross below, HIGH for cross above
            if not pd.isna(prev.get('ma7')) and not pd.isna(curr.get('ma7')):
                if prev['close'] >= prev['ma7'] and curr['low'] < curr['ma7']:
                    df.at[df.index[i], 'cross_below_ma7'] = True
                elif prev['close'] <= prev['ma7'] and curr['high'] > curr['ma7']:
                    df.at[df.index[i], 'cross_above_ma7'] = True
            
            # MA20 crossovers
            if not pd.isna(prev.get('ma20')) and not pd.isna(curr.get('ma20')):
                if prev['close'] >= prev['ma20'] and curr['low'] < curr['ma20']:
                    df.at[df.index[i], 'cross_below_ma20'] = True
                elif prev['close'] <= prev['ma20'] and curr['high'] > curr['ma20']:
                    df.at[df.index[i], 'cross_above_ma20'] = True
            
            # LBB crossovers - only cross below matters
            if not pd.isna(prev.get('bb_lower')) and not pd.isna(curr.get('bb_lower')):
                if prev['close'] >= prev['bb_lower'] and curr['low'] < curr['bb_lower']:
                    df.at[df.index[i], 'cross_below_lbb'] = True
            
            # UBB crossovers - only cross above matters
            if not pd.isna(prev.get('bb_upper')) and not pd.isna(curr.get('bb_upper')):
                if prev['close'] <= prev['bb_upper'] and curr['high'] > curr['bb_upper']:
                    df.at[df.index[i], 'cross_above_ubb'] = True
        
        return df
    
    def detect_crossovers_from_candles(self, prev_candle: Dict, curr_candle: Dict, 
                                      indicators: Dict) -> List[Dict]:
        """
        Detect crossovers from two consecutive candles (for real-time trading)
        
        Args:
            prev_candle: Previous candle dict with keys: close, low, high
            curr_candle: Current candle dict with keys: close, low, high
            indicators: Dict with indicator values: ma7, ma20, lbb, ubb
        
        Returns:
            List of crossover dicts with keys: type, trigger, direction, indicator_value
        """
        crossovers = []
        
        # MA7 crossovers
        if indicators.get('ma7') is not None:
            if prev_candle['close'] >= indicators['ma7'] and curr_candle['low'] < indicators['ma7']:
                crossovers.append({
                    'type': 'cross_below_ma7',
                    'trigger': '7ma',
                    'direction': 'below',
                    'indicator_value': indicators['ma7']
                })
            elif prev_candle['close'] <= indicators['ma7'] and curr_candle['high'] > indicators['ma7']:
                crossovers.append({
                    'type': 'cross_above_ma7',
                    'trigger': '7ma',
                    'direction': 'above',
                    'indicator_value': indicators['ma7']
                })
        
        # MA20 crossovers
        if indicators.get('ma20') is not None:
            if prev_candle['close'] >= indicators['ma20'] and curr_candle['low'] < indicators['ma20']:
                crossovers.append({
                    'type': 'cross_below_ma20',
                    'trigger': '20ma',
                    'direction': 'below',
                    'indicator_value': indicators['ma20']
                })
            elif prev_candle['close'] <= indicators['ma20'] and curr_candle['high'] > indicators['ma20']:
                crossovers.append({
                    'type': 'cross_above_ma20',
                    'trigger': '20ma',
                    'direction': 'above',
                    'indicator_value': indicators['ma20']
                })
        
        # LBB crossovers - only below
        if indicators.get('lbb') is not None:
            if prev_candle['close'] >= indicators['lbb'] and curr_candle['low'] < indicators['lbb']:
                crossovers.append({
                    'type': 'cross_below_lbb',
                    'trigger': 'lbb',
                    'direction': 'below',
                    'indicator_value': indicators['lbb']
                })
        
        # UBB crossovers - only above
        if indicators.get('ubb') is not None:
            if prev_candle['close'] <= indicators['ubb'] and curr_candle['high'] > indicators['ubb']:
                crossovers.append({
                    'type': 'cross_above_ubb',
                    'trigger': 'ubb',
                    'direction': 'above',
                    'indicator_value': indicators['ubb']
                })
        
        return crossovers
    
    # ===== TRADE DECISION MATRIX (CORE STRATEGY LOGIC) =====
    
    def evaluate_trade_decision(self, major_trend: str, minor_trend: str,
                                option_type: str, trigger: str,
                                crossover_direction: str,
                                reverse_signals: bool = False) -> Tuple[bool, str]:
        """
        THE CORE TRADING DECISION LOGIC - applies to all modules
        
        Decision Matrix:
        ┌─────────────┬─────────────┬────────────────────────────────┬────────────────────────────────┐
        │ Major Trend │ Minor Trend │ CE (Call) Decision             │ PE (Put) Decision              │
        ├─────────────┼─────────────┼────────────────────────────────┼────────────────────────────────┤
        │ UP          │ UP          │ BUY on crossover BELOW         │ SKIP                           │
        │             │             │ (7MA/20MA/LBB support)         │                                │
        ├─────────────┼─────────────┼────────────────────────────────┼────────────────────────────────┤
        │ UP          │ DOWN        │ SKIP                           │ BUY on crossover ABOVE         │
        │             │             │                                │ (7MA/20MA/UBB resistance)      │
        ├─────────────┼─────────────┼────────────────────────────────┼────────────────────────────────┤
        │ DOWN        │ DOWN        │ SKIP                           │ BUY on crossover ABOVE         │
        │             │             │                                │ (7MA/20MA/UBB resistance)      │
        ├─────────────┼─────────────┼────────────────────────────────┼────────────────────────────────┤
        │ DOWN        │ UP          │ BUY on crossover BELOW         │ SKIP                           │
        │             │             │ (7MA/20MA/LBB support)         │                                │
        └─────────────┴─────────────┴────────────────────────────────┴────────────────────────────────┘
        
        Args:
            major_trend: Major timeframe trend ('uptrend', 'downtrend', 'neutral')
            minor_trend: Minor timeframe trend ('uptrend', 'downtrend', 'neutral')
            option_type: Option type ('CE' or 'PE')
            trigger: Trigger type ('7ma', '20ma', 'lbb', 'ubb')
            crossover_direction: Direction of crossover ('below' or 'above')
            reverse_signals: If True, reverse CE/PE decisions
        
        Returns:
            Tuple of (should_trade: bool, reason: str)
        """
        # Skip if neutral trends
        if major_trend == 'neutral' or minor_trend == 'neutral':
            return False, f"Neutral trend: Major={major_trend}, Minor={minor_trend}"
        
        # Apply signal reversal if enabled
        if reverse_signals:
            option_type = 'PE' if option_type == 'CE' else 'CE'
        
        # Decision logic based on trend combinations
        if major_trend == 'uptrend' and minor_trend == 'uptrend':
            if option_type == 'CE':
                # CE: Buy on crossover below (support)
                if trigger in ['7ma', '20ma'] and crossover_direction == 'below':
                    return True, "Major UP + Minor UP: CE on 7MA/20MA cross below (support)"
                elif trigger == 'lbb' and crossover_direction == 'below':
                    return True, "Major UP + Minor UP: CE on LBB cross below (support)"
                else:
                    return False, f"Major UP + Minor UP: CE not allowed on {trigger} cross {crossover_direction}"
            else:  # PE
                return False, "Major UP + Minor UP: PE not allowed"
        
        elif major_trend == 'uptrend' and minor_trend == 'downtrend':
            if option_type == 'PE':
                # PE: Buy on crossover above (resistance)
                if trigger in ['7ma', '20ma'] and crossover_direction == 'above':
                    return True, "Major UP + Minor DOWN: PE on 7MA/20MA cross above (resistance)"
                else:
                    return False, f"Major UP + Minor DOWN: PE not allowed on {trigger} cross {crossover_direction}"
            else:  # CE
                return False, "Major UP + Minor DOWN: CE not allowed"
        
        elif major_trend == 'downtrend' and minor_trend == 'downtrend':
            if option_type == 'PE':
                # PE: Buy on crossover above (resistance)
                if trigger in ['7ma', '20ma'] and crossover_direction == 'above':
                    return True, "Major DOWN + Minor DOWN: PE on 7MA/20MA cross above (resistance)"
                else:
                    return False, f"Major DOWN + Minor DOWN: PE not allowed on {trigger} cross {crossover_direction}"
            else:  # CE
                return False, "Major DOWN + Minor DOWN: CE not allowed"
        
        elif major_trend == 'downtrend' and minor_trend == 'uptrend':
            if option_type == 'CE':
                # CE: Buy on crossover below (support)
                if trigger in ['7ma', '20ma'] and crossover_direction == 'below':
                    return True, "Major DOWN + Minor UP: CE on 7MA/20MA cross below (support)"
                elif trigger == 'lbb' and crossover_direction == 'below':
                    return True, "Major DOWN + Minor UP: CE on LBB cross below (support)"
                else:
                    return False, f"Major DOWN + Minor UP: CE not allowed on {trigger} cross {crossover_direction}"
            else:  # PE
                return False, "Major DOWN + Minor UP: PE not allowed"
        
        return False, f"Invalid combination: Major={major_trend}, Minor={minor_trend}, Type={option_type}"
    
    # ===== CONTRACT SELECTION HELPERS =====
    
    def calculate_strike_price(self, spot_price: float, option_type: str,
                               min_strike_gap: int = 100,
                               strike_round_to: int = 100) -> float:
        """
        Calculate appropriate OTM strike price
        
        Args:
            spot_price: Current spot price (e.g., NIFTY value)
            option_type: 'CE' or 'PE'
            min_strike_gap: Minimum gap from spot (default 100)
            strike_round_to: Round strike to this value (default 100)
        
        Returns:
            Calculated strike price
        """
        # Calculate target strike
        if option_type == 'CE':
            # For Call, add gap and round up
            target_strike = spot_price + min_strike_gap
            strike = int(np.ceil(target_strike / strike_round_to)) * strike_round_to
        else:  # PE
            # For Put, subtract gap and round down
            target_strike = spot_price - min_strike_gap
            strike = int(np.floor(target_strike / strike_round_to)) * strike_round_to
        
        return float(strike)
    
    # ===== POSITION SIZING =====
    
    def calculate_position_size(self, available_capital: float,
                               contract_price: float,
                               lot_size: int,
                               capital_allocation_pct: float = 16.67) -> int:
        """
        Calculate position size (number of lots)
        
        Formula: max_lots = available_fund / (ltp * lot_size), then round down
        Default allocation: 16.67% = 1/6 (for 6 simultaneous positions)
        
        Args:
            available_capital: Available capital for trading
            contract_price: Price per unit of contract (LTP)
            lot_size: Contract lot size
            capital_allocation_pct: Percentage of capital to allocate (default 16.67%)
        
        Returns:
            Number of lots to trade
        """
        if contract_price <= 0 or available_capital <= 0 or lot_size <= 0:
            return 0
        
        # Calculate capital for this position
        capital_for_trade = available_capital * (capital_allocation_pct / 100)
        
        # Calculate number of lots: available_fund / (ltp * lot_size), then round down
        lots = int(capital_for_trade / (contract_price * lot_size))
        
        # Return 0 if insufficient for even 1 lot
        return lots
    
    def calculate_quantity(self, available_capital: float,
                          contract_price: float,
                          lot_size: int,
                          capital_allocation_pct: float = 16.67) -> int:
        """
        Calculate quantity (lots * lot_size)
        
        Args:
            available_capital: Available capital
            contract_price: Price per unit
            lot_size: Contract lot size
            capital_allocation_pct: Capital allocation percentage
        
        Returns:
            Total quantity to trade
        """
        lots = self.calculate_position_size(
            available_capital, contract_price, lot_size, capital_allocation_pct
        )
        return lots * lot_size
    
    # ===== TARGET & STOPLOSS CALCULATION =====
    
    def calculate_target_price(self, entry_price: float, target_pct: float) -> float:
        """Calculate target price from entry price and target percentage"""
        return entry_price * (1 + target_pct / 100)
    
    def calculate_stoploss_price(self, entry_price: float, stoploss_pct: float) -> float:
        """Calculate stoploss price from entry price and stoploss percentage"""
        return entry_price * (1 - stoploss_pct / 100)
    
    def adjust_price_to_tick(self, price: float, tick_size: float = 0.05) -> float:
        """
        Adjust price to valid tick size
        
        Args:
            price: Original price
            tick_size: Tick size (default 0.05 for NIFTY options)
        
        Returns:
            Adjusted price
        """
        if tick_size <= 0:
            return price
        return round(price / tick_size) * tick_size
