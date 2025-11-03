"""
Migration script to add new columns to live_trading_signals table
"""
from sqlalchemy import text
from backend.database import SessionLocal, engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_signal_table():
    """Add new columns to live_trading_signals table"""
    db = SessionLocal()
    
    migrations = [
        # Add signal_date for filtering
        "ALTER TABLE live_trading_signals ADD COLUMN IF NOT EXISTS signal_date TIMESTAMP",
        "CREATE INDEX IF NOT EXISTS idx_live_signals_config_date ON live_trading_signals(config_id, signal_date)",
        
        # Add instrument_token
        "ALTER TABLE live_trading_signals ADD COLUMN IF NOT EXISTS instrument_token VARCHAR(50)",
        
        # Add option_type
        "ALTER TABLE live_trading_signals ADD COLUMN IF NOT EXISTS option_type VARCHAR(10)",
        "CREATE INDEX IF NOT EXISTS idx_live_signals_option_type ON live_trading_signals(option_type)",
        
        # Add strike_price
        "ALTER TABLE live_trading_signals ADD COLUMN IF NOT EXISTS strike_price FLOAT",
        
        # Add entry details
        "ALTER TABLE live_trading_signals ADD COLUMN IF NOT EXISTS buy_price FLOAT",
        "ALTER TABLE live_trading_signals ADD COLUMN IF NOT EXISTS quantity INTEGER",
        
        # Add exit details
        "ALTER TABLE live_trading_signals ADD COLUMN IF NOT EXISTS sell_time TIMESTAMP",
        "ALTER TABLE live_trading_signals ADD COLUMN IF NOT EXISTS sell_price FLOAT",
        
        # Add trade outcome
        "ALTER TABLE live_trading_signals ADD COLUMN IF NOT EXISTS realized_pnl FLOAT DEFAULT 0.0",
        "ALTER TABLE live_trading_signals ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'open'",
        "CREATE INDEX IF NOT EXISTS idx_live_signals_status ON live_trading_signals(status)",
        
        # Add exit_reason
        "ALTER TABLE live_trading_signals ADD COLUMN IF NOT EXISTS exit_reason VARCHAR(50)",
        
        # Add trade_id link
        "ALTER TABLE live_trading_signals ADD COLUMN IF NOT EXISTS trade_id INTEGER",
        "ALTER TABLE live_trading_signals ADD CONSTRAINT fk_signal_trade FOREIGN KEY (trade_id) REFERENCES live_trades(id) ON DELETE SET NULL",
        
        # Update signal_date from timestamp for existing records
        "UPDATE live_trading_signals SET signal_date = timestamp WHERE signal_date IS NULL",
        
        # Make signal_type indexed
        "CREATE INDEX IF NOT EXISTS idx_live_signals_signal_type ON live_trading_signals(signal_type)",
        
        # Make trigger indexed
        "CREATE INDEX IF NOT EXISTS idx_live_signals_trigger ON live_trading_signals(trigger)",
        
        # Update index on timestamp
        "CREATE INDEX IF NOT EXISTS idx_live_signals_timestamp ON live_trading_signals(timestamp)",
    ]
    
    try:
        for migration_sql in migrations:
            try:
                logger.info(f"Executing: {migration_sql[:80]}...")
                db.execute(text(migration_sql))
                db.commit()
                logger.info("✓ Success")
            except Exception as e:
                logger.warning(f"Migration step failed (may already exist): {e}")
                db.rollback()
        
        logger.info("✓ All migrations completed successfully")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("Starting live_trading_signals table migration...")
    migrate_signal_table()
    logger.info("Migration complete!")
