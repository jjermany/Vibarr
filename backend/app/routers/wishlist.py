"""Wishlist endpoints."""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.album import Album
from app.models.artist import Artist
from app.models.wishlist import WishlistItem, WishlistStatus, WishlistPriority
from app.services.prowlarr import prowlarr_service

router = APIRouter()


class WishlistItemCreate(BaseModel):
    """Create wishlist item request."""
    item_type: str  # artist, album, track, playlist
    artist_id: Optional[int] = None
    album_id: Optional[int] = None
    artist_name: Optional[str] = None
    album_title: Optional[str] = None
    musicbrainz_id: Optional[str] = None
    spotify_id: Optional[str] = None
    image_url: Optional[str] = None
    priority: WishlistPriority = WishlistPriority.NORMAL
    preferred_format: Optional[str] = None
    auto_download: bool = False
    notes: Optional[str] = None


class WishlistItemResponse(BaseModel):
    """Wishlist item response."""
    id: int
    item_type: str
    artist_id: Optional[int] = None
    album_id: Optional[int] = None
    artist_name: Optional[str] = None
    album_title: Optional[str] = None
    status: WishlistStatus
    priority: WishlistPriority
    source: str
    confidence_score: Optional[float] = None
    image_url: Optional[str] = None
    auto_download: bool
    created_at: datetime

    class Config:
        from_attributes = True


class WishlistItemUpdate(BaseModel):
    """Update wishlist item request."""
    status: Optional[WishlistStatus] = None
    priority: Optional[WishlistPriority] = None
    preferred_format: Optional[str] = None
    auto_download: Optional[bool] = None
    notes: Optional[str] = None


@router.get("", response_model=List[WishlistItemResponse])
async def get_wishlist(
    status: Optional[WishlistStatus] = Query(None),
    priority: Optional[WishlistPriority] = Query(None),
    item_type: Optional[str] = Query(None),
    sort: str = Query("created", description="Sort: created, priority, status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get wishlist items."""
    query = (
        select(WishlistItem, Album.cover_url, Artist.image_url)
        .outerjoin(Album, WishlistItem.album_id == Album.id)
        .outerjoin(Artist, WishlistItem.artist_id == Artist.id)
    )

    if status:
        query = query.where(WishlistItem.status == status)

    if priority:
        query = query.where(WishlistItem.priority == priority)

    if item_type:
        query = query.where(WishlistItem.item_type == item_type)

    if sort == "created":
        query = query.order_by(WishlistItem.created_at.desc())
    elif sort == "priority":
        query = query.order_by(WishlistItem.priority.desc(), WishlistItem.created_at.desc())
    elif sort == "status":
        query = query.order_by(WishlistItem.status, WishlistItem.created_at.desc())

    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    return [
        WishlistItemResponse.model_validate(
            {
                **_wishlist_item_to_dict(item),
                "image_url": item.image_url or album_cover_url or artist_image_url,
            }
        )
        for item, album_cover_url, artist_image_url in rows
    ]


@router.post("", response_model=WishlistItemResponse)
async def add_to_wishlist(
    item: WishlistItemCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add item to wishlist."""
    wishlist_item = WishlistItem(
        item_type=item.item_type,
        artist_id=item.artist_id,
        album_id=item.album_id,
        artist_name=item.artist_name,
        album_title=item.album_title,
        musicbrainz_id=item.musicbrainz_id,
        spotify_id=item.spotify_id,
        image_url=item.image_url,
        priority=item.priority,
        preferred_format=item.preferred_format,
        auto_download=item.auto_download,
        notes=item.notes,
        source="manual",
    )

    db.add(wishlist_item)
    await db.commit()
    await db.refresh(wishlist_item)

    return WishlistItemResponse.model_validate(
        {
            **_wishlist_item_to_dict(wishlist_item),
            "image_url": None,
        }
    )


@router.get("/{item_id}", response_model=WishlistItemResponse)
async def get_wishlist_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get wishlist item by ID."""
    result = await db.execute(
        select(WishlistItem, Album.cover_url, Artist.image_url)
        .outerjoin(Album, WishlistItem.album_id == Album.id)
        .outerjoin(Artist, WishlistItem.artist_id == Artist.id)
        .where(WishlistItem.id == item_id)
    )
    row = result.one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="Wishlist item not found")

    item, album_cover_url, artist_image_url = row
    return WishlistItemResponse.model_validate(
        {
            **_wishlist_item_to_dict(item),
            "image_url": item.image_url or album_cover_url or artist_image_url,
        }
    )


@router.patch("/{item_id}", response_model=WishlistItemResponse)
async def update_wishlist_item(
    item_id: int,
    update: WishlistItemUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update wishlist item."""
    result = await db.execute(select(WishlistItem).where(WishlistItem.id == item_id))
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Wishlist item not found")

    if update.status is not None:
        item.status = update.status
    if update.priority is not None:
        item.priority = update.priority
    if update.preferred_format is not None:
        item.preferred_format = update.preferred_format
    if update.auto_download is not None:
        item.auto_download = update.auto_download
    if update.notes is not None:
        item.notes = update.notes

    await db.commit()
    await db.refresh(item)

    return WishlistItemResponse.model_validate(
        {
            **_wishlist_item_to_dict(item),
            "image_url": await _resolve_item_image(db, item),
        }
    )


@router.delete("/{item_id}")
async def delete_wishlist_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete wishlist item."""
    result = await db.execute(select(WishlistItem).where(WishlistItem.id == item_id))
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Wishlist item not found")

    await db.delete(item)
    await db.commit()

    return {"status": "deleted", "id": item_id}


@router.post("/search-all")
async def search_all_wishlist(
    db: AsyncSession = Depends(get_db),
):
    """Search for all wanted wishlist items."""
    from app.tasks.downloads import process_wishlist

    if not prowlarr_service.is_available:
        raise HTTPException(
            status_code=503,
            detail="Search is unavailable until Prowlarr is configured and reachable",
        )

    # Count items to search
    result = await db.execute(
        select(WishlistItem)
        .where(WishlistItem.status == WishlistStatus.WANTED)
    )
    items = result.scalars().all()

    process_wishlist.delay(search_all=True)

    return {"status": "search_all_queued", "items_to_search": len(items)}


@router.post("/{item_id}/search")
async def search_wishlist_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Trigger search for wishlist item via Prowlarr."""
    result = await db.execute(select(WishlistItem).where(WishlistItem.id == item_id))
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Wishlist item not found")

    if not prowlarr_service.is_available:
        raise HTTPException(
            status_code=503,
            detail="Search is unavailable until Prowlarr is configured and reachable",
        )

    # Queue Celery task to search Prowlarr
    from app.tasks.downloads import search_wishlist_item as search_task
    search_task.delay(item_id)

    return {"status": "search_queued", "id": item_id}


def _wishlist_item_to_dict(item: WishlistItem) -> dict:
    """Convert a wishlist ORM object into a response-compatible dict."""
    return {
        "id": item.id,
        "item_type": item.item_type,
        "artist_id": item.artist_id,
        "album_id": item.album_id,
        "artist_name": item.artist_name,
        "album_title": item.album_title,
        "status": item.status,
        "priority": item.priority,
        "source": item.source,
        "confidence_score": item.confidence_score,
        "image_url": item.image_url,
        "status_message": item.notes,
        "last_searched_at": item.last_searched_at,
        "search_count": item.search_count,
        "updated_at": item.updated_at,
        "auto_download": item.auto_download,
        "created_at": item.created_at,
    }


async def _resolve_item_image(db: AsyncSession, item: WishlistItem) -> Optional[str]:
    """Resolve artwork URL for a wishlist item from album or artist records."""
    if item.image_url:
        return item.image_url

    if item.album_id:
        album_result = await db.execute(
            select(Album.cover_url).where(Album.id == item.album_id)
        )
        album_cover_url = album_result.scalar_one_or_none()
        if album_cover_url:
            return album_cover_url

    if item.artist_id:
        artist_result = await db.execute(
            select(Artist.image_url).where(Artist.id == item.artist_id)
        )
        return artist_result.scalar_one_or_none()

    return None
