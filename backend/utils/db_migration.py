"""Database migration utilities to fix schema mismatches"""
import logging
import time
from sqlalchemy import inspect, text
from backend.database import engine
from backend.models import Base

logger = logging.getLogger(__name__)

# Current schema version - increment this when making schema changes
CURRENT_SCHEMA_VERSION = "v1.0.0"


def is_migration_applied(version: str) -> bool:
    """Check if a migration version has already been applied"""
    from sqlalchemy import inspect
    from backend.database import SessionLocal
    
    # Check if schema_migrations table exists
    inspector = inspect(engine)
    if "schema_migrations" not in inspector.get_table_names():
        return False
    
    # Check if this version is already applied
    db = SessionLocal()
    try:
        from backend.models import SchemaMigration
        existing = db.query(SchemaMigration).filter(
            SchemaMigration.version == version,
            SchemaMigration.status == "applied"
        ).first()
        return existing is not None
    except Exception as e:
        logger.debug(f"Migration check error (table may not exist yet): {e}")
        return False
    finally:
        db.close()


def record_migration(version: str, description: str, execution_time_ms: int, status: str = "applied", error: str = None):
    """Record a migration in the schema_migrations table"""
    from backend.database import SessionLocal
    from backend.models import SchemaMigration
    from datetime import datetime
    
    db = SessionLocal()
    try:
        migration = SchemaMigration(
            version=version,
            description=description,
            applied_at=datetime.utcnow(),
            status=status,
            execution_time_ms=execution_time_ms,
            error_message=error
        )
        db.add(migration)
        db.commit()
        logger.info(f"✓ Migration {version} recorded as {status}")
    except Exception as e:
        logger.error(f"Failed to record migration {version}: {e}")
        db.rollback()
    finally:
        db.close()


def get_table_columns(table_name: str) -> set:
    """Get existing columns in a table"""
    inspector = inspect(engine)
    try:
        columns = inspector.get_columns(table_name)
        return {col['name'] for col in columns}
    except Exception:
        return set()


def get_model_columns(model) -> dict:
    """Get columns defined in SQLAlchemy model with their types"""
    columns = {}
    for column in model.__table__.columns:
        columns[column.name] = column
    return columns


def migrate_table_schema(model):
    """Migrate a single table to match its model definition"""
    table_name = model.__tablename__
    
    # Check if table exists
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        logger.info(f"Table {table_name} doesn't exist - will be created by init_db()")
        return
    
    # Get existing and expected columns
    existing_columns = get_table_columns(table_name)
    model_columns = get_model_columns(model)
    
    logger.debug(f"Checking {table_name}: {len(existing_columns)} existing, {len(model_columns)} expected")
    
    # Find missing columns
    missing_columns = set(model_columns.keys()) - existing_columns
    
    if not missing_columns:
        logger.info(f"✓ Table {table_name} schema is up to date")
        return
    
    logger.info(f"Migrating table {table_name}: adding {len(missing_columns)} missing columns")
    
    # Add missing columns
    with engine.connect() as conn:
        for col_name in missing_columns:
            column = model_columns[col_name]
            
            # Build column definition
            col_type = column.type.compile(engine.dialect)
            nullable = "NULL" if column.nullable else "NOT NULL"
            default = ""
            
            # Handle default values
            if column.default is not None:
                if column.default.is_scalar:
                    default_value = column.default.arg
                    if isinstance(default_value, str):
                        default = f"DEFAULT '{default_value}'"
                    elif isinstance(default_value, bool):
                        default = f"DEFAULT {1 if default_value else 0}"
                    elif default_value is None:
                        default = "DEFAULT NULL"
                    else:
                        default = f"DEFAULT {default_value}"
            
            # For SQLite, we need to handle NULL defaults specially
            if column.nullable and not default:
                default = "DEFAULT NULL"
            
            try:
                alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type} {default}"
                logger.info(f"Executing: {alter_sql}")
                conn.execute(text(alter_sql))
                conn.commit()
                logger.info(f"✓ Added column {col_name} to {table_name}")
            except Exception as e:
                logger.error(f"✗ Failed to add column {col_name} to {table_name}: {e}")
                conn.rollback()


def migrate_all_tables():
    """Migrate all tables to match their model definitions"""
    
    # Check if migration already applied
    if is_migration_applied(CURRENT_SCHEMA_VERSION):
        logger.info(f"✓ Schema version {CURRENT_SCHEMA_VERSION} already applied - skipping migration")
        return
    
    logger.info(f"Starting database schema migration to version {CURRENT_SCHEMA_VERSION}...")
    start_time = time.time()
    
    # Import all models to ensure they're registered with Base
    from backend.models import (
        TradingConfig, BrokerConfig, Instrument,
        PaperTrade, PaperTradingMarketData, PaperTradingAlert,
        LiveTrade, LiveTradingMarketData, LiveTradingAlert, LiveTradingSignal,
        HistoricalData, InstrumentDownloadLog, SchemaMigration, LiveTradingState
    )
    
    # List of all models to check
    models = [
        TradingConfig,
        BrokerConfig,
        Instrument,
        PaperTrade,
        PaperTradingMarketData,
        PaperTradingAlert,
        LiveTrade,
        LiveTradingState,
        LiveTradingMarketData,
        LiveTradingAlert,
        LiveTradingSignal,
        HistoricalData,
        InstrumentDownloadLog,
        SchemaMigration
    ]
    
    # Migrate each table
    migration_success = True
    for model in models:
        try:
            migrate_table_schema(model)
        except Exception as e:
            logger.error(f"Error migrating {model.__tablename__}: {e}")
            migration_success = False
    
    execution_time_ms = int((time.time() - start_time) * 1000)
    
    if migration_success:
        logger.info(f"✓ Database schema migration complete in {execution_time_ms}ms")
        record_migration(
            version=CURRENT_SCHEMA_VERSION,
            description="Auto-migration of all tables to match current schema",
            execution_time_ms=execution_time_ms,
            status="applied"
        )
    else:
        logger.error(f"✗ Database schema migration completed with errors in {execution_time_ms}ms")
        record_migration(
            version=CURRENT_SCHEMA_VERSION,
            description="Auto-migration of all tables to match current schema",
            execution_time_ms=execution_time_ms,
            status="failed",
            error="One or more table migrations failed - check logs"
        )


def verify_database_schema():
    """Verify database schema matches models and report any issues"""
    logger.info("Verifying database schema...")
    
    from backend.models import (
        TradingConfig, BrokerConfig, Instrument,
        PaperTrade, PaperTradingMarketData, PaperTradingAlert,
        LiveTrade, LiveTradingMarketData, LiveTradingAlert, LiveTradingSignal,
        HistoricalData
    )
    
    models = [
        TradingConfig, BrokerConfig, Instrument,
        PaperTrade, PaperTradingMarketData, PaperTradingAlert,
        LiveTrade, LiveTradingMarketData, LiveTradingAlert, LiveTradingSignal,
        HistoricalData
    ]
    
    issues_found = False
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    for model in models:
        table_name = model.__tablename__
        
        if table_name not in existing_tables:
            logger.warning(f"⚠ Table {table_name} does not exist")
            issues_found = True
            continue
        
        existing_columns = get_table_columns(table_name)
        model_columns = get_model_columns(model)
        missing_columns = set(model_columns.keys()) - existing_columns
        
        if missing_columns:
            logger.warning(f"⚠ Table {table_name} is missing columns: {missing_columns}")
            issues_found = True
        else:
            logger.debug(f"✓ Table {table_name} schema is correct")
    
    if not issues_found:
        logger.info("✓ Database schema verification passed")
    else:
        logger.warning("⚠ Database schema issues found")
    
    return not issues_found
