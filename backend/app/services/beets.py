"""Beets integration for post-download music import and tagging."""

import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List

from app.services import app_settings as cfg

logger = logging.getLogger(__name__)


class BeetsImportResult:
    """Result of a beets import operation."""

    def __init__(
        self,
        success: bool,
        source_path: str,
        final_path: Optional[str] = None,
        albums_imported: int = 0,
        tracks_imported: int = 0,
        error: Optional[str] = None,
        output: str = "",
    ):
        self.success = success
        self.source_path = source_path
        self.final_path = final_path
        self.albums_imported = albums_imported
        self.tracks_imported = tracks_imported
        self.error = error
        self.output = output

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "source_path": self.source_path,
            "final_path": self.final_path,
            "albums_imported": self.albums_imported,
            "tracks_imported": self.tracks_imported,
            "error": self.error,
        }


class BeetsService:
    """Service for importing and organizing music via beets."""

    @property
    def is_available(self) -> bool:
        """Check if beets is configured and available."""
        if not cfg.get_bool("beets_enabled"):
            return False
        return shutil.which("beet") is not None

    def _get_config_path(self) -> str:
        return cfg.get_setting("beets_config_path", "/config/beets/config.yaml")

    def _get_library_path(self) -> str:
        return cfg.get_setting("beets_library_path", "/music")

    async def test_connection(self) -> Dict[str, Any]:
        """Test that beets is properly configured."""
        if not cfg.get_bool("beets_enabled"):
            return {"available": False, "reason": "Beets not enabled in settings"}

        beet_path = shutil.which("beet")
        if not beet_path:
            return {"available": False, "reason": "beet command not found in PATH"}

        try:
            proc = await asyncio.create_subprocess_exec(
                "beet", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                version = stdout.decode().strip().split("\n")[0]
                return {"available": True, "version": version, "path": beet_path}
            else:
                return {
                    "available": False,
                    "reason": f"beet --version failed: {stderr.decode().strip()}",
                }
        except Exception as e:
            return {"available": False, "reason": str(e)}

    async def import_directory(
        self,
        source_path: str,
        artist_hint: Optional[str] = None,
        album_hint: Optional[str] = None,
        move: Optional[bool] = None,
    ) -> BeetsImportResult:
        """
        Import a directory of music files using beets.

        Uses beet import in quiet/auto mode so no interactive prompts are needed.
        """
        if not self.is_available:
            return BeetsImportResult(
                success=False,
                source_path=source_path,
                error="Beets is not available",
            )

        source = Path(source_path)
        if not source.exists():
            return BeetsImportResult(
                success=False,
                source_path=source_path,
                error=f"Source path does not exist: {source_path}",
            )

        should_move = move if move is not None else cfg.get_bool("beets_move_files", True)

        cmd = [
            "beet",
            "-c", self._get_config_path(),
            "import",
            "--quiet",  # Non-interactive, skip ambiguous
            "-l", cfg.get_setting("beets_library_path", "/music"),
        ]

        if should_move:
            cmd.append("--move")
        else:
            cmd.append("--copy")

        # Add search hints if provided
        if artist_hint and album_hint:
            cmd.extend(["--search-id", f"{artist_hint} - {album_hint}"])

        cmd.append(str(source))

        logger.info(f"Running beets import: {' '.join(cmd)}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "BEETSDIR": str(Path(self._get_config_path()).parent)},
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=600  # 10 min timeout
            )

            stdout_text = stdout.decode()
            stderr_text = stderr.decode()
            output = stdout_text + stderr_text

            if proc.returncode == 0:
                # Parse output to determine final path and counts
                final_path = self._parse_import_path(output)
                albums, tracks = self._parse_import_counts(output)

                return BeetsImportResult(
                    success=True,
                    source_path=source_path,
                    final_path=final_path or cfg.get_setting("beets_library_path", "/music"),
                    albums_imported=albums,
                    tracks_imported=tracks,
                    output=output,
                )
            else:
                logger.error(f"Beets import failed (rc={proc.returncode}): {output}")
                return BeetsImportResult(
                    success=False,
                    source_path=source_path,
                    error=f"Import failed with return code {proc.returncode}",
                    output=output,
                )
        except asyncio.TimeoutError:
            return BeetsImportResult(
                success=False,
                source_path=source_path,
                error="Import timed out after 10 minutes",
            )
        except Exception as e:
            logger.error(f"Beets import error: {e}")
            return BeetsImportResult(
                success=False,
                source_path=source_path,
                error=str(e),
            )

    async def list_library(
        self, query: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List albums in the beets library."""
        if not self.is_available:
            return []

        cmd = [
            "beet",
            "-c", self._get_config_path(),
            "list",
            "-a",  # Album mode
            "-f", "$albumartist - $album ($year) [$format]",
        ]
        if query:
            cmd.append(query)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)

            if proc.returncode == 0:
                lines = stdout.decode().strip().split("\n")
                return [{"display": line.strip()} for line in lines[:limit] if line.strip()]
        except Exception as e:
            logger.error(f"Beets list failed: {e}")
        return []

    def _parse_import_path(self, output: str) -> Optional[str]:
        """Parse the final import path from beets output."""
        for line in output.split("\n"):
            # Beets logs "added <path>" or "moved <path>"
            for prefix in ("added ", "Moving to ", "Copying to "):
                if prefix in line:
                    path = line.split(prefix, 1)[-1].strip().rstrip(".")
                    if path and os.path.sep in path:
                        return path
        return None

    def _parse_import_counts(self, output: str) -> tuple:
        """Parse album and track counts from beets output."""
        albums = 0
        tracks = 0
        for line in output.split("\n"):
            if "album" in line.lower() and ("added" in line.lower() or "imported" in line.lower()):
                albums += 1
            if "item" in line.lower() or "track" in line.lower():
                # Try to extract count
                for word in line.split():
                    if word.isdigit():
                        tracks = max(tracks, int(word))
                        break
        return max(albums, 1) if tracks > 0 else albums, tracks

    def generate_default_config(self) -> str:
        """Generate a default beets config.yaml."""
        return f"""directory: {cfg.get_setting("beets_library_path", "/music")}
library: /config/beets/library.db

import:
    move: {'yes' if cfg.get_bool("beets_move_files", True) else 'no'}
    write: yes
    quiet_fallback: skip
    timid: no
    log: /config/beets/import.log

match:
    strong_rec_thresh: 0.1
    preferred:
        media: ['Digital Media|File', 'CD']

paths:
    default: $albumartist/$album%aunique{{}}/$track $title
    singleton: Non-Album/$artist/$title
    comp: Compilations/$album%aunique{{}}/$track $title

plugins: []
"""


# Singleton instance
beets_service = BeetsService()
