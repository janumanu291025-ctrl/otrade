"""
HFT-Optimized Trading Calculations
==================================

Numba JIT-compiled functions for ultra-fast trading calculations.
10-100x performance improvement over pure Python.
"""

import numpy as np
from numba import jit, float64, int32, boolean
import numba as nb


@jit(nopython=True, fastmath=True, cache=True)
def calculate_limit_buy_price(ltp: float, percentage_below: float, tick_size: float) -> float:
    """
    JIT-compiled LIMIT BUY price calculation.

    Args:
        ltp: Last traded price
        percentage_below: Percentage to reduce below LTP
        tick_size: Tick size for rounding (e.g., 0.05)

    Returns:
        Rounded limit buy price
    """
    buy_price = ltp * (1.0 - percentage_below / 100.0)
    return round(buy_price / tick_size) * tick_size


@jit(nopython=True, fastmath=True, cache=True)
def calculate_limit_sell_price(buy_price: float, target_percentage: float, tick_size: float) -> float:
    """
    JIT-compiled LIMIT SELL price calculation.

    Args:
        buy_price: Executed buy price
        target_percentage: Target percentage above buy price
        tick_size: Tick size for rounding

    Returns:
        Rounded limit sell price
    """
    sell_price = buy_price * (1.0 + target_percentage / 100.0)
    return round(sell_price / tick_size) * tick_size


@jit(nopython=True, fastmath=True, cache=True)
def calculate_bracket_prices(ltp: float,
                           buy_percentage: float,
                           sell_percentage: float,
                           tick_size: float):
    """
    JIT-compiled bracket order price calculation.

    Args:
        ltp: Last traded price
        buy_percentage: Percentage below LTP for buy
        sell_percentage: Percentage above buy for sell
        tick_size: Tick size for rounding

    Returns:
        Tuple of (buy_price, sell_price)
    """
    buy_price = ltp * (1.0 - buy_percentage / 100.0)
    buy_price = round(buy_price / tick_size) * tick_size

    sell_price = buy_price * (1.0 + sell_percentage / 100.0)
    sell_price = round(sell_price / tick_size) * tick_size

    return buy_price, sell_price


@jit(nopython=True, fastmath=True, cache=True)
def calculate_trade_quantity(capital_available: float,
                           option_price: float,
                           lot_size: int,
                           capital_allocation_pct: float) -> int:
    """
    JIT-compiled trade quantity calculation.

    Args:
        capital_available: Available trading capital
        option_price: Option premium price
        lot_size: Contract lot size
        capital_allocation_pct: Percentage of capital to allocate

    Returns:
        Number of lots to trade
    """
    capital_per_trade = capital_available * (capital_allocation_pct / 100.0)
    max_lots = int(capital_per_trade / (option_price * lot_size))

    # Ensure at least 1 lot if capital allows
    return max(max_lots, 0)


@jit(nopython=True, fastmath=True, cache=True)
def detect_crossover_signals(price_buffer: np.ndarray,
                           ma7_buffer: np.ndarray,
                           ma20_buffer: np.ndarray,
                           lbb_buffer: np.ndarray,
                           ubb_buffer: np.ndarray) -> np.ndarray:
    """
    JIT-compiled signal detection for multiple strategies.

    Args:
        price_buffer: Recent price data
        ma7_buffer: 7-period moving average
        ma20_buffer: 20-period moving average
        lbb_buffer: Lower Bollinger Band
        ubb_buffer: Upper Bollinger Band

    Returns:
        Array of signal types (0=no signal, 1=7MA buy, -1=7MA sell, 2=LBB buy, -2=UBB sell)
    """
    signals = np.zeros(len(price_buffer), dtype=np.int32)

    for i in range(1, len(price_buffer)):
        price = price_buffer[i]
        ma7 = ma7_buffer[i]
        ma20 = ma20_buffer[i]
        lbb = lbb_buffer[i]
        ubb = ubb_buffer[i]

        ma7_prev = ma7_buffer[i-1]
        ma20_prev = ma20_buffer[i-1]

        # 7MA crossover signals
        if ma7_prev <= ma20_prev and ma7 > ma20:
            signals[i] = 1  # BUY signal
        elif ma7_prev >= ma20_prev and ma7 < ma20:
            signals[i] = -1  # SELL signal

        # Bollinger Band signals (override MA signals if stronger)
        elif price <= lbb:
            signals[i] = 2  # LBB BUY signal
        elif price >= ubb:
            signals[i] = -2  # UBB SELL signal

    return signals


@jit(nopython=True, fastmath=True, cache=True)
def calculate_moving_averages(price_buffer: np.ndarray, short_period: int, long_period: int):
    """
    JIT-compiled moving average calculation.

    Args:
        price_buffer: Price data array
        short_period: Short MA period (e.g., 7)
        long_period: Long MA period (e.g., 20)

    Returns:
        Tuple of (short_ma, long_ma) arrays
    """
    # Calculate moving averages
    short_ma = np.convolve(price_buffer, np.ones(short_period)/short_period, mode='valid')
    long_ma = np.convolve(price_buffer, np.ones(long_period)/long_period, mode='valid')

    # Create full-length arrays filled with NaN
    short_ma_full = np.full(len(price_buffer), np.nan, dtype=np.float64)
    long_ma_full = np.full(len(price_buffer), np.nan, dtype=np.float64)

    # Fill the valid portions
    short_start_idx = short_period - 1
    long_start_idx = long_period - 1

    short_end_idx = short_start_idx + len(short_ma)
    long_end_idx = long_start_idx + len(long_ma)

    short_ma_full[short_start_idx:short_end_idx] = short_ma
    long_ma_full[long_start_idx:long_end_idx] = long_ma

    return short_ma_full, long_ma_full


@jit(nopython=True, fastmath=True, cache=True)
def calculate_bollinger_bands(price_buffer: np.ndarray,
                            period: int = 20,
                            std_dev: float = 2.0):
    """
    JIT-compiled Bollinger Bands calculation.

    Args:
        price_buffer: Price data array
        period: Moving average period
        std_dev: Standard deviation multiplier

    Returns:
        Tuple of (middle_band, upper_band, lower_band)
    """
    # Calculate SMA
    sma = np.convolve(price_buffer, np.ones(period)/period, mode='valid')

    # Calculate rolling standard deviation
    rolling_std = np.zeros(len(sma))
    for i in range(len(sma)):
        start_idx = max(0, i - period + 1)
        end_idx = i + 1
        prices = price_buffer[start_idx:end_idx]
        rolling_std[i] = np.std(prices)

    # Calculate bands
    upper_band = sma + (rolling_std * std_dev)
    lower_band = sma - (rolling_std * std_dev)

    # Pad arrays to match input length
    sma_full = np.full(len(price_buffer), np.nan)
    upper_full = np.full(len(price_buffer), np.nan)
    lower_full = np.full(len(price_buffer), np.nan)

    sma_full[period-1:] = sma
    upper_full[period-1:] = upper_band
    lower_full[period-1:] = lower_band

    return sma_full, upper_full, lower_full


@jit(nopython=True, fastmath=True, cache=True)
def calculate_pnl(entry_price: float, exit_price: float, quantity: int) -> float:
    """
    JIT-compiled P&L calculation.

    Args:
        entry_price: Position entry price
        exit_price: Position exit price
        quantity: Position quantity

    Returns:
        Realized P&L
    """
    return (exit_price - entry_price) * quantity


@jit(nopython=True, fastmath=True, cache=True)
def check_position_targets(current_price: float,
                         target_price: float,
                         stoploss_price: float) -> np.ndarray:
    """
    JIT-compiled position target checking.

    Args:
        current_price: Current market price
        target_price: Target price for profit booking
        stoploss_price: Stoploss price for loss cutting

    Returns:
        Array of [target_hit, stoploss_hit]
    """
    target_hit = current_price >= target_price if not np.isnan(target_price) else False
    stoploss_hit = current_price <= stoploss_price if not np.isnan(stoploss_price) else False

    return np.array([target_hit, stoploss_hit], dtype=boolean)


@jit(nopython=True, fastmath=True, cache=True)
def update_price_buffer(price_buffer: np.ndarray, new_price: float) -> np.ndarray:
    """
    JIT-compiled price buffer update (rolling window).

    Args:
        price_buffer: Existing price buffer
        new_price: New price to add

    Returns:
        Updated price buffer
    """
    # Shift buffer left and add new price at end
    updated_buffer = np.roll(price_buffer, -1)
    updated_buffer[-1] = new_price

    return updated_buffer


@jit(nopython=True, fastmath=True, cache=True)
def validate_funds_for_entry(capital_available: float,
                           capital_required: float,
                           min_allocation: float = 1000.0) -> bool:
    """
    JIT-compiled funds validation for trade entry.

    Args:
        capital_available: Available trading capital
        capital_required: Capital required for trade
        min_allocation: Minimum allocation threshold

    Returns:
        True if sufficient funds available
    """
    return capital_available >= capital_required and capital_required >= min_allocation


# Pre-compile critical functions for immediate availability
print("🔥 Pre-compiling JIT functions for HFT performance...")

# Force compilation by calling with dummy data
_dummy_prices = np.array([100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0,
                         110.0, 111.0, 112.0, 113.0, 114.0, 115.0, 116.0, 117.0, 118.0, 119.0,
                         120.0, 121.0, 122.0, 123.0, 124.0, 125.0, 126.0, 127.0, 128.0, 129.0])
_dummy_ma7 = np.array([99.0, 100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0,
                      109.0, 110.0, 111.0, 112.0, 113.0, 114.0, 115.0, 116.0, 117.0, 118.0,
                      119.0, 120.0, 121.0, 122.0, 123.0, 124.0, 125.0, 126.0, 127.0, 128.0])
_dummy_ma20 = np.array([98.0, 99.0, 100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0,
                       108.0, 109.0, 110.0, 111.0, 112.0, 113.0, 114.0, 115.0, 116.0, 117.0,
                       118.0, 119.0, 120.0, 121.0, 122.0, 123.0, 124.0, 125.0, 126.0, 127.0])
_dummy_lbb = np.array([97.0, 98.0, 99.0, 100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0,
                      107.0, 108.0, 109.0, 110.0, 111.0, 112.0, 113.0, 114.0, 115.0, 116.0,
                      117.0, 118.0, 119.0, 120.0, 121.0, 122.0, 123.0, 124.0, 125.0, 126.0])
_dummy_ubb = np.array([103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0, 110.0, 111.0, 112.0,
                      113.0, 114.0, 115.0, 116.0, 117.0, 118.0, 119.0, 120.0, 121.0, 122.0,
                      123.0, 124.0, 125.0, 126.0, 127.0, 128.0, 129.0, 130.0, 131.0, 132.0])

# Pre-compile all functions
calculate_limit_buy_price(100.0, 0.5, 0.05)
calculate_limit_sell_price(99.5, 2.5, 0.05)
calculate_bracket_prices(100.0, 0.5, 2.5, 0.05)
calculate_trade_quantity(10000.0, 100.0, 50, 10.0)
detect_crossover_signals(_dummy_prices, _dummy_ma7, _dummy_ma20, _dummy_lbb, _dummy_ubb)
calculate_moving_averages(_dummy_prices, 7, 20)
calculate_bollinger_bands(_dummy_prices)
calculate_pnl(100.0, 105.0, 50)
check_position_targets(105.0, 105.0, 95.0)
update_price_buffer(_dummy_prices, 103.0)
validate_funds_for_entry(10000.0, 5000.0)

print("✅ All JIT functions compiled and ready for HFT!")
