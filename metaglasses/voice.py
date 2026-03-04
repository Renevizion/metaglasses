"""
Voice command handling for Ray-Ban Meta Smart Glasses (Generation 2).

The glasses expose a Bluetooth audio stream that is processed locally on the
companion phone and, optionally, by Meta AI in the cloud.  This module lets
you register custom voice-command handlers that are invoked when recognised
phrases are heard.

Typical usage::

    from metaglasses import Glasses, VoiceCommandHandler

    glasses = Glasses()
    glasses.connect()

    handler = VoiceCommandHandler(glasses)

    @handler.command("hey meta, take a photo")
    def on_photo(_ctx):
        glasses.take_photo()
        print("Photo taken!")

    handler.start()
    # ... keep the process alive ...
    handler.stop()
    glasses.disconnect()
"""

from __future__ import annotations

import re
import threading
from typing import Callable, Dict, List, Optional

from .glasses import Glasses, GlassesNotConnectedError


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

CommandCallback = Callable[[dict], None]


# ---------------------------------------------------------------------------
# VoiceCommandHandler
# ---------------------------------------------------------------------------

class VoiceCommandHandler:
    """Register and dispatch voice-command callbacks.

    Commands are matched against transcribed utterances using simple
    keyword matching (or an optional regex pattern).

    Parameters
    ----------
    glasses:
        A connected :class:`~metaglasses.glasses.Glasses` instance.
    wake_word:
        The phrase that must precede a command.  Defaults to
        ``"hey meta"``.  Set to ``""`` to match any utterance.
    """

    def __init__(
        self,
        glasses: Glasses,
        wake_word: str = "hey meta",
    ) -> None:
        self._glasses = glasses
        self.wake_word = wake_word.lower().strip()
        self._commands: List[tuple[re.Pattern, CommandCallback]] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def command(
        self,
        phrase: str,
        *,
        pattern: Optional[str] = None,
    ) -> Callable[[CommandCallback], CommandCallback]:
        """Decorator — register a function as a voice-command handler.

        Parameters
        ----------
        phrase:
            Literal phrase to match (case-insensitive, after the wake word).
        pattern:
            Optional regex that overrides *phrase*.

        Examples
        --------
        ::

            @handler.command("take a photo")
            def snap(ctx):
                glasses.take_photo()

            @handler.command("start recording", pattern=r"start (recording|video)")
            def rec(ctx):
                glasses.start_video()
        """
        regex = re.compile(pattern or re.escape(phrase), re.IGNORECASE)

        def decorator(fn: CommandCallback) -> CommandCallback:
            self._commands.append((regex, fn))
            return fn

        return decorator

    def register(
        self,
        phrase: str,
        callback: CommandCallback,
        *,
        pattern: Optional[str] = None,
    ) -> None:
        """Programmatically register a callback without using the decorator.

        Parameters
        ----------
        phrase:
            Literal phrase to match.
        callback:
            Callable to invoke when the phrase is recognised.
        pattern:
            Optional regex override.
        """
        regex = re.compile(pattern or re.escape(phrase), re.IGNORECASE)
        self._commands.append((regex, callback))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background audio-transcription loop.

        Raises
        ------
        GlassesNotConnectedError
            If the glasses are not connected.
        RuntimeError
            If the handler is already running.
        """
        if not self._glasses.is_connected:
            raise GlassesNotConnectedError(
                "Not connected to any glasses. Call Glasses.connect() first."
            )
        if self._running:
            raise RuntimeError("VoiceCommandHandler is already running.")
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the background audio-transcription loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    @property
    def is_running(self) -> bool:
        """``True`` if the handler is actively listening."""
        return self._running

    # ------------------------------------------------------------------
    # Dispatch (also callable directly from tests / custom audio pipelines)
    # ------------------------------------------------------------------

    def dispatch(self, utterance: str) -> bool:
        """Process *utterance* and invoke any matching callbacks.

        Parameters
        ----------
        utterance:
            A transcribed string from the audio stream.

        Returns
        -------
        bool
            ``True`` if at least one command was matched and invoked.
        """
        text = utterance.lower().strip()

        # Strip wake word if present
        if self.wake_word and text.startswith(self.wake_word):
            text = text[len(self.wake_word):].strip(",. ")

        matched = False
        ctx = {"utterance": utterance, "matched_text": text}
        for pattern, callback in self._commands:
            if pattern.search(text):
                callback(ctx)
                matched = True

        return matched

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _listen_loop(self) -> None:
        """Background thread that consumes audio from the glasses.

        In a real implementation this would call into a BLE audio sink and
        feed PCM frames to a speech-recognition engine (e.g. whisper.cpp or
        the Meta on-device model).  Here we simply idle.
        """
        while self._running:
            import time
            time.sleep(0.05)
