"""Technical indicator calculations using Numba for performance"""
import numpy as np
from numba import njit
from typing import Tuple


@njit
def calculate_sma(prices: np.ndarray, period: int) -> np.ndarray:
    """
    Calculate Simple Moving Average using Numba JIT compilation
    
    Args:
        prices: Array of prices
        period: Period for moving average
        
    Returns:
        Array of SMA values
    """
    n = len(prices)
    sma = np.empty(n)
    sma[:period-1] = np.nan
    
    for i in range(period-1, n):
        sma[i] = np.mean(prices[i-period+1:i+1])
    
    return sma


@njit
def calculate_bollinger_bands(prices: np.ndarray, period: int = 20, std_dev: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate Bollinger Bands using Numba JIT compilation
    
    Args:
        prices: Array of prices
        period: Period for moving average
        std_dev: Number of standard deviations
        
    Returns:
        Tuple of (upper_band, middle_band, lower_band)
    """
    n = len(prices)
    middle = np.empty(n)
    upper = np.empty(n)
    lower = np.empty(n)
    
    middle[:period-1] = np.nan
    upper[:period-1] = np.nan
    lower[:period-1] = np.nan
    
    for i in range(period-1, n):
        window = prices[i-period+1:i+1]
        mean = np.mean(window)
        std = np.std(window)
        
        middle[i] = mean
        upper[i] = mean + (std_dev * std)
        lower[i] = mean - (std_dev * std)
    
    return upper, middle, lower


@njit
def detect_crossover(series1: np.ndarray, series2: np.ndarray) -> np.ndarray:
    """
    Detect when series1 crosses above series2
    
    Args:
        series1: First price series
        series2: Second price series
        
    Returns:
        Boolean array indicating crossover points
    """
    n = len(series1)
    crossover = np.zeros(n, dtype=np.bool_)
    
    for i in range(1, n):
        if not np.isnan(series1[i]) and not np.isnan(series2[i]):
            if series1[i-1] <= series2[i-1] and series1[i] > series2[i]:
                crossover[i] = True
    
    return crossover


@njit
def detect_crossunder(series1: np.ndarray, series2: np.ndarray) -> np.ndarray:
    """
    Detect when series1 crosses below series2
    
    Args:
        series1: First price series
        series2: Second price series
        
    Returns:
        Boolean array indicating crossunder points
    """
    n = len(series1)
    crossunder = np.zeros(n, dtype=np.bool_)
    
    for i in range(1, n):
        if not np.isnan(series1[i]) and not np.isnan(series2[i]):
            if series1[i-1] >= series2[i-1] and series1[i] < series2[i]:
                crossunder[i] = True
    
    return crossunder


@njit
def calculate_rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
    """
    Calculate Relative Strength Index
    
    Args:
        prices: Array of prices
        period: RSI period
        
    Returns:
        Array of RSI values
    """
    n = len(prices)
    rsi = np.empty(n)
    rsi[:period] = np.nan
    
    # Calculate price changes
    deltas = np.diff(prices)
    
    # Separate gains and losses
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    # Calculate initial average gain and loss
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    
    if avg_loss == 0:
        rsi[period] = 100
    else:
        rs = avg_gain / avg_loss
        rsi[period] = 100 - (100 / (1 + rs))
    
    # Calculate subsequent RSI values
    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period
        
        if avg_loss == 0:
            rsi[i] = 100
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100 - (100 / (1 + rs))
    
    return rsi


class IndicatorCalculator:
    """Main class for calculating technical indicators"""
    
    @staticmethod
    def calculate_ma(prices: list, period: int) -> list:
        """Calculate Moving Average"""
        prices_array = np.array(prices, dtype=np.float64)
        ma = calculate_sma(prices_array, period)
        return ma.tolist()
    
    @staticmethod
    def calculate_bollinger(prices: list, period: int = 20, std_dev: float = 2.0) -> dict:
        """Calculate Bollinger Bands"""
        prices_array = np.array(prices, dtype=np.float64)
        upper, middle, lower = calculate_bollinger_bands(prices_array, period, std_dev)
        return {
            "upper": upper.tolist(),
            "middle": middle.tolist(),
            "lower": lower.tolist()
        }
    
    @staticmethod
    def check_trend(prices: list, ma_short_period: int, ma_long_period: int) -> str:
        """
        Check if trend is uptrend or downtrend
        
        Returns:
            "uptrend" if short MA > long MA, else "downtrend"
        """
        if len(prices) < max(ma_short_period, ma_long_period):
            return "neutral"
        
        prices_array = np.array(prices, dtype=np.float64)
        ma_short = calculate_sma(prices_array, ma_short_period)
        ma_long = calculate_sma(prices_array, ma_long_period)
        
        # Get the latest values
        latest_short = ma_short[-1]
        latest_long = ma_long[-1]
        
        if np.isnan(latest_short) or np.isnan(latest_long):
            return "neutral"
        
        return "uptrend" if latest_short > latest_long else "downtrend"
    
    @staticmethod
    def check_ltp_cross_ma(prices: list, ma_period: int) -> dict:
        """
        Check if LTP crossed below MA (buy signal for uptrend strategy)
        
        Returns:
            dict with crossunder and crossover signals
        """
        if len(prices) < ma_period + 1:
            return {"crossunder": False, "crossover": False}
        
        prices_array = np.array(prices, dtype=np.float64)
        ma = calculate_sma(prices_array, ma_period)
        
        crossunder = detect_crossunder(prices_array, ma)
        crossover = detect_crossover(prices_array, ma)
        
        return {
            "crossunder": bool(crossunder[-1]),
            "crossover": bool(crossover[-1])
        }
    
    @staticmethod
    def check_ltp_cross_bollinger(prices: list, period: int = 20, std_dev: float = 2.0) -> dict:
        """
        Check if LTP crossed below Lower Bollinger Band
        
        Returns:
            dict with crossunder_lbb and crossover_ubb signals
        """
        if len(prices) < period + 1:
            return {"crossunder_lbb": False, "crossover_ubb": False}
        
        prices_array = np.array(prices, dtype=np.float64)
        upper, middle, lower = calculate_bollinger_bands(prices_array, period, std_dev)
        
        crossunder_lbb = detect_crossunder(prices_array, lower)
        crossover_ubb = detect_crossover(prices_array, upper)
        
        return {
            "crossunder_lbb": bool(crossunder_lbb[-1]),
            "crossover_ubb": bool(crossover_ubb[-1])
        }
