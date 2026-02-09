"""Health check endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import get_settings
from app.services import app_settings as cfg

router = APIRouter()
settings = get_settings()


@router.get("/health")
async def health_check():
    """Basic health check."""
    return {"status": "healthy", "version": settings.app_version}


@router.get("/health/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Readiness check including database connectivity."""
    checks = {
        "database": False,
        "redis": False,
    }

    # Check database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass

    # Check Redis
    try:
        import redis
        r = redis.from_url(settings.redis_url)
        r.ping()
        checks["redis"] = True
    except Exception:
        pass

    all_healthy = all(checks.values())
    return {
        "status": "ready" if all_healthy else "degraded",
        "checks": checks,
    }


@router.get("/health/services")
async def service_status():
    """Check status of external service connections."""
    services = {
        "spotify": {"configured": bool(cfg.get_optional("spotify_client_id")), "connected": False},
        "lastfm": {"configured": bool(cfg.get_optional("lastfm_api_key")), "connected": False},
        "plex": {"configured": bool(cfg.get_optional("plex_url") and cfg.get_optional("plex_token")), "connected": False},
        "prowlarr": {"configured": bool(cfg.get_optional("prowlarr_url") and cfg.get_optional("prowlarr_api_key")), "connected": False},
    }

    # Test connections (done async in real implementation)
    # For now, just return configuration status

    return {"services": services}
