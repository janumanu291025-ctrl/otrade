from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime


class BaseBroker(ABC):
    """Base broker interface that all broker implementations must follow"""
    
    def __init__(self, api_key: str, api_secret: str, access_token: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = access_token
    
    @abstractmethod
    def generate_auth_url(self) -> str:
        """Generate authorization URL for user to authenticate"""
        pass
    
    @abstractmethod
    def get_access_token(self, request_token: str) -> Dict[str, Any]:
        """Exchange request token for access token"""
        pass
    
    @abstractmethod
    def get_profile(self) -> Dict[str, Any]:
        """Get user profile information"""
        pass
    
    @abstractmethod
    def get_funds(self) -> Dict[str, Any]:
        """Get available funds and margins"""
        pass
    
    @abstractmethod
    def get_instruments(self) -> List[Dict[str, Any]]:
        """Get all tradeable instruments"""
        pass
    
    @abstractmethod
    def get_quote(self, instruments: List[str]) -> Dict[str, Any]:
        """Get market quotes for given instruments"""
        pass
    
    @abstractmethod
    def get_ltp(self, instruments: List[str]) -> Dict[str, float]:
        """Get last traded price for instruments"""
        pass
    
    @abstractmethod
    def get_market_depth(self, instrument: str) -> Dict[str, Any]:
        """Get market depth (order book) for instrument"""
        pass
    
    @abstractmethod
    def get_historical_data(
        self, 
        instrument: str, 
        from_date: datetime, 
        to_date: datetime, 
        interval: str
    ) -> List[Dict[str, Any]]:
        """Get historical candle data"""
        pass
    
    @abstractmethod
    def place_order(
        self,
        symbol: str,
        transaction_type: str,  # BUY or SELL
        quantity: int,
        order_type: str,  # LIMIT or MARKET
        price: Optional[float] = None,
        product: str = "MIS",  # MIS (intraday) or CNC (delivery)
        variety: str = "regular"
    ) -> Dict[str, Any]:
        """Place an order"""
        pass
    
    @abstractmethod
    def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        order_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Modify an existing order"""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str, variety: str = "regular") -> Dict[str, Any]:
        """Cancel an order"""
        pass
    
    @abstractmethod
    def get_orders(self) -> List[Dict[str, Any]]:
        """Get all orders for the day"""
        pass
    
    @abstractmethod
    def get_order_history(self, order_id: str) -> List[Dict[str, Any]]:
        """Get order history for specific order"""
        pass
    
    @abstractmethod
    def get_positions(self) -> Dict[str, Any]:
        """Get current positions"""
        pass
    
    @abstractmethod
    def get_holdings(self) -> List[Dict[str, Any]]:
        """Get holdings (long-term positions)"""
        pass
    
    @abstractmethod
    def connect_websocket(self, on_message_callback, instruments: List[str]):
        """Connect to websocket for real-time data"""
        pass


class BrokerError(Exception):
    """Base exception for broker-related errors"""
    pass


class AuthenticationError(BrokerError):
    """Exception for authentication failures"""
    pass


class TokenExpiredError(AuthenticationError):
    """Exception for expired access token (401/403 errors)"""
    pass


class OrderError(BrokerError):
    """Exception for order-related errors"""
    pass


class NetworkError(BrokerError):
    """Exception for network-related errors"""
    pass
