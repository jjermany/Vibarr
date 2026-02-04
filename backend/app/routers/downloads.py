"""Download queue and history endpoints."""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.download import Download, DownloadStatus

router = APIRouter()


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
    release_format: Optional[str] = None
    release_quality: Optional[str] = None
    indexer_name: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class SearchResult(BaseModel):
    """Search result from indexers."""
    id: str
    indexer: str
    title: str
    size: int
    format: Optional[str] = None
    quality: Optional[str] = None
    seeders: int
    leechers: int
    age_days: int


@router.get("", response_model=List[DownloadResponse])
async def get_downloads(
    status: Optional[DownloadStatus] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get download queue and history."""
    query = select(Download)

    if status:
        query = query.where(Download.status == status)

    query = query.order_by(Download.created_at.desc())
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    downloads = result.scalars().all()

    return downloads


@router.get("/queue", response_model=List[DownloadResponse])
async def get_download_queue(
    db: AsyncSession = Depends(get_db),
):
    """Get active downloads (not completed/failed)."""
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
        .where(Download.status.in_([DownloadStatus.COMPLETED, DownloadStatus.FAILED]))
        .order_by(Download.completed_at.desc())
        .limit(limit)
    )
    downloads = result.scalars().all()

    return downloads


@router.post("", response_model=DownloadResponse)
async def create_download(
    request: DownloadRequest,
    db: AsyncSession = Depends(get_db),
):
    """Add item to download queue."""
    download = Download(
        album_id=request.album_id,
        wishlist_id=request.wishlist_id,
        artist_name=request.artist_name,
        album_title=request.album_title,
        search_query=request.search_query,
        status=DownloadStatus.PENDING,
        source="manual",
    )

    db.add(download)
    await db.commit()
    await db.refresh(download)

    # TODO: Queue Celery task to search and download

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

    download.status = DownloadStatus.CANCELLED
    await db.commit()

    # TODO: Cancel actual download in download client

    return {"status": "cancelled", "id": download_id}


@router.post("/{download_id}/retry")
async def retry_download(
    download_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Retry a failed download."""
    result = await db.execute(select(Download).where(Download.id == download_id))
    download = result.scalar_one_or_none()

    if not download:
        raise HTTPException(status_code=404, detail="Download not found")

    download.status = DownloadStatus.PENDING
    download.status_message = None
    await db.commit()

    # TODO: Queue Celery task

    return {"status": "retry_queued", "id": download_id}


@router.post("/search")
async def search_releases(
    artist: str = Query(...),
    album: str = Query(...),
    format: Optional[str] = Query(None, description="Preferred format: flac, 320, v0"),
):
    """Search for releases via Prowlarr."""
    # TODO: Implement Prowlarr search
    return {
        "query": f"{artist} {album}",
        "results": [],
    }


@router.post("/grab")
async def grab_release(
    release_id: str = Query(...),
    indexer: str = Query(...),
    download_id: Optional[int] = Query(None),
):
    """Grab a specific release from search results."""
    # TODO: Implement Prowlarr grab
    return {
        "status": "grabbed",
        "release_id": release_id,
        "indexer": indexer,
    }
