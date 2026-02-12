"""Download queue and history endpoints."""

from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.download import Download, DownloadStatus
from app.services.prowlarr import prowlarr_service
from app.services.download_client import download_client_service
from app.services.sabnzbd import sabnzbd_service
from app.services import app_settings as cfg

router = APIRouter()
settings = get_settings()


# --- Pydantic Schemas ---

class DownloadRequest(BaseModel):
    """Download request."""
    album_id: Optional[int] = None
    wishlist_id: Optional[int] = None
    artist_name: str
    album_title: str
    preferred_format: Optional[str] = None
    search_query: Optional[str] = None


class DownloadResponse(BaseModel):
    """Download response."""
    id: int
    artist_name: str
    album_title: str
    status: DownloadStatus
    status_message: Optional[str] = None
    progress: float
    release_title: Optional[str] = None
    release_size: Optional[int] = None
    release_format: Optional[str] = None
    release_quality: Optional[str] = None
    indexer_name: Optional[str] = None
    seeders: Optional[int] = None
    leechers: Optional[int] = None
    download_speed: Optional[int] = None
    eta_seconds: Optional[int] = None
    download_client: Optional[str] = None
    download_id: Optional[str] = None
    download_path: Optional[str] = None
    source: str = "manual"
    beets_imported: bool = False
    final_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SearchResultResponse(BaseModel):
    """Search result from indexers."""
    guid: str
    indexer: Optional[str] = None
    indexer_id: Optional[int] = None
    title: str
    size: int
    format: Optional[str] = None
    quality: Optional[str] = None
    seeders: int
    leechers: int
    download_url: Optional[str] = None
    score: float = 0.0
    protocol: Optional[str] = None  # "torrent" or "usenet"


class GrabRequest(BaseModel):
    """Request to grab a specific release."""
    guid: str
    indexer_id: int
    download_id: Optional[int] = None
    artist_name: Optional[str] = None
    album_title: Optional[str] = None
    release_title: Optional[str] = None
    release_size: Optional[int] = None
    release_format: Optional[str] = None
    release_quality: Optional[str] = None
    seeders: Optional[int] = None
    indexer_name: Optional[str] = None
    protocol: Optional[str] = None  # "torrent" or "usenet"
    download_url: Optional[str] = None


class DownloadStatsResponse(BaseModel):
    """Download queue statistics."""
    total: int
    pending: int
    searching: int
    downloading: int
    importing: int
    completed: int
    failed: int
    active_client_downloads: int


class BulkDeleteRequest(BaseModel):
    """Bulk delete request for downloads."""
    download_ids: Optional[List[int]] = None
    all: bool = False
    scope: str = "all"


class BulkDeleteResponse(BaseModel):
    """Bulk delete response for downloads."""
    deleted: int
    failed: int
    deleted_ids: List[int]


# --- Endpoints ---

@router.get("", response_model=List[DownloadResponse])
async def get_downloads(
    status: Optional[DownloadStatus] = Query(None),
    source: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get download queue and history."""
    query = select(Download)

    if status:
        query = query.where(Download.status == status)
    if source:
        query = query.where(Download.source == source)

    query = query.order_by(Download.created_at.desc())
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    downloads = result.scalars().all()

    return downloads


@router.get("/stats", response_model=DownloadStatsResponse)
async def get_download_stats(db: AsyncSession = Depends(get_db)):
    """Get download queue statistics."""
    result = await db.execute(
        select(Download.status, func.count(Download.id))
        .group_by(Download.status)
    )
    status_counts = dict(result.all())

    active_client = 0
    if download_client_service.is_configured:
        active_client += await download_client_service.get_active_count()
    if sabnzbd_service.is_configured:
        active_client += await sabnzbd_service.get_active_count()

    total = sum(status_counts.values())

    return DownloadStatsResponse(
        total=total,
        pending=status_counts.get(DownloadStatus.PENDING, 0),
        searching=status_counts.get(DownloadStatus.SEARCHING, 0),
        downloading=status_counts.get(DownloadStatus.DOWNLOADING, 0),
        importing=status_counts.get(DownloadStatus.IMPORTING, 0),
        completed=status_counts.get(DownloadStatus.COMPLETED, 0),
        failed=status_counts.get(DownloadStatus.FAILED, 0),
        active_client_downloads=active_client,
    )


@router.get("/queue", response_model=List[DownloadResponse])
async def get_download_queue(
    db: AsyncSession = Depends(get_db),
):
    """Get active downloads (not completed/failed/cancelled)."""
    active_statuses = [
        DownloadStatus.PENDING,
        DownloadStatus.SEARCHING,
        DownloadStatus.FOUND,
        DownloadStatus.QUEUED,
        DownloadStatus.DOWNLOADING,
        DownloadStatus.IMPORTING,
    ]

    result = await db.execute(
        select(Download)
        .where(Download.status.in_(active_statuses))
        .order_by(Download.created_at.desc())
    )
    downloads = result.scalars().all()

    return downloads


@router.get("/history", response_model=List[DownloadResponse])
async def get_download_history(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Get completed download history."""
    result = await db.execute(
        select(Download)
        .where(Download.status.in_([DownloadStatus.COMPLETED, DownloadStatus.FAILED, DownloadStatus.CANCELLED]))
        .order_by(Download.completed_at.desc().nullslast())
        .limit(limit)
    )
    downloads = result.scalars().all()

    return downloads


async def _check_storage_limit(db: AsyncSession) -> None:
    """Raise 409 if the configured storage limit has been reached."""
    await cfg.ensure_cache(db)
    limit_gb = cfg.get_int("storage_limit_gb", 0)
    if limit_gb <= 0:
        return

    from pathlib import Path

    library_path = cfg.get_setting("beets_library_path", "/media/music")
    completed_path = cfg.get_setting("qbittorrent_completed_path", "/media/completed")

    total = 0
    for dir_path in (library_path, completed_path):
        p = Path(dir_path)
        if p.exists():
            try:
                for f in p.rglob("*"):
                    if f.is_file():
                        total += f.stat().st_size
            except (PermissionError, OSError):
                pass

    limit_bytes = limit_gb * 1024 * 1024 * 1024
    if total >= limit_bytes:
        used_gb = round(total / (1024 ** 3), 1)
        raise HTTPException(
            status_code=409,
            detail=f"Storage limit reached ({used_gb} GB used of {limit_gb} GB limit). "
                   "Free up space or increase the limit in Settings.",
        )


@router.post("", response_model=DownloadResponse)
async def create_download(
    request: DownloadRequest,
    db: AsyncSession = Depends(get_db),
):
    """Add item to download queue and begin searching."""
    await _check_storage_limit(db)

    download = Download(
        album_id=request.album_id,
        wishlist_id=request.wishlist_id,
        artist_name=request.artist_name,
        album_title=request.album_title,
        search_query=request.search_query or f"{request.artist_name} {request.album_title}",
        status=DownloadStatus.SEARCHING,
        source="manual",
    )

    db.add(download)
    await db.commit()
    await db.refresh(download)

    # Queue Celery task to search for the album
    from app.tasks.downloads import search_for_album
    search_for_album.delay(
        download_id=download.id,
        artist=request.artist_name,
        album=request.album_title,
        preferred_format=request.preferred_format,
    )

    return download


@router.get("/{download_id}", response_model=DownloadResponse)
async def get_download(
    download_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get download by ID."""
    result = await db.execute(select(Download).where(Download.id == download_id))
    download = result.scalar_one_or_none()

    if not download:
        raise HTTPException(status_code=404, detail="Download not found")

    return download


@router.delete("/{download_id}")
async def cancel_download(
    download_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Cancel a download."""
    result = await db.execute(select(Download).where(Download.id == download_id))
    download = result.scalar_one_or_none()

    if not download:
        raise HTTPException(status_code=404, detail="Download not found")

    if download.status in [DownloadStatus.COMPLETED, DownloadStatus.CANCELLED]:
        raise HTTPException(status_code=400, detail="Download cannot be cancelled")

    # Cancel in download client if actively downloading
    if download.download_id:
        if download.download_client == "sabnzbd" and sabnzbd_service.is_configured:
            await sabnzbd_service.delete_download(download.download_id, del_files=True)
        elif download_client_service.is_configured:
            await download_client_service.delete_torrent(
                download.download_id, delete_files=True
            )

    download.status = DownloadStatus.CANCELLED
    download.completed_at = datetime.utcnow()
    await db.commit()

    return {"status": "cancelled", "id": download_id}


@router.delete("/bulk/delete", response_model=BulkDeleteResponse)
async def delete_downloads_bulk(
    request: BulkDeleteRequest = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """Delete selected downloads or clear queue/history."""
    valid_scopes = {"all", "queue", "history"}
    scope = request.scope if request.scope in valid_scopes else "all"

    active_statuses = [
        DownloadStatus.PENDING,
        DownloadStatus.SEARCHING,
        DownloadStatus.FOUND,
        DownloadStatus.QUEUED,
        DownloadStatus.DOWNLOADING,
        DownloadStatus.IMPORTING,
    ]
    history_statuses = [
        DownloadStatus.COMPLETED,
        DownloadStatus.FAILED,
        DownloadStatus.CANCELLED,
    ]

    query = select(Download)
    if request.all:
        if scope == "queue":
            query = query.where(Download.status.in_(active_statuses))
        elif scope == "history":
            query = query.where(Download.status.in_(history_statuses))
    else:
        ids = request.download_ids or []
        if not ids:
            raise HTTPException(status_code=400, detail="download_ids required when all=false")
        query = query.where(Download.id.in_(ids))

    result = await db.execute(query)
    downloads = result.scalars().all()

    deleted_ids: List[int] = []
    failed = 0

    for download in downloads:
        try:
            if download.download_id:
                if download.download_client == "sabnzbd" and sabnzbd_service.is_configured:
                    await sabnzbd_service.delete_download(download.download_id, del_files=True)
                elif download_client_service.is_configured:
                    await download_client_service.delete_torrent(
                        download.download_id,
                        delete_files=True,
                    )
            await db.delete(download)
            deleted_ids.append(download.id)
        except Exception:
            failed += 1

    await db.commit()

    return BulkDeleteResponse(
        deleted=len(deleted_ids),
        failed=failed,
        deleted_ids=deleted_ids,
    )


@router.post("/{download_id}/retry", response_model=DownloadResponse)
async def retry_download(
    download_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Retry a failed download."""
    result = await db.execute(select(Download).where(Download.id == download_id))
    download = result.scalar_one_or_none()

    if not download:
        raise HTTPException(status_code=404, detail="Download not found")

    if download.status not in [DownloadStatus.FAILED, DownloadStatus.CANCELLED]:
        raise HTTPException(status_code=400, detail="Can only retry failed or cancelled downloads")

    download.status = DownloadStatus.SEARCHING
    download.status_message = None
    download.progress = 0.0
    download.download_id = None
    await db.commit()

    # Re-queue the search
    from app.tasks.downloads import search_for_album
    search_for_album.delay(
        download_id=download.id,
        artist=download.artist_name,
        album=download.album_title,
        preferred_format=download.release_format,
    )

    await db.refresh(download)
    return download


@router.post("/search", response_model=List[SearchResultResponse])
async def search_releases(
    artist: str = Query(...),
    album: str = Query(...),
    format: Optional[str] = Query(None, description="Preferred format: flac, 320, v0"),
):
    """Search for releases via Prowlarr."""
    if not prowlarr_service.is_available:
        raise HTTPException(status_code=503, detail="Prowlarr is not configured")

    results = await prowlarr_service.search_album(
        artist=artist,
        album=album,
        preferred_format=format,
    )

    return [
        SearchResultResponse(
            guid=r.get("guid", ""),
            indexer=r.get("indexer"),
            indexer_id=r.get("indexer_id"),
            title=r.get("title", ""),
            size=r.get("size", 0),
            format=r.get("format"),
            quality=r.get("quality"),
            seeders=r.get("seeders", 0),
            leechers=r.get("leechers", 0),
            download_url=r.get("download_url"),
            score=r.get("score", 0),
            protocol=r.get("protocol"),
        )
        for r in results
    ]


@router.post("/grab", response_model=DownloadResponse)
async def grab_release(
    request: GrabRequest,
    db: AsyncSession = Depends(get_db),
):
    """Grab a specific release from search results and start downloading."""
    await _check_storage_limit(db)

    if not prowlarr_service.is_available:
        raise HTTPException(status_code=503, detail="Prowlarr is not configured")

    # Get or create download record
    download = None
    if request.download_id:
        result = await db.execute(
            select(Download).where(Download.id == request.download_id)
        )
        download = result.scalar_one_or_none()
        if not download:
            raise HTTPException(status_code=404, detail="Download not found")

    if not download:
        if not request.artist_name or not request.album_title:
            raise HTTPException(
                status_code=400,
                detail="artist_name and album_title required when download_id not provided",
            )
        download = Download(
            artist_name=request.artist_name,
            album_title=request.album_title,
            status=DownloadStatus.FOUND,
            source="manual",
        )
        db.add(download)
        await db.commit()
        await db.refresh(download)

    # Update download with release info
    download.indexer_name = request.indexer_name
    download.indexer_id = str(request.indexer_id)
    download.release_title = request.release_title
    download.release_size = request.release_size
    download.release_format = request.release_format
    download.release_quality = request.release_quality
    download.seeders = request.seeders
    download.status = DownloadStatus.QUEUED
    await db.commit()

    # Queue the grab task
    from app.tasks.downloads import grab_release as grab_task
    grab_task.delay(
        download_id=download.id,
        guid=request.guid,
        indexer_id=request.indexer_id,
        protocol=request.protocol,
        download_url=request.download_url,
        release_title=request.release_title,
    )

    await db.refresh(download)
    return download


@router.post("/{download_id}/pause")
async def pause_download(
    download_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Pause an active download."""
    result = await db.execute(select(Download).where(Download.id == download_id))
    download = result.scalar_one_or_none()

    if not download:
        raise HTTPException(status_code=404, detail="Download not found")

    if download.status != DownloadStatus.DOWNLOADING:
        raise HTTPException(status_code=400, detail="Download is not actively downloading")

    if download.download_id:
        if download.download_client == "sabnzbd" and sabnzbd_service.is_configured:
            success = await sabnzbd_service.pause_download(download.download_id)
        elif download_client_service.is_configured:
            success = await download_client_service.pause_torrent(download.download_id)
        else:
            success = False
        if not success:
            raise HTTPException(status_code=500, detail="Failed to pause in download client")

    return {"status": "paused", "id": download_id}


@router.post("/{download_id}/resume")
async def resume_download(
    download_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Resume a paused download."""
    result = await db.execute(select(Download).where(Download.id == download_id))
    download = result.scalar_one_or_none()

    if not download:
        raise HTTPException(status_code=404, detail="Download not found")

    if download.download_id:
        if download.download_client == "sabnzbd" and sabnzbd_service.is_configured:
            success = await sabnzbd_service.resume_download(download.download_id)
        elif download_client_service.is_configured:
            success = await download_client_service.resume_torrent(download.download_id)
        else:
            success = False
        if not success:
            raise HTTPException(status_code=500, detail="Failed to resume in download client")

    return {"status": "resumed", "id": download_id}
