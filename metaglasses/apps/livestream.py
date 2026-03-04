"""
LivestreamApp — multi-platform livestream manager for the glasses.

Supported platforms
-------------------
* YouTube Live (RTMP)
* Twitch
* Instagram Live
* Facebook Live
* TikTok Live
* Twitter / X Live
* Custom RTMP endpoint

Single platform
~~~~~~~~~~~~~~~
::

    app.go_live(Platform.YOUTUBE)

Multiple platforms simultaneously
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The glasses produce one RTMP output.  To fan it out to several platforms at
once, point that output at a **relay service** (e.g. Restream.io, your own
``nginx-rtmp`` server) and tell the app which platforms are being targeted so
it can track sessions, fire events, and respond to voice commands correctly::

    app.go_live_multi(
        [Platform.YOUTUBE, Platform.INSTAGRAM, Platform.TWITTER],
        relay_url="rtmp://live.restream.io/live/re_XXXX",
    )

If no ``relay_url`` is given, the first platform's native RTMP URL is used
and the others are tracked as *intended targets*::

    app.go_live_multi([Platform.YOUTUBE, Platform.TWITCH])
    # streams to YouTube; Twitch is listed in active_sessions

Go live on every configured platform at once::

    app.go_live_all()                         # uses relay_url if set
    app.go_live_all("rtmp://relay.example.com/live/KEY")

Voice commands
~~~~~~~~~~~~~~
* "go live on youtube"
* "go live on instagram and twitter"
* "go live everywhere" / "go live on all"
* "stop streaming"

Typical usage::

    from metaglasses import Glasses
    from metaglasses.apps.livestream import LivestreamApp, Platform

    glasses = Glasses()
    glasses.connect()

    app = LivestreamApp(
        glasses,
        stream_keys={
            Platform.YOUTUBE:   "xxxx-xxxx-xxxx-xxxx",
            Platform.INSTAGRAM: "xxxx-xxxx-xxxx-xxxx",
            Platform.TWITTER:   "xxxx-xxxx-xxxx-xxxx",
        },
        relay_url="rtmp://live.restream.io/live/re_XXXX",
        on_event=lambda e: print(e),
    )
    app.start()

    # Single platform
    app.go_live(Platform.YOUTUBE)
    app.end_stream()

    # All at once
    app.go_live_all()
    app.end_stream()

    app.stop()
    glasses.disconnect()
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Dict, List, Optional

from ..apps import App
from ..voice import VoiceCommandHandler


# ---------------------------------------------------------------------------
# Platform definitions
# ---------------------------------------------------------------------------

class Platform(str, Enum):
    """Supported streaming platforms."""
    YOUTUBE   = "youtube"
    TWITCH    = "twitch"
    INSTAGRAM = "instagram"
    FACEBOOK  = "facebook"
    TIKTOK    = "tiktok"
    TWITTER   = "twitter"
    CUSTOM    = "custom"


_RTMP_BASE_URLS: Dict[Platform, str] = {
    Platform.YOUTUBE:   "rtmp://a.rtmp.youtube.com/live2",
    Platform.TWITCH:    "rtmp://live.twitch.tv/live",
    Platform.INSTAGRAM: "rtmps://live-upload.instagram.com:443/rtmp",
    Platform.FACEBOOK:  "rtmps://live-api-s.facebook.com:443/rtmp",
    Platform.TIKTOK:    "rtmp://push.tiktok.com/live",
    Platform.TWITTER:   "rtmp://ingest.pscp.tv:80/x",
}

# Maps spoken words → Platform
_VOICE_ALIASES: Dict[str, Platform] = {
    "youtube":        Platform.YOUTUBE,
    "youtube live":   Platform.YOUTUBE,
    "twitch":         Platform.TWITCH,
    "instagram":      Platform.INSTAGRAM,
    "instagram live": Platform.INSTAGRAM,
    "insta":          Platform.INSTAGRAM,
    "facebook":       Platform.FACEBOOK,
    "facebook live":  Platform.FACEBOOK,
    "fb":             Platform.FACEBOOK,
    "tiktok":         Platform.TIKTOK,
    "tik tok":        Platform.TIKTOK,
    "twitter":        Platform.TWITTER,
    "twitter live":   Platform.TWITTER,
    "x":              Platform.TWITTER,
    "x live":         Platform.TWITTER,
}

# Words that mean "broadcast to all configured platforms"
_ALL_ALIASES = {"everywhere", "all", "all platforms", "everything"}


# ---------------------------------------------------------------------------
# Session info
# ---------------------------------------------------------------------------

@dataclass
class StreamSession:
    """Metadata for an active or completed stream session."""
    platform: Platform
    rtmp_url: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.ended_at is None:
            return None
        return (self.ended_at - self.started_at).total_seconds()


# ---------------------------------------------------------------------------
# LivestreamApp
# ---------------------------------------------------------------------------

class LivestreamApp(App):
    """Multi-platform livestream manager.

    Parameters
    ----------
    glasses:
        A connected :class:`~metaglasses.glasses.Glasses` instance.
    ai:
        Optional AI client (not required for this app).
    stream_keys:
        Mapping from :class:`Platform` to stream key / RTMP stream name.
        For ``Platform.CUSTOM`` the value must be the full RTMP URL.
    relay_url:
        RTMP URL of your relay / restream server.  When set, all multi-
        platform streams push to this URL while all listed platforms are
        tracked as targets.
    on_event:
        Optional callback invoked with stream lifecycle events.
    """

    name = "livestream"
    description = (
        "Go live on YouTube, Twitch, Instagram, Facebook, TikTok, Twitter/X, "
        "or all platforms at once via a relay"
    )

    def __init__(
        self,
        glasses,
        ai=None,
        stream_keys: Optional[Dict[Platform, str]] = None,
        relay_url: Optional[str] = None,
        on_event: Optional[Callable[[dict], None]] = None,
    ) -> None:
        super().__init__(glasses, ai)
        self.stream_keys: Dict[Platform, str] = stream_keys or {}
        self.relay_url = relay_url
        self.on_event = on_event
        # active sessions keyed by platform
        self._active_sessions: Dict[Platform, StreamSession] = {}
        self.session_history: List[StreamSession] = []

    # ------------------------------------------------------------------
    # Single-platform
    # ------------------------------------------------------------------

    def go_live(
        self,
        platform: "Platform | str",
        stream_key: Optional[str] = None,
    ) -> StreamSession:
        """Start a livestream to *platform*.

        Parameters
        ----------
        platform:
            A :class:`Platform` enum value or its string name
            (case-insensitive, e.g. ``"youtube"``).
        stream_key:
            Stream key override.  If omitted the key from ``stream_keys``
            is used.

        Returns
        -------
        StreamSession

        Raises
        ------
        RuntimeError
            If a stream is already active or no stream key is available.
        ValueError
            If *platform* is not recognised.
        """
        platform = self._resolve_platform(platform)
        if platform in self._active_sessions:
            raise RuntimeError(
                f"A stream to {platform.value!r} is already active."
            )
        rtmp_url = self._build_rtmp_url(platform, stream_key)
        self.glasses.start_livestream(rtmp_url)
        session = StreamSession(platform=platform, rtmp_url=rtmp_url)
        self._active_sessions[platform] = session
        self._fire({
            "event": "stream_started",
            "platform": platform.value,
            "rtmp_url": rtmp_url,
            "targets": [platform.value],
        })
        return session

    # ------------------------------------------------------------------
    # Multi-platform
    # ------------------------------------------------------------------

    def go_live_multi(
        self,
        platforms: List["Platform | str"],
        relay_url: Optional[str] = None,
    ) -> List[StreamSession]:
        """Stream to *multiple platforms simultaneously*.

        The glasses push a **single RTMP stream** — either to the
        ``relay_url`` (a restream/relay server that fans it out) or, if
        no relay is given, to the first platform's native RTMP endpoint
        while the rest are tracked as additional targets.

        Parameters
        ----------
        platforms:
            List of :class:`Platform` values or string names.
        relay_url:
            RTMP URL of your relay server.  Overrides the instance-level
            ``relay_url`` set in the constructor for this call.

        Returns
        -------
        list[StreamSession]
            One session per platform.

        Raises
        ------
        RuntimeError
            If any target platform is already streaming.
        ValueError
            If the platform list is empty.
        """
        if not platforms:
            raise ValueError("platforms list must not be empty.")

        resolved = [self._resolve_platform(p) for p in platforms]
        for p in resolved:
            if p in self._active_sessions:
                raise RuntimeError(f"A stream to {p.value!r} is already active.")

        effective_relay = relay_url or self.relay_url

        if effective_relay:
            push_url = effective_relay
        else:
            # Fall back to the first platform's native RTMP URL
            push_url = self._build_rtmp_url(resolved[0], stream_key=None)

        self.glasses.start_livestream(push_url)

        sessions: List[StreamSession] = []
        for p in resolved:
            session = StreamSession(platform=p, rtmp_url=push_url)
            self._active_sessions[p] = session
            sessions.append(session)

        self._fire({
            "event": "stream_started",
            "platforms": [p.value for p in resolved],
            "rtmp_url": push_url,
            "targets": [p.value for p in resolved],
            "relay": bool(effective_relay),
        })
        return sessions

    def go_live_all(self, relay_url: Optional[str] = None) -> List[StreamSession]:
        """Stream to **every configured platform** at once.

        Requires at least one entry in ``stream_keys``.

        Parameters
        ----------
        relay_url:
            RTMP URL of your relay server.  Overrides the instance-level
            ``relay_url`` for this call.

        Returns
        -------
        list[StreamSession]

        Raises
        ------
        RuntimeError
            If no stream keys are configured.
        """
        if not self.stream_keys:
            raise RuntimeError(
                "No stream keys configured. "
                "Pass stream_keys={Platform.X: 'key', ...} to LivestreamApp()."
            )
        return self.go_live_multi(list(self.stream_keys.keys()), relay_url=relay_url)

    # ------------------------------------------------------------------
    # Stop
    # ------------------------------------------------------------------

    def end_stream(self) -> List[StreamSession]:
        """Stop all active streams.

        Returns
        -------
        list[StreamSession]
            All completed sessions (one per previously active platform).
        """
        if not self._active_sessions:
            return []

        self.glasses.stop_livestream()
        ended_at = datetime.now(timezone.utc)
        completed: List[StreamSession] = []
        for session in self._active_sessions.values():
            session.ended_at = ended_at
            self.session_history.append(session)
            completed.append(session)

        platforms = [s.platform.value for s in completed]
        self._active_sessions.clear()
        self._fire({
            "event": "stream_ended",
            "platforms": platforms,
            "sessions": [
                {"platform": s.platform.value, "duration_seconds": s.duration_seconds}
                for s in completed
            ],
        })
        return completed

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def is_live(self) -> bool:
        """``True`` if any stream is currently active."""
        return bool(self._active_sessions)

    @property
    def active_sessions(self) -> Dict[Platform, StreamSession]:
        """Read-only view of currently active sessions keyed by platform."""
        return dict(self._active_sessions)

    @property
    def active_platforms(self) -> List[Platform]:
        """List of platforms currently being streamed to."""
        return list(self._active_sessions.keys())

    def add_platform(self, platform: Platform, stream_key: str) -> None:
        """Register or update a stream key for *platform*."""
        self.stream_keys[platform] = stream_key

    # ------------------------------------------------------------------
    # App internals
    # ------------------------------------------------------------------

    def _register_commands(self, handler: VoiceCommandHandler) -> None:
        handler.register(
            "go live",
            self._handle_go_live,
            pattern=r"(?:go live(?:\s+on)?|start (?:stream|streaming|live)|live on)\s*(.*)",
        )
        handler.register(
            "stop streaming",
            self._handle_end_stream,
            pattern=r"(?:stop|end)\s+(?:stream(?:ing)?|live)",
        )

    def _handle_go_live(self, ctx: dict) -> None:
        m = re.search(
            r"(?:go live(?:\s+on)?|start (?:stream|streaming|live)|live on)\s*(.*)",
            ctx["matched_text"],
            re.IGNORECASE,
        )
        raw = m.group(1).strip().lower() if m and m.group(1).strip() else ""

        # "everywhere" / "all" / "all platforms"
        if raw in _ALL_ALIASES or not raw:
            try:
                if self.stream_keys:
                    self.go_live_all()
                else:
                    self._fire({"event": "stream_error", "error": "No stream keys configured."})
            except RuntimeError as exc:
                self._fire({"event": "stream_error", "error": str(exc)})
            return

        # "youtube and instagram", "twitch, tiktok", "twitter"
        # Split on " and ", ", and ", or ","
        parts = [p.strip() for p in re.split(r"\s+and\s+|,\s*and\s+|,\s*", raw) if p.strip()]
        resolved: List[Platform] = []
        unrecognised: List[str] = []
        for part in parts:
            p = _VOICE_ALIASES.get(part)
            if p:
                resolved.append(p)
            else:
                unrecognised.append(part)

        if unrecognised:
            self._fire({"event": "stream_error", "error": f"Unknown platforms: {unrecognised}"})
            return

        try:
            if len(resolved) == 1:
                self.go_live(resolved[0])
            else:
                self.go_live_multi(resolved)
        except RuntimeError as exc:
            self._fire({"event": "stream_error", "error": str(exc)})

    def _handle_end_stream(self, ctx: dict) -> None:
        self.end_stream()

    def _fire(self, event: dict) -> None:
        if self.on_event:
            self.on_event(event)

    def _build_rtmp_url(self, platform: Platform, stream_key: Optional[str]) -> str:
        key = stream_key or self.stream_keys.get(platform, "")
        if platform == Platform.CUSTOM:
            if not key:
                raise RuntimeError(
                    "Platform.CUSTOM requires a full RTMP URL as the stream key."
                )
            return key
        if not key:
            raise RuntimeError(
                f"No stream key configured for {platform.value!r}. "
                "Pass stream_keys={{Platform.{p}: 'your-key'}} to LivestreamApp()."
            )
        return f"{_RTMP_BASE_URLS[platform]}/{key}"

    @staticmethod
    def _resolve_platform(platform: "Platform | str") -> Platform:
        if isinstance(platform, Platform):
            return platform
        name = str(platform).lower().strip()
        for p in Platform:
            if p.value == name:
                return p
        raise ValueError(
            f"Unknown platform {platform!r}. "
            f"Use one of: {[p.value for p in Platform]}"
        )
