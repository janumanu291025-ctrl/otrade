"""
Kite Connect broker implementation
Strictly aligned with Kite Connect API v3 documentation
https://kite.trade/docs/connect/v3/
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from kiteconnect import KiteConnect, KiteTicker
from kiteconnect.exceptions import TokenException, KiteException
from backend.broker.base import BaseBroker, AuthenticationError, OrderError, NetworkError, TokenExpiredError
import logging

logger = logging.getLogger(__name__)


class KiteBroker(BaseBroker):
    """
    Kite Connect (Zerodha) broker implementation
    
    Implements all Kite Connect API v3 endpoints:
    - User authentication and profile
    - Order placement, modification, cancellation
    - Portfolio (holdings and positions)
    - Market data (quotes, instruments, historical)
    - WebSocket streaming
    - Margins and funds
    """
    
    def __init__(self, api_key: str, api_secret: str, access_token: Optional[str] = None):
        super().__init__(api_key, api_secret, access_token)
        self.kite = KiteConnect(api_key=api_key)
        if access_token:
            self.kite.set_access_token(access_token)
        self.ticker = None
    
    # ========== Authentication Methods ==========
    
    def generate_auth_url(self) -> str:
        """
        Generate Kite Connect login URL
        Returns: https://kite.zerodha.com/connect/login?v=3&api_key=xxx
        Reference: https://kite.trade/docs/connect/v3/user/#login-flow
        """
        try:
            return self.kite.login_url()
        except TokenException as e:
            logger.error(f"Token expired while generating auth URL: {str(e)}")
            raise TokenExpiredError(f"Access token expired. Please re-login: {str(e)}")

        except KiteException as e:
            logger.error(f"Kite API error generating auth URL: {str(e)}")
            raise AuthenticationError(f"Failed to generate auth URL: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error generating auth URL: {str(e)}")
            raise AuthenticationError(f"Failed to generate auth URL: {str(e)}")
    
    def get_access_token(self, request_token: str) -> Dict[str, Any]:
        """
        Exchange request token for access token
        POST /session/token
        Reference: https://kite.trade/docs/connect/v3/user/#authentication-and-token-exchange
        
        Returns:
            user_id, user_name, email, broker, exchanges, products, 
            order_types, api_key, access_token, public_token, login_time, meta
        """
        try:
            data = self.kite.generate_session(request_token, api_secret=self.api_secret)
            self.access_token = data["access_token"]
            self.kite.set_access_token(self.access_token)
            return data
        except TokenException as e:
            logger.error(f"Token expired while getting access token: {str(e)}")
            raise TokenExpiredError(f"Access token expired. Please re-login: {str(e)}")

        except KiteException as e:
            logger.error(f"Kite API error getting access token: {str(e)}")
            raise AuthenticationError(f"Failed to get access token: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error getting access token: {str(e)}")
            raise AuthenticationError(f"Failed to get access token: {str(e)}")
    
    def get_profile(self) -> Dict[str, Any]:
        """
        Get user profile
        GET /user/profile
        Reference: https://kite.trade/docs/connect/v3/user/#user-profile
        
        Returns:
            user_id, user_name, user_shortname, email, user_type, broker,
            exchanges, products, order_types, avatar_url, meta
        """
        try:
            return self.kite.profile()
        except TokenException as e:
            logger.error(f"Token expired while getting profile: {str(e)}")
            raise TokenExpiredError(f"Access token expired. Please re-login: {str(e)}")

        except KiteException as e:
            logger.error(f"Kite API error getting profile: {str(e)}")
            raise AuthenticationError(f"Failed to get profile: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error getting profile: {str(e)}")
            raise AuthenticationError(f"Failed to get profile: {str(e)}")
    
    def invalidate_session(self) -> bool:
        """
        Logout and invalidate the access token
        DELETE /session/token
        Reference: https://kite.trade/docs/connect/v3/user/#logout
        """
        try:
            self.kite.invalidate_access_token()
            self.access_token = None
            return True
        except TokenException as e:
            logger.error(f"Token expired while invalidating session: {str(e)}")
            raise TokenExpiredError(f"Access token expired. Please re-login: {str(e)}")

        except KiteException as e:
            logger.error(f"Kite API error invalidating session: {str(e)}")
            raise AuthenticationError(f"Failed to invalidate session: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error invalidating session: {str(e)}")
            raise AuthenticationError(f"Failed to invalidate session: {str(e)}")
    
    # ========== Funds and Margins Methods ==========
    
    def get_funds(self, segment: Optional[str] = None) -> Dict[str, Any]:
        """
        Get available funds and margins
        GET /user/margins or GET /user/margins/:segment
        Reference: https://kite.trade/docs/connect/v3/user/#funds-and-margins
        
        Args:
            segment: Optional, either 'equity' or 'commodity'. If None, returns all.
        
        Returns:
            For all segments: {"equity": {...}, "commodity": {...}}
            For specific segment: {enabled, net, available, utilised}
        """
        try:
            if segment:
                return self.kite.margins(segment=segment)
            return self.kite.margins()
        except TokenException as e:
            logger.error(f"Token expired while getting funds: {str(e)}")
            raise TokenExpiredError(f"Access token expired. Please re-login: {str(e)}")
        except KiteException as e:
            logger.error(f"Kite API error getting funds: {str(e)}")
            raise NetworkError(f"Failed to get funds: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error getting funds: {str(e)}")
            raise NetworkError(f"Failed to get funds: {str(e)}")
    
    # ========== Instruments and Market Data Methods ==========
    
    def get_instruments(self, exchange: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all instruments (CSV format converted to list of dicts)
        GET /instruments or GET /instruments/:exchange
        Reference: https://kite.trade/docs/connect/v3/market-quotes/#retrieving-the-full-instrument-list
        
        Args:
            exchange: Optional exchange code (NSE, BSE, NFO, BFO, CDS, MCX, BCD, MF)
        
        Returns:
            List of instruments with: instrument_token, exchange_token, tradingsymbol,
            name, last_price, expiry, strike, tick_size, lot_size, instrument_type,
            segment, exchange
        """
        try:
            instruments = self.kite.instruments(exchange) if exchange else self.kite.instruments()
            # Convert to dict format
            return [
                {
                    "instrument_token": inst.get("instrument_token"),
                    "exchange_token": inst.get("exchange_token"),
                    "tradingsymbol": inst.get("tradingsymbol"),
                    "name": inst.get("name"),
                    "last_price": inst.get("last_price", 0),
                    "expiry": inst.get("expiry"),
                    "strike": inst.get("strike"),
                    "tick_size": inst.get("tick_size"),
                    "lot_size": inst.get("lot_size"),
                    "instrument_type": inst.get("instrument_type"),
                    "segment": inst.get("segment"),
                    "exchange": inst.get("exchange"),
                }
                for inst in instruments
            ]
        except TokenException as e:
            logger.error(f"Token expired while getting instruments: {str(e)}")
            raise TokenExpiredError(f"Access token expired. Please re-login: {str(e)}")

        except KiteException as e:
            logger.error(f"Kite API error getting instruments: {str(e)}")
            raise NetworkError(f"Failed to get instruments: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error getting instruments: {str(e)}")
            raise NetworkError(f"Failed to get instruments: {str(e)}")
    
    def get_quote(self, instruments: List[str]) -> Dict[str, Any]:
        """
        Get full market quotes (up to 500 instruments)
        GET /quote?i=NSE:INFY&i=NSE:SBIN...
        Reference: https://kite.trade/docs/connect/v3/market-quotes/#retrieving-full-market-quotes
        
        Args:
            instruments: List of instruments in format "EXCHANGE:SYMBOL" (e.g., "NSE:INFY")
        
        Returns:
            Dict with instrument as key and quote data including:
            instrument_token, timestamp, last_price, volume, ohlc, depth, etc.
        """
        try:
            return self.kite.quote(instruments)
        except TokenException as e:
            logger.error(f"Token expired while getting quote: {str(e)}")
            raise TokenExpiredError(f"Access token expired. Please re-login: {str(e)}")

        except KiteException as e:
            logger.error(f"Kite API error getting quote: {str(e)}")
            raise NetworkError(f"Failed to get quote: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error getting quote: {str(e)}")
            raise NetworkError(f"Failed to get quote: {str(e)}")
    
    def get_ohlc(self, instruments: List[str]) -> Dict[str, Any]:
        """
        Get OHLC quotes (up to 1000 instruments)
        GET /quote/ohlc?i=NSE:INFY&i=NSE:SBIN...
        Reference: https://kite.trade/docs/connect/v3/market-quotes/#retrieving-ohlc-quotes
        
        Args:
            instruments: List of instruments in format "EXCHANGE:SYMBOL"
        
        Returns:
            Dict with instrument as key and OHLC data:
            instrument_token, last_price, ohlc{open, high, low, close}
        """
        try:
            return self.kite.ohlc(instruments)
        except TokenException as e:
            logger.error(f"Token expired while getting OHLC: {str(e)}")
            raise TokenExpiredError(f"Access token expired. Please re-login: {str(e)}")

        except KiteException as e:
            logger.error(f"Kite API error getting OHLC: {str(e)}")
            raise NetworkError(f"Failed to get OHLC: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error getting OHLC: {str(e)}")
            raise NetworkError(f"Failed to get OHLC: {str(e)}")
    
    def get_ltp(self, instruments: List[str]) -> Dict[str, Any]:
        """
        Get last traded price (up to 1000 instruments)
        GET /quote/ltp?i=NSE:INFY&i=NSE:SBIN...
        Reference: https://kite.trade/docs/connect/v3/market-quotes/#retrieving-ltp-quotes
        
        Args:
            instruments: List of instruments in format "EXCHANGE:SYMBOL"
        
        Returns:
            Dict with instrument as key and: {instrument_token, last_price}
        """
        try:
            return self.kite.ltp(instruments)
        except TokenException as e:
            logger.error(f"Token expired while getting LTP: {str(e)}")
            raise TokenExpiredError(f"Access token expired. Please re-login: {str(e)}")

        except KiteException as e:
            logger.error(f"Kite API error getting LTP: {str(e)}")
            raise NetworkError(f"Failed to get LTP: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error getting LTP: {str(e)}")
            raise NetworkError(f"Failed to get LTP: {str(e)}")
    
    def get_market_depth(self, instrument: str) -> Dict[str, Any]:
        """
        Get market depth (5 levels of bid/ask)
        Part of GET /quote response
        Reference: https://kite.trade/docs/connect/v3/market-quotes/#retrieving-full-market-quotes
        
        Returns:
            {buy: [{price, quantity, orders}, ...], sell: [{price, quantity, orders}, ...]}
        """
        try:
            quote = self.kite.quote([instrument])[instrument]
            return quote.get("depth", {"buy": [], "sell": []})
        except TokenException as e:
            logger.error(f"Token expired while getting market depth: {str(e)}")
            raise TokenExpiredError(f"Access token expired. Please re-login: {str(e)}")

        except KiteException as e:
            logger.error(f"Kite API error getting market depth: {str(e)}")
            raise NetworkError(f"Failed to get market depth: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error getting market depth: {str(e)}")
            raise NetworkError(f"Failed to get market depth: {str(e)}")
    
    def get_historical_data(
        self,
        instrument_token: str,
        from_date: datetime,
        to_date: datetime,
        interval: str = "minute"
    ) -> List[Dict[str, Any]]:
        """
        Get historical candle data
        GET /instruments/historical/:instrument_token/:interval
        Reference: https://kite.trade/docs/connect/v3/historical/
        
        Args:
            instrument_token: Numerical instrument token
            from_date: Start date
            to_date: End date
            interval: minute, day, 3minute, 5minute, 10minute, 15minute, 30minute, 60minute
        
        Returns:
            List of candles: [{date, open, high, low, close, volume, oi}, ...]
        """
        try:
            data = self.kite.historical_data(
                instrument_token=int(instrument_token),
                from_date=from_date,
                to_date=to_date,
                interval=interval
            )
            return data
        except TokenException as e:
            logger.error(f"Token expired while getting historical data: {str(e)}")
            raise TokenExpiredError(f"Access token expired. Please re-login: {str(e)}")

        except KiteException as e:
            logger.error(f"Kite API error getting historical data: {str(e)}")
            raise NetworkError(f"Failed to get historical data: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error getting historical data: {str(e)}")
            raise NetworkError(f"Failed to get historical data: {str(e)}")
    
    # ========== Order Management Methods ==========
    
    def place_order(
        self,
        tradingsymbol: str,
        exchange: str,
        transaction_type: str,
        quantity: int,
        order_type: str,
        product: str = "MIS",
        variety: str = "regular",
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        disclosed_quantity: Optional[int] = None,
        validity: str = "DAY",
        validity_ttl: Optional[int] = None,
        iceberg_legs: Optional[int] = None,
        iceberg_quantity: Optional[int] = None,
        auction_number: Optional[str] = None,
        market_protection: Optional[int] = None,
        autoslice: Optional[bool] = None,
        tag: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Place an order
        POST /orders/:variety
        Reference: https://kite.trade/docs/connect/v3/orders/#placing-orders
        
        Args:
            tradingsymbol: Exchange tradingsymbol (e.g., "INFY", "NIFTY2410016000CE")
            exchange: Exchange code (NSE, BSE, NFO, BFO, CDS, MCX, BCD)
            transaction_type: BUY or SELL
            quantity: Quantity to transact
            order_type: MARKET, LIMIT, SL, SL-M
            product: CNC, NRML, MIS, MTF (margin product)
            variety: regular, amo, co, iceberg, auction
            price: Price for LIMIT orders
            trigger_price: Trigger price for SL/SL-M orders
            disclosed_quantity: Quantity to disclose publicly (equity only)
            validity: DAY, IOC, TTL
            validity_ttl: Order life in minutes (for TTL validity)
            iceberg_legs: Number of legs for iceberg orders (2-10)
            iceberg_quantity: Split quantity per iceberg leg
            auction_number: Unique identifier for auction
            market_protection: 0 (no protection), 0-100 (custom %), -1 (auto)
            autoslice: Enable automatic order slicing for freeze quantities
            tag: Optional tag to identify order (alphanumeric, max 20 chars)
        
        Returns:
            {"order_id": "151220000000000"}
        """
        try:
            params = {
                "variety": variety,
                "exchange": exchange,
                "tradingsymbol": tradingsymbol,
                "transaction_type": transaction_type,
                "quantity": quantity,
                "order_type": order_type,
                "product": product,
                "validity": validity
            }
            
            # Add optional parameters
            if price is not None:
                params["price"] = price
            if trigger_price is not None:
                params["trigger_price"] = trigger_price
            if disclosed_quantity is not None:
                params["disclosed_quantity"] = disclosed_quantity
            if validity_ttl is not None:
                params["validity_ttl"] = validity_ttl
            if iceberg_legs is not None:
                params["iceberg_legs"] = iceberg_legs
            if iceberg_quantity is not None:
                params["iceberg_quantity"] = iceberg_quantity
            if auction_number is not None:
                params["auction_number"] = auction_number
            if market_protection is not None:
                params["market_protection"] = market_protection
            if autoslice is not None:
                params["autoslice"] = autoslice
            if tag is not None:
                params["tag"] = tag
            
            order_id = self.kite.place_order(**params)
            return {"order_id": order_id, "status": "success"}
        except TokenException as e:
            logger.error(f"Token expired while placing order: {str(e)}")
            raise TokenExpiredError(f"Access token expired. Please re-login: {str(e)}")
        except KiteException as e:
            logger.error(f"Kite API error placing order: {str(e)}")
            raise OrderError(f"Failed to place order: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error placing order: {str(e)}")
            raise OrderError(f"Failed to place order: {str(e)}")
    
    def modify_order(
        self,
        order_id: str,
        variety: str = "regular",
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        order_type: Optional[str] = None,
        disclosed_quantity: Optional[int] = None,
        validity: Optional[str] = None,
        validity_ttl: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Modify an open or pending order
        PUT /orders/:variety/:order_id
        Reference: https://kite.trade/docs/connect/v3/orders/#modifying-orders
        
        Args:
            order_id: Unique order ID
            variety: regular, amo, co, iceberg, auction
            quantity: New quantity
            price: New price
            trigger_price: New trigger price
            order_type: New order type
            disclosed_quantity: New disclosed quantity
            validity: New validity
            validity_ttl: New validity TTL
        
        Returns:
            {"order_id": "151220000000000"}
        """
        try:
            params = {"variety": variety, "order_id": order_id}
            
            if quantity is not None:
                params["quantity"] = quantity
            if price is not None:
                params["price"] = price
            if trigger_price is not None:
                params["trigger_price"] = trigger_price
            if order_type is not None:
                params["order_type"] = order_type
            if disclosed_quantity is not None:
                params["disclosed_quantity"] = disclosed_quantity
            if validity is not None:
                params["validity"] = validity
            if validity_ttl is not None:
                params["validity_ttl"] = validity_ttl
            
            self.kite.modify_order(**params)
            return {"order_id": order_id, "status": "modified"}
        except TokenException as e:
            logger.error(f"Token expired while modifying order: {str(e)}")
            raise TokenExpiredError(f"Access token expired. Please re-login: {str(e)}")

        except KiteException as e:
            logger.error(f"Kite API error modifying order: {str(e)}")
            raise OrderError(f"Failed to modify order: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error modifying order: {str(e)}")
            raise OrderError(f"Failed to modify order: {str(e)}")
    
    def cancel_order(self, order_id: str, variety: str = "regular") -> Dict[str, Any]:
        """
        Cancel an open or pending order
        DELETE /orders/:variety/:order_id
        Reference: https://kite.trade/docs/connect/v3/orders/#cancelling-orders
        
        Args:
            order_id: Unique order ID
            variety: regular, amo, co, iceberg, auction
        
        Returns:
            {"order_id": "151220000000000"}
        """
        try:
            self.kite.cancel_order(variety=variety, order_id=order_id)
            return {"order_id": order_id, "status": "cancelled"}
        except TokenException as e:
            logger.error(f"Token expired while cancelling order: {str(e)}")
            raise TokenExpiredError(f"Access token expired. Please re-login: {str(e)}")

        except KiteException as e:
            logger.error(f"Kite API error cancelling order: {str(e)}")
            raise OrderError(f"Failed to cancel order: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error cancelling order: {str(e)}")
            raise OrderError(f"Failed to cancel order: {str(e)}")
    
    def get_orders(self) -> List[Dict[str, Any]]:
        """
        Get all orders for the day (open, pending, executed)
        GET /orders
        Reference: https://kite.trade/docs/connect/v3/orders/#retrieving-orders
        
        Returns:
            List of orders with: order_id, parent_order_id, exchange_order_id,
            status, tradingsymbol, exchange, transaction_type, order_type,
            product, quantity, price, trigger_price, average_price, etc.
        """
        try:
            return self.kite.orders()
        except TokenException as e:
            logger.error(f"Token expired while getting orders: {str(e)}")
            raise TokenExpiredError(f"Access token expired. Please re-login: {str(e)}")
        except KiteException as e:
            logger.error(f"Kite API error getting orders: {str(e)}")
            raise NetworkError(f"Failed to get orders: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error getting orders: {str(e)}")
            raise NetworkError(f"Failed to get orders: {str(e)}")
    
    def get_order_history(self, order_id: str) -> List[Dict[str, Any]]:
        """
        Get history of a specific order (all state changes)
        GET /orders/:order_id
        Reference: https://kite.trade/docs/connect/v3/orders/#retrieving-an-orders-history
        
        Args:
            order_id: Unique order ID
        
        Returns:
            List of order states with timestamps showing order lifecycle
        """
        try:
            return self.kite.order_history(order_id)
        except TokenException as e:
            logger.error(f"Token expired while getting order history: {str(e)}")
            raise TokenExpiredError(f"Access token expired. Please re-login: {str(e)}")

        except KiteException as e:
            logger.error(f"Kite API error getting order history: {str(e)}")
            raise NetworkError(f"Failed to get order history: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error getting order history: {str(e)}")
            raise NetworkError(f"Failed to get order history: {str(e)}")
    
    def get_trades(self) -> List[Dict[str, Any]]:
        """
        Get all executed trades for the day
        GET /trades
        Reference: https://kite.trade/docs/connect/v3/orders/#retrieving-all-trades
        
        Returns:
            List of trades with: trade_id, order_id, exchange_order_id,
            tradingsymbol, exchange, transaction_type, product, quantity,
            average_price, fill_timestamp, etc.
        """
        try:
            return self.kite.trades()
        except TokenException as e:
            logger.error(f"Token expired while getting trades: {str(e)}")
            raise TokenExpiredError(f"Access token expired. Please re-login: {str(e)}")

        except KiteException as e:
            logger.error(f"Kite API error getting trades: {str(e)}")
            raise NetworkError(f"Failed to get trades: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error getting trades: {str(e)}")
            raise NetworkError(f"Failed to get trades: {str(e)}")
    
    def get_order_trades(self, order_id: str) -> List[Dict[str, Any]]:
        """
        Get trades for a specific order
        GET /orders/:order_id/trades
        Reference: https://kite.trade/docs/connect/v3/orders/#retrieving-an-orders-trades
        
        Args:
            order_id: Unique order ID
        
        Returns:
            List of trades spawned by the order
        """
        try:
            return self.kite.order_trades(order_id)
        except TokenException as e:
            logger.error(f"Token expired while getting order trades: {str(e)}")
            raise TokenExpiredError(f"Access token expired. Please re-login: {str(e)}")

        except KiteException as e:
            logger.error(f"Kite API error getting order trades: {str(e)}")
            raise NetworkError(f"Failed to get order trades: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error getting order trades: {str(e)}")
            raise NetworkError(f"Failed to get order trades: {str(e)}")
    
    # ========== Portfolio Methods ==========
    
    def get_holdings(self) -> List[Dict[str, Any]]:
        """
        Get long term equity holdings
        GET /portfolio/holdings
        Reference: https://kite.trade/docs/connect/v3/portfolio/#holdings
        
        Returns:
            List of holdings with: tradingsymbol, exchange, instrument_token,
            quantity, average_price, last_price, pnl, day_change, etc.
        """
        try:
            return self.kite.holdings()
        except TokenException as e:
            logger.error(f"Token expired while getting holdings: {str(e)}")
            raise TokenExpiredError(f"Access token expired. Please re-login: {str(e)}")

        except KiteException as e:
            logger.error(f"Kite API error getting holdings: {str(e)}")
            raise NetworkError(f"Failed to get holdings: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error getting holdings: {str(e)}")
            raise NetworkError(f"Failed to get holdings: {str(e)}")
    
    def get_holdings_auctions(self) -> List[Dict[str, Any]]:
        """
        Get list of auctions for holdings
        GET /portfolio/holdings/auctions
        Reference: https://kite.trade/docs/connect/v3/portfolio/#holdings-auction-list
        
        Returns:
            List of holdings currently in auction with auction_number
        """
        try:
            return self.kite.auctions()
        except TokenException as e:
            logger.error(f"Token expired while getting holdings auctions: {str(e)}")
            raise TokenExpiredError(f"Access token expired. Please re-login: {str(e)}")

        except KiteException as e:
            logger.error(f"Kite API error getting holdings auctions: {str(e)}")
            raise NetworkError(f"Failed to get holdings auctions: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error getting holdings auctions: {str(e)}")
            raise NetworkError(f"Failed to get holdings auctions: {str(e)}")
    
    def get_positions(self) -> Dict[str, Any]:
        """
        Get current positions (derivatives and intraday equity)
        GET /portfolio/positions
        Reference: https://kite.trade/docs/connect/v3/portfolio/#positions
        
        Returns:
            {
                "net": [list of net positions],
                "day": [list of day positions]
            }
            
            Each position includes: tradingsymbol, exchange, instrument_token,
            product, quantity, overnight_quantity, multiplier, average_price,
            pnl, m2m, unrealised, realised, buy_quantity, sell_quantity, etc.
        """
        try:
            return self.kite.positions()
        except TokenException as e:
            logger.error(f"Token expired while getting positions: {str(e)}")
            raise TokenExpiredError(f"Access token expired. Please re-login: {str(e)}")
        except KiteException as e:
            logger.error(f"Kite API error getting positions: {str(e)}")
            raise NetworkError(f"Failed to get positions: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error getting positions: {str(e)}")
            raise NetworkError(f"Failed to get positions: {str(e)}")
    
    def convert_position(
        self,
        tradingsymbol: str,
        exchange: str,
        transaction_type: str,
        position_type: str,
        quantity: int,
        old_product: str,
        new_product: str
    ) -> bool:
        """
        Convert position from one margin product to another
        PUT /portfolio/positions
        Reference: https://kite.trade/docs/connect/v3/portfolio/#position-conversion
        
        Args:
            tradingsymbol: Trading symbol
            exchange: Exchange code
            transaction_type: BUY or SELL
            position_type: overnight or day
            quantity: Quantity to convert
            old_product: Existing product (CNC, NRML, MIS)
            new_product: Target product (CNC, NRML, MIS)
        
        Returns:
            True if successful
        """
        try:
            return self.kite.convert_position(
                exchange=exchange,
                tradingsymbol=tradingsymbol,
                transaction_type=transaction_type,
                position_type=position_type,
                quantity=quantity,
                old_product=old_product,
                new_product=new_product
            )
        except TokenException as e:
            logger.error(f"Token expired while converting position: {str(e)}")
            raise TokenExpiredError(f"Access token expired. Please re-login: {str(e)}")

        except KiteException as e:
            logger.error(f"Kite API error converting position: {str(e)}")
            raise OrderError(f"Failed to convert position: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error converting position: {str(e)}")
            raise OrderError(f"Failed to convert position: {str(e)}")
    
    # ========== WebSocket Methods ==========
    
    def connect_websocket(self, on_message_callback, instruments: List[int], mode: str = "full"):
        """
        Connect to Kite WebSocket for real-time market data
        wss://ws.kite.trade?api_key=xxx&access_token=yyy
        Reference: https://kite.trade/docs/connect/v3/websocket/
        
        Args:
            on_message_callback: Callback function to receive tick data
            instruments: List of instrument tokens to subscribe
            mode: Streaming mode - 'ltp', 'quote', or 'full'
        
        WebSocket Modes:
            - ltp: Only last traded price (8 bytes)
            - quote: LTP + volume, OHLC (44 bytes)
            - full: Full market depth (184 bytes)
        """
        try:
            self.ticker = KiteTicker(self.api_key, self.access_token)
            
            def on_ticks(ws, ticks):
                """Handle incoming tick data"""
                logger.info(f"[KITE WS] 📥 Received {len(ticks)} ticks from Kite WebSocket")
                for tick in ticks[:3]:  # Log first 3 ticks for debugging
                    logger.info(f"[KITE WS] Sample tick: Token={tick.get('instrument_token')}, LTP={tick.get('last_price')}")
                on_message_callback(ticks)
            
            def on_connect(ws, response):
                """Handle WebSocket connection"""
                logger.info(f"[KITE WS] WebSocket connected: {response}")
                # Subscribe to instruments
                ws.subscribe(instruments)
                logger.info(f"[KITE WS] Called ws.subscribe() for {len(instruments)} instruments: {instruments[:5]}...")
                
                # Set streaming mode
                if mode == "ltp":
                    ws.set_mode(ws.MODE_LTP, instruments)
                    logger.info(f"[KITE WS] Set MODE_LTP for instruments")
                elif mode == "quote":
                    ws.set_mode(ws.MODE_QUOTE, instruments)
                    logger.info(f"[KITE WS] Set MODE_QUOTE for instruments")
                else:  # full
                    ws.set_mode(ws.MODE_FULL, instruments)
                    logger.info(f"[KITE WS] Set MODE_FULL for instruments")
                
                logger.info(f"[KITE WS] ✓ Subscribed to {len(instruments)} instruments in '{mode}' mode")
            
            def on_close(ws, code, reason):
                """Handle WebSocket disconnection"""
                logger.warning(f"[KITE WS] ⚠️ WebSocket closed: {code} - {reason}")
            
            def on_error(ws, code, reason):
                """Handle WebSocket errors"""
                logger.error(f"[KITE WS] ❌ WebSocket error: {code} - {reason}")
            
            def on_reconnect(ws, attempts_count):
                """Handle WebSocket reconnection"""
                logger.warning(f"[KITE WS] 🔄 WebSocket reconnecting (attempt {attempts_count})")
            
            def on_noreconnect(ws):
                """Handle when max reconnect attempts reached"""
                logger.error("[KITE WS] ❌ WebSocket max reconnect attempts reached")
            
            def on_order_update(ws, data):
                """Handle order postback updates"""
                logger.info(f"[KITE WS] 📋 Order update received: {data}")
                # You can add custom handling for order updates here
            
            # Attach callbacks
            self.ticker.on_ticks = on_ticks
            self.ticker.on_connect = on_connect
            self.ticker.on_close = on_close
            self.ticker.on_error = on_error
            self.ticker.on_reconnect = on_reconnect
            self.ticker.on_noreconnect = on_noreconnect
            self.ticker.on_order_update = on_order_update
            
            # Connect in threaded mode
            self.ticker.connect(threaded=True)
            logger.info("[KITE WS] 🚀 WebSocket connection initiated (threaded mode)")
            
        except TokenException as e:
            logger.error(f"Token expired while connecting WebSocket: {str(e)}")
            raise TokenExpiredError(f"Access token expired. Please re-login: {str(e)}")

            
        except KiteException as e:
            logger.error(f"Kite API error connecting WebSocket: {str(e)}")
            raise NetworkError(f"Failed to connect WebSocket: {str(e)}")

            
        except Exception as e:
            logger.error(f"Unexpected error connecting WebSocket: {str(e)}")
            raise NetworkError(f"Failed to connect WebSocket: {str(e)}")
    
    def subscribe_instruments(self, instruments: List[int], mode: str = "full"):
        """
        Subscribe to additional instruments on existing WebSocket connection
        
        Args:
            instruments: List of instrument tokens
            mode: 'ltp', 'quote', or 'full'
        """
        if not self.ticker:
            raise NetworkError("WebSocket not connected. Call connect_websocket first.")
        
        try:
            self.ticker.subscribe(instruments)
            
            if mode == "ltp":
                self.ticker.set_mode(self.ticker.MODE_LTP, instruments)
            elif mode == "quote":
                self.ticker.set_mode(self.ticker.MODE_QUOTE, instruments)
            else:
                self.ticker.set_mode(self.ticker.MODE_FULL, instruments)
            
            logger.info(f"Subscribed to {len(instruments)} additional instruments in '{mode}' mode")
        except TokenException as e:
            logger.error(f"Token expired while subscribing instruments: {str(e)}")
            raise TokenExpiredError(f"Access token expired. Please re-login: {str(e)}")

        except KiteException as e:
            logger.error(f"Kite API error subscribing instruments: {str(e)}")
            raise NetworkError(f"Failed to subscribe instruments: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error subscribing instruments: {str(e)}")
            raise NetworkError(f"Failed to subscribe instruments: {str(e)}")
    
    def unsubscribe_instruments(self, instruments: List[int]):
        """
        Unsubscribe from instruments
        
        Args:
            instruments: List of instrument tokens to unsubscribe
        """
        if not self.ticker:
            raise NetworkError("WebSocket not connected")
        
        try:
            self.ticker.unsubscribe(instruments)
            logger.info(f"Unsubscribed from {len(instruments)} instruments")
        except TokenException as e:
            logger.error(f"Token expired while unsubscribing instruments: {str(e)}")
            raise TokenExpiredError(f"Access token expired. Please re-login: {str(e)}")

        except KiteException as e:
            logger.error(f"Kite API error unsubscribing instruments: {str(e)}")
            raise NetworkError(f"Failed to unsubscribe instruments: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error unsubscribing instruments: {str(e)}")
            raise NetworkError(f"Failed to unsubscribe instruments: {str(e)}")
    
    def disconnect_websocket(self):
        """
        Disconnect and close WebSocket connection
        """
        if self.ticker:
            try:
                self.ticker.close()
                self.ticker = None
                logger.info("WebSocket disconnected")
            except TokenException as e:
                logger.error(f"Token expired while disconnecting WebSocket: {str(e)}")
                raise TokenExpiredError(f"Access token expired. Please re-login: {str(e)}")

            except KiteException as e:
                logger.error(f"Kite API error disconnecting WebSocket: {str(e)}")
                raise NetworkError(f"Failed to disconnect WebSocket: {str(e)}")

            except Exception as e:
                logger.error(f"Unexpected error disconnecting WebSocket: {str(e)}")
                raise NetworkError(f"Failed to disconnect WebSocket: {str(e)}")
    
    def is_websocket_connected(self) -> bool:
        """
        Check if WebSocket is connected
        
        Returns:
            True if connected, False otherwise
        """
        return self.ticker is not None and self.ticker.is_connected()
