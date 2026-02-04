"""Recommendation endpoints."""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.recommendation import Recommendation

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


@router.get("", response_model=List[RecommendationResponse])
async def get_recommendations(
    category: Optional[str] = Query(None, description="Filter by category"),
    type: Optional[str] = Query(None, description="Filter by type: artist, album, track"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    include_dismissed: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get personalized recommendations."""
    query = select(Recommendation).where(Recommendation.confidence_score >= min_confidence)

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

    return recommendations


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

    if rec:
        rec.dismissed = True
        from datetime import datetime
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

    if rec:
        rec.clicked = True
        from datetime import datetime
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

    if rec:
        rec.added_to_wishlist = True
        from datetime import datetime
        rec.added_to_wishlist_at = datetime.utcnow()
        await db.commit()

        # TODO: Actually create wishlist item

    return {"status": "added_to_wishlist", "id": recommendation_id}


@router.post("/generate")
async def generate_recommendations(
    category: Optional[str] = Query(None, description="Generate for specific category"),
):
    """Manually trigger recommendation generation."""
    # TODO: Queue Celery task
    return {"status": "generation_queued", "category": category or "all"}


@router.get("/stats")
async def get_recommendation_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get recommendation statistics."""
    # TODO: Calculate actual stats
    return {
        "total_generated": 0,
        "total_clicked": 0,
        "total_added_to_wishlist": 0,
        "total_dismissed": 0,
        "click_rate": 0.0,
        "wishlist_rate": 0.0,
    }
