"""
HTTP server that acts as the backend service for your glasses apps.

If you build your user-interface in Lovable.dev, React, Next.js, or any
other web framework, **this is the Python backend you connect it to**.  Run
this server once on your computer (or phone), then call it from your frontend
app with ordinary ``fetch()`` calls.

Architecture
------------
::

    Your App (Lovable.dev, React, any web / mobile UI)
       |  fetch("http://localhost:8765/capture/photo", {method: "POST"})
       |
    MobileBridge  ←  this module, starts with one line of Python
       |  glasses.take_photo()  /  ai.chat(message)  / …
    metaglasses SDK (Glasses, VoiceCommandHandler, Apps, MetaAIClient …)
       |  (Bluetooth LE / MWDAT mobile SDK)
    Ray-Ban Meta Glasses

REST API
--------
Every response is JSON with CORS headers so browser apps can call the
server directly without a proxy.

+----------------------------------+--------+-------------------------------------------+
| Endpoint                         | Method | Description                               |
+==================================+========+===========================================+
| ``/health``                      | GET    | ``{"status": "ok"}``                      |
+----------------------------------+--------+-------------------------------------------+
| ``/status``                      | GET    | Glasses status dict (battery, firmware …) |
+----------------------------------+--------+-------------------------------------------+
| ``/capture/photo``               | POST   | Take a photo → ``{"media_id": "..."}``    |
+----------------------------------+--------+-------------------------------------------+
| ``/capture/video/start``         | POST   | Start recording → ``{}``                  |
+----------------------------------+--------+-------------------------------------------+
| ``/capture/video/stop``          | POST   | Stop recording → ``{"media_id": "..."}``  |
+----------------------------------+--------+-------------------------------------------+
| ``/ai/chat``                     | POST   | Chat with AI → ``{"text": "...", …}``     |
+----------------------------------+--------+-------------------------------------------+
| ``/event``                       | POST   | Forward a raw glasses event dict          |
+----------------------------------+--------+-------------------------------------------+
| ``/media``                       | POST   | Upload captured media bytes               |
+----------------------------------+--------+-------------------------------------------+
| ``/response``                    | GET    | Poll for TTS/AI replies (mobile app use)  |
+----------------------------------+--------+-------------------------------------------+

Quick start (Python side)::

    from metaglasses import Glasses, MetaAIClient
    from metaglasses.bridge import MobileBridge

    glasses = Glasses()
    glasses.connect()
    ai = MetaAIClient(api_key="YOUR_KEY")

    bridge = MobileBridge(glasses, ai=ai, host="0.0.0.0", port=8765)
    bridge.start()
    # → Server is now listening.  Call it from any frontend app.

Quick start (JavaScript / Lovable.dev side)::

    const BASE = "http://localhost:8765";

    // Check glasses status
    const status = await fetch(`${BASE}/status`).then(r => r.json());
    console.log(status.battery_pct, status.firmware);

    // Take a photo
    const { media_id } = await fetch(`${BASE}/capture/photo`, {
      method: "POST"
    }).then(r => r.json());

    // Ask the AI a question
    const { text } = await fetch(`${BASE}/ai/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: "What restaurants are nearby?" })
    }).then(r => r.json());

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
from typing import TYPE_CHECKING, Any, Callable, List, Optional

from .glasses import Glasses, GlassesNotConnectedError

if TYPE_CHECKING:
    from .ai import MetaAIClient

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MobileBridge
# ---------------------------------------------------------------------------

class MobileBridge:
    """HTTP server that exposes the glasses to any frontend app.

    Run it alongside your existing app — whether that app lives in Lovable.dev,
    a GitHub repo, or anywhere else.  Your frontend calls ordinary HTTP endpoints
    on this server; the server translates those calls into glasses actions.

    Parameters
    ----------
    glasses:
        The :class:`~metaglasses.glasses.Glasses` instance to dispatch
        incoming requests to.
    ai:
        Optional :class:`~metaglasses.ai.MetaAIClient`.  Required for the
        ``POST /ai/chat`` endpoint.
    host:
        Interface to bind the HTTP server to.  Use ``"0.0.0.0"`` to accept
        connections from other devices on the same Wi-Fi network.
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
        ai: Optional["MetaAIClient"] = None,
        host: str = "127.0.0.1",
        port: int = 8765,
        on_media: Optional[Callable[[bytes, dict], None]] = None,
    ) -> None:
        self.glasses = glasses
        self.ai = ai
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

            # ----------------------------------------------------------
            # CORS pre-flight (browsers send this before cross-origin
            # POST requests, e.g. from a Lovable.dev app)
            # ----------------------------------------------------------

            def do_OPTIONS(self) -> None:
                self.send_response(200)
                self._cors_headers()
                self.send_header("Content-Length", "0")
                self.end_headers()

            # ----------------------------------------------------------
            # GET
            # ----------------------------------------------------------

            def do_GET(self) -> None:
                if self.path == "/health":
                    self._ok({"status": "ok"})
                elif self.path == "/status":
                    try:
                        self._ok(bridge.glasses.status())
                    except GlassesNotConnectedError as exc:
                        self._error(503, str(exc))
                elif self.path == "/response":
                    self._ok({"responses": bridge.pending_responses()})
                else:
                    self._error(404, f"Unknown endpoint: {self.path}")

            # ----------------------------------------------------------
            # POST
            # ----------------------------------------------------------

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)

                if self.path == "/capture/photo":
                    self._handle_capture_photo()
                elif self.path == "/capture/video/start":
                    self._handle_video_start()
                elif self.path == "/capture/video/stop":
                    self._handle_video_stop()
                elif self.path == "/ai/chat":
                    self._handle_ai_chat(body)
                elif self.path == "/event":
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
                    self._error(404, f"Unknown endpoint: {self.path}")

            # ----------------------------------------------------------
            # Capture helpers
            # ----------------------------------------------------------

            def _handle_capture_photo(self) -> None:
                try:
                    media_id = bridge.glasses.take_photo()
                    self._ok({"media_id": media_id})
                except GlassesNotConnectedError as exc:
                    self._error(503, str(exc))

            def _handle_video_start(self) -> None:
                try:
                    bridge.glasses.start_video()
                    self._ok({})
                except GlassesNotConnectedError as exc:
                    self._error(503, str(exc))
                except RuntimeError as exc:
                    self._error(409, str(exc))

            def _handle_video_stop(self) -> None:
                try:
                    media_id = bridge.glasses.stop_video()
                    self._ok({"media_id": media_id})
                except GlassesNotConnectedError as exc:
                    self._error(503, str(exc))

            # ----------------------------------------------------------
            # AI helper
            # ----------------------------------------------------------

            def _handle_ai_chat(self, body: bytes) -> None:
                if bridge.ai is None:
                    self._error(
                        503,
                        "No AI client configured. Pass ai=MetaAIClient(...) "
                        "to MobileBridge().",
                    )
                    return
                try:
                    payload: Any = json.loads(body.decode())
                except (json.JSONDecodeError, UnicodeDecodeError):
                    self._error(400, "Request body must be JSON with a 'message' field.")
                    return
                message = (payload or {}).get("message", "")
                if not message:
                    self._error(400, "Missing 'message' field in request body.")
                    return
                try:
                    response = bridge.ai.chat(message)
                    self._ok({"text": response.text, "model": response.model})
                except Exception as exc:
                    self._error(500, str(exc))

            # ----------------------------------------------------------
            # Response helpers
            # ----------------------------------------------------------

            def _ok(self, payload: dict) -> None:
                data = json.dumps(payload).encode()
                self.send_response(200)
                self._cors_headers()
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _error(self, code: int, message: str) -> None:
                data = json.dumps({"error": message}).encode()
                self.send_response(code)
                self._cors_headers()
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _cors_headers(self) -> None:
                """Add CORS headers so browser-based apps (Lovable.dev, React…)
                can call this server without a proxy."""
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header(
                    "Access-Control-Allow-Methods",
                    "GET, POST, OPTIONS",
                )
                self.send_header(
                    "Access-Control-Allow-Headers",
                    "Content-Type, X-Media-Metadata",
                )

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
