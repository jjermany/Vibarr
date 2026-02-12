"""Database configuration and session management."""

import asyncio
import logging
import os

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

from app.config import get_settings

settings = get_settings()

# Ensure asyncpg doesn't try to read /root/.postgresql/ SSL files when
# running as a non-root user (e.g. vibarr via supervisord).  The database
# is always local (same container) so SSL is unnecessary.
os.environ.setdefault("PGSSLMODE", "disable")

# Create async engine
engine = create_async_engine(
    settings.async_database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
Base = declarative_base()
logger = logging.getLogger(__name__)


def _is_transient_database_startup_error(exc: BaseException) -> bool:
    """Return whether an exception is likely transient during DB startup."""
    if isinstance(exc, (ConnectionRefusedError, OperationalError)):
        return True

    if isinstance(exc, DBAPIError):
        original_error = getattr(exc, "orig", None)
        if original_error is None:
            return True

        transient_error_names = {
            "CannotConnectNowError",
            "ConnectionDoesNotExistError",
            "ConnectionFailureError",
            "ConnectionRefusedError",
            "TooManyConnectionsError",
        }
        if original_error.__class__.__name__ in transient_error_names:
            return True

        message = str(original_error).lower()
        transient_message_markers = (
            "starting up",
            "in recovery mode",
            "cannot connect now",
            "connection refused",
            "the database system is starting up",
            "the database system is in recovery mode",
        )
        if any(marker in message for marker in transient_message_markers):
            return True

    return False


async def _wait_for_database(max_attempts: int = 30, retry_delay_seconds: float = 1.0) -> None:
    """Wait for the database to become available.

    In the all-in-one container, PostgreSQL and the API process are started by
    supervisord at nearly the same time. This can cause a brief startup race
    where the API attempts to connect before PostgreSQL is ready.
    """

    for attempt in range(1, max_attempts + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return
        except (ConnectionRefusedError, OperationalError, DBAPIError):
            if attempt == max_attempts:
                raise
            await asyncio.sleep(retry_delay_seconds)


async def _apply_schema_migrations(conn) -> None:
    """Apply incremental schema migrations for columns added after initial release.

    SQLAlchemy ``create_all`` only creates *new* tables; it will not alter
    existing ones.  This helper runs idempotent ``ALTER TABLE … ADD COLUMN``
    statements so that deployments upgrading from an earlier schema pick up
    any newly-declared columns.
    """
    migrations = [
        (
            "wishlist",
            "image_url",
            "ALTER TABLE wishlist ADD COLUMN image_url VARCHAR(1000)",
        ),
        (
            "users",
            "preferred_language",
            "ALTER TABLE users ADD COLUMN preferred_language VARCHAR(32)",
        ),
        (
            "users",
            "secondary_languages",
            "ALTER TABLE users ADD COLUMN secondary_languages JSON",
        ),
    ]
    for table, column, ddl in migrations:
        result = await conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :table AND column_name = :column"
            ),
            {"table": table, "column": column},
        )
        if not result.fetchone():
            await conn.execute(text(ddl))


async def init_db() -> None:
    """Initialize database tables."""
    max_attempts = 30
    initial_retry_delay_seconds = 1.0

    for attempt in range(1, max_attempts + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                await _apply_schema_migrations(conn)
            return
        except (ConnectionRefusedError, OperationalError, DBAPIError) as exc:
            if not _is_transient_database_startup_error(exc) or attempt == max_attempts:
                raise

            retry_delay = initial_retry_delay_seconds * (2 ** (attempt - 1))
            logger.warning(
                "Database initialization attempt failed; retrying",
                extra={
                    "attempt": attempt,
                    "max_attempts": max_attempts,
                    "exception_class": exc.__class__.__name__,
                    "retry_delay_seconds": retry_delay,
                },
            )
            await asyncio.sleep(retry_delay)


async def get_db() -> AsyncSession:
    """Get database session dependency."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
