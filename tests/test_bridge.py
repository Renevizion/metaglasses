"""
Tests for metaglasses.bridge (MobileBridge HTTP server).
"""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request

import pytest

from metaglasses.bridge import MobileBridge
from metaglasses.glasses import Glasses


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _free_port() -> int:
    """Return a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _post(url: str, payload: dict | None = None, data: bytes = b"", headers: dict | None = None) -> dict:
    body = data if data else json.dumps(payload or {}).encode()
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def _get(url: str) -> dict:
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def _wait_for_server(host: str, port: int, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            _get(f"http://{host}:{port}/health")
            return
        except Exception:
            time.sleep(0.05)
    pytest.fail(f"Bridge server did not start within {timeout}s")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def glasses() -> Glasses:
    g = Glasses()
    g.connect()
    return g


@pytest.fixture
def bridge(glasses):
    port = _free_port()
    b = MobileBridge(glasses, host="127.0.0.1", port=port)
    b.start()
    _wait_for_server("127.0.0.1", port)
    yield b
    b.stop()


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

class TestLifecycle:
    def test_start_sets_running(self, glasses):
        port = _free_port()
        b = MobileBridge(glasses, port=port)
        assert not b.is_running
        b.start()
        _wait_for_server("127.0.0.1", port)
        assert b.is_running
        b.stop()

    def test_stop_clears_running(self, bridge):
        bridge.stop()
        assert not bridge.is_running

    def test_double_start_raises(self, bridge):
        with pytest.raises(RuntimeError, match="already running"):
            bridge.start()

    def test_stop_is_idempotent(self, glasses):
        port = _free_port()
        b = MobileBridge(glasses, port=port)
        b.start()
        _wait_for_server("127.0.0.1", port)
        b.stop()
        b.stop()  # second stop should not raise

    def test_repr_stopped(self, glasses):
        b = MobileBridge(glasses, port=_free_port())
        assert "stopped" in repr(b)

    def test_repr_running(self, bridge):
        assert "running" in repr(bridge)


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_health_returns_ok(self, bridge):
        url = f"http://127.0.0.1:{bridge.port}/health"
        resp = _get(url)
        assert resp["status"] == "ok"


# ---------------------------------------------------------------------------
# Event endpoint  POST /event
# ---------------------------------------------------------------------------

class TestEventEndpoint:
    def test_event_dispatched_to_glasses(self, bridge, glasses):
        received = []
        glasses.on_event = received.append

        url = f"http://127.0.0.1:{bridge.port}/event"
        _post(url, {"event": "button_press", "button": "camera"})
        time.sleep(0.05)

        assert len(received) == 1
        assert received[0]["event"] == "button_press"

    def test_event_returns_200(self, bridge):
        url = f"http://127.0.0.1:{bridge.port}/event"
        result = _post(url, {"event": "test"})
        assert result == {}

    def test_invalid_json_is_ignored(self, bridge, glasses):
        received = []
        glasses.on_event = received.append

        url = f"http://127.0.0.1:{bridge.port}/event"
        req = urllib.request.Request(
            url,
            data=b"not json",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
        assert received == []

    def test_multiple_events_dispatched(self, bridge, glasses):
        received = []
        glasses.on_event = received.append

        url = f"http://127.0.0.1:{bridge.port}/event"
        for i in range(3):
            _post(url, {"event": f"evt_{i}"})
        time.sleep(0.1)

        assert len(received) == 3


# ---------------------------------------------------------------------------
# Media endpoint  POST /media
# ---------------------------------------------------------------------------

class TestMediaEndpoint:
    def test_media_callback_invoked(self, glasses):
        port = _free_port()
        calls = []
        b = MobileBridge(glasses, port=port, on_media=lambda data, meta: calls.append((data, meta)))
        b.start()
        _wait_for_server("127.0.0.1", port)

        url = f"http://127.0.0.1:{port}/media"
        fake_image = b"\xff\xd8\xff\xe0fake-jpeg-bytes"
        req = urllib.request.Request(
            url,
            data=fake_image,
            headers={
                "Content-Type": "application/octet-stream",
                "X-Media-Metadata": json.dumps({"type": "photo", "media_id": "abc"}),
            },
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200

        b.stop()
        assert len(calls) == 1
        data, meta = calls[0]
        assert data == fake_image
        assert meta["type"] == "photo"
        assert meta["media_id"] == "abc"

    def test_media_without_callback_does_not_raise(self, bridge):
        url = f"http://127.0.0.1:{bridge.port}/media"
        req = urllib.request.Request(
            url,
            data=b"bytes",
            headers={"Content-Type": "application/octet-stream"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200

    def test_media_with_invalid_metadata_header(self, bridge):
        calls = []
        bridge.on_media = lambda data, meta: calls.append(meta)

        url = f"http://127.0.0.1:{bridge.port}/media"
        req = urllib.request.Request(
            url,
            data=b"bytes",
            headers={
                "Content-Type": "application/octet-stream",
                "X-Media-Metadata": "not-json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
        assert calls == [{}]


# ---------------------------------------------------------------------------
# Response queue  GET /response
# ---------------------------------------------------------------------------

class TestResponseQueue:
    def test_no_responses_returns_empty_list(self, bridge):
        url = f"http://127.0.0.1:{bridge.port}/response"
        resp = _get(url)
        assert resp["responses"] == []

    def test_enqueued_responses_returned(self, bridge):
        bridge.send_response("Hello from Python!")
        bridge.send_response("Second message")
        url = f"http://127.0.0.1:{bridge.port}/response"
        resp = _get(url)
        assert resp["responses"] == ["Hello from Python!", "Second message"]

    def test_responses_drained_after_retrieval(self, bridge):
        bridge.send_response("once")
        url = f"http://127.0.0.1:{bridge.port}/response"
        _get(url)  # drain
        resp = _get(url)
        assert resp["responses"] == []

    def test_pending_responses_method(self, bridge):
        bridge.send_response("a")
        bridge.send_response("b")
        assert bridge.pending_responses() == ["a", "b"]
        assert bridge.pending_responses() == []


# ---------------------------------------------------------------------------
# Unknown routes
# ---------------------------------------------------------------------------

class TestUnknownRoutes:
    def test_unknown_post_returns_404(self, bridge):
        url = f"http://127.0.0.1:{bridge.port}/unknown"
        req = urllib.request.Request(url, data=b"{}", method="POST")
        try:
            urllib.request.urlopen(req)
            pytest.fail("Expected HTTPError")
        except urllib.error.HTTPError as exc:
            assert exc.code == 404

    def test_unknown_get_returns_404(self, bridge):
        url = f"http://127.0.0.1:{bridge.port}/unknown"
        try:
            urllib.request.urlopen(url)
            pytest.fail("Expected HTTPError")
        except urllib.error.HTTPError as exc:
            assert exc.code == 404


# ---------------------------------------------------------------------------
# Glasses.connect_via_bridge()
# ---------------------------------------------------------------------------

class TestConnectViaBridge:
    def test_connect_via_bridge_marks_connected(self, bridge):
        g = Glasses()
        assert not g.is_connected
        g.connect_via_bridge(bridge)
        assert g.is_connected

    def test_connect_via_bridge_populates_device_info(self, bridge):
        g = Glasses()
        g.connect_via_bridge(bridge)
        info = g.device_info()
        assert info.firmware_version
        assert 0 <= info.battery_pct <= 100

    def test_connect_via_bridge_requires_running_bridge(self, glasses):
        port = _free_port()
        b = MobileBridge(glasses, port=port)
        # Not started
        with pytest.raises(RuntimeError, match="must be started"):
            glasses.connect_via_bridge(b)

    def test_disconnect_clears_bridge(self, bridge):
        g = Glasses()
        g.connect_via_bridge(bridge)
        assert g.is_connected
        g.disconnect()
        assert not g.is_connected
        assert g._bridge is None

    def test_bridge_events_dispatched_after_connect_via_bridge(self):
        received = []
        g = Glasses(on_event=received.append)
        port = _free_port()
        b = MobileBridge(g, port=port)
        b.start()
        _wait_for_server("127.0.0.1", port)
        g.connect_via_bridge(b)

        url = f"http://127.0.0.1:{port}/event"
        _post(url, {"event": "audio_transcript", "text": "take a photo"})
        time.sleep(0.05)

        b.stop()
        assert any(e.get("event") == "audio_transcript" for e in received)
