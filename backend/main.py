"""Main FastAPI application - Configuration via .env file"""
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from backend.config import settings
from backend.api import (
    broker, webhook, orders,
    websocket, paper_trading, config, middleware
)
from backend.api import market_time
from backend.api import live_trading_v2
from backend.broker.kite.client import KiteBroker
from backend.utils.performance import PerformanceMiddleware
from backend.middleware.error_handler import register_error_handlers
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler('otrade.log')]
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    redirect_slashes=False
)

# Register error handlers
register_error_handlers(app)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add performance monitoring middleware
app.add_middleware(PerformanceMiddleware, slow_threshold_ms=200)

# Include routers
app.include_router(config.router)
app.include_router(broker.router)
app.include_router(orders.router)
app.include_router(websocket.router)
app.include_router(market_time.router)
app.include_router(middleware.router)
app.include_router(webhook.router)
app.include_router(paper_trading.router)
app.include_router(live_trading_v2.router)

from backend.api import portfolio
app.include_router(portfolio.router)


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    try:
        from backend.services.middleware_helper import get_middleware_instance
        
        # Check if broker has access token configured
        broker_type = settings.BROKER_TYPE.lower()
        access_token = None
        
        if broker_type == "kite":
            access_token = settings.KITE_ACCESS_TOKEN
        elif broker_type == "upstox":
            access_token = settings.UPSTOX_ACCESS_TOKEN
        
        if access_token:
            try:
                middleware = get_middleware_instance()
                import asyncio
                loop = asyncio.get_event_loop()
                loop.create_task(middleware.start())
                logger.info("✓ Unified broker middleware initialized")
            except Exception as e:
                logger.error(f"Error initializing middleware: {e}")
        else:
            logger.info("No access token configured in .env - broker not authenticated yet")
    except Exception as e:
        logger.error(f"Error during startup: {e}")
    
    logger.info("Application startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down application")
    
    try:
        from backend.services.middleware_helper import get_middleware_instance, reset_middleware
        
        try:
            middleware = get_middleware_instance()
            if middleware.running:
                await middleware.stop()
                logger.info("✓ Unified broker middleware stopped")
        except Exception as e:
            logger.warning(f"Middleware not running or already stopped: {e}")
        finally:
            reset_middleware()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    
    logger.info("Application shutdown complete")


@app.get("/")
async def root():
    return {"name": settings.APP_NAME, "version": settings.APP_VERSION, "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/callback")
async def kite_callback(request_token: str = Query(...), action: str = Query(None)):
    logger.info(f"Callback received - request_token: {request_token}")
    
    frontend_url = f"http://{settings.HOST}:{settings.FRONTEND_PORT}"
    
    if not settings.KITE_API_KEY or not settings.KITE_API_SECRET:
        logger.error("Kite broker config not found in .env")
        return RedirectResponse(
            url=f"{frontend_url}/settings?auth=error&message=Broker+not+configured",
            status_code=302
        )
    
    try:
        kite_broker = KiteBroker(
            api_key=settings.KITE_API_KEY,
            api_secret=settings.KITE_API_SECRET
        )
        
        session_data = kite_broker.generate_session(
            request_token=request_token,
            api_secret=settings.KITE_API_SECRET
        )
        
        access_token = session_data["access_token"]
        user_id = session_data.get("user_id", "")
        
        logger.info(f"Successfully authenticated {user_id} with Kite")
        
        # Update .env file with new access token
        from pathlib import Path
        env_path = Path(__file__).parent.parent / '.env'
        
        if env_path.exists():
            with open(env_path, 'r') as f:
                lines = f.readlines()
            
            new_lines = []
            found_token = False
            
            for line in lines:
                if line.strip().startswith('KITE_ACCESS_TOKEN='):
                    new_lines.append(f"KITE_ACCESS_TOKEN={access_token}\n")
                    found_token = True
                else:
                    new_lines.append(line)
            
            if not found_token:
                new_lines.append(f"\nKITE_ACCESS_TOKEN={access_token}\n")
            
            with open(env_path, 'w') as f:
                f.writelines(new_lines)
            
            # Reload settings
            from dotenv import load_dotenv
            load_dotenv(override=True)
        
        return RedirectResponse(
            url=f"{frontend_url}/settings?auth=success&message=Authentication+successful",
            status_code=302
        )
    except Exception as e:
        logger.error(f"Error during callback: {str(e)}")
        return RedirectResponse(
            url=f"{frontend_url}/settings?auth=error&message={str(e)}",
            status_code=302
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
