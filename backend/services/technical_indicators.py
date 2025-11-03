"""
Technical Indicators Calculator for MA Crossover Strategy
"""
import numpy as np
from numba import njit
from typing import List, Dict, Tuple
from datetime import datetime


# ==========================================================
# 🔹 Numba-accelerated math kernels
# ==========================================================

@njit(cache=True, fastmath=True)
def _moving_average(arr, period):
    n = len(arr)
    if n < period:
        return np.nan
    total = 0.0
    for i in range(n - period, n):
        total += arr[i]
    return total / period


@njit(cache=True, fastmath=True)
def _bollinger_bands(arr, period=20, std_dev=2.0):
    n = len(arr)
    if n < period:
        return np.nan, np.nan, np.nan
    subset = arr[-period:]
    mean = np.mean(subset)
    std = np.std(subset)
    upper = mean + std_dev * std
    lower = mean - std_dev * std
    return upper, mean, lower


@njit(cache=True, fastmath=True)
def _sd_metrics(arr, period=20):
    n = len(arr)
    if n < period:
        return np.nan, np.nan, np.nan
    subset = arr[-period:]
    mean = np.mean(subset)
    deviations = subset - mean
    sd = np.sqrt(np.mean(deviations ** 2))
    pos = deviations[deviations > 0]
    neg = deviations[deviations < 0]
    sd_pos = np.mean(pos) if len(pos) > 0 else 0.0
    sd_neg = np.mean(neg) if len(neg) > 0 else 0.0
    return sd, sd_pos, sd_neg


# ==========================================================
# 🔹 TechnicalIndicators (same structure, faster inside)
# ==========================================================

class TechnicalIndicators:
    """Calculate technical indicators for trading strategies (optimized)."""

    @staticmethod
    def calculate_moving_average(data: List[float], period: int) -> float:
        if len(data) < period:
            return None
        arr = np.asarray(data, dtype=np.float64)
        result = _moving_average(arr, period)
        return None if np.isnan(result) else float(result)

    @staticmethod
    def calculate_bollinger_bands(
        data: List[float], period: int = 20, std_dev: float = 2.0
    ) -> Tuple[float, float, float]:
        if len(data) < period:
            return None, None, None
        arr = np.asarray(data, dtype=np.float64)
        upper, middle, lower = _bollinger_bands(arr, period, std_dev)
        return (
            None if np.isnan(upper) else float(upper),
            None if np.isnan(middle) else float(middle),
            None if np.isnan(lower) else float(lower),
        )

    @staticmethod
    def calculate_standard_deviation_metrics(
        data: List[float], period: int = 20
    ) -> Tuple[float, float, float]:
        if len(data) < period:
            return None, None, None
        arr = np.asarray(data, dtype=np.float64)
        sd, pos, neg = _sd_metrics(arr, period)
        return (
            None if np.isnan(sd) else float(sd),
            float(pos),
            float(neg),
        )

    @staticmethod
    def detect_trend(short_ma: float, long_ma: float) -> str:
        if short_ma is None or long_ma is None:
            return None
        return "uptrend" if short_ma > long_ma else "downtrend"

    @staticmethod
    def detect_crossover(
        current_price: float,
        indicator_value: float,
        prev_price: float,
        prev_indicator: float,
        cross_type: str = "below",
    ) -> bool:
        if any(x is None for x in [current_price, indicator_value, prev_price, prev_indicator]):
            return False
        if cross_type == "below":
            return prev_price >= prev_indicator and current_price < indicator_value
        else:
            return prev_price <= prev_indicator and current_price > indicator_value

    @staticmethod
    def calculate_percentage_change(current: float, previous: float) -> float:
        if previous == 0:
            return 0
        return ((current - previous) / previous) * 100


# ==========================================================
# ✅ PriceDataStore (unchanged but faster NumPy ops)
# ==========================================================

class PriceDataStore:
    """Store and manage price data for multiple timeframes."""

    def __init__(self):
        self.data = {}  # {instrument_token: {timeframe: [prices]}}
        self.timestamps = {}  # {instrument_token: {timeframe: [timestamps]}}
        self.max_candles = {
            "15sec": 500,
            "1min": 500,
            "3min": 500,
            "10min": 500,
            "15min": 500,
            "30min": 500,
            "hour": 500,
            "day": 365,
            "week": 104,
            "month": 60,
        }

    def add_tick(self, instrument_token: str, price: float, timestamp: datetime = None):
        if timestamp is None:
            timestamp = datetime.now()

        if instrument_token not in self.data:
            self.data[instrument_token] = {}
            self.timestamps[instrument_token] = {}

        self._update_timeframe(instrument_token, "15sec", price, timestamp)
        self._aggregate_timeframes(instrument_token, timestamp)

    def _update_timeframe(self, instrument_token: str, timeframe: str, price: float, timestamp: datetime):
        if timeframe not in self.data[instrument_token]:
            self.data[instrument_token][timeframe] = []
            self.timestamps[instrument_token][timeframe] = []

        prices = self.data[instrument_token][timeframe]
        timestamps = self.timestamps[instrument_token][timeframe]

        prices.append(price)
        timestamps.append(timestamp)

        max_len = self.max_candles.get(timeframe, 500)
        if len(prices) > max_len:
            prices.pop(0)
            timestamps.pop(0)

    def _aggregate_timeframes(self, instrument_token: str, timestamp: datetime):
        if "15sec" not in self.data[instrument_token]:
            return

        sec15_prices = np.array(self.data[instrument_token]["15sec"], dtype=np.float64)
        sec15_times = self.timestamps[instrument_token]["15sec"]

        if len(sec15_prices) < 2:
            return

        candle_time_1min = timestamp.replace(second=0, microsecond=0)
        mask = [t >= candle_time_1min for t in sec15_times]
        if any(mask):
            self._update_timeframe(
                instrument_token, "1min", float(sec15_prices[mask][-1]), candle_time_1min
            )

        if "1min" not in self.data[instrument_token]:
            return

        one_min_prices = np.array(self.data[instrument_token]["1min"], dtype=np.float64)
        one_min_times = self.timestamps[instrument_token]["1min"]

        if len(one_min_prices) < 2:
            return

        timeframe_map = {
            "3min": 3,
            "10min": 10,
            "15min": 15,
            "30min": 30,
            "hour": 60,
        }

        for tf, minutes in timeframe_map.items():
            candle_time = timestamp.replace(second=0, microsecond=0)
            candle_time = candle_time.replace(minute=(candle_time.minute // minutes) * minutes)
            mask = [t >= candle_time for t in one_min_times]
            if any(mask):
                close_price = float(one_min_prices[mask][-1])
                self._update_timeframe(instrument_token, tf, close_price, candle_time)

    def get_prices(self, instrument_token: str, timeframe: str) -> List[float]:
        if instrument_token not in self.data:
            return []
        return self.data[instrument_token].get(timeframe, [])

    def get_latest_price(self, instrument_token: str, timeframe: str = "1min") -> float:
        prices = self.get_prices(instrument_token, timeframe)
        return prices[-1] if prices else None

    def get_indicator_values(self, instrument_token: str, timeframe: str, ma_short: int, ma_long: int) -> Dict:
        prices = self.get_prices(instrument_token, timeframe)
        if not prices:
            return {
                "ltp": None,
                "ma_short": None,
                "ma_long": None,
                "upper_bb": None,
                "middle_bb": None,
                "lower_bb": None,
                "trend": None,
                "sd": None,
                "sd_positive": None,
                "sd_negative": None,
            }

        ltp = prices[-1]
        ma_short_val = TechnicalIndicators.calculate_moving_average(prices, ma_short)
        ma_long_val = TechnicalIndicators.calculate_moving_average(prices, ma_long)
        upper_bb, middle_bb, lower_bb = TechnicalIndicators.calculate_bollinger_bands(prices, 20, 2.0)
        trend = TechnicalIndicators.detect_trend(ma_short_val, ma_long_val)
        sd, sd_positive, sd_negative = TechnicalIndicators.calculate_standard_deviation_metrics(prices, 20)

        return {
            "ltp": ltp,
            "ma_short": ma_short_val,
            "ma_long": ma_long_val,
            "upper_bb": upper_bb,
            "middle_bb": middle_bb,
            "lower_bb": lower_bb,
            "trend": trend,
            "sd": sd,
            "sd_positive": sd_positive,
            "sd_negative": sd_negative,
        }
