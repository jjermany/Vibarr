"""Settings and configuration endpoints.

All user-configurable settings are stored in the database and managed
through these endpoints + the frontend Settings page.
"""

from typing import Optional, List, Dict
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.quality_profile import QualityProfile, DEFAULT_PROFILES
from app.models.user import User
from app.services.download_client import download_client_service
from app.services.sabnzbd import sabnzbd_service
from app.services.beets import beets_service
from app.services import app_settings as cfg
from app.services.auth import require_admin

router = APIRouter()


# --- Pydantic Schemas ---

class DownloadSettingsResponse(BaseModel):
    auto_download_enabled: bool
    auto_download_confidence_threshold: float
    preferred_quality: str
    max_concurrent_downloads: int
    download_path: str
    completed_download_path: str

class GeneralSettingsResponse(BaseModel):
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    lastfm_api_key: str = ""
    lastfm_shared_secret: str = ""
    plex_url: str = ""
    plex_token: str = ""
    prowlarr_url: str = ""
    prowlarr_api_key: str = ""
    qbittorrent_url: str = ""
    qbittorrent_username: str = "admin"
    qbittorrent_password: str = ""
    qbittorrent_category: str = "vibarr"
    qbittorrent_categories: str = "vibarr,music"
    qbittorrent_incomplete_path: str = "/incomplete"
    qbittorrent_completed_path: str = "/media/completed"
    qbittorrent_remove_completed: bool = False
    sabnzbd_enabled: bool = False
    sabnzbd_url: str = ""
    sabnzbd_api_key: str = ""
    sabnzbd_category: str = "music"
    sabnzbd_remove_completed: bool = True
    beets_enabled: bool = False
    beets_config_path: str = "/config/beets/config.yaml"
    beets_library_path: str = "/media/music"
    beets_auto_import: bool = True
    beets_move_files: bool = True
    beets_hardlink: bool = True
    auto_download_enabled: bool = False
    auto_download_confidence_threshold: float = 0.8
    preferred_quality: str = "flac"
    max_concurrent_downloads: int = 3
    download_path: str = "/downloads"
    completed_download_path: str = "/media/completed"
    musicbrainz_user_agent: str = "Vibarr/1.0"
    registration_enabled: bool = True
    max_users: int = 10
    ml_profiling_enabled: bool = True
    taste_embedding_half_life_days: float = 21.0
    plex_auth_enabled: bool = False
    storage_limit_gb: int = 0

class SettingsUpdateRequest(BaseModel):
    settings: Dict[str, str]

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
    sabnzbd: dict
    beets: dict


# --- All Settings (read / write) ---

@router.get("/general")
async def get_all_settings(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Get all user-configurable settings. Admin only."""
    await cfg.ensure_cache(db)
    return GeneralSettingsResponse(
        spotify_client_id=cfg.get_setting("spotify_client_id"),
        spotify_client_secret=cfg.get_setting("spotify_client_secret"),
        lastfm_api_key=cfg.get_setting("lastfm_api_key"),
        lastfm_shared_secret=cfg.get_setting("lastfm_shared_secret"),
        plex_url=cfg.get_setting("plex_url"),
        plex_token=cfg.get_setting("plex_token"),
        prowlarr_url=cfg.get_setting("prowlarr_url"),
        prowlarr_api_key=cfg.get_setting("prowlarr_api_key"),
        qbittorrent_url=cfg.get_setting("qbittorrent_url"),
        qbittorrent_username=cfg.get_setting("qbittorrent_username", "admin"),
        qbittorrent_password=cfg.get_setting("qbittorrent_password"),
        qbittorrent_category=cfg.get_setting("qbittorrent_category", "vibarr"),
        qbittorrent_categories=cfg.get_setting("qbittorrent_categories", "vibarr,music"),
        qbittorrent_incomplete_path=cfg.get_setting("qbittorrent_incomplete_path", "/incomplete"),
        qbittorrent_completed_path=cfg.get_setting("qbittorrent_completed_path", "/media/completed"),
        qbittorrent_remove_completed=cfg.get_bool("qbittorrent_remove_completed"),
        sabnzbd_enabled=cfg.get_bool("sabnzbd_enabled"),
        sabnzbd_url=cfg.get_setting("sabnzbd_url"),
        sabnzbd_api_key=cfg.get_setting("sabnzbd_api_key"),
        sabnzbd_category=cfg.get_setting("sabnzbd_category", "music"),
        sabnzbd_remove_completed=cfg.get_bool("sabnzbd_remove_completed", True),
        beets_enabled=cfg.get_bool("beets_enabled"),
        beets_config_path=cfg.get_setting("beets_config_path", "/config/beets/config.yaml"),
        beets_library_path=cfg.get_setting("beets_library_path", "/media/music"),
        beets_auto_import=cfg.get_bool("beets_auto_import", True),
        beets_move_files=cfg.get_bool("beets_move_files", True),
        beets_hardlink=cfg.get_bool("beets_hardlink", True),
        auto_download_enabled=cfg.get_bool("auto_download_enabled"),
        auto_download_confidence_threshold=cfg.get_float("auto_download_confidence_threshold", 0.8),
        preferred_quality=cfg.get_setting("preferred_quality", "flac"),
        max_concurrent_downloads=cfg.get_int("max_concurrent_downloads", 3),
        download_path=cfg.get_setting("download_path", "/downloads"),
        completed_download_path=cfg.get_setting("completed_download_path", "/media/completed"),
        musicbrainz_user_agent=cfg.get_setting("musicbrainz_user_agent", "Vibarr/1.0"),
        registration_enabled=cfg.get_bool("registration_enabled", True),
        max_users=cfg.get_int("max_users", 10),
        ml_profiling_enabled=cfg.get_bool("ml_profiling_enabled", True),
        taste_embedding_half_life_days=cfg.get_float("taste_embedding_half_life_days", 21.0),
        plex_auth_enabled=cfg.get_bool("plex_auth_enabled"),
        storage_limit_gb=cfg.get_int("storage_limit_gb", 0),
    )


@router.put("/general")
async def update_all_settings(
    body: SettingsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Update one or more user-configurable settings. Admin only."""
    await cfg.update_settings_bulk(db, body.settings)
    # Reinitialize services that cache connection details
    _reinit_services()
    return {"status": "ok", "updated": list(body.settings.keys())}


# --- Download Settings (convenience endpoint) ---

@router.get("/download", response_model=DownloadSettingsResponse)
async def get_download_settings(db: AsyncSession = Depends(get_db)):
    """Get current download automation settings."""
    await cfg.ensure_cache(db)
    return DownloadSettingsResponse(
        auto_download_enabled=cfg.get_bool("auto_download_enabled"),
        auto_download_confidence_threshold=cfg.get_float("auto_download_confidence_threshold", 0.8),
        preferred_quality=cfg.get_setting("preferred_quality", "flac"),
        max_concurrent_downloads=cfg.get_int("max_concurrent_downloads", 3),
        download_path=cfg.get_setting("download_path", "/downloads"),
        completed_download_path=cfg.get_setting("completed_download_path", "/media/completed"),
    )


# --- Service Status ---

@router.get("/services", response_model=ServiceStatusResponse)
async def get_service_status(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Get status of all download-related services. Admin only."""
    await cfg.ensure_cache(db)

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

    # SABnzbd
    sab_connected = False
    sab_version = None
    if sabnzbd_service.is_configured:
        sab_connected = await sabnzbd_service.test_connection()
        if sab_connected:
            sab_version = await sabnzbd_service.get_version()

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
            "url": cfg.get_setting("qbittorrent_url"),
            "category": cfg.get_setting("qbittorrent_category", "vibarr"),
            "categories": [
                c.strip()
                for c in cfg.get_setting("qbittorrent_categories", "vibarr,music").split(",")
                if c.strip()
            ],
            "incomplete_path": cfg.get_setting("qbittorrent_incomplete_path"),
            "completed_path": cfg.get_setting("qbittorrent_completed_path"),
            "version": qbit_version,
        },
        sabnzbd={
            "configured": sabnzbd_service.is_configured,
            "connected": sab_connected,
            "url": cfg.get_setting("sabnzbd_url"),
            "category": cfg.get_setting("sabnzbd_category", "music"),
            "version": sab_version,
        },
        beets=beets_info,
    )


@router.post("/services/test")
async def test_service_connection(
    service: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Test connection to a specific service after saving new settings. Admin only."""
    await cfg.ensure_cache(db)
    _reinit_services()

    if service == "prowlarr":
        from app.services.prowlarr import prowlarr_service
        if not prowlarr_service.is_available:
            return {"connected": False, "reason": "Prowlarr URL or API key not configured"}
        connected = await prowlarr_service.test_connection()
        return {"connected": connected}

    elif service == "qbittorrent":
        if not download_client_service.is_configured:
            return {"connected": False, "reason": "qBittorrent URL not configured"}
        connected = await download_client_service.test_connection()
        version = await download_client_service.get_version() if connected else None
        return {"connected": connected, "version": version}

    elif service == "sabnzbd":
        sabnzbd_service._client = None  # Reset cached client
        if not sabnzbd_service.is_configured:
            return {"connected": False, "reason": "SABnzbd URL or API key not configured"}
        connected = await sabnzbd_service.test_connection()
        version = await sabnzbd_service.get_version() if connected else None
        return {"connected": connected, "version": version}

    elif service == "beets":
        info = await beets_service.test_connection()
        return info

    raise HTTPException(status_code=400, detail=f"Unknown service: {service}")


# --- qBittorrent Categories ---

@router.get("/qbittorrent/categories")
async def get_qbittorrent_categories(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Get the configured qBittorrent categories. Admin only."""
    await cfg.ensure_cache(db)
    raw = cfg.get_setting("qbittorrent_categories", "vibarr,music")
    categories = [c.strip() for c in raw.split(",") if c.strip()]
    default_cat = cfg.get_setting("qbittorrent_category", "vibarr")
    return {
        "categories": categories,
        "default_category": default_cat,
    }


@router.put("/qbittorrent/categories")
async def update_qbittorrent_categories(
    body: Dict,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Update qBittorrent categories and optionally sync them to qBit. Admin only."""
    categories = body.get("categories", [])
    if isinstance(categories, list):
        cat_str = ",".join(c.strip() for c in categories if c.strip())
    else:
        cat_str = str(categories)

    await cfg.update_setting(db, "qbittorrent_categories", cat_str)

    # Optionally set default category
    default_cat = body.get("default_category")
    if default_cat:
        await cfg.update_setting(db, "qbittorrent_category", default_cat)

    # Sync categories to qBittorrent if connected
    synced = []
    if download_client_service.is_configured:
        for cat in cat_str.split(","):
            cat = cat.strip()
            if cat:
                ok = await download_client_service.ensure_category_by_name(
                    cat, cfg.get_setting("download_path", "/downloads")
                )
                if ok:
                    synced.append(cat)

    return {
        "status": "ok",
        "categories": [c.strip() for c in cat_str.split(",") if c.strip()],
        "synced_to_qbittorrent": synced,
    }


# --- Completed Download Import ---

@router.post("/downloads/import-completed")
async def import_completed_downloads(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Scan the completed download path and trigger import for any
    finished downloads that haven't been imported yet (Arr-style). Admin only."""
    await cfg.ensure_cache(db)

    completed_path = cfg.get_setting("qbittorrent_completed_path") or cfg.get_setting(
        "completed_download_path", "/media/completed"
    )

    if not completed_path:
        raise HTTPException(status_code=400, detail="No completed download path configured")

    from pathlib import Path
    import os

    target = Path(completed_path)
    if not target.exists():
        return {"status": "ok", "message": "Completed path does not exist yet", "scanned": 0, "imported": 0}

    # Find subdirectories (each is typically one download)
    entries = [
        entry for entry in target.iterdir()
        if entry.is_dir() or (entry.is_file() and entry.suffix.lower() in (
            ".flac", ".mp3", ".ogg", ".opus", ".m4a", ".wav", ".aac",
        ))
    ]

    # Cross-reference with existing downloads to find un-imported ones
    from app.models.download import Download, DownloadStatus

    result = await db.execute(
        select(Download).where(
            Download.status == DownloadStatus.COMPLETED,
            Download.beets_imported == False,
        )
    )
    unimported = result.scalars().all()

    triggered = 0
    for download in unimported:
        # Check if the download path matches something in the completed folder
        dl_path = download.download_path or ""
        if dl_path and Path(dl_path).exists():
            from app.tasks.downloads import import_completed_download as import_task
            import_task.delay(download_id=download.id)
            triggered += 1

    # Also detect orphaned directories (files in completed that have no Download record)
    orphaned = []
    known_paths = {d.download_path for d in unimported if d.download_path}
    for entry in entries:
        entry_str = str(entry)
        if entry_str not in known_paths and not any(entry_str in kp for kp in known_paths):
            orphaned.append(str(entry.name))

    return {
        "status": "ok",
        "completed_path": completed_path,
        "scanned": len(entries),
        "import_triggered": triggered,
        "orphaned_entries": orphaned,
    }


# --- Quality Profiles ---

@router.get("/quality-profiles", response_model=List[QualityProfileResponse])
async def list_quality_profiles(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """List all quality profiles. Admin only."""
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
    admin: User = Depends(require_admin),
):
    """Create a new quality profile. Admin only."""
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
    admin: User = Depends(require_admin),
):
    """Get a specific quality profile. Admin only."""
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
    admin: User = Depends(require_admin),
):
    """Update a quality profile. Admin only."""
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
    admin: User = Depends(require_admin),
):
    """Delete a quality profile. Admin only."""
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


# --- SABnzbd Categories ---

@router.get("/sabnzbd/categories")
async def get_sabnzbd_categories(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Get categories from SABnzbd. Admin only."""
    await cfg.ensure_cache(db)
    if not sabnzbd_service.is_configured:
        return {"categories": []}
    categories = await sabnzbd_service.get_categories()
    return {
        "categories": categories,
        "current_category": cfg.get_setting("sabnzbd_category", "music"),
    }


# --- Beets ---

@router.get("/beets/config")
async def get_beets_config(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Get current beets configuration. Admin only."""
    await cfg.ensure_cache(db)
    info = await beets_service.test_connection()
    return {
        "enabled": cfg.get_bool("beets_enabled"),
        "config_path": cfg.get_setting("beets_config_path", "/config/beets/config.yaml"),
        "library_path": cfg.get_setting("beets_library_path", "/media/music"),
        "auto_import": cfg.get_bool("beets_auto_import", True),
        "move_files": cfg.get_bool("beets_move_files", True),
        **info,
    }


@router.get("/beets/library")
async def get_beets_library(
    query: Optional[str] = None,
    limit: int = 50,
    admin: User = Depends(require_admin),
):
    """List albums in the beets library. Admin only."""
    albums = await beets_service.list_library(query=query, limit=limit)
    return {"albums": albums, "count": len(albums)}


@router.post("/beets/generate-config")
async def generate_beets_config(admin: User = Depends(require_admin)):
    """Generate a default beets config file. Admin only."""
    config = beets_service.generate_default_config()
    return {"config": config}


# --- Storage Usage ---

@router.get("/storage")
async def get_storage_usage(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Get current storage usage for music library paths. Admin only."""
    import shutil
    from pathlib import Path

    await cfg.ensure_cache(db)

    library_path = cfg.get_setting("beets_library_path", "/media/music")
    completed_path = cfg.get_setting("qbittorrent_completed_path", "/media/completed")
    incomplete_path = cfg.get_setting("qbittorrent_incomplete_path", "/incomplete")
    storage_limit_gb = cfg.get_int("storage_limit_gb", 0)

    def _dir_size(path_str: str) -> int:
        """Calculate total size of a directory in bytes."""
        p = Path(path_str)
        if not p.exists():
            return 0
        total = 0
        try:
            for f in p.rglob("*"):
                if f.is_file():
                    total += f.stat().st_size
        except (PermissionError, OSError):
            pass
        return total

    library_bytes = _dir_size(library_path)
    completed_bytes = _dir_size(completed_path)
    incomplete_bytes = _dir_size(incomplete_path)
    total_bytes = library_bytes + completed_bytes + incomplete_bytes

    # Disk info for the library path
    disk_total = 0
    disk_free = 0
    try:
        usage = shutil.disk_usage(library_path if Path(library_path).exists() else "/")
        disk_total = usage.total
        disk_free = usage.free
    except (OSError, FileNotFoundError):
        pass

    limit_bytes = storage_limit_gb * 1024 * 1024 * 1024 if storage_limit_gb > 0 else 0

    return {
        "library_bytes": library_bytes,
        "completed_bytes": completed_bytes,
        "incomplete_bytes": incomplete_bytes,
        "total_music_bytes": total_bytes,
        "storage_limit_gb": storage_limit_gb,
        "storage_limit_bytes": limit_bytes,
        "limit_exceeded": limit_bytes > 0 and total_bytes >= limit_bytes,
        "disk_total_bytes": disk_total,
        "disk_free_bytes": disk_free,
    }


# --- Filesystem Browse ---

@router.get("/browse")
async def browse_filesystem(
    path: str = "/",
    admin: User = Depends(require_admin),
):
    """Browse directories on the server filesystem. Admin only.

    Returns a list of directories and files at the given path so the
    admin can pick paths from the UI rather than typing them manually.
    """
    from pathlib import Path as _Path
    import os

    target = _Path(path)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Path does not exist: {path}")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail=f"Path is not a directory: {path}")

    entries = []
    try:
        for entry in sorted(target.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            try:
                stat = entry.stat()
                entries.append({
                    "name": entry.name,
                    "path": str(entry),
                    "is_dir": entry.is_dir(),
                    "size": stat.st_size if entry.is_file() else None,
                })
            except (PermissionError, OSError):
                continue
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"Permission denied: {path}")

    parent = str(target.parent) if str(target) != "/" else None

    return {
        "current_path": str(target),
        "parent": parent,
        "entries": entries,
    }


# --- Notifications ---

@router.get("/notifications")
async def get_notifications(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get recent notifications (download events, imports, errors). Admin only."""
    from app.models.download import Download, DownloadStatus
    from sqlalchemy import desc

    # Fetch recent downloads as notification-like events
    result = await db.execute(
        select(Download)
        .order_by(desc(Download.updated_at))
        .limit(limit)
    )
    downloads = result.scalars().all()

    notifications = []
    for dl in downloads:
        ntype = "info"
        if dl.status == DownloadStatus.COMPLETED:
            ntype = "success"
            message = f"{dl.artist_name} - {dl.album_title} completed"
            if dl.beets_imported:
                message += " and imported"
        elif dl.status == DownloadStatus.FAILED:
            ntype = "error"
            message = f"{dl.artist_name} - {dl.album_title} failed"
            if dl.status_message:
                message += f": {dl.status_message}"
        elif dl.status == DownloadStatus.DOWNLOADING:
            ntype = "info"
            message = f"{dl.artist_name} - {dl.album_title} downloading ({dl.progress}%)"
        elif dl.status == DownloadStatus.IMPORTING:
            ntype = "info"
            message = f"{dl.artist_name} - {dl.album_title} importing..."
        elif dl.status == DownloadStatus.SEARCHING:
            ntype = "info"
            message = f"Searching for {dl.artist_name} - {dl.album_title}"
        else:
            message = f"{dl.artist_name} - {dl.album_title}: {dl.status.value}"

        notifications.append({
            "id": dl.id,
            "type": ntype,
            "message": message,
            "status": dl.status.value,
            "timestamp": (dl.updated_at or dl.created_at).isoformat() if (dl.updated_at or dl.created_at) else None,
        })

    return {"notifications": notifications, "count": len(notifications)}


# --- Helpers ---

async def _clear_default_profiles(db: AsyncSession):
    """Clear the default flag from all quality profiles."""
    result = await db.execute(
        select(QualityProfile).where(QualityProfile.is_default == True)
    )
    for profile in result.scalars().all():
        profile.is_default = False


def _reinit_services():
    """Reset cached HTTP clients so services pick up new settings."""
    from app.services.prowlarr import prowlarr_service
    prowlarr_service._client = None

    download_client_service._client = None
    download_client_service._authenticated = False

    sabnzbd_service._client = None
