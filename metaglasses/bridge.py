"""
Mobile bridge server for Ray-Ban Meta Smart Glasses.

Because the glasses communicate through the Meta AI app on your phone
(not via a generic Bluetooth API), Python cannot connect to the glasses
directly from a laptop or desktop.  Instead, build a small iOS or Android
app using the official Meta Wearables Device Access Toolkit (MWDAT), and
have it forward glasses events to this bridge server over HTTP.

Architecture::

    Glasses
       |  (proprietary BLE / MWDAT SDK)
    Mobile App (iOS / Android)
       |  (HTTP POST — events, media)
    MobileBridge  ←  this module, runs in your Python process
       |  (Python API)
    metaglasses SDK (Glasses, VoiceCommandHandler, Apps, MetaAIClient …)

The mobile app POSTs glasses events (button presses, audio transcriptions,
capture completions, etc.) to ``POST /event``.  It also POSTs captured media
bytes to ``POST /media``.  Responses from your Python logic (e.g. AI replies
to be spoken through the glasses) are enqueued via :meth:`MobileBridge.send_response`
and retrieved by the mobile app via ``GET /response``.

Typical usage::

    from metaglasses import Glasses
    from metaglasses.bridge import MobileBridge

    glasses = Glasses()
    bridge = MobileBridge(glasses, host="0.0.0.0", port=8765)
    bridge.start()

    # Put the glasses in bridge mode (marks them as connected,
    # delegates event dispatch to the bridge)
    glasses.connect_via_bridge(bridge)

    # Your app logic runs as normal — voice commands, AI queries, etc.
    # Events arriving over HTTP from the mobile app are dispatched here.

    bridge.stop()
    glasses.disconnect()

Mobile app integration
----------------------
On the mobile side (iOS Swift / Android Kotlin), after initialising the
MWDAT SDK and pairing the glasses, forward every ``WearablesEvent`` to this
server:

iOS (Swift) example::

    func onWearablesEvent(_ event: WearablesEvent) {
        guard let url = URL(string: "http://<python-host>:8765/event") else { return }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONEncoder().encode(event.asDictionary())
        URLSession.shared.dataTask(with: request).resume()
    }

Android (Kotlin) example::

    fun onWearablesEvent(event: WearablesEvent) {
        val json = event.toJson()
        val body = json.toRequestBody("application/json".toMediaType())
        val request = Request.Builder()
            .url("http://<python-host>:8765/event")
            .post(body)
            .build()
        OkHttpClient().newCall(request).enqueue(object : Callback { ... })
    }
"""

from __future__ import annotations

import json
import logging
import queue
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable, List, Optional

from .glasses import Glasses

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MobileBridge
# ---------------------------------------------------------------------------

class MobileBridge:
    """HTTP server that receives events forwarded from the mobile companion app.

    The mobile app (iOS / Android) uses the Meta MWDAT SDK to talk to the
    glasses over the official channel, then forwards events (button presses,
    audio transcriptions, captured media metadata, etc.) to this server via
    HTTP POST requests.

    Python sends responses back by enqueuing them via :meth:`send_response`;
    the mobile app polls ``GET /response`` to pick them up and route them to
    the glasses' speaker (e.g. via on-device TTS) or display.

    Parameters
    ----------
    glasses:
        The :class:`~metaglasses.glasses.Glasses` instance to dispatch
        incoming events to.
    host:
        Interface to bind the HTTP server to.  Use ``"0.0.0.0"`` to accept
        connections from the mobile app on the same Wi-Fi network.
        Defaults to ``"127.0.0.1"``.
    port:
        TCP port to listen on.  Defaults to ``8765``.
    on_media:
        Optional callback invoked when the mobile app POSTs media bytes to
        ``POST /media``.  Receives ``(media_bytes: bytes, metadata: dict)``.
    """

    def __init__(
        self,
        glasses: Glasses,
        host: str = "127.0.0.1",
        port: int = 8765,
        on_media: Optional[Callable[[bytes, dict], None]] = None,
    ) -> None:
        self.glasses = glasses
        self.host = host
        self.port = port
        self.on_media = on_media
        self._response_queue: queue.Queue = queue.Queue()
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the bridge HTTP server in a background thread.

        Raises
        ------
        RuntimeError
            If the bridge is already running.
        """
        if self._running:
            raise RuntimeError("MobileBridge is already running.")
        self._server = HTTPServer((self.host, self.port), self._make_handler())
        self._running = True
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Shut down the bridge HTTP server."""
        self._running = False
        if self._server:
            self._server.shutdown()
            self._server = None
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

    @property
    def is_running(self) -> bool:
        """``True`` if the bridge server is currently running."""
        return self._running

    # ------------------------------------------------------------------
    # Response queue  (Python → mobile app → glasses speaker)
    # ------------------------------------------------------------------

    def send_response(self, text: str) -> None:
        """Enqueue *text* to be picked up by the mobile app.

        The mobile app should call ``GET /response`` periodically and
        route returned text to the glasses' speaker (e.g. via on-device TTS).

        Parameters
        ----------
        text:
            The reply text to send back through the glasses.
        """
        self._response_queue.put(text)

    def pending_responses(self) -> List[str]:
        """Drain and return all queued responses (non-blocking).

        Returns
        -------
        list[str]
            All responses that have been enqueued since the last call.
        """
        responses: List[str] = []
        while not self._response_queue.empty():
            try:
                responses.append(self._response_queue.get_nowait())
            except queue.Empty:
                break
        return responses

    # ------------------------------------------------------------------
    # Internal HTTP handler
    # ------------------------------------------------------------------

    def _serve(self) -> None:
        assert self._server is not None
        self._server.serve_forever()

    def _make_handler(self) -> type:
        bridge = self

        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                if self.path == "/event":
                    bridge._handle_event(body)
                    self._ok({})
                elif self.path == "/media":
                    meta_raw = self.headers.get("X-Media-Metadata", "{}")
                    try:
                        metadata = json.loads(meta_raw)
                    except json.JSONDecodeError:
                        metadata = {}
                    bridge._handle_media(body, metadata)
                    self._ok({})
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_GET(self) -> None:
                if self.path == "/response":
                    responses = bridge.pending_responses()
                    self._ok({"responses": responses})
                elif self.path == "/health":
                    self._ok({"status": "ok"})
                else:
                    self.send_response(404)
                    self.end_headers()

            def _ok(self, payload: dict) -> None:
                data = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, fmt: str, *args: object) -> None:
                pass  # suppress default per-request logging

        return _Handler

    def _handle_event(self, body: bytes) -> None:
        """Parse an event POSTed by the mobile app and dispatch it."""
        try:
            event = json.loads(body.decode())
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            _logger.warning(
                "MobileBridge: received malformed event payload (%d bytes): %s",
                len(body),
                exc,
            )
            return
        if isinstance(event, dict):
            self.glasses._dispatch_event(event)
        else:
            _logger.warning(
                "MobileBridge: expected a JSON object for /event, got %s",
                type(event).__name__,
            )

    def _handle_media(self, body: bytes, metadata: dict) -> None:
        """Forward media bytes + metadata to the on_media callback."""
        if self.on_media:
            self.on_media(body, metadata)

    def __repr__(self) -> str:
        state = "running" if self._running else "stopped"
        return f"MobileBridge(host={self.host!r}, port={self.port}, state={state})"
