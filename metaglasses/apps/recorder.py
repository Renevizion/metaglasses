"""
RecorderApp — smart recording session manager for the glasses.

Features
--------
* Voice-activated start/stop: *"hey meta, start recording"* / *"stop recording"*
* Auto-named files using ISO-8601 timestamps (e.g. ``recording_20260303T214500.mp4``)
* Session tracking: duration, storage consumed, clip list
* Pre-roll guard: warns if storage is below a configurable threshold
* Optional AI-generated clip titles from voice description

Typical usage::

    from metaglasses import Glasses
    from metaglasses.apps.recorder import RecorderApp

    glasses = Glasses()
    glasses.connect()

    app = RecorderApp(
        glasses,
        on_clip_saved=lambda c: print(f"Saved {c.filename} ({c.duration_seconds:.1f}s)"),
    )
    app.start()
    app.begin_recording()
    # … time passes …
    clip = app.finish_recording()
    print(clip)
    app.stop()
    glasses.disconnect()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, List, Optional

from ..apps import App
from ..glasses import Glasses
from ..voice import VoiceCommandHandler


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Clip:
    """Metadata for a recorded video clip."""
    media_id: str
    filename: str
    started_at: datetime
    ended_at: datetime
    title: Optional[str] = None

    @property
    def duration_seconds(self) -> float:
        return (self.ended_at - self.started_at).total_seconds()

    @property
    def duration_str(self) -> str:
        total = int(self.duration_seconds)
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h}h {m:02d}m {s:02d}s"
        return f"{m}m {s:02d}s"


# ---------------------------------------------------------------------------
# RecorderApp
# ---------------------------------------------------------------------------

class RecorderApp(App):
    """Voice-activated smart recording manager.

    Parameters
    ----------
    glasses:
        A connected :class:`~metaglasses.glasses.Glasses` instance.
    ai:
        Optional AI client.  When provided, clip titles are generated from
        a brief voice description.
    on_clip_saved:
        Callback invoked with a :class:`Clip` each time recording stops.
    min_storage_mb:
        Minimum free storage in MB required before recording is allowed.
        Defaults to ``500``.
    """

    name = "recorder"
    description = "Voice-activated recording with auto-named clips and session tracking"

    def __init__(
        self,
        glasses: Glasses,
        ai=None,
        on_clip_saved: Optional[Callable[[Clip], None]] = None,
        min_storage_mb: float = 500.0,
    ) -> None:
        super().__init__(glasses, ai)
        self.on_clip_saved = on_clip_saved
        self.min_storage_mb = min_storage_mb

        self.clips: List[Clip] = []
        self._recording_started_at: Optional[datetime] = None
        self._pending_title_hint: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def begin_recording(self, title_hint: Optional[str] = None) -> None:
        """Start a new recording session.

        Parameters
        ----------
        title_hint:
            Optional short description used to generate an AI clip title.

        Raises
        ------
        RuntimeError
            If a recording is already in progress or storage is too low.
        """
        if self._recording_started_at is not None:
            raise RuntimeError("A recording is already in progress. Call finish_recording() first.")
        self._check_storage()
        self._recording_started_at = datetime.now(timezone.utc)
        self.glasses.start_video()
        self._pending_title_hint = title_hint

    def finish_recording(self) -> Clip:
        """Stop the active recording and return its :class:`Clip` metadata.

        Raises
        ------
        RuntimeError
            If no recording is in progress.
        """
        if self._recording_started_at is None:
            raise RuntimeError("No recording is in progress. Call begin_recording() first.")
        started_at = self._recording_started_at
        self._recording_started_at = None

        media_id = self.glasses.stop_video()
        ended_at = datetime.now(timezone.utc)
        ts = started_at.strftime("%Y%m%dT%H%M%S")
        filename = f"recording_{ts}.mp4"

        title: Optional[str] = None
        hint = getattr(self, "_pending_title_hint", None)
        if hint and self.ai:
            try:
                resp = self.ai.chat(
                    f"Generate a short, descriptive filename-style title (no extension, "
                    f"use underscores, max 5 words) for a video clip described as: {hint}"
                )
                title = resp.text.strip().replace(" ", "_").lower()
            except Exception:
                pass
        self._pending_title_hint = None

        clip = Clip(
            media_id=media_id,
            filename=filename,
            started_at=started_at,
            ended_at=ended_at,
            title=title,
        )
        self.clips.append(clip)
        if self.on_clip_saved:
            self.on_clip_saved(clip)
        return clip

    @property
    def is_recording(self) -> bool:
        """``True`` if a recording is currently in progress."""
        return self._recording_started_at is not None

    def session_summary(self) -> dict:
        """Return a summary of all clips recorded in this session.

        Returns
        -------
        dict
            Keys: ``clip_count``, ``total_duration_seconds``, ``clips``.
        """
        total_dur = sum(c.duration_seconds for c in self.clips)
        return {
            "clip_count": len(self.clips),
            "total_duration_seconds": total_dur,
            "clips": [
                {
                    "media_id": c.media_id,
                    "filename": c.filename,
                    "title": c.title,
                    "duration": c.duration_str,
                }
                for c in self.clips
            ],
        }

    # ------------------------------------------------------------------
    # App internals
    # ------------------------------------------------------------------

    def _register_commands(self, handler: VoiceCommandHandler) -> None:
        handler.register(
            "start recording",
            self._handle_start,
            pattern=r"(?:start|begin)\s+(?:recording|video|clip)\s*(.*)",
        )
        handler.register(
            "stop recording",
            self._handle_stop,
            pattern=r"(?:stop|end|finish)\s+(?:recording|video|clip)",
        )

    def _handle_start(self, ctx: dict) -> None:
        import re
        m = re.search(
            r"(?:start|begin)\s+(?:recording|video|clip)\s*(.*)",
            ctx["matched_text"],
            re.IGNORECASE,
        )
        hint = m.group(1).strip() if m and m.group(1).strip() else None
        try:
            self.begin_recording(title_hint=hint)
        except RuntimeError:
            pass  # already recording

    def _handle_stop(self, ctx: dict) -> None:
        try:
            self.finish_recording()
        except RuntimeError:
            pass  # nothing to stop

    def _check_storage(self) -> None:
        try:
            info = self.glasses.device_info()
            free = info.storage_total_mb - info.storage_used_mb
            if free < self.min_storage_mb:
                raise RuntimeError(
                    f"Insufficient storage: {free:.0f} MB free, "
                    f"{self.min_storage_mb:.0f} MB required."
                )
        except Exception as exc:
            if "Insufficient storage" in str(exc):
                raise
            # Device info unavailable — proceed optimistically.
