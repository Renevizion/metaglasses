"""
LivestreamApp — multi-platform livestream manager for the glasses.

Supported platforms
-------------------
* YouTube Live (RTMP)
* Twitch
* Instagram Live
* Facebook Live
* TikTok Live
* Custom RTMP endpoint

Workflow
--------
1. Pre-configure RTMP keys per platform in the constructor.
2. Say **"hey meta, go live on youtube"** — the app looks up the RTMP URL,
   calls :meth:`~metaglasses.glasses.Glasses.start_livestream`, and fires
   the ``on_event`` callback.
3. Say **"hey meta, stop streaming"** to end the session.

Typical usage::

    from metaglasses import Glasses
    from metaglasses.apps.livestream import LivestreamApp, Platform

    glasses = Glasses()
    glasses.connect()

    app = LivestreamApp(
        glasses,
        stream_keys={
            Platform.YOUTUBE: "xxxx-xxxx-xxxx-xxxx",
            Platform.TWITCH: "live_XXXXXXXXXXXXXX",
        },
        on_event=lambda e: print(e),
    )
    app.start()
    app.go_live(Platform.YOUTUBE)
    # … broadcast …
    app.end_stream()
    app.stop()
    glasses.disconnect()
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Dict, Optional

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
    CUSTOM    = "custom"


_RTMP_BASE_URLS: Dict[Platform, str] = {
    Platform.YOUTUBE:   "rtmp://a.rtmp.youtube.com/live2",
    Platform.TWITCH:    "rtmp://live.twitch.tv/live",
    Platform.INSTAGRAM: "rtmps://live-upload.instagram.com:443/rtmp",
    Platform.FACEBOOK:  "rtmps://live-api-s.facebook.com:443/rtmp",
    Platform.TIKTOK:    "rtmp://push.tiktok.com/live",
}

_VOICE_ALIASES: Dict[str, Platform] = {
    "youtube": Platform.YOUTUBE,
    "twitch":  Platform.TWITCH,
    "instagram": Platform.INSTAGRAM,
    "instagram live": Platform.INSTAGRAM,
    "facebook": Platform.FACEBOOK,
    "facebook live": Platform.FACEBOOK,
    "tiktok": Platform.TIKTOK,
    "tik tok": Platform.TIKTOK,
}


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
    on_event:
        Optional callback invoked with stream lifecycle events.
    """

    name = "livestream"
    description = "Go live on YouTube, Twitch, Instagram, Facebook, TikTok, or custom RTMP"

    def __init__(
        self,
        glasses,
        ai=None,
        stream_keys: Optional[Dict[Platform, str]] = None,
        on_event: Optional[Callable[[dict], None]] = None,
    ) -> None:
        super().__init__(glasses, ai)
        self.stream_keys: Dict[Platform, str] = stream_keys or {}
        self.on_event = on_event
        self._session: Optional[StreamSession] = None
        self.session_history: list[StreamSession] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def go_live(self, platform: "Platform | str", stream_key: Optional[str] = None) -> StreamSession:
        """Start a livestream to *platform*.

        Parameters
        ----------
        platform:
            A :class:`Platform` enum value or its string name (case-insensitive).
        stream_key:
            Stream key override.  If omitted, the key from ``stream_keys``
            constructor argument is used.

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
        if self._session is not None:
            raise RuntimeError(
                f"A stream to {self._session.platform.value!r} is already active. "
                "Call end_stream() first."
            )

        platform = self._resolve_platform(platform)
        key = stream_key or self.stream_keys.get(platform, "")

        if platform == Platform.CUSTOM:
            if not key:
                raise RuntimeError(
                    "Platform.CUSTOM requires a full RTMP URL as the stream key."
                )
            rtmp_url = key
        else:
            if not key:
                raise RuntimeError(
                    f"No stream key configured for {platform.value!r}. "
                    "Pass stream_keys={Platform.X: 'your-key'} to LivestreamApp()."
                )
            rtmp_url = f"{_RTMP_BASE_URLS[platform]}/{key}"

        self.glasses.start_livestream(rtmp_url)
        self._session = StreamSession(platform=platform, rtmp_url=rtmp_url)
        self._fire({"event": "stream_started", "platform": platform.value, "rtmp_url": rtmp_url})
        return self._session

    def end_stream(self) -> Optional[StreamSession]:
        """Stop the active livestream.

        Returns
        -------
        StreamSession | None
            The completed session, or ``None`` if no stream was active.
        """
        if self._session is None:
            return None
        self.glasses.stop_livestream()
        self._session.ended_at = datetime.now(timezone.utc)
        completed = self._session
        self.session_history.append(completed)
        self._session = None
        self._fire({
            "event": "stream_ended",
            "platform": completed.platform.value,
            "duration_seconds": completed.duration_seconds,
        })
        return completed

    @property
    def is_live(self) -> bool:
        """``True`` if a stream is currently active."""
        return self._session is not None

    @property
    def current_session(self) -> Optional[StreamSession]:
        """The active :class:`StreamSession`, or ``None``."""
        return self._session

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
            pattern=r"(?:go live|start (?:stream|streaming|live)|live on)\s*(.*)",
        )
        handler.register(
            "stop streaming",
            self._handle_end_stream,
            pattern=r"(?:stop|end)\s+(?:stream(?:ing)?|live)",
        )

    def _handle_go_live(self, ctx: dict) -> None:
        import re
        m = re.search(
            r"(?:go live|start (?:stream|streaming|live)|live on)\s*(.*)",
            ctx["matched_text"],
            re.IGNORECASE,
        )
        platform_str = m.group(1).strip().lower() if m and m.group(1).strip() else ""
        platform = _VOICE_ALIASES.get(platform_str, Platform.CUSTOM if platform_str else Platform.YOUTUBE)
        try:
            self.go_live(platform)
        except RuntimeError as exc:
            self._fire({"event": "stream_error", "error": str(exc)})

    def _handle_end_stream(self, ctx: dict) -> None:
        self.end_stream()

    def _fire(self, event: dict) -> None:
        if self.on_event:
            self.on_event(event)

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
