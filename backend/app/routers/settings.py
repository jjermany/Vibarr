"""Settings and configuration endpoints for download automation."""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.quality_profile import QualityProfile, DEFAULT_PROFILES
from app.services.download_client import download_client_service
from app.services.beets import beets_service

router = APIRouter()
settings = get_settings()


# --- Pydantic Schemas ---

class DownloadSettingsResponse(BaseModel):
    auto_download_enabled: bool
    auto_download_confidence_threshold: float
    preferred_quality: str
    max_concurrent_downloads: int
    download_path: str
    completed_download_path: str

class DownloadSettingsUpdate(BaseModel):
    auto_download_enabled: Optional[bool] = None
    auto_download_confidence_threshold: Optional[float] = None
    preferred_quality: Optional[str] = None
    max_concurrent_downloads: Optional[int] = None

class QBittorrentSettingsResponse(BaseModel):
    configured: bool
    url: Optional[str] = None
    username: str
    category: str
    connected: bool = False
    version: Optional[str] = None

class BeetsSettingsResponse(BaseModel):
    enabled: bool
    available: bool
    config_path: str
    library_path: str
    auto_import: bool
    move_files: bool
    version: Optional[str] = None

class QualityProfileResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    is_default: bool
    preferred_formats: list
    min_quality: str
    max_size_mb: int
    min_seeders: int
    prefer_well_seeded: bool
    format_match_weight: float
    seeder_weight: float

    class Config:
        from_attributes = True

class QualityProfileCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_default: bool = False
    preferred_formats: List[str] = ["flac", "320", "v0"]
    min_quality: str = "any"
    max_size_mb: int = 0
    min_seeders: int = 1
    prefer_well_seeded: bool = True
    format_match_weight: float = 30.0
    seeder_weight: float = 15.0

class QualityProfileUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_default: Optional[bool] = None
    preferred_formats: Optional[List[str]] = None
    min_quality: Optional[str] = None
    max_size_mb: Optional[int] = None
    min_seeders: Optional[int] = None
    prefer_well_seeded: Optional[bool] = None
    format_match_weight: Optional[float] = None
    seeder_weight: Optional[float] = None

class ServiceStatusResponse(BaseModel):
    prowlarr: dict
    qbittorrent: dict
    beets: dict


# --- Download Settings ---

@router.get("/download", response_model=DownloadSettingsResponse)
async def get_download_settings():
    """Get current download automation settings."""
    return DownloadSettingsResponse(
        auto_download_enabled=settings.auto_download_enabled,
        auto_download_confidence_threshold=settings.auto_download_confidence_threshold,
        preferred_quality=settings.preferred_quality,
        max_concurrent_downloads=settings.max_concurrent_downloads,
        download_path=settings.download_path,
        completed_download_path=settings.completed_download_path,
    )


# --- Service Status ---

@router.get("/services", response_model=ServiceStatusResponse)
async def get_service_status():
    """Get status of all download-related services."""
    # Prowlarr
    from app.services.prowlarr import prowlarr_service
    prowlarr_connected = False
    if prowlarr_service.is_available:
        prowlarr_connected = await prowlarr_service.test_connection()

    # qBittorrent
    qbit_connected = False
    qbit_version = None
    if download_client_service.is_configured:
        qbit_connected = await download_client_service.test_connection()
        if qbit_connected:
            qbit_version = await download_client_service.get_version()

    # Beets
    beets_info = await beets_service.test_connection()

    return ServiceStatusResponse(
        prowlarr={
            "configured": prowlarr_service.is_available,
            "connected": prowlarr_connected,
        },
        qbittorrent={
            "configured": download_client_service.is_configured,
            "connected": qbit_connected,
            "url": settings.qbittorrent_url,
            "category": settings.qbittorrent_category,
            "version": qbit_version,
        },
        beets=beets_info,
    )


# --- Quality Profiles ---

@router.get("/quality-profiles", response_model=List[QualityProfileResponse])
async def list_quality_profiles(db: AsyncSession = Depends(get_db)):
    """List all quality profiles."""
    result = await db.execute(
        select(QualityProfile).order_by(QualityProfile.is_default.desc(), QualityProfile.name)
    )
    profiles = result.scalars().all()

    # Seed default profiles if none exist
    if not profiles:
        for profile_data in DEFAULT_PROFILES:
            profile = QualityProfile(**profile_data)
            db.add(profile)
        await db.commit()

        result = await db.execute(
            select(QualityProfile).order_by(QualityProfile.is_default.desc(), QualityProfile.name)
        )
        profiles = result.scalars().all()

    return profiles


@router.post("/quality-profiles", response_model=QualityProfileResponse)
async def create_quality_profile(
    data: QualityProfileCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new quality profile."""
    # Check for duplicate name
    existing = await db.execute(
        select(QualityProfile).where(QualityProfile.name == data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Profile with this name already exists")

    profile = QualityProfile(**data.model_dump())

    # If setting as default, unset other defaults
    if data.is_default:
        await _clear_default_profiles(db)

    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/quality-profiles/{profile_id}", response_model=QualityProfileResponse)
async def get_quality_profile(
    profile_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific quality profile."""
    result = await db.execute(
        select(QualityProfile).where(QualityProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Quality profile not found")
    return profile


@router.patch("/quality-profiles/{profile_id}", response_model=QualityProfileResponse)
async def update_quality_profile(
    profile_id: int,
    data: QualityProfileUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a quality profile."""
    result = await db.execute(
        select(QualityProfile).where(QualityProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Quality profile not found")

    update_data = data.model_dump(exclude_unset=True)

    # If setting as default, unset other defaults
    if update_data.get("is_default"):
        await _clear_default_profiles(db)

    for key, value in update_data.items():
        setattr(profile, key, value)

    await db.commit()
    await db.refresh(profile)
    return profile


@router.delete("/quality-profiles/{profile_id}")
async def delete_quality_profile(
    profile_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a quality profile."""
    result = await db.execute(
        select(QualityProfile).where(QualityProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Quality profile not found")

    if profile.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete the default profile")

    await db.delete(profile)
    await db.commit()
    return {"status": "deleted", "id": profile_id}


# --- Beets ---

@router.get("/beets/config")
async def get_beets_config():
    """Get current beets configuration."""
    info = await beets_service.test_connection()
    return {
        "enabled": settings.beets_enabled,
        "config_path": settings.beets_config_path,
        "library_path": settings.beets_library_path,
        "auto_import": settings.beets_auto_import,
        "move_files": settings.beets_move_files,
        **info,
    }


@router.get("/beets/library")
async def get_beets_library(query: Optional[str] = None, limit: int = 50):
    """List albums in the beets library."""
    albums = await beets_service.list_library(query=query, limit=limit)
    return {"albums": albums, "count": len(albums)}


@router.post("/beets/generate-config")
async def generate_beets_config():
    """Generate a default beets config file."""
    config = beets_service.generate_default_config()
    return {"config": config}


# --- Helpers ---

async def _clear_default_profiles(db: AsyncSession):
    """Clear the default flag from all quality profiles."""
    result = await db.execute(
        select(QualityProfile).where(QualityProfile.is_default == True)
    )
    for profile in result.scalars().all():
        profile.is_default = False
