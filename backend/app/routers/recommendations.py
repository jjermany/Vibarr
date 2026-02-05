"""Recommendation endpoints."""

import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.recommendation import Recommendation
from app.models.artist import Artist
from app.models.album import Album
from app.models.wishlist import WishlistItem

logger = logging.getLogger(__name__)

router = APIRouter()


class RecommendationResponse(BaseModel):
    """Recommendation response."""
    id: int
    type: str
    artist_id: Optional[int] = None
    album_id: Optional[int] = None
    track_id: Optional[int] = None
    category: str
    reason: Optional[str] = None
    confidence_score: float
    relevance_score: float
    novelty_score: float

    # Populated data
    artist_name: Optional[str] = None
    album_title: Optional[str] = None
    image_url: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("")
async def get_recommendations(
    category: Optional[str] = Query(None, description="Filter by category"),
    type: Optional[str] = Query(None, description="Filter by type: artist, album, track"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    include_dismissed: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get personalized recommendations with populated artist/album data."""
    query = (
        select(Recommendation)
        .where(Recommendation.confidence_score >= min_confidence)
        .where(Recommendation.expires_at > datetime.utcnow())
    )

    if category:
        query = query.where(Recommendation.category == category)

    if type:
        query = query.where(Recommendation.recommendation_type == type)

    if not include_dismissed:
        query = query.where(Recommendation.dismissed == False)

    query = query.order_by(Recommendation.confidence_score.desc())
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    recommendations = result.scalars().all()

    # Populate artist/album data
    response = []
    for rec in recommendations:
        item = {
            "id": rec.id,
            "type": rec.recommendation_type,
            "artist_id": rec.artist_id,
            "album_id": rec.album_id,
            "category": rec.category,
            "reason": rec.reason,
            "confidence_score": rec.confidence_score,
            "relevance_score": rec.relevance_score,
            "novelty_score": rec.novelty_score,
            "artist_name": None,
            "album_title": None,
            "image_url": None,
        }

        if rec.artist_id:
            artist_result = await db.execute(
                select(Artist).where(Artist.id == rec.artist_id)
            )
            artist = artist_result.scalar_one_or_none()
            if artist:
                item["artist_name"] = artist.name
                item["image_url"] = artist.image_url

        if rec.album_id:
            album_result = await db.execute(
                select(Album).where(Album.id == rec.album_id)
            )
            album = album_result.scalar_one_or_none()
            if album:
                item["album_title"] = album.title
                item["image_url"] = album.cover_url or item["image_url"]
                if not item["artist_name"] and album.artist:
                    item["artist_name"] = album.artist.name

        response.append(item)

    return response


@router.get("/categories")
async def get_recommendation_categories():
    """Get available recommendation categories."""
    categories = [
        {
            "id": "discover_weekly",
            "name": "Discover Weekly",
            "description": "Personalized weekly discoveries",
        },
        {
            "id": "release_radar",
            "name": "Release Radar",
            "description": "New releases from followed artists",
        },
        {
            "id": "similar_artists",
            "name": "Similar Artists",
            "description": "Artists similar to your favorites",
        },
        {
            "id": "deep_cuts",
            "name": "Deep Cuts",
            "description": "Lesser-known albums from artists you know",
        },
        {
            "id": "genre_explore",
            "name": "Genre Exploration",
            "description": "New artists in your favorite genres",
        },
        {
            "id": "mood_based",
            "name": "Mood Based",
            "description": "Music matching your listening mood",
        },
    ]
    return {"categories": categories}


@router.post("/{recommendation_id}/dismiss")
async def dismiss_recommendation(
    recommendation_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Dismiss a recommendation (don't show again)."""
    result = await db.execute(
        select(Recommendation).where(Recommendation.id == recommendation_id)
    )
    rec = result.scalar_one_or_none()

    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    rec.dismissed = True
    rec.dismissed_at = datetime.utcnow()
    await db.commit()

    return {"status": "dismissed", "id": recommendation_id}


@router.post("/{recommendation_id}/click")
async def track_recommendation_click(
    recommendation_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Track when user clicks on a recommendation."""
    result = await db.execute(
        select(Recommendation).where(Recommendation.id == recommendation_id)
    )
    rec = result.scalar_one_or_none()

    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    rec.clicked = True
    rec.clicked_at = datetime.utcnow()
    await db.commit()

    return {"status": "tracked", "id": recommendation_id}


@router.post("/{recommendation_id}/wishlist")
async def add_recommendation_to_wishlist(
    recommendation_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Add recommended item to wishlist."""
    result = await db.execute(
        select(Recommendation).where(Recommendation.id == recommendation_id)
    )
    rec = result.scalar_one_or_none()

    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    rec.added_to_wishlist = True
    rec.added_to_wishlist_at = datetime.utcnow()

    # Create wishlist item from recommendation
    artist_name = None
    album_title = None

    if rec.artist_id:
        artist_result = await db.execute(
            select(Artist).where(Artist.id == rec.artist_id)
        )
        artist = artist_result.scalar_one_or_none()
        if artist:
            artist_name = artist.name

    if rec.album_id:
        album_result = await db.execute(
            select(Album).where(Album.id == rec.album_id)
        )
        album = album_result.scalar_one_or_none()
        if album:
            album_title = album.title
            if not artist_name and album.artist:
                artist_name = album.artist.name

    # Determine item type
    item_type = rec.recommendation_type
    if item_type == "track":
        item_type = "album"  # Wishlist tracks as albums

    wishlist_item = WishlistItem(
        item_type=item_type,
        artist_id=rec.artist_id,
        album_id=rec.album_id,
        artist_name=artist_name or "Unknown",
        album_title=album_title,
        status="wanted",
        priority="medium",
        source="recommendation",
        confidence_score=rec.confidence_score,
        notes=rec.reason,
    )
    db.add(wishlist_item)
    await db.commit()

    return {
        "status": "added_to_wishlist",
        "recommendation_id": recommendation_id,
        "wishlist_item_id": wishlist_item.id,
    }


@router.post("/generate")
async def generate_recommendations(
    category: Optional[str] = Query(None, description="Generate for specific category"),
):
    """Manually trigger recommendation generation."""
    from app.tasks.recommendations import (
        generate_daily_recommendations,
        check_new_releases,
        update_taste_profile,
    )

    if category == "release_radar":
        check_new_releases.delay()
    elif category == "taste_profile":
        update_taste_profile.delay()
    else:
        generate_daily_recommendations.delay()

    return {"status": "generation_queued", "category": category or "all"}


@router.get("/stats")
async def get_recommendation_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get recommendation statistics."""
    total_result = await db.execute(
        select(func.count(Recommendation.id))
    )
    total_generated = total_result.scalar() or 0

    clicked_result = await db.execute(
        select(func.count(Recommendation.id))
        .where(Recommendation.clicked == True)
    )
    total_clicked = clicked_result.scalar() or 0

    wishlisted_result = await db.execute(
        select(func.count(Recommendation.id))
        .where(Recommendation.added_to_wishlist == True)
    )
    total_wishlisted = wishlisted_result.scalar() or 0

    dismissed_result = await db.execute(
        select(func.count(Recommendation.id))
        .where(Recommendation.dismissed == True)
    )
    total_dismissed = dismissed_result.scalar() or 0

    # Active (not expired, not dismissed)
    active_result = await db.execute(
        select(func.count(Recommendation.id))
        .where(Recommendation.dismissed == False)
        .where(Recommendation.expires_at > datetime.utcnow())
    )
    total_active = active_result.scalar() or 0

    # Category breakdown
    category_result = await db.execute(
        select(
            Recommendation.category,
            func.count(Recommendation.id).label("count"),
        )
        .where(Recommendation.dismissed == False)
        .where(Recommendation.expires_at > datetime.utcnow())
        .group_by(Recommendation.category)
    )
    categories = {row.category: row.count for row in category_result.all()}

    click_rate = round(total_clicked / max(total_generated, 1) * 100, 1)
    wishlist_rate = round(total_wishlisted / max(total_generated, 1) * 100, 1)

    return {
        "total_generated": total_generated,
        "total_active": total_active,
        "total_clicked": total_clicked,
        "total_added_to_wishlist": total_wishlisted,
        "total_dismissed": total_dismissed,
        "click_rate": click_rate,
        "wishlist_rate": wishlist_rate,
        "categories": categories,
    }
