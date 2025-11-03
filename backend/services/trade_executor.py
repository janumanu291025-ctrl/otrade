"""
Advanced Trade Executor for Real/Paper Trading
Manages multiple positions with dynamic order management based on strategy conditions
"""
import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
import numpy as np
from numba import jit

from backend.models import Order, Position, Instrument
from backend.broker.base import BaseBroker
from backend.services.technical_indicators import TechnicalIndicators, PriceDataStore
from backend.services.contract_selector import ContractSelector

logger = logging.getLogger(__name__)


@jit(nopython=True)
def adjust_to_tick_size(price: float, tick_size: float = 0.05) -> float:
    """Adjust price to nearest valid tick size using numba for speed"""
    return round(price / tick_size) * tick_size


class TradePosition:
    """Represents a single trade position"""
    def __init__(self, position_id: int, buy_condition: str, option_type: str):
        self.position_id = position_id  # 1-6
        self.buy_condition = buy_condition  # '7ma', '20ma', 'lbb'
        self.option_type = option_type  # 'CE' or 'PE'
        self.buy_order_id = None
        self.sell_order_id = None
        self.instrument_token = None
        self.symbol = None
        self.quantity = 0
        self.buy_price = 0.0
        self.sell_price = 0.0
        self.status = 'idle'  # idle, buy_pending, bought, sell_pending, sold
        self.buy_triggered_at = None
        self.bought_at = None
        self.sold_at = None


class TradeConfig:
    """Configuration for trade execution"""
    def __init__(self, db: Session, strategy_id: int, broker: BaseBroker = None):
        self.strategy_id = strategy_id
        self.db = db
        self.broker = broker
        
        # Cash allocation - Will be fetched from broker if available
        self.total_capital = 100000.0  # Default fallback
        self.available_funds = 0.0  # Actual funds from broker
        self.call_allocation = 0.50  # 50%
        self.put_allocation = 0.50  # 50%
        self.positions_per_type = 3  # 3 call + 3 put
        
        # Fetch available funds from broker
        if broker:
            self._fetch_available_funds()
        
        # Buy conditions with % adjustments
        self.buy_conditions = {
            '7ma': {'enabled': True, 'percent_below': 0.0, 'sell_target': 2.5},
            '20ma': {'enabled': True, 'percent_below': 0.0, 'sell_target': 3.0},
            'lbb': {'enabled': True, 'percent_below': 0.0, 'sell_target': 5.0},
        }
        
        # Contract selection
        self.min_strike_gap = 100  # Minimum 100 points gap
        self.strike_rounding = 100  # Round to 100
        self.exclude_same_day_expiry = True
        self.only_otm = True
        
        # Order settings
        self.lot_size = 75  # Nifty lot size
        self.tick_size = 0.05  # Nifty option tick
        
        # Timeframes
        self.major_trend_timeframe = '15min'
        self.minor_trend_timeframe = '1min'
        
        # Day end square off
        self.auto_square_off = True
        self.square_off_time = time(15, 28)  # 3:28 PM
        
        # Trading mode
        self.paper_trading = True  # True for paper, False for real
    
    def _fetch_available_funds(self):
        """Fetch available funds from broker"""
        try:
            funds_data = self.broker.get_funds()
            equity_data = funds_data.get("equity", {})
            
            # Get available cash for trading (includes intraday_payin)
            self.available_funds = equity_data.get("available", {}).get("cash", 0)
            
            # Use available cash as total capital
            if self.available_funds > 0:
                self.total_capital = self.available_funds
                logger.info(f"Fetched available cash from broker: ₹{self.available_funds:,.2f}")
            else:
                logger.warning("No funds available from broker, using default capital")
        except Exception as e:
            logger.error(f"Error fetching funds from broker: {e}")
            logger.warning(f"Using default capital: ₹{self.total_capital:,.2f}")
    
    def refresh_funds(self):
        """Refresh available funds from broker"""
        if self.broker:
            self._fetch_available_funds()



class TradeExecutor:
    """Advanced trade executor managing 6 positions (3 calls + 3 puts)"""
    
    def __init__(self, strategy_id: int, broker: BaseBroker, db: Session):
        self.strategy_id = strategy_id
        self.broker = broker
        self.db = db
        self.config = TradeConfig(db, strategy_id, broker)  # Pass broker to config
        self.strategy = None
        
        # Price data
        self.price_store = PriceDataStore()
        self.contract_selector = ContractSelector(db)
        self.index_ltp = 0.0
        self.index_symbol = "NIFTY 50"
        
        # Positions - 6 total (3 calls + 3 puts)
        self.positions: Dict[int, TradePosition] = {}
        self._initialize_positions()
        
        # Indicators cache
        self.indicators_cache = {
            '15sec': {},
            '1min': {},
            '15min': {},
            '1hour': {},
            'day': {}
        }
        
        # Notifications
        self.notifications: List[Dict] = []
        
        # Execution control
        self.running = False
        self.last_update = datetime.now()
        
        # Statistics
        self.stats = {
            'call': {'buy': 0, 'sell': 0, 'total_value': 0, 'pnl': 0},
            'put': {'buy': 0, 'sell': 0, 'total_value': 0, 'pnl': 0},
            'total': {'trades': 0, 'value': 0, 'pnl': 0, 'roc': 0}
        }
    
    def _initialize_positions(self):
        """Initialize 6 trade positions"""
        conditions = ['7ma', '20ma', 'lbb']
        
        # 3 Call positions
        for i, condition in enumerate(conditions, start=1):
            self.positions[i] = TradePosition(i, condition, 'CE')
        
        # 3 Put positions
        for i, condition in enumerate(conditions, start=4):
            self.positions[i] = TradePosition(i, condition, 'PE')
    
    def _get_capital_per_position(self, option_type: str) -> float:
        """Calculate capital available per position"""
        if option_type == 'CE':
            allocation = self.config.call_allocation
        else:
            allocation = self.config.put_allocation
        
        capital_per_type = self.config.total_capital * allocation
        capital_per_position = capital_per_type / self.config.positions_per_type
        return capital_per_position
    
    async def start(self):
        """Start trade execution"""
        self.running = True
        self.strategy = self.db.query(Strategy).filter(
            Strategy.id == self.strategy_id
        ).first()
        
        if not self.strategy:
            raise ValueError(f"Strategy {self.strategy_id} not found")
        
        logger.info(f"Starting trade executor for strategy: {self.strategy.name}")
        self._add_notification("Trade executor started", "success")
        
        # Main execution loop
        while self.running:
            try:
                await self._execution_cycle()
                await asyncio.sleep(0.1)  # 100ms cycle for fast updates
            except Exception as e:
                logger.error(f"Error in execution cycle: {e}")
                self._add_notification(f"Error: {str(e)}", "error")
                await asyncio.sleep(1)
    
    def stop(self):
        """Stop trade execution"""
        self.running = False
        logger.info(f"Stopped trade executor for strategy: {self.strategy.name}")
        self._add_notification("Trade executor stopped", "warning")
    
    async def _execution_cycle(self):
        """Main execution cycle"""
        now = datetime.now()
        
        # Check if market is open (9:15 AM to 3:30 PM)
        if not self._is_market_open(now):
            return
        
        # Check for day end square off
        if self._should_square_off(now):
            await self._square_off_all_positions()
            return
        
        # Get index LTP
        await self._update_index_ltp()
        
        # Update indicators
        await self._update_indicators()
        
        # Check trend conditions
        trends = self._analyze_trends()
        
        # Process each position
        for position_id, position in self.positions.items():
            if position.status == 'idle':
                # Check for buy signal
                await self._check_buy_signal(position, trends)
            
            elif position.status == 'buy_pending':
                # Check if buy order is filled
                await self._check_buy_order_status(position)
            
            elif position.status == 'bought':
                # Place sell order if not placed
                if not position.sell_order_id:
                    await self._place_sell_order(position)
            
            elif position.status == 'sell_pending':
                # Check if sell order is filled
                await self._check_sell_order_status(position)
        
        # Update statistics
        self._update_statistics()
        
        self.last_update = now
    
    def _is_market_open(self, dt: datetime) -> bool:
        """Check if market is open"""
        if dt.weekday() >= 5:  # Saturday or Sunday
            return False
        
        market_open = time(9, 15)
        market_close = time(15, 30)
        current_time = dt.time()
        
        return market_open <= current_time <= market_close
    
    def _should_square_off(self, dt: datetime) -> bool:
        """Check if positions should be squared off"""
        if not self.config.auto_square_off:
            return False
        
        return dt.time() >= self.config.square_off_time
    
    async def _update_index_ltp(self):
        """Update index LTP from broker"""
        try:
            # Get NIFTY 50 spot price - run in thread pool to avoid blocking
            quote = await asyncio.to_thread(
                self.broker.get_quote, ["NSE:NIFTY 50"]
            )
            if quote and "NSE:NIFTY 50" in quote:
                self.index_ltp = quote["NSE:NIFTY 50"].get('last_price', 0.0)
                
                # Update price store for indicator calculation
                self.price_store.add_tick('NIFTY50', self.index_ltp)
        except Exception as e:
            logger.error(f"Error updating index LTP: {e}")
    
    async def _update_indicators(self):
        """Update technical indicators for all timeframes"""
        try:
            timeframes = ['15sec', '1min', '15min', '1hour', 'day']
            
            for tf in timeframes:
                # Get price history from price store
                history = self.price_store.get_ohlc('NIFTY50', tf, 100)
                
                if len(history) < 20:  # Need at least 20 candles
                    continue
                
                close_prices = np.array([c['close'] for c in history])
                
                # Calculate indicators
                ma7 = TechnicalIndicators.calculate_sma(close_prices, 7)
                ma20 = TechnicalIndicators.calculate_sma(close_prices, 20)
                bb_upper, bb_middle, bb_lower = TechnicalIndicators.calculate_bollinger_bands(
                    close_prices, 20, 2
                )
                
                # Calculate standard deviation
                sd = np.std(close_prices[-20:])
                
                self.indicators_cache[tf] = {
                    'ma7': ma7[-1] if len(ma7) > 0 else 0,
                    'ma20': ma20[-1] if len(ma20) > 0 else 0,
                    'ubb': bb_upper[-1] if len(bb_upper) > 0 else 0,
                    'lbb': bb_lower[-1] if len(bb_lower) > 0 else 0,
                    'sd': sd
                }
        except Exception as e:
            logger.error(f"Error updating indicators: {e}")
    
    def _analyze_trends(self) -> Dict[str, str]:
        """Analyze major and minor trends"""
        trends = {
            'major': 'neutral',  # uptrend, downtrend, neutral
            'minor': 'neutral',
            'signal_type': None  # call_buy, put_buy
        }
        
        # Major trend (15min)
        major = self.indicators_cache.get(self.config.major_trend_timeframe, {})
        if major:
            ma7 = major.get('ma7', 0)
            ma20 = major.get('ma20', 0)
            
            if ma7 > ma20:
                trends['major'] = 'uptrend'
            elif ma7 < ma20:
                trends['major'] = 'downtrend'
        
        # Minor trend (1min)
        minor = self.indicators_cache.get(self.config.minor_trend_timeframe, {})
        if minor:
            ma7 = minor.get('ma7', 0)
            ma20 = minor.get('ma20', 0)
            
            if ma7 > ma20:
                trends['minor'] = 'uptrend'
            elif ma7 < ma20:
                trends['minor'] = 'downtrend'
        
        # Determine signal type based on trend combination
        if trends['major'] == 'uptrend' and trends['minor'] == 'uptrend':
            trends['signal_type'] = 'call_buy'  # Buy call at crossover below
        elif trends['major'] == 'uptrend' and trends['minor'] == 'downtrend':
            trends['signal_type'] = 'put_buy'  # Buy put at crossover above
        elif trends['major'] == 'downtrend' and trends['minor'] == 'downtrend':
            trends['signal_type'] = 'put_buy'  # Buy put at crossover below
        elif trends['major'] == 'downtrend' and trends['minor'] == 'uptrend':
            trends['signal_type'] = 'call_buy'  # Buy call at crossover above
        
        return trends
    
    async def _check_buy_signal(self, position: TradePosition, trends: Dict):
        """Check for buy signal based on position conditions"""
        # Check if condition is enabled
        condition_config = self.config.buy_conditions.get(position.buy_condition)
        if not condition_config or not condition_config['enabled']:
            return
        
        # Check if signal type matches position type
        expected_signal = 'call_buy' if position.option_type == 'CE' else 'put_buy'
        if trends['signal_type'] != expected_signal:
            return
        
        # Get minor trend indicators
        indicators = self.indicators_cache.get(self.config.minor_trend_timeframe, {})
        if not indicators:
            return
        
        # Determine trigger level based on condition
        if position.buy_condition == '7ma':
            trigger_level = indicators.get('ma7', 0)
        elif position.buy_condition == '20ma':
            trigger_level = indicators.get('ma20', 0)
        elif position.buy_condition == 'lbb':
            trigger_level = indicators.get('lbb', 0)
        else:
            return
        
        if trigger_level == 0:
            return
        
        # Check if LTP crosses the trigger level
        ltp = self.index_ltp
        percent_adjustment = condition_config['percent_below']
        
        # Determine if crossover happened
        crossover = False
        if trends['minor'] == 'uptrend':
            # Price crosses above trigger
            adjusted_trigger = trigger_level * (1 + percent_adjustment / 100)
            crossover = ltp >= adjusted_trigger
        else:
            # Price crosses below trigger
            adjusted_trigger = trigger_level * (1 - percent_adjustment / 100)
            crossover = ltp <= adjusted_trigger
        
        if crossover:
            # Trigger buy order
            await self._trigger_buy_order(position, adjusted_trigger)
    
    async def _trigger_buy_order(self, position: TradePosition, trigger_price: float):
        """Trigger buy order for a position"""
        try:
            # Select contract
            contract = await self._select_contract(position.option_type)
            if not contract:
                logger.warning(f"No suitable contract found for position {position.position_id}")
                return
            
            # Get contract LTP
            contract_ltp = await self._get_contract_ltp(contract)
            if contract_ltp == 0:
                return
            
            # Adjust price to tick size
            order_price = adjust_to_tick_size(contract_ltp, self.config.tick_size)
            
            # Calculate quantity
            capital = self._get_capital_per_position(position.option_type)
            quantity = self._calculate_quantity(capital, contract_ltp)
            
            if quantity == 0:
                logger.warning(f"Insufficient capital for position {position.position_id}")
                return
            
            # Place buy order
            order_id = await self._place_buy_order(
                contract, quantity, order_price, position
            )
            
            if order_id:
                position.status = 'buy_pending'
                position.buy_order_id = order_id
                position.instrument_token = str(contract.instrument_token)
                position.symbol = contract.tradingsymbol
                position.quantity = quantity
                position.buy_price = order_price
                position.buy_triggered_at = datetime.now()
                
                self._add_notification(
                    f"Buy order placed: {contract.tradingsymbol} x{quantity} @ {order_price}",
                    "info"
                )
                
                logger.info(
                    f"Position {position.position_id}: Buy order placed - "
                    f"{contract.tradingsymbol} x{quantity} @ {order_price}"
                )
        except Exception as e:
            logger.error(f"Error triggering buy order: {e}")
            self._add_notification(f"Buy order failed: {str(e)}", "error")
    
    async def _select_contract(self, option_type: str) -> Optional[Instrument]:
        """Select appropriate option contract"""
        try:
            import math
            
            # Get current spot price
            spot_price = self.index_ltp
            
            # Apply gap for OTM with proper rounding
            if option_type == 'CE':
                # Call - Round UP then add gap
                base_strike = math.ceil(spot_price / self.config.strike_rounding) * self.config.strike_rounding
                strike = base_strike + self.config.min_strike_gap
            else:
                # Put - Round DOWN then subtract gap
                base_strike = math.floor(spot_price / self.config.strike_rounding) * self.config.strike_rounding
                strike = base_strike - self.config.min_strike_gap
            
            # Get today's date
            today = datetime.now().date()
            
            # Query for contract
            query = self.db.query(Instrument).filter(
                Instrument.segment == 'NFO-OPT',
                Instrument.name == 'NIFTY',
                Instrument.instrument_type == option_type,
                Instrument.strike == float(strike)
            )
            
            # Exclude same day expiry
            if self.config.exclude_same_day_expiry:
                query = query.filter(Instrument.expiry != today.strftime('%Y-%m-%d'))
            
            # Get nearest expiry
            contract = query.order_by(Instrument.expiry).first()
            
            return contract
        except Exception as e:
            logger.error(f"Error selecting contract: {e}")
            return None
    
    async def _get_contract_ltp(self, contract: Instrument) -> float:
        """Get contract LTP"""
        try:
            instrument_key = f"{contract.exchange}:{contract.tradingsymbol}"
            quote = await asyncio.to_thread(
                self.broker.get_quote, [instrument_key]
            )
            if quote and instrument_key in quote:
                return quote[instrument_key].get('last_price', 0.0)
        except Exception as e:
            logger.error(f"Error getting contract LTP: {e}")
        return 0.0
    
    def _calculate_quantity(self, capital: float, ltp: float) -> int:
        """Calculate order quantity based on capital"""
        contract_value = self.config.lot_size * ltp
        lots = int(capital / contract_value)
        quantity = lots * self.config.lot_size
        return quantity
    
    async def _place_buy_order(
        self, contract: Instrument, quantity: int, price: float, position: TradePosition
    ) -> Optional[str]:
        """Place buy order"""
        try:
            if self.config.paper_trading:
                # Paper trading - generate mock order ID
                order_id = f"PAPER_{position.position_id}_{datetime.now().timestamp()}"
                
                # Save to database
                order = Order(
                    strategy_id=self.strategy_id,
                    broker_order_id=order_id,
                    instrument_token=str(contract.instrument_token),
                    symbol=contract.tradingsymbol,
                    exchange=contract.exchange,
                    order_type='buy',
                    transaction_type='limit',
                    product='MIS',
                    quantity=quantity,
                    price=price,
                    average_price=price,
                    status='pending',
                    placed_at=datetime.now()
                )
                self.db.add(order)
                self.db.commit()
                
                return order_id
            else:
                # Real trading - call broker with proper signature
                result = await asyncio.to_thread(
                    self.broker.place_order,
                    tradingsymbol=contract.tradingsymbol,
                    exchange=contract.exchange,
                    transaction_type='BUY',
                    quantity=quantity,
                    order_type='LIMIT',
                    price=price,
                    product='MIS'
                )
                
                order_id = result.get('order_id')
                
                # Save to database
                order = Order(
                    strategy_id=self.strategy_id,
                    broker_order_id=order_id,
                    instrument_token=str(contract.instrument_token),
                    symbol=contract.tradingsymbol,
                    exchange=contract.exchange,
                    order_type='buy',
                    transaction_type='limit',
                    product='MIS',
                    quantity=quantity,
                    price=price,
                    status='pending',
                    placed_at=datetime.now()
                )
                self.db.add(order)
                self.db.commit()
                
                return order_id
        except Exception as e:
            logger.error(f"Error placing buy order: {e}")
            return None
    
    async def _check_buy_order_status(self, position: TradePosition):
        """Check if buy order is filled"""
        try:
            # Get order from database
            order = self.db.query(Order).filter(
                Order.broker_order_id == position.buy_order_id
            ).first()
            
            if not order:
                return
            
            if self.config.paper_trading:
                # Paper trading - auto fill after 1 second
                if (datetime.now() - order.placed_at).total_seconds() > 1:
                    order.status = 'completed'
                    order.filled_at = datetime.now()
                    order.average_price = order.price
                    self.db.commit()
            else:
                # Real trading - check with broker
                order_history = await asyncio.to_thread(
                    self.broker.get_order_history, position.buy_order_id
                )
                if order_history and len(order_history) > 0:
                    latest_status = order_history[-1]  # Last status
                    if latest_status.get('status') == 'COMPLETE':
                        order.status = 'completed'
                        order.filled_at = datetime.now()
                        order.average_price = latest_status.get('average_price', order.price)
                        self.db.commit()
            
            # Update position if order is filled
            if order.status == 'completed':
                position.status = 'bought'
                position.bought_at = order.filled_at
                position.buy_price = order.average_price
                
                self._add_notification(
                    f"Buy executed: {order.symbol} x{order.quantity} @ {order.average_price}",
                    "success"
                )
                
                # Create position record
                pos_record = Position(
                    strategy_id=self.strategy_id,
                    instrument_token=order.instrument_token,
                    symbol=order.symbol,
                    quantity=order.quantity,
                    average_price=order.average_price,
                    last_price=order.average_price,
                    opened_at=order.filled_at
                )
                self.db.add(pos_record)
                self.db.commit()
                
                logger.info(f"Position {position.position_id}: Buy order filled")
        except Exception as e:
            logger.error(f"Error checking buy order status: {e}")
    
    async def _place_sell_order(self, position: TradePosition):
        """Place sell order after buy execution"""
        try:
            # Get sell target from config
            condition_config = self.config.buy_conditions.get(position.buy_condition)
            target_percent = condition_config.get('sell_target', 2.5)
            
            # Calculate sell price
            sell_price = position.buy_price * (1 + target_percent / 100)
            sell_price = adjust_to_tick_size(sell_price, self.config.tick_size)
            
            # Get contract
            contract = self.db.query(Instrument).filter(
                Instrument.instrument_token == position.instrument_token
            ).first()
            
            if not contract:
                logger.error(f"Contract not found for position {position.position_id}")
                return
            
            # Place sell order
            if self.config.paper_trading:
                order_id = f"PAPER_SELL_{position.position_id}_{datetime.now().timestamp()}"
                
                order = Order(
                    strategy_id=self.strategy_id,
                    broker_order_id=order_id,
                    instrument_token=position.instrument_token,
                    symbol=position.symbol,
                    exchange='NFO',
                    order_type='sell',
                    transaction_type='limit',
                    product='MIS',
                    quantity=position.quantity,
                    price=sell_price,
                    status='pending',
                    placed_at=datetime.now()
                )
                self.db.add(order)
                self.db.commit()
            else:
                result = await asyncio.to_thread(
                    self.broker.place_order,
                    tradingsymbol=contract.tradingsymbol,
                    exchange=contract.exchange,
                    transaction_type='SELL',
                    quantity=position.quantity,
                    order_type='LIMIT',
                    price=sell_price,
                    product='MIS'
                )
                
                order_id = result.get('order_id')
                
                order = Order(
                    strategy_id=self.strategy_id,
                    broker_order_id=order_id,
                    instrument_token=position.instrument_token,
                    symbol=position.symbol,
                    exchange=contract.exchange,
                    order_type='sell',
                    transaction_type='limit',
                    product='MIS',
                    quantity=position.quantity,
                    price=sell_price,
                    status='pending',
                    placed_at=datetime.now()
                )
                self.db.add(order)
                self.db.commit()
            
            position.status = 'sell_pending'
            position.sell_order_id = order_id
            position.sell_price = sell_price
            
            self._add_notification(
                f"Sell order placed: {position.symbol} x{position.quantity} @ {sell_price}",
                "info"
            )
            
            logger.info(
                f"Position {position.position_id}: Sell order placed @ {sell_price} "
                f"(Target: {target_percent}%)"
            )
        except Exception as e:
            logger.error(f"Error placing sell order: {e}")
            self._add_notification(f"Sell order failed: {str(e)}", "error")
    
    async def _check_sell_order_status(self, position: TradePosition):
        """Check if sell order is filled"""
        try:
            order = self.db.query(Order).filter(
                Order.broker_order_id == position.sell_order_id
            ).first()
            
            if not order:
                return
            
            if self.config.paper_trading:
                # Paper trading - check if price reached
                contract = self.db.query(Instrument).filter(
                    Instrument.instrument_token == position.instrument_token
                ).first()
                
                if contract:
                    current_ltp = await self._get_contract_ltp(contract)
                    if current_ltp >= order.price:
                        order.status = 'completed'
                        order.filled_at = datetime.now()
                        order.average_price = order.price
                        self.db.commit()
            else:
                order_history = await asyncio.to_thread(
                    self.broker.get_order_history, position.sell_order_id
                )
                if order_history and len(order_history) > 0:
                    latest_status = order_history[-1]
                    if latest_status.get('status') == 'COMPLETE':
                        order.status = 'completed'
                        order.filled_at = datetime.now()
                        order.average_price = latest_status.get('average_price', order.price)
                        self.db.commit()
            
            if order.status == 'completed':
                position.status = 'sold'
                position.sold_at = order.filled_at
                
                # Calculate P&L
                pnl = (order.average_price - position.buy_price) * position.quantity
                pnl_percent = ((order.average_price - position.buy_price) / position.buy_price) * 100
                
                self._add_notification(
                    f"Sell executed: {order.symbol} x{order.quantity} @ {order.average_price} "
                    f"(P&L: {pnl:.2f}, {pnl_percent:.2f}%)",
                    "success"
                )
                
                # Update position record
                pos_record = self.db.query(Position).filter(
                    Position.instrument_token == position.instrument_token,
                    Position.strategy_id == self.strategy_id,
                    Position.closed_at.is_(None)
                ).first()
                
                if pos_record:
                    pos_record.last_price = order.average_price
                    pos_record.pnl = pnl
                    pos_record.pnl_percentage = pnl_percent
                    pos_record.closed_at = order.filled_at
                    self.db.commit()
                
                # Reset position for next trade
                logger.info(
                    f"Position {position.position_id}: Sell order filled - "
                    f"P&L: {pnl:.2f} ({pnl_percent:.2f}%)"
                )
                
                # Reset position
                position.status = 'idle'
                position.buy_order_id = None
                position.sell_order_id = None
                position.instrument_token = None
                position.symbol = None
                position.quantity = 0
                position.buy_price = 0.0
                position.sell_price = 0.0
        except Exception as e:
            logger.error(f"Error checking sell order status: {e}")
    
    async def _square_off_all_positions(self):
        """Square off all open positions at market price"""
        logger.info("Squaring off all positions...")
        self._add_notification("Day end square off initiated", "warning")
        
        for position_id, position in self.positions.items():
            if position.status in ['bought', 'sell_pending']:
                try:
                    # Cancel existing sell order if any
                    if position.sell_order_id:
                        await self._cancel_order(position.sell_order_id)
                    
                    # Place market sell order
                    contract = self.db.query(Instrument).filter(
                        Instrument.instrument_token == position.instrument_token
                    ).first()
                    
                    if not contract:
                        continue
                    
                    if self.config.paper_trading:
                        order_id = f"PAPER_SQOFF_{position.position_id}_{datetime.now().timestamp()}"
                        current_ltp = await self._get_contract_ltp(contract)
                        
                        order = Order(
                            strategy_id=self.strategy_id,
                            broker_order_id=order_id,
                            instrument_token=position.instrument_token,
                            symbol=position.symbol,
                            order_type='sell',
                            transaction_type='market',
                            quantity=position.quantity,
                            price=current_ltp,
                            average_price=current_ltp,
                            status='completed',
                            placed_at=datetime.now(),
                            filled_at=datetime.now()
                        )
                        self.db.add(order)
                        self.db.commit()
                        
                        # Update position
                        position.status = 'sold'
                        position.sold_at = datetime.now()
                        
                        self._add_notification(
                            f"Squared off: {position.symbol} @ market",
                            "warning"
                        )
                    else:
                        result = await asyncio.to_thread(
                            self.broker.place_order,
                            tradingsymbol=contract.tradingsymbol,
                            exchange=contract.exchange,
                            transaction_type='SELL',
                            quantity=position.quantity,
                            order_type='MARKET',
                            product='MIS'
                        )
                        
                        order_id = result.get('order_id')
                        
                        # Wait for execution
                        await asyncio.sleep(1)
                        
                        order_history = await asyncio.to_thread(
                            self.broker.get_order_history, order_id
                        )
                        if order_history and len(order_history) > 0:
                            latest_status = order_history[-1]
                            order = Order(
                                strategy_id=self.strategy_id,
                                broker_order_id=order_id,
                                instrument_token=position.instrument_token,
                                symbol=position.symbol,
                                order_type='sell',
                                transaction_type='market',
                                quantity=position.quantity,
                                price=latest_status.get('average_price', 0),
                                average_price=latest_status.get('average_price', 0),
                                status='completed',
                                placed_at=datetime.now(),
                                filled_at=datetime.now()
                            )
                            self.db.add(order)
                            self.db.commit()
                            
                            position.status = 'sold'
                            position.sold_at = datetime.now()
                except Exception as e:
                    logger.error(f"Error squaring off position {position_id}: {e}")
        
        logger.info("Square off completed")
    
    async def _cancel_order(self, order_id: str):
        """Cancel an order"""
        try:
            if not self.config.paper_trading:
                await asyncio.to_thread(
                    self.broker.cancel_order, order_id
                )
            
            # Update order in database
            order = self.db.query(Order).filter(
                Order.broker_order_id == order_id
            ).first()
            
            if order:
                order.status = 'cancelled'
                self.db.commit()
        except Exception as e:
            logger.error(f"Error canceling order {order_id}: {e}")
    
    def _update_statistics(self):
        """Update trading statistics"""
        try:
            # Reset stats
            self.stats = {
                'call': {'buy': 0, 'sell': 0, 'total_value': 0, 'pnl': 0},
                'put': {'buy': 0, 'sell': 0, 'total_value': 0, 'pnl': 0},
                'total': {'trades': 0, 'value': 0, 'pnl': 0, 'roc': 0}
            }
            
            # Query orders
            orders = self.db.query(Order).filter(
                Order.strategy_id == self.strategy_id,
                Order.status == 'completed'
            ).all()
            
            # Group by option type and order type
            for order in orders:
                # Determine option type from symbol (CE or PE)
                option_type = 'call' if 'CE' in order.symbol else 'put'
                
                if order.order_type == 'buy':
                    self.stats[option_type]['buy'] += 1
                    self.stats[option_type]['total_value'] += order.average_price * order.quantity
                elif order.order_type == 'sell':
                    self.stats[option_type]['sell'] += 1
            
            # Calculate P&L from positions
            positions = self.db.query(Position).filter(
                Position.strategy_id == self.strategy_id,
                Position.closed_at.isnot(None)
            ).all()
            
            for pos in positions:
                option_type = 'call' if 'CE' in pos.symbol else 'put'
                self.stats[option_type]['pnl'] += pos.pnl
            
            # Calculate totals
            self.stats['total']['trades'] = (
                self.stats['call']['buy'] + self.stats['call']['sell'] +
                self.stats['put']['buy'] + self.stats['put']['sell']
            )
            self.stats['total']['value'] = (
                self.stats['call']['total_value'] + self.stats['put']['total_value']
            )
            self.stats['total']['pnl'] = (
                self.stats['call']['pnl'] + self.stats['put']['pnl']
            )
            
            # Calculate ROC
            if self.stats['total']['value'] > 0:
                self.stats['total']['roc'] = (
                    self.stats['total']['pnl'] / self.stats['total']['value']
                ) * 100
        except Exception as e:
            logger.error(f"Error updating statistics: {e}")
    
    def _add_notification(self, message: str, level: str = "info"):
        """Add a notification"""
        notification = {
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'level': level
        }
        self.notifications.insert(0, notification)
        
        # Keep only last 10 notifications
        self.notifications = self.notifications[:10]
    
    def get_state(self) -> Dict:
        """Get current state for frontend"""
        return {
            'strategy_id': self.strategy_id,
            'strategy_name': self.strategy.name if self.strategy else '',
            'status': 'active' if self.running else 'stopped',
            'index_ltp': self.index_ltp,
            'last_update': self.last_update.isoformat(),
            'positions': [
                {
                    'id': pos.position_id,
                    'condition': pos.buy_condition,
                    'type': pos.option_type,
                    'symbol': pos.symbol,
                    'quantity': pos.quantity,
                    'buy_price': pos.buy_price,
                    'sell_price': pos.sell_price,
                    'status': pos.status
                }
                for pos in self.positions.values()
            ],
            'indicators': self.indicators_cache,
            'notifications': self.notifications[:3],  # Last 3
            'statistics': self.stats,
            'config': {
                'total_capital': self.config.total_capital,
                'available_funds': self.config.available_funds,
                'lot_size': self.config.lot_size,
                'tick_size': self.config.tick_size,
                'auto_square_off': self.config.auto_square_off,
                'paper_trading': self.config.paper_trading
            }
        }
