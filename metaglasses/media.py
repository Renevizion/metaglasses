"""
Media management for Ray-Ban Meta Smart Glasses (Generation 2).

Photos and videos captured on the glasses are synced to the host device via
the companion Bluetooth/Wi-Fi connection.  This module provides helpers to
list, download, and delete media items.

Typical usage::

    from metaglasses import Glasses, MediaManager

    glasses = Glasses()
    glasses.connect()

    mgr = MediaManager(glasses)
    photos = mgr.list_photos()
    for photo in photos:
        mgr.download(photo, dest_dir="/tmp/glasses_media")

    glasses.disconnect()
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .glasses import Glasses, GlassesNotConnectedError


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Photo:
    """Represents a photo stored on the glasses."""
    media_id: str
    filename: str
    size_bytes: int
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    width: int = 2592
    height: int = 1944
    thumbnail_url: Optional[str] = None


@dataclass
class Video:
    """Represents a video stored on the glasses."""
    media_id: str
    filename: str
    size_bytes: int
    duration_seconds: float
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    width: int = 1920
    height: int = 1080
    fps: int = 30
    thumbnail_url: Optional[str] = None


# ---------------------------------------------------------------------------
# MediaManager
# ---------------------------------------------------------------------------

class MediaManager:
    """Provides access to photos and videos stored on the glasses.

    Parameters
    ----------
    glasses:
        A connected :class:`~metaglasses.glasses.Glasses` instance.
    """

    def __init__(self, glasses: Glasses) -> None:
        self._glasses = glasses

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def list_photos(self) -> List[Photo]:
        """Return all photos currently stored on the glasses.

        Returns
        -------
        list[Photo]
            Sorted from newest to oldest.

        Raises
        ------
        GlassesNotConnectedError
            If the glasses are not connected.
        """
        self._require_connected()
        # In a real implementation this would enumerate media via the BLE
        # media-list characteristic or a companion Wi-Fi transfer protocol.
        return []

    def list_videos(self) -> List[Video]:
        """Return all videos currently stored on the glasses.

        Returns
        -------
        list[Video]
            Sorted from newest to oldest.
        """
        self._require_connected()
        return []

    def count(self) -> dict:
        """Return counts of photos and videos on the glasses."""
        return {
            "photos": len(self.list_photos()),
            "videos": len(self.list_videos()),
        }

    # ------------------------------------------------------------------
    # Transfer
    # ------------------------------------------------------------------

    def download(self, media: "Photo | Video", dest_dir: str = ".") -> Path:
        """Download *media* from the glasses to *dest_dir*.

        Parameters
        ----------
        media:
            A :class:`Photo` or :class:`Video` instance.
        dest_dir:
            Local directory to write the file to.  Will be created if it
            does not exist.

        Returns
        -------
        pathlib.Path
            The path to the downloaded file.
        """
        self._require_connected()
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / media.filename
        # In a real implementation this would pull bytes over Wi-Fi/BLE.
        target.touch()
        return target

    def download_all(self, dest_dir: str = ".") -> List[Path]:
        """Download every photo and video to *dest_dir*.

        Returns
        -------
        list[pathlib.Path]
            Paths to all downloaded files.
        """
        paths: List[Path] = []
        for photo in self.list_photos():
            paths.append(self.download(photo, dest_dir))
        for video in self.list_videos():
            paths.append(self.download(video, dest_dir))
        return paths

    # ------------------------------------------------------------------
    # Deletion
    # ------------------------------------------------------------------

    def delete(self, media: "Photo | Video") -> None:
        """Delete *media* from the glasses' internal storage.

        Parameters
        ----------
        media:
            A :class:`Photo` or :class:`Video` instance.
        """
        self._require_connected()
        # In a real implementation this would send a delete command over BLE.

    def delete_all(self) -> int:
        """Delete every photo and video from the glasses.

        Returns
        -------
        int
            Number of items deleted.
        """
        items = [*self.list_photos(), *self.list_videos()]
        for item in items:
            self.delete(item)
        return len(items)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _require_connected(self) -> None:
        if not self._glasses.is_connected:
            raise GlassesNotConnectedError(
                "Not connected to any glasses. Call Glasses.connect() first."
            )
