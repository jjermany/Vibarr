"""Download management tasks."""

import logging
from datetime import datetime

from app.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.services.prowlarr import prowlarr_service
from app.models.wishlist import WishlistItem, WishlistStatus
from app.models.download import Download, DownloadStatus

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.downloads.process_wishlist")
def process_wishlist():
    """Process wishlist items and search for downloads."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _process_wishlist_async()
    )


async def _process_wishlist_async():
    """Async implementation of wishlist processing."""
    logger.info("Processing wishlist")

    if not prowlarr_service.is_available:
        return {"status": "skipped", "reason": "Prowlarr not available"}

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select

        # Get wanted items
        result = await db.execute(
            select(WishlistItem)
            .where(WishlistItem.status == WishlistStatus.WANTED)
            .where(WishlistItem.auto_download == True)
        )
        items = result.scalars().all()

        searched = 0
        found = 0

        for item in items:
            try:
                # Update status
                item.status = WishlistStatus.SEARCHING
                item.last_searched_at = datetime.utcnow()
                item.search_count += 1
                await db.commit()

                # Build search query
                artist_name = item.artist_name or ""
                album_title = item.album_title or ""

                if not artist_name and not album_title:
                    continue

                # Search via Prowlarr
                results = await prowlarr_service.search_album(
                    artist=artist_name,
                    album=album_title,
                    preferred_format=item.preferred_format,
                )
                searched += 1

                if results:
                    # Found results
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
                        release_title=best_result.get("title"),
                        release_size=best_result.get("size"),
                        release_format=best_result.get("format"),
                        release_quality=best_result.get("quality"),
                        seeders=best_result.get("seeders"),
                        leechers=best_result.get("leechers"),
                        source="wishlist",
                    )
                    db.add(download)

                    # If auto-download is enabled and score is high enough
                    from app.config import get_settings
                    settings = get_settings()

                    if (
                        settings.auto_download_enabled
                        and best_result.get("score", 0) >= settings.auto_download_confidence_threshold * 100
                    ):
                        # Queue the grab
                        grab_release.delay(
                            download_id=download.id,
                            guid=best_result.get("guid"),
                            indexer_id=best_result.get("indexer_id"),
                        )
                else:
                    # No results found
                    item.status = WishlistStatus.WANTED  # Reset to try again later

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
    }


@celery_app.task(name="app.tasks.downloads.search_wishlist_item")
def search_wishlist_item(item_id: int):
    """Search for a specific wishlist item via Prowlarr."""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_search_wishlist_item_async(item_id))
    finally:
        loop.close()


async def _search_wishlist_item_async(item_id: int):
    """Async implementation of individual wishlist item search."""
    logger.info(f"Searching for wishlist item {item_id}")

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
                item.status = WishlistStatus.FOUND
                await db.commit()
                return {
                    "status": "found",
                    "results_count": len(results),
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
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
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

    if not prowlarr_service.is_available:
        return {"status": "error", "message": "Prowlarr not available"}

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select

        # Get download entry
        result = await db.execute(
            select(Download).where(Download.id == download_id)
        )
        download = result.scalar_one_or_none()

        if not download:
            return {"status": "error", "message": "Download not found"}

        try:
            download.status = DownloadStatus.SEARCHING
            await db.commit()

            # Search
            results = await prowlarr_service.search_album(
                artist=artist,
                album=album,
                preferred_format=preferred_format,
            )

            if results:
                best_result = results[0]
                download.status = DownloadStatus.FOUND
                download.indexer_name = best_result.get("indexer")
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
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _grab_release_async(download_id, guid, indexer_id)
    )


async def _grab_release_async(download_id: int, guid: str, indexer_id: int):
    """Async implementation of release grab."""
    logger.info(f"Grabbing release for download {download_id}")

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

            # Grab via Prowlarr
            download_client_id = await prowlarr_service.grab(guid, indexer_id)

            if download_client_id:
                download.status = DownloadStatus.DOWNLOADING
                download.download_id = download_client_id
                download.started_at = datetime.utcnow()
                await db.commit()

                # Update associated wishlist item
                if download.wishlist_id:
                    wishlist_result = await db.execute(
                        select(WishlistItem).where(WishlistItem.id == download.wishlist_id)
                    )
                    wishlist_item = wishlist_result.scalar_one_or_none()
                    if wishlist_item:
                        wishlist_item.status = WishlistStatus.DOWNLOADING
                        await db.commit()

                return {
                    "status": "grabbed",
                    "download_id": download_id,
                    "client_id": download_client_id,
                }
            else:
                download.status = DownloadStatus.FAILED
                download.status_message = "Failed to grab release"
                await db.commit()
                return {"status": "error", "message": "Failed to grab release"}

        except Exception as e:
            logger.error(f"Grab failed for download {download_id}: {e}")
            download.status = DownloadStatus.FAILED
            download.status_message = str(e)
            await db.commit()
            return {"status": "error", "message": str(e)}


@celery_app.task(name="app.tasks.downloads.check_download_status")
def check_download_status():
    """Check status of active downloads."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _check_download_status_async()
    )


async def _check_download_status_async():
    """Check and update download statuses."""
    logger.info("Checking download statuses")

    # TODO: Implement download client status checking
    # This would integrate with qBittorrent or other download clients

    return {"status": "completed"}


@celery_app.task(name="app.tasks.downloads.import_completed_download")
def import_completed_download(download_id: int):
    """Import a completed download via beets."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _import_completed_download_async(download_id)
    )


async def _import_completed_download_async(download_id: int):
    """Async implementation of download import."""
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
            return {"status": "error", "message": "No download path"}

        try:
            download.status = DownloadStatus.IMPORTING
            await db.commit()

            # TODO: Implement beets import
            # This would call beets to import, tag, and organize the download

            download.status = DownloadStatus.COMPLETED
            download.completed_at = datetime.utcnow()
            download.beets_imported = True
            await db.commit()

            # Update wishlist item
            if download.wishlist_id:
                wishlist_result = await db.execute(
                    select(WishlistItem).where(WishlistItem.id == download.wishlist_id)
                )
                wishlist_item = wishlist_result.scalar_one_or_none()
                if wishlist_item:
                    wishlist_item.status = WishlistStatus.DOWNLOADED
                    await db.commit()

            return {
                "status": "completed",
                "download_id": download_id,
            }

        except Exception as e:
            logger.error(f"Import failed for download {download_id}: {e}")
            download.status = DownloadStatus.FAILED
            download.status_message = f"Import failed: {str(e)}"
            await db.commit()
            return {"status": "error", "message": str(e)}
