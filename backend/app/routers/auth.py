"""Authentication router for user registration, login, and profile management."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    get_password_hash,
    require_user,
)

router = APIRouter()


# Request/Response models

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    display_name: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class ProfileUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    profile_public: Optional[bool] = None
    share_listening_activity: Optional[bool] = None
    share_library: Optional[bool] = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    bio: Optional[str]
    is_admin: bool
    profile_public: bool
    share_listening_activity: bool
    share_library: bool
    taste_cluster: Optional[str]
    taste_tags: Optional[list]
    created_at: str


def _user_to_dict(user: User) -> dict:
    """Convert user model to response dict."""
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "display_name": user.display_name or user.username,
        "avatar_url": user.avatar_url,
        "bio": user.bio,
        "is_admin": user.is_admin,
        "profile_public": user.profile_public,
        "share_listening_activity": user.share_listening_activity,
        "share_library": user.share_library,
        "taste_cluster": user.taste_cluster,
        "taste_tags": user.taste_tags or [],
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user."""
    # Check if username exists
    existing = await db.execute(
        select(User).where(
            (func.lower(User.username) == request.username.lower())
            | (func.lower(User.email) == request.email.lower())
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered",
        )

    # Check if this is the first user (make admin)
    count_result = await db.execute(select(func.count(User.id)))
    user_count = count_result.scalar() or 0

    user = User(
        username=request.username,
        email=request.email,
        hashed_password=get_password_hash(request.password),
        display_name=request.display_name or request.username,
        is_admin=user_count == 0,  # First user is admin
        last_login_at=datetime.utcnow(),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(data={"sub": user.id})
    return TokenResponse(
        access_token=token,
        user=_user_to_dict(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate and get access token."""
    user = await authenticate_user(db, request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user.last_login_at = datetime.utcnow()
    await db.commit()

    token = create_access_token(data={"sub": user.id})
    return TokenResponse(
        access_token=token,
        user=_user_to_dict(user),
    )


@router.get("/me")
async def get_profile(current_user: User = Depends(require_user)):
    """Get current user profile."""
    return _user_to_dict(current_user)


@router.patch("/me")
async def update_profile(
    request: ProfileUpdateRequest,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user profile."""
    update_data = request.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(current_user, field, value)

    await db.commit()
    await db.refresh(current_user)
    return _user_to_dict(current_user)


@router.get("/users")
async def list_users(
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all users with public profiles."""
    query = select(User).where(User.is_active == True)
    if not current_user or not current_user.is_admin:
        query = query.where(User.profile_public == True)

    result = await db.execute(query.order_by(User.created_at))
    users = result.scalars().all()

    return [
        {
            "id": u.id,
            "username": u.username,
            "display_name": u.display_name or u.username,
            "avatar_url": u.avatar_url,
            "bio": u.bio,
            "taste_cluster": u.taste_cluster,
            "taste_tags": u.taste_tags or [],
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific user's public profile."""
    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.profile_public and (not current_user or current_user.id != user.id):
        raise HTTPException(status_code=403, detail="Profile is private")

    # Get follower/following counts
    from app.models.social import UserFollow
    follower_count = await db.execute(
        select(func.count(UserFollow.id)).where(UserFollow.following_id == user_id)
    )
    following_count = await db.execute(
        select(func.count(UserFollow.id)).where(UserFollow.follower_id == user_id)
    )

    is_following = False
    if current_user:
        follow_check = await db.execute(
            select(UserFollow).where(
                UserFollow.follower_id == current_user.id,
                UserFollow.following_id == user_id,
            )
        )
        is_following = follow_check.scalar_one_or_none() is not None

    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name or user.username,
        "avatar_url": user.avatar_url,
        "bio": user.bio,
        "taste_cluster": user.taste_cluster,
        "taste_tags": user.taste_tags or [],
        "follower_count": follower_count.scalar() or 0,
        "following_count": following_count.scalar() or 0,
        "is_following": is_following,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
