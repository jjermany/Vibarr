"""Database configuration and session management."""

import asyncio
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


async def init_db() -> None:
    """Initialize database tables."""
    await _wait_for_database()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """Get database session dependency."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
