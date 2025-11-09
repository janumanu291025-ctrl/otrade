"""Main FastAPI application"""
from fastapi import FastAPI, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from backend.config import settings
from backend.database import init_db, get_db
from backend.api import (
    broker, webhook, orders,
    websocket, paper_trading, config, middleware
)
from backend.api import market_time
from backend.api import live_trading_v2
from backend.models import BrokerConfig
from backend.broker.kite.client import KiteBroker
from backend.utils.performance import PerformanceMiddleware
from backend.middleware.error_handler import register_error_handlers
from datetime import datetime, timedelta
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('otrade.log')
    ]
)

logger = logging.getLogger(__name__)


async def auto_download_instruments_if_needed():
    """Auto-download instruments on startup if not already downloaded today"""
    from datetime import date
    from sqlalchemy import func
    from backend.models import Instrument, InstrumentDownloadLog
    
    db = next(get_db())
    try:
        # Check download log for today's automatic download
        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())
        
        existing_download = db.query(InstrumentDownloadLog).filter(
            InstrumentDownloadLog.download_date >= today_start,
            InstrumentDownloadLog.download_type == "auto",
            InstrumentDownloadLog.status == "completed"
        ).first()
        
        if existing_download:
            logger.info(
                f"✓ Instruments already auto-downloaded today at "
                f"{existing_download.download_date.strftime('%H:%M:%S')} "
                f"({existing_download.instrument_count} instruments)"
            )
            return
        
        # Check if broker is authenticated
        broker_config = db.query(BrokerConfig).filter(
            BrokerConfig.broker_type == "kite",
            BrokerConfig.is_active == True
        ).first()
        
        if not broker_config or not broker_config.access_token:
            logger.warning("Broker not authenticated - skipping instrument download")
            return
        
        # Download instruments
        logger.info("🔄 Auto-downloading instruments from broker...")
        download_start = datetime.now()
        
        try:
            broker_client = KiteBroker(
                api_key=broker_config.api_key,
                api_secret=broker_config.api_secret,
                access_token=broker_config.access_token
            )
            
            instruments_data = broker_client.get_instruments()
            
            # Clear existing instruments
            db.query(Instrument).delete()
            
            # Batch insert new instruments
            instruments_to_add = []
            for inst_data in instruments_data:
                # Handle both dict and object formats
                if isinstance(inst_data, dict):
                    instrument = Instrument(
                        instrument_token=str(inst_data.get("instrument_token")),
                        exchange_token=str(inst_data.get("exchange_token")) if inst_data.get("exchange_token") else None,
                        tradingsymbol=inst_data.get("tradingsymbol"),
                        name=inst_data.get("name"),
                        last_price=inst_data.get("last_price", 0.0),
                        expiry=str(inst_data.get("expiry")) if inst_data.get("expiry") else None,
                        strike=inst_data.get("strike"),
                        tick_size=inst_data.get("tick_size"),
                        lot_size=inst_data.get("lot_size"),
                        instrument_type=inst_data.get("instrument_type"),
                        segment=inst_data.get("segment"),
                        exchange=inst_data.get("exchange")
                    )
                else:
                    instrument = Instrument(
                        instrument_token=str(inst_data.instrument_token),
                        exchange_token=str(inst_data.exchange_token) if inst_data.exchange_token else None,
                        tradingsymbol=inst_data.tradingsymbol,
                        name=inst_data.name,
                        last_price=inst_data.last_price if hasattr(inst_data, 'last_price') else 0.0,
                        expiry=str(inst_data.expiry) if inst_data.expiry else None,
                        strike=inst_data.strike if hasattr(inst_data, 'strike') else None,
                        tick_size=inst_data.tick_size if hasattr(inst_data, 'tick_size') else None,
                        lot_size=inst_data.lot_size if hasattr(inst_data, 'lot_size') else None,
                        instrument_type=inst_data.instrument_type if hasattr(inst_data, 'instrument_type') else None,
                        segment=inst_data.segment if hasattr(inst_data, 'segment') else None,
                        exchange=inst_data.exchange
                    )
                instruments_to_add.append(instrument)
            
            db.bulk_save_objects(instruments_to_add)
            
            # Record successful download in log
            download_log = InstrumentDownloadLog(
                download_date=download_start,
                instrument_count=len(instruments_to_add),
                download_type="auto",
                source="broker_api",
                status="completed"
            )
            db.add(download_log)
            db.commit()
            
            count = len(instruments_to_add)
            duration = (datetime.now() - download_start).total_seconds()
            logger.info(f"✓ Auto-downloaded {count} instruments successfully in {duration:.2f}s")
            
        except Exception as e:
            db.rollback()
            
            # Record failed download in log
            download_log = InstrumentDownloadLog(
                download_date=download_start,
                instrument_count=0,
                download_type="auto",
                source="broker_api",
                status="failed",
                error_message=str(e)
            )
            db.add(download_log)
            db.commit()
            
            logger.error(f"Failed to auto-download instruments: {str(e)}")
    finally:
        db.close()


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG
)

# Register error handlers (must be done before adding middleware)
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
app.add_middleware(
    PerformanceMiddleware,
    slow_threshold_ms=200  # Log requests slower than 200ms
)

# Include routers
app.include_router(config.router)
app.include_router(broker.router)
app.include_router(orders.router)  # Consolidated order management API
app.include_router(websocket.router)
app.include_router(market_time.router)
app.include_router(middleware.router)
app.include_router(webhook.router)
app.include_router(paper_trading.router)
app.include_router(live_trading_v2.router)  # Live Trading V2 API

# Portfolio router - Consolidated positions and holdings API
from backend.api import portfolio
app.include_router(portfolio.router)

# Positions router disabled - use consolidated portfolio API instead
# from backend.api import positions
# app.include_router(positions.router)


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # Initialize database
    init_db()
    logger.info("Database initialized")
    
    # Run database migrations to fix any schema mismatches (runs only once per version)
    try:
        from backend.utils.db_migration import migrate_all_tables, verify_database_schema
        migrate_all_tables()
        verify_database_schema()
    except Exception as e:
        logger.error(f"Database migration error: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    # Auto-download instruments if not done today (runs only once per day)
    await auto_download_instruments_if_needed()
    
    # Initialize unified broker middleware (market-time-aware data service)
    db = next(get_db())
    try:
        from backend.services.market_calendar import is_market_open
        from backend.services.unified_broker_middleware import get_unified_broker_middleware
        from backend.broker.factory import get_broker_client
        
        # Get active broker
        broker_config = db.query(BrokerConfig).filter(
            BrokerConfig.broker_type == "kite",
            BrokerConfig.is_active == True
        ).first()
        
        if broker_config and broker_config.access_token:
            try:
                broker_client = get_broker_client(db, raise_exception=False)
                if broker_client:
                    # Initialize middleware
                    middleware = get_unified_broker_middleware(broker_client, db)
                    
                    # Start middleware (handles webhook/API switching based on market time)
                    import asyncio
                    loop = asyncio.get_event_loop()
                    loop.create_task(middleware.start())
                    
                    logger.info("✓ Unified broker middleware initialized (replaces old LTP processor & market data stream)")
                else:
                    logger.warning("Broker client not available - middleware not started")
            except Exception as e:
                logger.error(f"Error initializing middleware: {e}")
        else:
            logger.info("No active broker configured - middleware will be initialized on first use")
    finally:
        db.close()
    
    logger.info("Application startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down application")
    
    # Stop unified broker middleware
    try:
        from backend.services.unified_broker_middleware import get_unified_broker_middleware, reset_middleware
        from backend.database import SessionLocal
        
        # Get middleware instance if it exists
        db = SessionLocal()
        try:
            from backend.broker.factory import get_broker_client
            broker_client = get_broker_client(db, raise_exception=False)
            if broker_client:
                middleware = get_unified_broker_middleware(broker_client, db)
                if middleware.running:
                    await middleware.stop()
                    logger.info("✓ Unified broker middleware stopped")
        except Exception as e:
            logger.error(f"Error stopping middleware: {e}")
        finally:
            db.close()
            reset_middleware()  # Clear singleton
    except Exception as e:
        logger.error(f"Error during middleware shutdown: {e}")
    
    logger.info("Application shutdown complete")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/callback")
async def kite_callback(
    request_token: str = Query(...),
    action: str = Query(None),
    type: str = Query(None),
    status: str = Query(None),
    db: Session = Depends(get_db)
):
    """
    Handle Kite Connect OAuth callback
    This endpoint is registered as the redirect URL in Kite Connect app settings
    """
    logger.info(f"Callback received - request_token: {request_token}, status: {status}")
    
    # Get frontend URL from settings
    frontend_url = f"http://{settings.HOST}:{settings.FRONTEND_PORT}"
    
    # Get Kite broker config
    config = db.query(BrokerConfig).filter(
        BrokerConfig.broker_type == "kite"
    ).first()
    
    if not config:
        logger.error("Kite broker config not found")
        return RedirectResponse(
            url=f"{frontend_url}/settings?auth=error&message=Broker+not+configured",
            status_code=302
        )
    
    try:
        # Initialize Kite broker client
        kite_broker = KiteBroker(
            api_key=config.api_key,
            api_secret=config.api_secret
        )
        
        # Exchange request token for access token
        token_data = kite_broker.get_access_token(request_token)
        
        # Update config with access token in database
        access_token = token_data.get("access_token")
        user_id = token_data.get("user_id")
        
        config.access_token = access_token
        config.user_id = user_id
        config.is_active = True
        config.updated_at = datetime.now()
        
        db.commit()
        
        # Update .env file with access token
        from pathlib import Path
        env_path = Path(".env")
        if env_path.exists():
            # Read current .env content
            with open(env_path, 'r') as f:
                lines = f.readlines()
            
            # Update or add KITE_ACCESS_TOKEN and KITE_USER_ID
            access_token_found = False
            user_id_found = False
            updated_lines = []
            
            for line in lines:
                if line.startswith('KITE_ACCESS_TOKEN='):
                    updated_lines.append(f'KITE_ACCESS_TOKEN={access_token}\n')
                    access_token_found = True
                elif line.startswith('KITE_USER_ID='):
                    updated_lines.append(f'KITE_USER_ID={user_id}\n')
                    user_id_found = True
                else:
                    updated_lines.append(line)
            
            # If tokens weren't found, add them after KITE_API_SECRET
            if not access_token_found or not user_id_found:
                final_lines = []
                for i, line in enumerate(updated_lines):
                    final_lines.append(line)
                    if line.startswith('KITE_API_SECRET='):
                        if not access_token_found:
                            final_lines.append(f'KITE_ACCESS_TOKEN={access_token}\n')
                        if not user_id_found:
                            # Check if next line is KITE_ACCESS_TOKEN or KITE_USER_ID
                            if i + 1 < len(updated_lines):
                                next_line = updated_lines[i + 1]
                                if not next_line.startswith('KITE_ACCESS_TOKEN=') and not next_line.startswith('KITE_USER_ID='):
                                    final_lines.append(f'KITE_USER_ID={user_id}\n')
                            else:
                                final_lines.append(f'KITE_USER_ID={user_id}\n')
                updated_lines = final_lines
            
            # Write back to .env
            with open(env_path, 'w') as f:
                f.writelines(updated_lines)
            
            logger.info(f"Updated .env file with access token and user_id")
        
        logger.info(f"Authentication successful for user: {user_id}")
        
        # Redirect to frontend with success
        return RedirectResponse(
            url=f"{frontend_url}/settings?auth=success&broker=kite",
            status_code=302
        )
    except Exception as e:
        logger.error(f"Error in callback: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return RedirectResponse(
            url=f"{frontend_url}/settings?auth=error&message={str(e)}",
            status_code=302
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG
    )
