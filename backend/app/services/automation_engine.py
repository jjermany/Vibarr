"""Advanced automation rules engine for evaluating and executing user-defined rules."""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def evaluate_condition(condition: Dict, context: Dict[str, Any]) -> bool:
    """Evaluate a single condition against a context.

    condition: {"field": "genre", "operator": "contains", "value": "rock"}
    context: {"genre": ["rock", "alternative"], "artist_name": "Band Name", ...}
    """
    field = condition.get("field", "")
    operator = condition.get("operator", "")
    expected = condition.get("value")
    actual = context.get(field)

    if actual is None:
        return operator in ("not_equals", "not_contains", "not_in_list")

    try:
        if operator == "equals":
            return _normalize(actual) == _normalize(expected)

        elif operator == "not_equals":
            return _normalize(actual) != _normalize(expected)

        elif operator == "contains":
            if isinstance(actual, list):
                return any(_normalize(expected) in _normalize(str(item)) for item in actual)
            return _normalize(expected) in _normalize(str(actual))

        elif operator == "not_contains":
            if isinstance(actual, list):
                return not any(_normalize(expected) in _normalize(str(item)) for item in actual)
            return _normalize(expected) not in _normalize(str(actual))

        elif operator == "greater_than":
            return float(actual) > float(expected)

        elif operator == "less_than":
            return float(actual) < float(expected)

        elif operator == "in_list":
            if isinstance(expected, list):
                return _normalize(actual) in [_normalize(v) for v in expected]
            return _normalize(actual) in [_normalize(v) for v in str(expected).split(",")]

        elif operator == "not_in_list":
            if isinstance(expected, list):
                return _normalize(actual) not in [_normalize(v) for v in expected]
            return _normalize(actual) not in [_normalize(v) for v in str(expected).split(",")]

        elif operator == "matches_regex":
            return bool(re.search(str(expected), str(actual), re.IGNORECASE))

        else:
            logger.warning(f"Unknown operator: {operator}")
            return False

    except (ValueError, TypeError) as e:
        logger.warning(f"Condition evaluation error: {e}")
        return False


def evaluate_all_conditions(conditions: List[Dict], context: Dict[str, Any]) -> bool:
    """Evaluate all conditions (AND logic). All must pass for the rule to fire."""
    if not conditions:
        return True

    return all(evaluate_condition(cond, context) for cond in conditions)


def build_context_from_item(item: Dict, item_type: str = "album") -> Dict[str, Any]:
    """Build evaluation context from an item dictionary.

    Extracts relevant fields that can be matched against rule conditions.
    """
    context = {}

    # Common fields
    context["artist_name"] = item.get("artist_name", "")
    context["genre"] = item.get("genres", [])
    context["release_year"] = item.get("release_year")
    context["popularity"] = item.get("popularity") or item.get("spotify_popularity", 0)
    context["source"] = item.get("source", "")

    # Audio features
    context["audio_energy"] = item.get("energy") or item.get("avg_energy")
    context["audio_danceability"] = item.get("danceability") or item.get("avg_danceability")
    context["audio_valence"] = item.get("valence") or item.get("avg_valence")
    context["audio_tempo"] = item.get("tempo") or item.get("avg_tempo")
    context["audio_acousticness"] = item.get("acousticness") or item.get("avg_acousticness")
    context["audio_instrumentalness"] = item.get("instrumentalness") or item.get("avg_instrumentalness")

    # Recommendation-specific
    context["confidence_score"] = item.get("confidence_score", 0)
    context["category"] = item.get("category", "")
    context["recommendation_type"] = item.get("recommendation_type", "")

    # Download-specific
    context["seeders"] = item.get("seeders", 0)
    context["format"] = item.get("format") or item.get("release_format", "")
    context["quality"] = item.get("quality") or item.get("release_quality", "")

    # Album-specific
    context["album_type"] = item.get("album_type", "")
    context["album_title"] = item.get("album_title") or item.get("title", "")

    # Listening-specific
    context["play_count"] = item.get("play_count", 0)

    return context


async def execute_action(action: Dict, context: Dict[str, Any], db=None) -> Dict:
    """Execute a single automation action.

    Returns a result dict with execution status.
    """
    action_type = action.get("type", "")
    params = action.get("params", {})

    result = {
        "action_type": action_type,
        "success": False,
        "message": "",
    }

    try:
        if action_type == "add_to_wishlist":
            result.update(await _action_add_to_wishlist(context, params, db))

        elif action_type == "start_download":
            result.update(await _action_start_download(context, params, db))

        elif action_type == "add_to_playlist":
            result.update(await _action_add_to_playlist(context, params, db))

        elif action_type == "send_notification":
            result.update(_action_send_notification(context, params))

        elif action_type == "tag_item":
            result.update(await _action_tag_item(context, params, db))

        elif action_type == "set_quality_profile":
            result.update(_action_set_quality_profile(context, params))

        elif action_type == "skip_item":
            result.update({"success": True, "message": "Item skipped"})

        elif action_type == "add_to_library":
            result.update(await _action_add_to_library(context, params, db))

        elif action_type == "import_playlist_url":
            result.update(await _action_import_playlist_url(context, params, db))

        else:
            result["message"] = f"Unknown action type: {action_type}"

    except Exception as e:
        result["message"] = f"Action execution error: {str(e)}"
        logger.error(f"Error executing action {action_type}: {e}")

    return result


async def execute_rule_actions(
    actions: List[Dict], context: Dict[str, Any], db=None
) -> List[Dict]:
    """Execute all actions for a rule in order.

    Returns list of action results. Stops on first skip_item action.
    """
    results = []

    for action in actions:
        action_result = await execute_action(action, context, db)
        results.append(action_result)

        # Stop processing if skip action
        if action.get("type") == "skip_item":
            break

    return results


async def _action_add_to_wishlist(context: Dict, params: Dict, db) -> Dict:
    """Add item to wishlist."""
    if not db:
        return {"success": False, "message": "No database session"}

    from app.models.wishlist import WishlistItem

    item = WishlistItem(
        item_type=params.get("item_type", "album"),
        artist_name=context.get("artist_name", ""),
        album_title=context.get("album_title", ""),
        status="wanted",
        priority=params.get("priority", "normal"),
        source="automation",
        auto_download=params.get("auto_download", False),
    )
    db.add(item)
    await db.flush()

    return {"success": True, "message": f"Added to wishlist: {context.get('artist_name')} - {context.get('album_title')}"}


async def _action_start_download(context: Dict, params: Dict, db) -> Dict:
    """Queue a download."""
    if not db:
        return {"success": False, "message": "No database session"}

    from app.models.download import Download

    download = Download(
        artist_name=context.get("artist_name", ""),
        album_title=context.get("album_title", ""),
        status="pending",
        source="automation",
    )
    db.add(download)
    await db.flush()

    return {"success": True, "message": f"Download queued: {context.get('artist_name')} - {context.get('album_title')}"}


async def _action_add_to_playlist(context: Dict, params: Dict, db) -> Dict:
    """Add item to a shared playlist."""
    playlist_id = params.get("playlist_id")
    if not playlist_id or not db:
        return {"success": False, "message": "No playlist specified or no database session"}

    from app.models.social import SharedPlaylistItem

    item = SharedPlaylistItem(
        playlist_id=playlist_id,
        artist_id=context.get("artist_id"),
        album_id=context.get("album_id"),
        track_id=context.get("track_id"),
        added_by_id=context.get("user_id", 1),
        note=params.get("note", "Added by automation rule"),
    )
    db.add(item)
    await db.flush()

    return {"success": True, "message": f"Added to playlist {playlist_id}"}


def _action_send_notification(context: Dict, params: Dict) -> Dict:
    """Send a notification (logged for now)."""
    message = params.get("message", "Automation rule triggered")
    # Format message with context values
    try:
        message = message.format(**context)
    except (KeyError, IndexError):
        pass

    logger.info(f"Automation notification: {message}")
    return {"success": True, "message": f"Notification sent: {message}"}


async def _action_tag_item(context: Dict, params: Dict, db) -> Dict:
    """Tag an artist or album."""
    tags = params.get("tags", [])
    if not tags or not db:
        return {"success": False, "message": "No tags specified or no database session"}

    artist_id = context.get("artist_id")
    if artist_id:
        from app.models.artist import Artist
        from sqlalchemy import select

        result = await db.execute(select(Artist).where(Artist.id == artist_id))
        artist = result.scalar_one_or_none()
        if artist:
            existing_tags = artist.tags or []
            artist.tags = list(set(existing_tags + tags))
            return {"success": True, "message": f"Tagged artist with: {tags}"}

    return {"success": False, "message": "Item not found for tagging"}


def _action_set_quality_profile(context: Dict, params: Dict) -> Dict:
    """Set quality profile for download context."""
    profile_name = params.get("profile_name", "")
    context["quality_profile"] = profile_name
    return {"success": True, "message": f"Quality profile set to: {profile_name}"}


async def _action_add_to_library(context: Dict, params: Dict, db) -> Dict:
    """Mark an item as in library."""
    if not db:
        return {"success": False, "message": "No database session"}

    album_id = context.get("album_id")
    if album_id:
        from app.models.album import Album
        from sqlalchemy import select

        result = await db.execute(select(Album).where(Album.id == album_id))
        album = result.scalar_one_or_none()
        if album:
            album.in_library = True
            return {"success": True, "message": f"Added album to library: {album.title}"}

    return {"success": False, "message": "Item not found"}


async def _action_import_playlist_url(context: Dict, params: Dict, db) -> Dict:
    """Import tracks from a playlist URL into the wishlist.

    Resolves the playlist via Deezer or YouTube Music, creates a single
    ``playlist`` wishlist item, plus individual ``track`` items for each
    track not already present (deduplication by artist + title).
    """
    if not db:
        return {"success": False, "message": "No database session"}

    url = params.get("url", "")
    if not url:
        return {"success": False, "message": "No playlist URL specified"}

    from app.routers.search import (
        DEEZER_PLAYLIST_PATTERN,
        YOUTUBE_PLAYLIST_PATTERN,
        _resolve_deezer_playlist,
        _resolve_youtube_playlist,
    )
    from app.models.wishlist import WishlistItem
    from sqlalchemy import select, and_, func

    try:
        deezer_match = DEEZER_PLAYLIST_PATTERN.search(url)
        youtube_match = YOUTUBE_PLAYLIST_PATTERN.search(url)

        if deezer_match:
            playlist = await _resolve_deezer_playlist(url, deezer_match.group(1))
        elif youtube_match:
            playlist = await _resolve_youtube_playlist(url, youtube_match.group(1))
        else:
            return {"success": False, "message": f"Unsupported playlist URL: {url}"}

        priority = params.get("priority", "normal")
        auto_download = params.get("auto_download", False)

        added = 0

        # Check if playlist-level item already exists (by title + type)
        existing_playlist = await db.execute(
            select(WishlistItem).where(
                and_(
                    func.lower(WishlistItem.album_title) == playlist.title.lower(),
                    WishlistItem.item_type == "playlist",
                )
            )
        )
        if not existing_playlist.scalar_one_or_none():
            playlist_item = WishlistItem(
                item_type="playlist",
                artist_name=playlist.creator or "",
                album_title=playlist.title,
                image_url=playlist.image_url,
                status="wanted",
                priority=priority,
                source="automation",
                auto_download=auto_download,
                notes=f"Playlist URL: {url}",
            )
            db.add(playlist_item)
            added += 1

        # Add individual tracks, skipping duplicates
        for track in playlist.tracks:
            track_title = f"{track.name}"
            if track.album_name:
                track_title += f" \u00b7 {track.album_name}"

            existing = await db.execute(
                select(WishlistItem).where(
                    and_(
                        func.lower(WishlistItem.artist_name) == (track.artist_name or "").lower(),
                        func.lower(WishlistItem.album_title) == track_title.lower(),
                    )
                )
            )
            if existing.scalar_one_or_none():
                continue

            item = WishlistItem(
                item_type="track",
                artist_name=track.artist_name or "",
                album_title=track_title,
                image_url=track.image_url,
                status="wanted",
                priority=priority,
                source="automation",
                auto_download=auto_download,
                notes=f"From playlist: {playlist.title}",
            )
            db.add(item)
            added += 1

        await db.flush()
        return {
            "success": True,
            "message": (
                f"Imported {added} new items from playlist "
                f"'{playlist.title}' ({playlist.track_count} total tracks)"
            ),
        }

    except Exception as e:
        return {"success": False, "message": f"Playlist import failed: {str(e)}"}


def _normalize(value: Any) -> str:
    """Normalize a value for comparison."""
    if value is None:
        return ""
    return str(value).strip().lower()
