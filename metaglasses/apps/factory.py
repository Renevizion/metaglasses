r"""
metaglasses.apps.factory — rapid app creation toolkit.

When you're "rapid-firing" apps for your glasses you don't want to write a
full sub-class for every idea.  :class:`QuickApp` lets you define a new
specialized app in **3-5 lines** using a fluent builder API.

Quick examples
--------------
::

    from metaglasses.apps.factory import QuickApp

    # Nutrition assistant
    nutrition = (
        QuickApp("nutrition", "Calorie & nutrition info for food you see",
                 ai_system_prompt="You are a certified nutritionist. Be concise.")
        .on(r"(?:calories|nutrition|how healthy is)\s+(.+)",
            lambda ctx, app: app.say(app.ask_ai(f"Nutrition info for: {ctx['groups'][0]}")))
        .on(r"is .+ healthy",
            lambda ctx, app: app.say(app.ask_ai(ctx["matched_text"])))
    )

    # Wine sommelier
    wine = (
        QuickApp("wine", "Sommelier — wine pairings and recommendations",
                 ai_system_prompt="You are a world-class sommelier. Be concise.")
        .on(r"(?:recommend|suggest|pair)\s+(?:a\s+)?wine\s*(.*)",
            lambda ctx, app: app.say(app.ask_ai(f"Recommend a wine for: {ctx['groups'][0]}")))
        .on(r"what wine goes with\s+(.+)",
            lambda ctx, app: app.say(app.ask_ai(f"Wine pairing for: {ctx['groups'][0]}")))
    )

    # Stock ticker
    stocks = (
        QuickApp("stocks", "Real-time stock price lookups",
                 ai_system_prompt="You are a financial assistant. Be brief.")
        .on(r"(?:price of|how is|stock)\s+([A-Z]+)",
            lambda ctx, app: app.say(app.ask_ai(f"Current stock price and 1-day change for {ctx['groups'][0]}")))
    )

AppRunner integration
---------------------
::

    runner = AppRunner(glasses, ai)
    for app in [nutrition, wine, stocks]:
        runner.register(app)

    runner.launch("nutrition")
    runner.launch("wine")
    # Both apps listen simultaneously
    runner.stop_all()

Callback signature
------------------
Callbacks receive two arguments:

* ``ctx`` — the same context dict passed by :class:`~metaglasses.voice.VoiceCommandHandler`:
  ``{"utterance": ..., "matched_text": ..., "groups": [...]}``
* ``app`` — the :class:`QuickApp` instance, giving access to
  ``app.ask_ai()``, ``app.glasses``, ``app.ai``, ``app.last_result``

If your callback only needs ``ctx`` (no AI calls), it can take a single arg::

    .on(r"take a photo", lambda ctx: glasses.take_photo())
"""

from __future__ import annotations

import inspect
import re
from typing import Any, Callable, List, Optional, Tuple

from ..apps import App
from ..voice import VoiceCommandHandler


# Callback type: fn(ctx, app) or fn(ctx)
_Callback = Callable[..., Any]


class QuickApp(App):
    """Rapid-fire app builder — define a specialized glasses app in a few lines.

    Parameters
    ----------
    name:
        Short identifier (e.g. ``"nutrition"``).
    description:
        One-line description shown in :class:`~metaglasses.apps.AppRunner` listings.
    ai_system_prompt:
        If provided, this system prompt is prepended to the AI conversation
        when the app is first activated.  Use it to specialise the AI persona
        for your app (e.g. ``"You are a certified nutritionist."``).
    on_result:
        Optional callback invoked with the return value of each command
        callback (useful for forwarding results to a display or TTS layer).
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        *,
        ai_system_prompt: Optional[str] = None,
        on_result: Optional[Callable[[Any], None]] = None,
    ) -> None:
        # Skip App.__init__ for now — we need glasses to be provided via
        # bind() or AppRunner.register() before the app can be started.
        # We store the init args and finish setup lazily in bind().
        self.name = name
        self.description = description
        self._ai_system_prompt = ai_system_prompt
        self.on_result = on_result
        self.last_result: Any = None
        self._pending: List[Tuple[re.Pattern, _Callback]] = []

        # Set to None until bind() is called; App internals initialised then.
        self.glasses = None  # type: ignore[assignment]
        self.ai = None
        self._active = False
        self._handler = None  # type: ignore[assignment]
        self._bound = False

    # ------------------------------------------------------------------
    # Fluent builder
    # ------------------------------------------------------------------

    def on(
        self,
        pattern: str,
        callback: _Callback,
    ) -> "QuickApp":
        """Register a voice command pattern and its callback.

        Parameters
        ----------
        pattern:
            A regular expression matched against the utterance (after the
            wake word has been stripped).  Named groups and positional
            groups are both supported.
        callback:
            Callable invoked when *pattern* matches.  Signature can be:

            * ``fn(ctx, app)`` — receives the context dict and this
              :class:`QuickApp` instance.
            * ``fn(ctx)`` — receives only the context dict.

        Returns
        -------
        QuickApp
            Returns ``self`` for chaining.
        """
        compiled = re.compile(pattern, re.IGNORECASE)
        self._pending.append((compiled, callback))
        return self

    def bind(self, glasses, ai=None) -> "QuickApp":
        """Attach *glasses* (and optionally *ai*) to this app.

        This is called automatically by :class:`~metaglasses.apps.AppRunner`
        when the app is registered with ``runner.register(app)``.  You only
        need to call it directly when using a QuickApp outside of a runner.

        Must be called before :meth:`start`.

        Returns
        -------
        QuickApp
            Returns ``self`` for chaining.
        """
        self.glasses = glasses
        self.ai = ai
        self._handler = VoiceCommandHandler(glasses)
        self._bound = True
        return self

    def start(self) -> None:
        """Activate the app and begin listening for voice commands.

        Raises
        ------
        RuntimeError
            If :meth:`bind` has not been called yet.
        """
        if not self._bound:
            raise RuntimeError(
                f"QuickApp {self.name!r} must be bound to a Glasses instance "
                "before starting. Call .bind(glasses) or register it with an AppRunner."
            )
        super().start()

    def stop(self) -> None:
        """Deactivate the app."""
        if not self._bound:
            return
        super().stop()

    # ------------------------------------------------------------------
    # AI helper
    # ------------------------------------------------------------------

    def ask_ai(self, prompt: str) -> str:
        """Send *prompt* to the AI and return the text reply.

        Parameters
        ----------
        prompt:
            The question or instruction.

        Returns
        -------
        str
            The AI's text response, or an error message if no AI client
            is configured.
        """
        if self.ai is None:
            return "[No AI client configured]"
        try:
            response = self.ai.chat(prompt)
            return response.text
        except Exception as exc:
            return f"[AI error: {exc}]"

    def say(self, text: str) -> str:
        """Store *text* as :attr:`last_result` and pass it to ``on_result``.

        In a real deployment you would pipe this to a TTS engine.  For now
        it just stores the value and calls your callback.

        Returns
        -------
        str
            The same *text* that was passed in.
        """
        self.last_result = text
        if self.on_result:
            self.on_result(text)
        return text

    # ------------------------------------------------------------------
    # App internals
    # ------------------------------------------------------------------

    def _on_start(self) -> None:
        # Apply system prompt once when the app first activates
        if self._ai_system_prompt and self.ai is not None:
            system_messages = [m for m in self.ai.history if m.role == "system"]
            if not system_messages:
                from ..ai import Message
                self.ai._history.insert(0, Message(role="system", content=self._ai_system_prompt))

    def _register_commands(self, handler: VoiceCommandHandler) -> None:
        for compiled_pattern, raw_cb in self._pending:
            # Wrap callback to inject groups into ctx and forward app ref
            cb = self._wrap(compiled_pattern, raw_cb)
            handler._commands.append((compiled_pattern, cb))

    def _wrap(self, pattern: re.Pattern, callback: _Callback) -> _Callback:
        """Return a VoiceCommandHandler-compatible callback."""
        needs_app = len(inspect.signature(callback).parameters) >= 2

        def wrapped(ctx: dict) -> None:
            m = pattern.search(ctx.get("matched_text", ""))
            ctx["groups"] = list(m.groups()) if m else []
            ctx["match"] = m
            result = callback(ctx, self) if needs_app else callback(ctx)
            if result is not None:
                self.say(str(result))

        return wrapped


# ---------------------------------------------------------------------------
# Convenience factory function
# ---------------------------------------------------------------------------

def quick_app(
    name: str,
    description: str = "",
    *,
    ai_system_prompt: Optional[str] = None,
    on_result: Optional[Callable[[Any], None]] = None,
) -> QuickApp:
    """Convenience function — same as ``QuickApp(name, description, ...)``."""
    return QuickApp(
        name,
        description,
        ai_system_prompt=ai_system_prompt,
        on_result=on_result,
    )
