"""Social features router - follows, playlists, activity feed, compatibility."""

from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.social import UserFollow, SharedPlaylist, SharedPlaylistItem, ActivityFeed
from app.services.auth import get_current_user, require_user
from app.services.ml_taste_profiler import compute_compatibility_score

router = APIRouter()


# Request/Response models

class FollowRequest(BaseModel):
    user_id: int


class PlaylistCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    is_public: bool = False
    collaborative: bool = False


class PlaylistUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None
    collaborative: Optional[bool] = None


class PlaylistItemAddRequest(BaseModel):
    track_id: Optional[int] = None
    album_id: Optional[int] = None
    artist_id: Optional[int] = None
    note: Optional[str] = None


# === Follow Endpoints ===

@router.post("/follow")
async def follow_user(
    request: FollowRequest,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Follow another user."""
    if request.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")

    # Check target user exists
    target = await db.execute(select(User).where(User.id == request.user_id, User.is_active == True))
    if not target.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    # Check if already following
    existing = await db.execute(
        select(UserFollow).where(
            UserFollow.follower_id == current_user.id,
            UserFollow.following_id == request.user_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already following this user")

    follow = UserFollow(follower_id=current_user.id, following_id=request.user_id)
    db.add(follow)

    # Create activity
    activity = ActivityFeed(
        user_id=current_user.id,
        activity_type="followed_user",
        target_user_id=request.user_id,
        message=f"started following a user",
    )
    db.add(activity)

    await db.commit()
    return {"status": "followed", "user_id": request.user_id}


@router.delete("/follow/{user_id}")
async def unfollow_user(
    user_id: int,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Unfollow a user."""
    result = await db.execute(
        select(UserFollow).where(
            UserFollow.follower_id == current_user.id,
            UserFollow.following_id == user_id,
        )
    )
    follow = result.scalar_one_or_none()
    if not follow:
        raise HTTPException(status_code=404, detail="Not following this user")

    await db.delete(follow)
    await db.commit()
    return {"status": "unfollowed", "user_id": user_id}


@router.get("/followers/{user_id}")
async def get_followers(
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a user's followers."""
    result = await db.execute(
        select(User)
        .join(UserFollow, UserFollow.follower_id == User.id)
        .where(UserFollow.following_id == user_id)
        .order_by(UserFollow.created_at.desc())
    )
    followers = result.scalars().all()

    return [
        {
            "id": u.id,
            "username": u.username,
            "display_name": u.display_name or u.username,
            "avatar_url": u.avatar_url,
            "taste_cluster": u.taste_cluster,
        }
        for u in followers
    ]


@router.get("/following/{user_id}")
async def get_following(
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get users that a user is following."""
    result = await db.execute(
        select(User)
        .join(UserFollow, UserFollow.following_id == User.id)
        .where(UserFollow.follower_id == user_id)
        .order_by(UserFollow.created_at.desc())
    )
    following = result.scalars().all()

    return [
        {
            "id": u.id,
            "username": u.username,
            "display_name": u.display_name or u.username,
            "avatar_url": u.avatar_url,
            "taste_cluster": u.taste_cluster,
        }
        for u in following
    ]


# === Compatibility ===

@router.get("/compatibility/{user_id}")
async def get_compatibility(
    user_id: int,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Get taste compatibility with another user."""
    target = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    target_user = target.scalar_one_or_none()

    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    embedding_a = current_user.compatibility_vector or []
    embedding_b = target_user.compatibility_vector or []

    if not embedding_a or not embedding_b:
        return {
            "compatibility_score": None,
            "message": "Not enough listening data to compute compatibility",
            "per_feature": {},
        }

    score, per_feature = compute_compatibility_score(embedding_a, embedding_b)

    return {
        "compatibility_score": score,
        "user": {
            "id": target_user.id,
            "display_name": target_user.display_name or target_user.username,
            "taste_cluster": target_user.taste_cluster,
        },
        "per_feature": per_feature,
    }


# === Shared Playlists ===

@router.get("/playlists")
async def list_playlists(
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List shared playlists visible to the current user."""
    query = select(SharedPlaylist)

    if current_user:
        query = query.where(
            or_(
                SharedPlaylist.is_public == True,
                SharedPlaylist.owner_id == current_user.id,
            )
        )
    else:
        query = query.where(SharedPlaylist.is_public == True)

    result = await db.execute(query.order_by(SharedPlaylist.updated_at.desc()))
    playlists = result.scalars().all()

    # Get owner info
    owner_ids = set(p.owner_id for p in playlists)
    owners = {}
    if owner_ids:
        owner_result = await db.execute(select(User).where(User.id.in_(owner_ids)))
        for u in owner_result.scalars().all():
            owners[u.id] = u

    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "cover_url": p.cover_url,
            "is_public": p.is_public,
            "collaborative": p.collaborative,
            "total_tracks": p.total_tracks,
            "owner": {
                "id": p.owner_id,
                "display_name": owners.get(p.owner_id, User()).display_name or "Unknown",
            } if p.owner_id in owners else None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }
        for p in playlists
    ]


@router.post("/playlists")
async def create_playlist(
    request: PlaylistCreateRequest,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new shared playlist."""
    playlist = SharedPlaylist(
        name=request.name,
        description=request.description,
        is_public=request.is_public,
        collaborative=request.collaborative,
        owner_id=current_user.id,
    )
    db.add(playlist)

    # Activity feed
    activity = ActivityFeed(
        user_id=current_user.id,
        activity_type="created_playlist",
        playlist_id=None,  # Will be set after flush
        message=f"created playlist \"{request.name}\"",
    )
    db.add(activity)
    await db.commit()
    await db.refresh(playlist)

    return {
        "id": playlist.id,
        "name": playlist.name,
        "description": playlist.description,
        "is_public": playlist.is_public,
        "collaborative": playlist.collaborative,
        "total_tracks": 0,
        "created_at": playlist.created_at.isoformat(),
    }


@router.get("/playlists/{playlist_id}")
async def get_playlist(
    playlist_id: int,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get playlist details with items."""
    result = await db.execute(select(SharedPlaylist).where(SharedPlaylist.id == playlist_id))
    playlist = result.scalar_one_or_none()

    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    if not playlist.is_public and (not current_user or current_user.id != playlist.owner_id):
        raise HTTPException(status_code=403, detail="Playlist is private")

    # Get items
    items_result = await db.execute(
        select(SharedPlaylistItem)
        .where(SharedPlaylistItem.playlist_id == playlist_id)
        .order_by(SharedPlaylistItem.position)
    )
    items = items_result.scalars().all()

    # Get owner
    owner_result = await db.execute(select(User).where(User.id == playlist.owner_id))
    owner = owner_result.scalar_one_or_none()

    return {
        "id": playlist.id,
        "name": playlist.name,
        "description": playlist.description,
        "cover_url": playlist.cover_url,
        "is_public": playlist.is_public,
        "collaborative": playlist.collaborative,
        "total_tracks": playlist.total_tracks,
        "owner": {
            "id": owner.id if owner else None,
            "display_name": owner.display_name if owner else "Unknown",
        },
        "items": [
            {
                "id": item.id,
                "position": item.position,
                "track_id": item.track_id,
                "album_id": item.album_id,
                "artist_id": item.artist_id,
                "note": item.note,
                "added_by_id": item.added_by_id,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in items
        ],
        "created_at": playlist.created_at.isoformat(),
        "updated_at": playlist.updated_at.isoformat(),
    }


@router.patch("/playlists/{playlist_id}")
async def update_playlist(
    playlist_id: int,
    request: PlaylistUpdateRequest,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a playlist."""
    result = await db.execute(select(SharedPlaylist).where(SharedPlaylist.id == playlist_id))
    playlist = result.scalar_one_or_none()

    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    if playlist.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not the playlist owner")

    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(playlist, field, value)

    await db.commit()
    await db.refresh(playlist)

    return {"id": playlist.id, "name": playlist.name, "updated": True}


@router.delete("/playlists/{playlist_id}")
async def delete_playlist(
    playlist_id: int,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a playlist."""
    result = await db.execute(select(SharedPlaylist).where(SharedPlaylist.id == playlist_id))
    playlist = result.scalar_one_or_none()

    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    if playlist.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not the playlist owner")

    await db.delete(playlist)
    await db.commit()
    return {"status": "deleted"}


@router.post("/playlists/{playlist_id}/items")
async def add_playlist_item(
    playlist_id: int,
    request: PlaylistItemAddRequest,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Add an item to a playlist."""
    result = await db.execute(select(SharedPlaylist).where(SharedPlaylist.id == playlist_id))
    playlist = result.scalar_one_or_none()

    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    # Check permissions
    can_edit = (
        playlist.owner_id == current_user.id
        or (playlist.collaborative and current_user.id in (playlist.allowed_editors or []))
    )
    if not can_edit:
        raise HTTPException(status_code=403, detail="Not authorized to edit this playlist")

    item = SharedPlaylistItem(
        playlist_id=playlist_id,
        track_id=request.track_id,
        album_id=request.album_id,
        artist_id=request.artist_id,
        added_by_id=current_user.id,
        note=request.note,
        position=playlist.total_tracks,
    )
    db.add(item)
    playlist.total_tracks += 1

    # Activity
    activity = ActivityFeed(
        user_id=current_user.id,
        activity_type="added_to_playlist",
        playlist_id=playlist_id,
        track_id=request.track_id,
        album_id=request.album_id,
        artist_id=request.artist_id,
        message=f"added an item to \"{playlist.name}\"",
    )
    db.add(activity)

    await db.commit()
    await db.refresh(item)
    return {"id": item.id, "position": item.position, "playlist_id": playlist_id}


@router.delete("/playlists/{playlist_id}/items/{item_id}")
async def remove_playlist_item(
    playlist_id: int,
    item_id: int,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove an item from a playlist."""
    result = await db.execute(
        select(SharedPlaylistItem).where(
            SharedPlaylistItem.id == item_id,
            SharedPlaylistItem.playlist_id == playlist_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Check permissions
    playlist_result = await db.execute(select(SharedPlaylist).where(SharedPlaylist.id == playlist_id))
    playlist = playlist_result.scalar_one_or_none()
    if not playlist or (playlist.owner_id != current_user.id and item.added_by_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    await db.delete(item)
    playlist.total_tracks = max(0, playlist.total_tracks - 1)
    await db.commit()
    return {"status": "removed"}


# === Activity Feed ===

@router.get("/activity")
async def get_activity_feed(
    current_user: User = Depends(require_user),
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Get activity feed from followed users."""
    since = datetime.utcnow() - timedelta(days=days)

    # Get followed user IDs
    following_result = await db.execute(
        select(UserFollow.following_id).where(UserFollow.follower_id == current_user.id)
    )
    following_ids = [row[0] for row in following_result.all()]
    following_ids.append(current_user.id)  # Include own activity

    result = await db.execute(
        select(ActivityFeed)
        .where(
            ActivityFeed.user_id.in_(following_ids),
            ActivityFeed.created_at >= since,
            ActivityFeed.is_public == True,
        )
        .order_by(ActivityFeed.created_at.desc())
        .limit(limit)
    )
    activities = result.scalars().all()

    # Get user info
    user_ids = set(a.user_id for a in activities)
    users = {}
    if user_ids:
        user_result = await db.execute(select(User).where(User.id.in_(user_ids)))
        for u in user_result.scalars().all():
            users[u.id] = u

    return [
        {
            "id": a.id,
            "user": {
                "id": a.user_id,
                "display_name": users.get(a.user_id, User()).display_name or "Unknown",
                "avatar_url": users.get(a.user_id, User()).avatar_url,
            } if a.user_id in users else None,
            "activity_type": a.activity_type,
            "message": a.message,
            "artist_id": a.artist_id,
            "album_id": a.album_id,
            "track_id": a.track_id,
            "playlist_id": a.playlist_id,
            "metadata": a.extra_data,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in activities
    ]


@router.get("/activity/global")
async def get_global_activity(
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get global public activity feed."""
    since = datetime.utcnow() - timedelta(days=7)

    result = await db.execute(
        select(ActivityFeed)
        .where(ActivityFeed.is_public == True, ActivityFeed.created_at >= since)
        .order_by(ActivityFeed.created_at.desc())
        .limit(limit)
    )
    activities = result.scalars().all()

    user_ids = set(a.user_id for a in activities)
    users = {}
    if user_ids:
        user_result = await db.execute(select(User).where(User.id.in_(user_ids)))
        for u in user_result.scalars().all():
            users[u.id] = u

    return [
        {
            "id": a.id,
            "user": {
                "id": a.user_id,
                "display_name": users.get(a.user_id, User()).display_name or "Unknown",
                "avatar_url": users.get(a.user_id, User()).avatar_url,
            } if a.user_id in users else None,
            "activity_type": a.activity_type,
            "message": a.message,
            "metadata": a.extra_data,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in activities
    ]
