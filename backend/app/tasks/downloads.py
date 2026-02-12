"""Download management tasks."""

import logging
from datetime import datetime

from app.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.services.prowlarr import prowlarr_service
from app.services.download_client import download_client_service
from app.services.beets import beets_service
from app.services.sabnzbd import sabnzbd_service
from app.services import app_settings as cfg
from app.models.wishlist import WishlistItem, WishlistStatus
from app.models.download import Download, DownloadStatus

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _sync_wishlist_status(db, download: Download, target_status: WishlistStatus, message: str = None):
    """Sync wishlist status for a download and commit in one place."""
    if not download.wishlist_id:
        return None

    from sqlalchemy import select

    wishlist_result = await db.execute(
        select(WishlistItem).where(WishlistItem.id == download.wishlist_id)
    )
    wishlist_item = wishlist_result.scalar_one_or_none()

    if not wishlist_item:
        return None

    wishlist_item.status = target_status
    if message:
        wishlist_item.notes = message

    await db.commit()
    return wishlist_item


@celery_app.task(name="app.tasks.downloads.process_wishlist")
def process_wishlist(search_all=False):
    """Process wishlist items and search for downloads."""
    return _run_async(_process_wishlist_async(search_all=search_all))


async def _process_wishlist_async(search_all=False):
    """Async implementation of wishlist processing."""
    logger.info("Processing wishlist")

    await cfg.ensure_cache()

    if not prowlarr_service.is_available:
        return {"status": "skipped", "reason": "Prowlarr not available"}

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select

        # Get wanted items (auto_download only for scheduled runs, all for manual)
        query = select(WishlistItem).where(WishlistItem.status == WishlistStatus.WANTED)
        if not search_all:
            query = query.where(WishlistItem.auto_download == True)
        result = await db.execute(query)
        items = result.scalars().all()

        searched = 0
        found = 0
        grabbed = 0

        for item in items:
            try:
                # Update status
                item.status = WishlistStatus.SEARCHING
                item.last_searched_at = datetime.utcnow()
                item.search_count += 1
                await db.commit()

                artist_name = item.artist_name or ""
                album_title = item.album_title or ""

                if not artist_name and not album_title:
                    item.status = WishlistStatus.WANTED
                    await db.commit()
                    continue

                # Search via Prowlarr
                results = await prowlarr_service.search_album(
                    artist=artist_name,
                    album=album_title,
                    preferred_format=item.preferred_format or cfg.get_setting("preferred_quality", "flac"),
                )
                searched += 1

                if results:
                    best_result = results[0]  # Already sorted by score

                    item.status = WishlistStatus.FOUND
                    found += 1

                    # Create download entry
                    download = Download(
                        wishlist_id=item.id,
                        album_id=item.album_id,
                        artist_name=artist_name,
                        album_title=album_title,
                        status=DownloadStatus.FOUND,
                        search_query=f"{artist_name} {album_title}",
                        indexer_name=best_result.get("indexer"),
                        indexer_id=str(best_result.get("indexer_id", "")),
                        release_title=best_result.get("title"),
                        release_size=best_result.get("size"),
                        release_format=best_result.get("format"),
                        release_quality=best_result.get("quality"),
                        seeders=best_result.get("seeders"),
                        leechers=best_result.get("leechers"),
                        source="wishlist",
                    )
                    db.add(download)
                    await db.commit()
                    await db.refresh(download)

                    # Auto-grab if score meets threshold
                    if (
                        cfg.get_bool("auto_download_enabled")
                        and best_result.get("score", 0)
                        >= cfg.get_float("auto_download_confidence_threshold", 0.8) * 100
                    ):
                        # Check concurrent download limit
                        active_count = 0
                        if download_client_service.is_configured:
                            active_count = await download_client_service.get_active_count()

                        if active_count < cfg.get_int("max_concurrent_downloads", 3):
                            grab_release.delay(
                                download_id=download.id,
                                guid=best_result.get("guid"),
                                indexer_id=best_result.get("indexer_id"),
                            )
                            grabbed += 1
                        else:
                            logger.info(
                                f"Skipping auto-grab for '{album_title}': "
                                f"concurrent limit reached ({active_count}/{cfg.get_int('max_concurrent_downloads', 3)})"
                            )
                else:
                    item.status = WishlistStatus.WANTED
                    await db.commit()

            except Exception as e:
                logger.error(f"Error processing wishlist item {item.id}: {e}")
                item.status = WishlistStatus.WANTED
                await db.commit()
                continue

    return {
        "status": "completed",
        "items_searched": searched,
        "items_found": found,
        "items_grabbed": grabbed,
    }


@celery_app.task(name="app.tasks.downloads.search_wishlist_item")
def search_wishlist_item(item_id: int):
    """Search for a specific wishlist item via Prowlarr."""
    return _run_async(_search_wishlist_item_async(item_id))


async def _search_wishlist_item_async(item_id: int):
    """Async implementation of individual wishlist item search."""
    logger.info(f"Searching for wishlist item {item_id}")

    await cfg.ensure_cache()

    if not prowlarr_service.is_available:
        return {"status": "skipped", "reason": "Prowlarr not configured"}

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select

        result = await db.execute(
            select(WishlistItem).where(WishlistItem.id == item_id)
        )
        item = result.scalar_one_or_none()

        if not item:
            return {"status": "error", "message": "Item not found"}

        artist_name = item.artist_name or ""
        album_title = item.album_title or ""

        if not artist_name and not album_title:
            item.status = WishlistStatus.WANTED
            await db.commit()
            return {"status": "error", "message": "No search terms"}

        try:
            item.status = WishlistStatus.SEARCHING
            item.last_searched_at = datetime.utcnow()
            item.search_count += 1
            await db.commit()

            results = await prowlarr_service.search_album(
                artist=artist_name,
                album=album_title,
                preferred_format=item.preferred_format,
            )

            if results:
                best_result = results[0]  # Already sorted by score

                item.status = WishlistStatus.FOUND
                # Create download entry for the best result
                download = Download(
                    wishlist_id=item.id,
                    album_id=item.album_id,
                    artist_name=artist_name,
                    album_title=album_title,
                    status=DownloadStatus.FOUND,
                    search_query=f"{artist_name} {album_title}",
                    indexer_name=best_result.get("indexer"),
                    indexer_id=str(best_result.get("indexer_id", "")),
                    release_title=best_result.get("title"),
                    release_size=best_result.get("size"),
                    release_format=best_result.get("format"),
                    release_quality=best_result.get("quality"),
                    seeders=best_result.get("seeders"),
                    leechers=best_result.get("leechers"),
                    source="wishlist",
                )
                db.add(download)
                await db.commit()
                await db.refresh(download)

                # Auto-grab if enabled and score meets threshold
                if (
                    cfg.get_bool("auto_download_enabled")
                    and best_result.get("score", 0)
                    >= cfg.get_float("auto_download_confidence_threshold", 0.8) * 100
                ):
                    active_count = 0
                    if download_client_service.is_configured:
                        active_count = await download_client_service.get_active_count()

                    if active_count < cfg.get_int("max_concurrent_downloads", 3):
                        grab_release.delay(
                            download_id=download.id,
                            guid=best_result.get("guid"),
                            indexer_id=best_result.get("indexer_id"),
                        )
                    else:
                        logger.info(
                            f"Skipping auto-grab for '{album_title}': "
                            f"concurrent limit reached ({active_count}/{cfg.get_int('max_concurrent_downloads', 3)})"
                        )

                return {
                    "status": "found",
                    "results_count": len(results),
                    "download_id": download.id,
                }
            else:
                item.status = WishlistStatus.WANTED
                await db.commit()
                return {"status": "not_found"}

        except Exception as e:
            logger.error(f"Error searching for wishlist item {item_id}: {e}")
            item.status = WishlistStatus.WANTED
            await db.commit()
            return {"status": "error", "message": str(e)}


@celery_app.task(name="app.tasks.downloads.search_for_album")
def search_for_album(
    download_id: int,
    artist: str,
    album: str,
    preferred_format: str = None,
):
    """Search for a specific album."""
    return _run_async(
        _search_for_album_async(download_id, artist, album, preferred_format)
    )


async def _search_for_album_async(
    download_id: int,
    artist: str,
    album: str,
    preferred_format: str,
):
    """Async implementation of album search."""
    logger.info(f"Searching for album: {artist} - {album}")

    await cfg.ensure_cache()

    if not prowlarr_service.is_available:
        return {"status": "error", "message": "Prowlarr not available"}

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select

        result = await db.execute(
            select(Download).where(Download.id == download_id)
        )
        download = result.scalar_one_or_none()

        if not download:
            return {"status": "error", "message": "Download not found"}

        try:
            download.status = DownloadStatus.SEARCHING
            await db.commit()

            results = await prowlarr_service.search_album(
                artist=artist,
                album=album,
                preferred_format=preferred_format,
            )

            if results:
                best_result = results[0]
                download.status = DownloadStatus.FOUND
                download.indexer_name = best_result.get("indexer")
                download.indexer_id = str(best_result.get("indexer_id", ""))
                download.release_title = best_result.get("title")
                download.release_size = best_result.get("size")
                download.release_format = best_result.get("format")
                download.release_quality = best_result.get("quality")
                download.seeders = best_result.get("seeders")
                download.leechers = best_result.get("leechers")
                await db.commit()

                return {
                    "status": "found",
                    "download_id": download_id,
                    "results_count": len(results),
                    "best_result": best_result,
                }
            else:
                download.status = DownloadStatus.FAILED
                download.status_message = "No results found"
                await db.commit()

                return {
                    "status": "not_found",
                    "download_id": download_id,
                }

        except Exception as e:
            logger.error(f"Search failed for download {download_id}: {e}")
            download.status = DownloadStatus.FAILED
            download.status_message = str(e)
            await db.commit()
            return {"status": "error", "message": str(e)}


@celery_app.task(name="app.tasks.downloads.grab_release")
def grab_release(download_id: int, guid: str, indexer_id: int):
    """Grab a release and send to download client."""
    return _run_async(_grab_release_async(download_id, guid, indexer_id))


async def _grab_release_async(download_id: int, guid: str, indexer_id: int):
    """Async implementation of release grab."""
    logger.info(f"Grabbing release for download {download_id}")

    await cfg.ensure_cache()

    if not prowlarr_service.is_available:
        return {"status": "error", "message": "Prowlarr not available"}

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select

        result = await db.execute(
            select(Download).where(Download.id == download_id)
        )
        download = result.scalar_one_or_none()

        if not download:
            return {"status": "error", "message": "Download not found"}

        try:
            download.status = DownloadStatus.QUEUED
            await db.commit()

            # Grab via Prowlarr (sends to download client)
            download_client_id = await prowlarr_service.grab(guid, indexer_id)

            if download_client_id:
                download.status = DownloadStatus.DOWNLOADING
                download.download_id = str(download_client_id)
                download.started_at = datetime.utcnow()
                await db.commit()

                await _sync_wishlist_status(
                    db,
                    download,
                    WishlistStatus.DOWNLOADING,
                )

                return {
                    "status": "grabbed",
                    "download_id": download_id,
                    "client_id": download_client_id,
                }
            else:
                download.status = DownloadStatus.FAILED
                download.status_message = "Failed to grab release from Prowlarr"
                await db.commit()
                await _sync_wishlist_status(
                    db,
                    download,
                    WishlistStatus.FAILED,
                    message=download.status_message,
                )
                return {"status": "error", "message": "Failed to grab release"}

        except Exception as e:
            logger.error(f"Grab failed for download {download_id}: {e}")
            download.status = DownloadStatus.FAILED
            download.status_message = str(e)
            await db.commit()
            await _sync_wishlist_status(
                db,
                download,
                WishlistStatus.FAILED,
                message=download.status_message,
            )
            return {"status": "error", "message": str(e)}


@celery_app.task(name="app.tasks.downloads.check_download_status")
def check_download_status():
    """Check status of active downloads via qBittorrent."""
    return _run_async(_check_download_status_async())


async def _check_download_status_async():
    """Check and update download statuses from qBittorrent.

    Handles the incomplete → completed path flow: when qBittorrent finishes
    a torrent it moves files from the incomplete/cache path to the completed
    path. We detect this and update download_path so the import step uses
    the correct final location (similar to how Sonarr/Radarr handle it).
    """
    logger.info("Checking download statuses")

    if not download_client_service.is_configured:
        return {"status": "skipped", "reason": "Download client not configured"}

    await cfg.ensure_cache()

    completed_dir = (
        cfg.get_setting("qbittorrent_completed_path")
        or cfg.get_setting("completed_download_path", "/media/completed")
    )

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select

        # Get all downloads that are actively downloading
        result = await db.execute(
            select(Download).where(
                Download.status == DownloadStatus.DOWNLOADING,
                Download.download_id.isnot(None),
            )
        )
        active_downloads = result.scalars().all()

        if not active_downloads:
            return {"status": "completed", "checked": 0}

        updated = 0
        completed = 0

        for download in active_downloads:
            try:
                torrent = await download_client_service.get_torrent(
                    download.download_id
                )

                if not torrent:
                    logger.warning(
                        f"Torrent {download.download_id} not found in client "
                        f"for download {download.id}"
                    )
                    continue

                # Update progress info
                download.progress = torrent.progress
                download.download_speed = torrent.dl_speed
                download.eta_seconds = torrent.eta if torrent.eta < 8640000 else None
                # Always track the latest content path from qBittorrent
                download.download_path = torrent.content_path or torrent.save_path
                updated += 1

                if torrent.is_complete:
                    download.progress = 100.0
                    download.completed_at = datetime.utcnow()
                    download.download_speed = None
                    download.eta_seconds = None
                    completed += 1

                    # When qBit moves files from incomplete to completed,
                    # the content_path / save_path updates. Use the
                    # completed directory setting as the canonical path if
                    # the torrent's reported path lives there.
                    final_path = torrent.content_path or torrent.save_path
                    if completed_dir and final_path:
                        download.download_path = final_path

                    # Auto-import with beets if enabled (Arr-style)
                    if cfg.get_bool("beets_enabled") and cfg.get_bool("beets_auto_import", True):
                        import_completed_download.delay(download_id=download.id)
                        download.status = DownloadStatus.IMPORTING
                        await _sync_wishlist_status(
                            db,
                            download,
                            WishlistStatus.IMPORTING,
                        )
                    else:
                        download.status = DownloadStatus.COMPLETED
                        await _sync_wishlist_status(
                            db,
                            download,
                            WishlistStatus.DOWNLOADED,
                        )

                    # Optionally remove the torrent from qBittorrent after
                    # import (like the Arrs do after a successful grab).
                    if cfg.get_bool("qbittorrent_remove_completed"):
                        await download_client_service.delete_torrent(
                            download.download_id, delete_files=False
                        )

                elif torrent.is_errored:
                    download.status = DownloadStatus.FAILED
                    download.status_message = f"Download client error: {torrent.state}"
                    download.completed_at = datetime.utcnow()
                    await _sync_wishlist_status(
                        db,
                        download,
                        WishlistStatus.FAILED,
                        message=download.status_message,
                    )

                await db.commit()

            except Exception as e:
                logger.error(
                    f"Error checking download {download.id}: {e}"
                )
                continue

    return {
        "status": "completed",
        "checked": len(active_downloads),
        "updated": updated,
        "completed": completed,
    }


@celery_app.task(name="app.tasks.downloads.import_completed_download")
def import_completed_download(download_id: int):
    """Import a completed download via beets."""
    return _run_async(_import_completed_download_async(download_id))


async def _import_completed_download_async(download_id: int):
    """Import a completed download using beets for tagging and organization."""
    logger.info(f"Importing download {download_id}")

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select

        result = await db.execute(
            select(Download).where(Download.id == download_id)
        )
        download = result.scalar_one_or_none()

        if not download:
            return {"status": "error", "message": "Download not found"}

        if not download.download_path:
            # Try to get path from download client
            if download.download_id and download_client_service.is_configured:
                torrent = await download_client_service.get_torrent(
                    download.download_id
                )
                if torrent:
                    download.download_path = torrent.content_path or torrent.save_path
                    await db.commit()

            if not download.download_path:
                download.status = DownloadStatus.FAILED
                download.status_message = "No download path available for import"
                await db.commit()
                await _sync_wishlist_status(
                    db,
                    download,
                    WishlistStatus.FAILED,
                    message=download.status_message,
                )
                return {"status": "error", "message": "No download path"}

        try:
            download.status = DownloadStatus.IMPORTING
            download.status_message = "Importing with beets..."
            await db.commit()

            if beets_service.is_available:
                # Run beets import
                import_result = await beets_service.import_directory(
                    source_path=download.download_path,
                    artist_hint=download.artist_name,
                    album_hint=download.album_title,
                )

                if import_result.success:
                    download.status = DownloadStatus.COMPLETED
                    download.completed_at = datetime.utcnow()
                    download.beets_imported = True
                    download.final_path = import_result.final_path
                    download.status_message = (
                        f"Imported {import_result.albums_imported} album(s), "
                        f"{import_result.tracks_imported} track(s)"
                    )
                    await db.commit()
                    await _sync_wishlist_status(
                        db,
                        download,
                        WishlistStatus.DOWNLOADED,
                    )
                else:
                    download.status = DownloadStatus.FAILED
                    download.beets_imported = False
                    download.status_message = f"Beets import failed: {import_result.error}"
                    logger.error(
                        f"Beets import failed for download {download_id}: "
                        f"{import_result.error}"
                    )
                    await db.commit()
                    await _sync_wishlist_status(
                        db,
                        download,
                        WishlistStatus.FAILED,
                        message=download.status_message,
                    )
            else:
                # Beets not available, just mark as completed
                download.status = DownloadStatus.COMPLETED
                download.completed_at = datetime.utcnow()
                download.beets_imported = False
                download.status_message = "Download complete (beets not available)"
                await db.commit()
                await _sync_wishlist_status(
                    db,
                    download,
                    WishlistStatus.DOWNLOADED,
                )
            await db.commit()

            # Remove from SABnzbd history after successful import
            if (
                download.download_client == "sabnzbd"
                and download.download_id
                and cfg.get_bool("sabnzbd_remove_completed", True)
            ):
                try:
                    await sabnzbd_service.delete_history_item(
                        download.download_id, del_files=True
                    )
                    logger.info(
                        f"Removed NZB {download.download_id} from SABnzbd history"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to remove NZB from SABnzbd history: {e}"
                    )

            return {
                "status": "completed",
                "download_id": download_id,
                "beets_imported": download.beets_imported,
                "final_path": download.final_path,
            }

        except Exception as e:
            logger.error(f"Import failed for download {download_id}: {e}")
            download.status = DownloadStatus.FAILED
            download.status_message = f"Import failed: {str(e)}"
            await db.commit()
            await _sync_wishlist_status(
                db,
                download,
                WishlistStatus.FAILED,
                message=download.status_message,
            )
            return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Playlist URL automation task
# ---------------------------------------------------------------------------

@celery_app.task(name="app.tasks.downloads.check_playlist_urls")
def check_playlist_urls():
    """Check all automation rules with playlist_url_check trigger."""
    return _run_async(_check_playlist_urls_async())


async def _check_playlist_urls_async():
    """Process all enabled automation rules with the playlist_url_check trigger."""
    from sqlalchemy import select
    from app.models.automation_rule import AutomationRule, AutomationLog
    from app.services.automation_engine import (
        evaluate_all_conditions,
        execute_rule_actions,
    )

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AutomationRule).where(
                AutomationRule.trigger == "playlist_url_check",
                AutomationRule.is_enabled == True,
            )
        )
        rules = result.scalars().all()

        if not rules:
            return {"status": "no_rules", "processed": 0}

        processed = 0
        for rule in rules:
            try:
                context = {"trigger": "playlist_url_check"}
                conditions_met = evaluate_all_conditions(
                    rule.conditions or [], context
                )
                if not conditions_met:
                    continue

                action_results = await execute_rule_actions(
                    rule.actions or [], context, db
                )

                rule.last_triggered_at = datetime.utcnow()
                rule.trigger_count = (rule.trigger_count or 0) + 1

                log = AutomationLog(
                    rule_id=rule.id,
                    trigger_type="playlist_url_check",
                    success=all(
                        r.get("success") for r in action_results
                    ),
                    actions_executed=action_results,
                )
                db.add(log)
                processed += 1

            except Exception as e:
                logger.error(
                    f"Error processing playlist rule {rule.id}: {e}"
                )
                rule.last_error = str(e)

        await db.commit()
        return {"status": "completed", "processed": processed}
