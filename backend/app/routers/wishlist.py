"""Wishlist endpoints."""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.wishlist import WishlistItem, WishlistStatus, WishlistPriority

router = APIRouter()


class WishlistItemCreate(BaseModel):
    """Create wishlist item request."""
    item_type: str  # artist, album
    artist_id: Optional[int] = None
    album_id: Optional[int] = None
    artist_name: Optional[str] = None
    album_title: Optional[str] = None
    musicbrainz_id: Optional[str] = None
    spotify_id: Optional[str] = None
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
    auto_download: bool
    created_at: str

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
    query = select(WishlistItem)

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
    items = result.scalars().all()

    return items


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
        priority=item.priority,
        preferred_format=item.preferred_format,
        auto_download=item.auto_download,
        notes=item.notes,
        source="manual",
    )

    db.add(wishlist_item)
    await db.commit()
    await db.refresh(wishlist_item)

    return wishlist_item


@router.get("/{item_id}", response_model=WishlistItemResponse)
async def get_wishlist_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get wishlist item by ID."""
    result = await db.execute(select(WishlistItem).where(WishlistItem.id == item_id))
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Wishlist item not found")

    return item


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

    return item


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

    # Update status to searching
    item.status = WishlistStatus.SEARCHING
    await db.commit()

    # Queue Celery task to search Prowlarr
    from app.tasks.downloads import search_wishlist_item as search_task
    search_task.delay(item_id)

    return {"status": "search_queued", "id": item_id}


@router.post("/search-all")
async def search_all_wishlist(
    db: AsyncSession = Depends(get_db),
):
    """Search for all wanted wishlist items."""
    from app.tasks.downloads import process_wishlist

    # Count items to search
    result = await db.execute(
        select(WishlistItem)
        .where(WishlistItem.status == WishlistStatus.WANTED)
    )
    items = result.scalars().all()

    process_wishlist.delay()

    return {"status": "search_all_queued", "items_to_search": len(items)}
