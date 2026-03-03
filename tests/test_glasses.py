"""
Tests for metaglasses.glasses (Glasses core module).
"""

import pytest

from metaglasses.glasses import (
    CaptureMode,
    Glasses,
    GlassesConnectionError,
    GlassesNotConnectedError,
    LEDColor,
)


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

class TestConnection:
    def test_connect_sets_connected(self):
        g = Glasses()
        assert not g.is_connected
        g.connect()
        assert g.is_connected

    def test_disconnect_clears_connected(self, connected_glasses):
        connected_glasses.disconnect()
        assert not connected_glasses.is_connected

    def test_repr_before_connect(self):
        g = Glasses(device_name="MyGlasses")
        assert "disconnected" in repr(g)
        assert "MyGlasses" in repr(g)

    def test_repr_after_connect(self, connected_glasses):
        assert "connected" in repr(connected_glasses)


# ---------------------------------------------------------------------------
# Device info / status
# ---------------------------------------------------------------------------

class TestDeviceInfo:
    def test_device_info_requires_connection(self):
        g = Glasses()
        with pytest.raises(GlassesNotConnectedError):
            g.device_info()

    def test_device_info_returns_data(self, connected_glasses):
        info = connected_glasses.device_info()
        assert 0 <= info.battery_pct <= 100
        assert info.firmware_version
        assert info.storage_total_mb > 0

    def test_status_keys(self, connected_glasses):
        status = connected_glasses.status()
        expected_keys = {
            "connected", "firmware", "battery_pct",
            "storage_used_mb", "storage_total_mb",
            "capture_mode", "is_charging",
        }
        assert expected_keys.issubset(status.keys())

    def test_status_connected_true(self, connected_glasses):
        assert connected_glasses.status()["connected"] is True


# ---------------------------------------------------------------------------
# Photo capture
# ---------------------------------------------------------------------------

class TestPhotoCapture:
    def test_take_photo_returns_media_id(self, connected_glasses):
        media_id = connected_glasses.take_photo()
        assert isinstance(media_id, str)
        assert media_id  # non-empty

    def test_take_photo_requires_connection(self):
        g = Glasses()
        with pytest.raises(GlassesNotConnectedError):
            g.take_photo()

    def test_take_photo_fires_event(self):
        events = []
        g = Glasses(on_event=events.append)
        g.connect()
        g.take_photo()
        types = [e["event"] for e in events]
        assert "capture_complete" in types

    def test_take_photo_event_has_media_id(self):
        events = []
        g = Glasses(on_event=events.append)
        g.connect()
        returned_id = g.take_photo()
        capture_event = next(e for e in events if e["event"] == "capture_complete")
        assert capture_event["media_id"] == returned_id


# ---------------------------------------------------------------------------
# Video recording
# ---------------------------------------------------------------------------

class TestVideoRecording:
    def test_start_stop_video(self, connected_glasses):
        connected_glasses.start_video()
        media_id = connected_glasses.stop_video()
        assert isinstance(media_id, str)

    def test_start_video_requires_connection(self):
        g = Glasses()
        with pytest.raises(GlassesNotConnectedError):
            g.start_video()

    def test_stop_video_requires_connection(self):
        g = Glasses()
        with pytest.raises(GlassesNotConnectedError):
            g.stop_video()

    def test_double_start_raises(self, connected_glasses):
        connected_glasses.start_video()
        with pytest.raises(RuntimeError):
            connected_glasses.start_video()

    def test_start_video_changes_mode(self, connected_glasses):
        connected_glasses.start_video()
        assert connected_glasses.device_info().capture_mode == CaptureMode.VIDEO

    def test_stop_video_resets_mode(self, connected_glasses):
        connected_glasses.start_video()
        connected_glasses.stop_video()
        assert connected_glasses.device_info().capture_mode == CaptureMode.PHOTO


# ---------------------------------------------------------------------------
# Livestream
# ---------------------------------------------------------------------------

class TestLivestream:
    def test_start_stop_livestream_fires_events(self):
        events = []
        g = Glasses(on_event=events.append)
        g.connect()
        g.start_livestream("rtmp://live.example.com/stream")
        g.stop_livestream()
        event_names = [e["event"] for e in events]
        assert "livestream_started" in event_names
        assert "livestream_stopped" in event_names

    def test_start_livestream_stores_url(self):
        events = []
        g = Glasses(on_event=events.append)
        g.connect()
        url = "rtmp://live.example.com/stream"
        g.start_livestream(url)
        started = next(e for e in events if e["event"] == "livestream_started")
        assert started["destination"] == url


# ---------------------------------------------------------------------------
# Capture mode
# ---------------------------------------------------------------------------

class TestCaptureMode:
    def test_set_capture_mode(self, connected_glasses):
        connected_glasses.set_capture_mode(CaptureMode.VIDEO)
        assert connected_glasses.device_info().capture_mode == CaptureMode.VIDEO

    def test_set_capture_mode_requires_connection(self):
        g = Glasses()
        with pytest.raises(GlassesNotConnectedError):
            g.set_capture_mode(CaptureMode.VIDEO)
