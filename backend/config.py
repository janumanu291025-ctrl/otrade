from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "OTrade"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    HOST: str = "127.0.0.1"
    BACKEND_PORT: int = 8000
    FRONTEND_PORT: int = 3000
    
    # Database
    DATABASE_URL: str = "sqlite:///./otrade.db"
    
    # Broker
    BROKER_TYPE: str = "kite"  # kite or upstox
    
    # Kite Connect
    KITE_API_KEY: Optional[str] = None
    KITE_API_SECRET: Optional[str] = None
    KITE_ACCESS_TOKEN: Optional[str] = None
    KITE_USER_ID: Optional[str] = None
    KITE_PASSWORD: Optional[str] = None
    KITE_REDIRECT_URL: Optional[str] = None
    KITE_POSTBACK_URL: Optional[str] = None
    
    # Upstox
    UPSTOX_API_KEY: Optional[str] = None
    UPSTOX_API_SECRET: Optional[str] = None
    UPSTOX_ACCESS_TOKEN: Optional[str] = None
    UPSTOX_USER_ID: Optional[str] = None
    UPSTOX_PASSWORD: Optional[str] = None
    
    # Trading Settings
    MAX_FUND_PERCENTAGE_PER_TRADE: float = 16.0
    DEFAULT_SELL_TARGET_PERCENTAGE: float = 2.5
    DEFAULT_STRIKE_GAP_POINTS: int = 100
    MARKET_DATA_REFRESH_INTERVAL: int = 1
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    ALLOWED_ORIGINS: str = ""
    
    @property
    def allowed_origins_list(self) -> list:
        """Generate CORS origins dynamically based on configured ports"""
        if self.ALLOWED_ORIGINS:
            # If explicitly set in .env, use that
            return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]
        
        # Otherwise, generate from HOST and FRONTEND_PORT
        origins = [
            f"http://localhost:{self.FRONTEND_PORT}",
            f"http://127.0.0.1:{self.FRONTEND_PORT}",
            f"http://{self.HOST}:{self.FRONTEND_PORT}"
        ]
        # Remove duplicates
        return list(set(origins))
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
