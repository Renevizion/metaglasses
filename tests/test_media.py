"""
Tests for metaglasses.media (MediaManager).
"""

import tempfile
from pathlib import Path

import pytest

from metaglasses.glasses import Glasses, GlassesNotConnectedError
from metaglasses.media import MediaManager, Photo, Video


class TestMediaManagerConnection:
    def test_list_photos_requires_connection(self):
        g = Glasses()
        mgr = MediaManager(g)
        with pytest.raises(GlassesNotConnectedError):
            mgr.list_photos()

    def test_list_videos_requires_connection(self):
        g = Glasses()
        mgr = MediaManager(g)
        with pytest.raises(GlassesNotConnectedError):
            mgr.list_videos()

    def test_download_requires_connection(self):
        g = Glasses()
        mgr = MediaManager(g)
        photo = Photo(media_id="abc", filename="img.jpg", size_bytes=1024)
        with pytest.raises(GlassesNotConnectedError):
            mgr.download(photo)

    def test_delete_requires_connection(self):
        g = Glasses()
        mgr = MediaManager(g)
        photo = Photo(media_id="abc", filename="img.jpg", size_bytes=1024)
        with pytest.raises(GlassesNotConnectedError):
            mgr.delete(photo)


class TestMediaManagerListing:
    def test_list_photos_returns_list(self, connected_glasses):
        mgr = MediaManager(connected_glasses)
        assert isinstance(mgr.list_photos(), list)

    def test_list_videos_returns_list(self, connected_glasses):
        mgr = MediaManager(connected_glasses)
        assert isinstance(mgr.list_videos(), list)

    def test_count_structure(self, connected_glasses):
        mgr = MediaManager(connected_glasses)
        c = mgr.count()
        assert "photos" in c and "videos" in c
        assert c["photos"] >= 0 and c["videos"] >= 0


class TestMediaManagerDownload:
    def test_download_photo_creates_file(self, connected_glasses):
        mgr = MediaManager(connected_glasses)
        photo = Photo(media_id="x1", filename="test.jpg", size_bytes=512)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = mgr.download(photo, dest_dir=tmpdir)
            assert path.exists()
            assert path.name == "test.jpg"

    def test_download_video_creates_file(self, connected_glasses):
        mgr = MediaManager(connected_glasses)
        video = Video(media_id="v1", filename="clip.mp4", size_bytes=1024, duration_seconds=5.0)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = mgr.download(video, dest_dir=tmpdir)
            assert path.exists()
            assert path.name == "clip.mp4"

    def test_download_creates_dest_dir(self, connected_glasses):
        mgr = MediaManager(connected_glasses)
        photo = Photo(media_id="x2", filename="img2.jpg", size_bytes=256)
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = str(Path(tmpdir) / "subdir" / "nested")
            path = mgr.download(photo, dest_dir=dest)
            assert path.exists()


class TestMediaDataclasses:
    def test_photo_defaults(self):
        p = Photo(media_id="m1", filename="a.jpg", size_bytes=100)
        assert p.width == 2592
        assert p.height == 1944
        assert p.thumbnail_url is None

    def test_video_defaults(self):
        v = Video(media_id="v1", filename="b.mp4", size_bytes=200, duration_seconds=3.0)
        assert v.width == 1920
        assert v.height == 1080
        assert v.fps == 30

