"""Database-backed application settings service.

All user-configurable settings are stored in the database and managed
through the UI. Only infrastructure settings (DATABASE_URL, REDIS_URL, etc.)
remain as environment variables.
"""

import logging
from typing import Optional, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.app_settings import AppSettings, DEFAULT_APP_SETTINGS

logger = logging.getLogger(__name__)

# In-memory cache for settings to avoid DB queries on every access
_settings_cache: Dict[str, str] = {}
_cache_loaded = False


async def _load_cache(db: AsyncSession) -> None:
    """Load all settings into the in-memory cache."""
    global _settings_cache, _cache_loaded
    result = await db.execute(select(AppSettings))
    rows = result.scalars().all()
    _settings_cache = {row.key: row.value or "" for row in rows}
    _cache_loaded = True


async def seed_defaults(db: AsyncSession) -> None:
    """Seed default settings, adding any missing keys.

    On first run this populates all defaults. On subsequent runs it
    fills in any newly-added keys so the settings page never encounters
    missing values after an upgrade.
    """
    # Fetch all existing keys in one query
    result = await db.execute(select(AppSettings.key))
    existing_keys = {row[0] for row in result.all()}

    added = 0
    for item in DEFAULT_APP_SETTINGS:
        if item["key"] not in existing_keys:
            db.add(AppSettings(**item))
            added += 1

    if added:
        await db.commit()
        logger.info("Seeded %d new default application setting(s)", added)


async def ensure_cache(db: Optional[AsyncSession] = None) -> None:
    """Make sure the in-memory cache is populated."""
    global _cache_loaded
    if _cache_loaded:
        return
    if db is None:
        async with AsyncSessionLocal() as db:
            await seed_defaults(db)
            await _load_cache(db)
    else:
        await seed_defaults(db)
        await _load_cache(db)


def invalidate_cache() -> None:
    """Invalidate the in-memory settings cache (forces reload on next access)."""
    global _cache_loaded
    _cache_loaded = False
    _settings_cache.clear()


def get_setting(key: str, default: str = "") -> str:
    """Get a setting value from cache. Returns default if not found."""
    return _settings_cache.get(key, default)


def get_bool(key: str, default: bool = False) -> bool:
    """Get a boolean setting."""
    val = _settings_cache.get(key, "")
    if not val:
        return default
    return val.lower() in ("true", "1", "yes")


def get_int(key: str, default: int = 0) -> int:
    """Get an integer setting."""
    val = _settings_cache.get(key, "")
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def get_float(key: str, default: float = 0.0) -> float:
    """Get a float setting."""
    val = _settings_cache.get(key, "")
    if not val:
        return default
    try:
        return float(val)
    except ValueError:
        return default


def get_optional(key: str) -> Optional[str]:
    """Get a setting, returning None if empty."""
    val = _settings_cache.get(key, "")
    return val if val else None


def get_all_settings() -> Dict[str, str]:
    """Get a copy of all settings."""
    return dict(_settings_cache)


async def update_setting(db: AsyncSession, key: str, value: str) -> None:
    """Update a single setting in DB and cache."""
    result = await db.execute(
        select(AppSettings).where(AppSettings.key == key)
    )
    row = result.scalar_one_or_none()
    if row:
        row.value = value
    else:
        db.add(AppSettings(key=key, value=value, category="general"))
    await db.commit()
    _settings_cache[key] = value


async def update_settings_bulk(db: AsyncSession, updates: Dict[str, str]) -> None:
    """Update multiple settings at once."""
    for key, value in updates.items():
        result = await db.execute(
            select(AppSettings).where(AppSettings.key == key)
        )
        row = result.scalar_one_or_none()
        if row:
            row.value = value
        else:
            db.add(AppSettings(key=key, value=value, category="general"))
        _settings_cache[key] = value
    await db.commit()


async def get_settings_by_category(db: AsyncSession, category: str) -> Dict[str, str]:
    """Get all settings for a category."""
    await ensure_cache(db)
    result = await db.execute(
        select(AppSettings).where(AppSettings.category == category)
    )
    rows = result.scalars().all()
    return {row.key: row.value or "" for row in rows}
