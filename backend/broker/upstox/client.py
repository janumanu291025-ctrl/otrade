"""Upstox broker implementation"""
from typing import Dict, List, Optional, Any
from datetime import datetime
import requests
from backend.broker.base import BaseBroker, AuthenticationError, OrderError, NetworkError
import logging

logger = logging.getLogger(__name__)


class UpstoxBroker(BaseBroker):
    """Upstox broker implementation"""
    
    BASE_URL = "https://api.upstox.com/v2"
    
    def __init__(self, api_key: str, api_secret: str, access_token: Optional[str] = None):
        super().__init__(api_key, api_secret, access_token)
        self.redirect_uri = "http://localhost:8000/api/broker/callback"
        self.headers = {}
        if access_token:
            self.headers["Authorization"] = f"Bearer {access_token}"
    
    def generate_auth_url(self) -> str:
        """Generate Upstox authorization URL"""
        try:
            auth_url = (
                f"https://api.upstox.com/v2/login/authorization/dialog"
                f"?client_id={self.api_key}"
                f"&redirect_uri={self.redirect_uri}"
                f"&response_type=code"
            )
            return auth_url
        except Exception as e:
            logger.error(f"Error generating auth URL: {str(e)}")
            raise AuthenticationError(f"Failed to generate auth URL: {str(e)}")
    
    def get_access_token(self, request_token: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        try:
            url = f"{self.BASE_URL}/login/authorization/token"
            data = {
                "code": request_token,
                "client_id": self.api_key,
                "client_secret": self.api_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code"
            }
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            
            response = requests.post(url, data=data, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            self.access_token = result.get("access_token")
            self.headers["Authorization"] = f"Bearer {self.access_token}"
            
            return result
        except Exception as e:
            logger.error(f"Error getting access token: {str(e)}")
            raise AuthenticationError(f"Failed to get access token: {str(e)}")
    
    def get_profile(self) -> Dict[str, Any]:
        """Get user profile"""
        try:
            url = f"{self.BASE_URL}/user/profile"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json().get("data", {})
        except Exception as e:
            logger.error(f"Error getting profile: {str(e)}")
            raise AuthenticationError(f"Failed to get profile: {str(e)}")
    
    def get_funds(self) -> Dict[str, Any]:
        """Get available funds and margins"""
        try:
            url = f"{self.BASE_URL}/user/get-funds-and-margin"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json().get("data", {})
        except Exception as e:
            logger.error(f"Error getting funds: {str(e)}")
            raise NetworkError(f"Failed to get funds: {str(e)}")
    
    def get_instruments(self, exchange: str = "NSE_FO") -> List[Dict[str, Any]]:
        """Get all instruments"""
        try:
            # Upstox provides instrument files for download
            # This would need to be implemented based on their CSV format
            # For now, returning empty list as placeholder
            logger.warning("Upstox get_instruments needs implementation with CSV parsing")
            return []
        except Exception as e:
            logger.error(f"Error getting instruments: {str(e)}")
            raise NetworkError(f"Failed to get instruments: {str(e)}")
    
    def get_quote(self, instruments: List[str]) -> Dict[str, Any]:
        """Get market quotes"""
        try:
            url = f"{self.BASE_URL}/market-quote/quotes"
            params = {"instrument_key": ",".join(instruments)}
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json().get("data", {})
        except Exception as e:
            logger.error(f"Error getting quote: {str(e)}")
            raise NetworkError(f"Failed to get quote: {str(e)}")
    
    def get_ltp(self, instruments: List[str]) -> Dict[str, float]:
        """Get last traded price"""
        try:
            url = f"{self.BASE_URL}/market-quote/ltp"
            params = {"instrument_key": ",".join(instruments)}
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            data = response.json().get("data", {})
            return {k: v.get("last_price", 0) for k, v in data.items()}
        except Exception as e:
            logger.error(f"Error getting LTP: {str(e)}")
            raise NetworkError(f"Failed to get LTP: {str(e)}")
    
    def get_market_depth(self, instrument: str) -> Dict[str, Any]:
        """Get market depth"""
        try:
            quotes = self.get_quote([instrument])
            if instrument in quotes:
                depth = quotes[instrument].get("depth", {})
                return depth
            return {"buy": [], "sell": []}
        except Exception as e:
            logger.error(f"Error getting market depth: {str(e)}")
            raise NetworkError(f"Failed to get market depth: {str(e)}")
    
    def get_historical_data(
        self,
        instrument_key: str,
        from_date: datetime,
        to_date: datetime,
        interval: str = "1minute"
    ) -> List[Dict[str, Any]]:
        """Get historical candle data"""
        try:
            url = f"{self.BASE_URL}/historical-candle/{instrument_key}/{interval}/{to_date.strftime('%Y-%m-%d')}/{from_date.strftime('%Y-%m-%d')}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            candles = response.json().get("data", {}).get("candles", [])
            # Convert to dict format
            result = []
            for candle in candles:
                result.append({
                    "date": candle[0],
                    "open": candle[1],
                    "high": candle[2],
                    "low": candle[3],
                    "close": candle[4],
                    "volume": candle[5]
                })
            return result
        except Exception as e:
            logger.error(f"Error getting historical data: {str(e)}")
            raise NetworkError(f"Failed to get historical data: {str(e)}")
    
    def place_order(
        self,
        instrument_key: str,
        transaction_type: str,
        quantity: int,
        order_type: str,
        price: Optional[float] = None,
        product: str = "I",  # I for intraday, D for delivery
        variety: str = "simple"
    ) -> Dict[str, Any]:
        """Place an order"""
        try:
            url = f"{self.BASE_URL}/order/place"
            data = {
                "instrument_token": instrument_key,
                "quantity": quantity,
                "transaction_type": transaction_type.upper(),
                "order_type": order_type.upper(),
                "product": product,
                "validity": "DAY"
            }
            
            if price is not None and order_type.upper() == "LIMIT":
                data["price"] = price
            
            response = requests.post(url, json=data, headers=self.headers)
            response.raise_for_status()
            
            return response.json().get("data", {})
        except Exception as e:
            logger.error(f"Error placing order: {str(e)}")
            raise OrderError(f"Failed to place order: {str(e)}")
    
    def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        order_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Modify an existing order"""
        try:
            url = f"{self.BASE_URL}/order/modify"
            data = {"order_id": order_id}
            
            if quantity is not None:
                data["quantity"] = quantity
            if price is not None:
                data["price"] = price
            if order_type is not None:
                data["order_type"] = order_type.upper()
            
            response = requests.put(url, json=data, headers=self.headers)
            response.raise_for_status()
            
            return response.json().get("data", {})
        except Exception as e:
            logger.error(f"Error modifying order: {str(e)}")
            raise OrderError(f"Failed to modify order: {str(e)}")
    
    def cancel_order(self, order_id: str, variety: str = "simple") -> Dict[str, Any]:
        """Cancel an order"""
        try:
            url = f"{self.BASE_URL}/order/cancel"
            data = {"order_id": order_id}
            
            response = requests.delete(url, json=data, headers=self.headers)
            response.raise_for_status()
            
            return response.json().get("data", {})
        except Exception as e:
            logger.error(f"Error cancelling order: {str(e)}")
            raise OrderError(f"Failed to cancel order: {str(e)}")
    
    def get_orders(self) -> List[Dict[str, Any]]:
        """Get all orders"""
        try:
            url = f"{self.BASE_URL}/order/retrieve-all"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json().get("data", [])
        except Exception as e:
            logger.error(f"Error getting orders: {str(e)}")
            raise NetworkError(f"Failed to get orders: {str(e)}")
    
    def get_order_history(self, order_id: str) -> List[Dict[str, Any]]:
        """Get order history"""
        try:
            url = f"{self.BASE_URL}/order/history"
            params = {"order_id": order_id}
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json().get("data", [])
        except Exception as e:
            logger.error(f"Error getting order history: {str(e)}")
            raise NetworkError(f"Failed to get order history: {str(e)}")
    
    def get_positions(self) -> Dict[str, Any]:
        """Get current positions"""
        try:
            url = f"{self.BASE_URL}/portfolio/short-term-positions"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json().get("data", {})
        except Exception as e:
            logger.error(f"Error getting positions: {str(e)}")
            raise NetworkError(f"Failed to get positions: {str(e)}")
    
    def get_holdings(self) -> List[Dict[str, Any]]:
        """Get holdings"""
        try:
            url = f"{self.BASE_URL}/portfolio/long-term-holdings"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json().get("data", [])
        except Exception as e:
            logger.error(f"Error getting holdings: {str(e)}")
            raise NetworkError(f"Failed to get holdings: {str(e)}")
    
    def connect_websocket(self, on_message_callback, instruments: List[str]):
        """Connect to Upstox WebSocket - requires separate implementation"""
        logger.warning("Upstox WebSocket implementation needed")
        # Upstox WebSocket v3 requires protobuf and separate connection logic
        # This would be implemented based on their WebSocket documentation
        pass
