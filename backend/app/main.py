"""Vibarr - Main FastAPI Application."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.routers import (
    artists,
    albums,
    discovery,
    downloads,
    health,
    library,
    recommendations,
    search,
    settings,
    stats,
    wishlist,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    await init_db()
    yield
    # Shutdown
    pass


app = FastAPI(
    title=settings.app_name,
    description="Music Metadata Discovery & Recommendation Engine",
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(search.router, prefix="/api/search", tags=["Search"])
app.include_router(artists.router, prefix="/api/artists", tags=["Artists"])
app.include_router(albums.router, prefix="/api/albums", tags=["Albums"])
app.include_router(library.router, prefix="/api/library", tags=["Library"])
app.include_router(discovery.router, prefix="/api/discovery", tags=["Discovery"])
app.include_router(recommendations.router, prefix="/api/recommendations", tags=["Recommendations"])
app.include_router(wishlist.router, prefix="/api/wishlist", tags=["Wishlist"])
app.include_router(downloads.router, prefix="/api/downloads", tags=["Downloads"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
app.include_router(stats.router, prefix="/api/stats", tags=["Statistics"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "Music Metadata Discovery & Recommendation Engine",
    }
