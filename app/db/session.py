from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from sqlalchemy_utils import database_exists, create_database
import atexit
from contextlib import contextmanager

from app.db.config import settings
from app.core.logging_config import setup_logger

logger = setup_logger(__name__)


def create_db_and_tables():
    engine = create_engine(
        settings.DB_URL,
        poolclass=QueuePool,
        pool_size=8,  # further reduced pool size to 8 to reduce memory usage
        max_overflow=12,  # Reduced overflow capacity
        pool_timeout=15,  # Shorter timeout to fail fast
        pool_pre_ping=True,
        pool_recycle=1800,  # Recycle connections every 30 minutes
        pool_reset_on_return="commit",  # Reset connections on return
        echo_pool=False,  # Disable pool logging in production
        connect_args={
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
            "options": "-c statement_timeout=300000",  # 5-minute statement timeout
        },
    )
    if not database_exists(engine.url):
        create_database(engine.url)

    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
        conn.execute(text("SET search_path TO public"))

    return engine


engine = create_db_and_tables()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def cleanup_connections():
    """Clean up all database connections on shutdown"""
    try:
        engine.dispose()
    except Exception as e:
        logger.error(f"Error cleaning up database connections: {e}")


def get_pool_status():
    """Get current connection pool status"""
    try:
        pool = engine.pool
        return {
            "size": pool.size(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "total": pool.size() + pool.overflow(),
            "available": pool.size() - pool.checkedout(),
        }
    except Exception as e:
        logger.error(f"Error getting pool status: {e}")
        return None


def force_cleanup_connections():
    """Force cleanup of all connections - use in emergency"""
    try:
        pool = engine.pool
        pool.dispose()

    except Exception as e:
        logger.error(f"Error in forced cleanup: {e}")


def check_and_cleanup_pool():
    """Check pool status and cleanup if needed"""
    try:
        pool = engine.pool
        checked_out = pool.checkedout()
        total_connections = pool.size() + pool.overflow()

        # If more than 80% of connections are in use, force cleanup
        if checked_out > pool.size() * 0.8:
            pool.dispose()

            return True
        return False
    except Exception as e:
        logger.error(f"Error in pool cleanup check: {e}")
        return False


# Register cleanup function to run on exit
atexit.register(cleanup_connections)


@contextmanager
def get_db_context():
    """Context manager for database sessions with proper logging"""
    db = None
    try:
        db = SessionLocal()
        # Log connection acquisition
        pool = engine.pool
        checked_out = pool.checkedout()
        total = pool.size() + pool.overflow()

        yield db
    except Exception as e:
        if db:
            db.rollback()
        logger.error(f"❌ DB Error in context: {str(e)}")
        raise
    finally:
        if db:
            try:
                db.close()
                # Log connection release
                pool = engine.pool
                checked_out = pool.checkedout()

            except Exception as close_error:
                logger.error(f"❌ Error closing DB connection: {close_error}")


def get_db():
    """Dependency for FastAPI endpoints - ensures connection is closed after use"""
    db = SessionLocal()
    try:
        # Log connection acquisition
        pool = engine.pool
        checked_out = pool.checkedout()

        yield db
    except Exception as e:
        db.rollback()
        error_msg = str(e) if str(e) else repr(e)
        logger.error(f"❌ FastAPI DB Error: {error_msg}", exc_info=True)
        raise
    finally:
        # Explicitly close the session and connection
        try:
            db.close()
            # Log connection release
            pool = engine.pool
            checked_out = pool.checkedout()

        except Exception as close_error:
            logger.error(f"❌ Error closing FastAPI database session: {close_error}")
