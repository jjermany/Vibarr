"""Vibarr - Main FastAPI Application."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Query, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from redis import asyncio as aioredis

logger = logging.getLogger(__name__)

from app.config import get_settings
from app.database import init_db
from app.services.app_settings import ensure_cache as ensure_settings_cache
from app.routers import (
    artists,
    albums,
    auth,
    automation,
    discovery,
    downloads,
    health,
    library,
    recommendations,
    search,
    settings,
    social,
    stats,
    wishlist,
)

config = get_settings()


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------
class ConnectionManager:
    """Manages active WebSocket connections for real-time download updates."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)
        logger.info("WebSocket client connected; total=%d", len(self._connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections = [c for c in self._connections if c is not websocket]
        logger.info("WebSocket client disconnected; total=%d", len(self._connections))

    async def broadcast(self, message: str) -> None:
        async with self._lock:
            dead: list[WebSocket] = []
            for ws in self._connections:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.append(ws)
            if dead:
                self._connections = [c for c in self._connections if c not in dead]


connection_manager = ConnectionManager()


async def _redis_pubsub_listener() -> None:
    """Subscribe to the Redis download_updates channel and broadcast to WebSocket clients."""
    while True:
        try:
            redis = aioredis.from_url(config.redis_url, decode_responses=True)
            pubsub = redis.pubsub()
            await pubsub.subscribe("download_updates")
            logger.info("Redis pub/sub listener subscribed to 'download_updates'")
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await connection_manager.broadcast(message["data"])
        except Exception as exc:
            logger.warning("Redis pub/sub listener error: %s — reconnecting in 5s", exc)
            await asyncio.sleep(5)


# Paths that do NOT require authentication
AUTH_EXEMPT_PATHS = {
    "/",
    "/health",
    "/ws/downloads",  # auth handled via query-param token check in the endpoint
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/setup",
    "/api/auth/setup-status",
    "/api/auth/plex/pin",
    "/api/auth/plex/callback",
}
AUTH_EXEMPT_PREFIXES = (
    "/docs",
    "/redoc",
    "/openapi",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    await init_db()
    await ensure_settings_cache()
    listener_task = asyncio.create_task(
        _redis_pubsub_listener(), name="redis_pubsub_listener"
    )
    yield
    listener_task.cancel()
    try:
        await listener_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title=config.app_name,
    description="Music Metadata Discovery & Recommendation Engine",
    version=config.app_version,
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


@app.middleware("http")
async def require_authentication(request: Request, call_next):
    """Enforce JWT authentication on all API routes except exempt paths."""
    path = request.url.path.rstrip("/")

    # Skip auth for exempt paths
    if path in AUTH_EXEMPT_PATHS or path.startswith(AUTH_EXEMPT_PREFIXES):
        return await call_next(request)

    # Skip auth for non-API paths (health, root, static)
    if not path.startswith("/api"):
        return await call_next(request)

    # Extract and validate token
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Authentication required"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header[7:]
    try:
        payload = jwt.decode(token, config.secret_key, algorithms=["HS256"])
        if payload.get("sub") is None:
            raise JWTError("Missing subject")
    except JWTError:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid or expired token"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await call_next(request)


@app.websocket("/ws/downloads")
async def websocket_downloads(
    websocket: WebSocket,
    token: str = Query(..., description="JWT auth token"),
) -> None:
    """Real-time download status updates via WebSocket. Authenticate via ?token=<jwt>."""
    try:
        payload = jwt.decode(token, config.secret_key, algorithms=["HS256"])
        if payload.get("sub") is None:
            await websocket.close(code=4001, reason="Unauthorized")
            return
    except JWTError:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    await connection_manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive; data is pushed via broadcast()
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await connection_manager.disconnect(websocket)


# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
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
app.include_router(social.router, prefix="/api/social", tags=["Social"])
app.include_router(automation.router, prefix="/api/automation", tags=["Automation"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": config.app_name,
        "version": config.app_version,
        "description": "Music Metadata Discovery & Recommendation Engine",
    }
