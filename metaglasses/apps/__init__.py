"""
metaglasses.apps — ready-to-use app building blocks for Ray-Ban Meta Smart Glasses.

Each app inherits from :class:`App` and follows the same lifecycle::

    app.start()   # activate; registers voice commands
    app.stop()    # deactivate; unregisters voice commands

Apps are designed to be managed by an :class:`AppRunner`, which handles
registration, launching, and teardown::

    from metaglasses import Glasses, MetaAIClient
    from metaglasses.apps import AppRunner
    from metaglasses.apps.pricing  import PricingApp
    from metaglasses.apps.research import ResearchApp

    glasses = Glasses()
    glasses.connect()
    ai = MetaAIClient(api_key="...")

    runner = AppRunner(glasses, ai)
    runner.register(PricingApp(glasses, ai))
    runner.register(ResearchApp(glasses, ai))

    runner.launch("pricing")
    # … say "hey meta, price check AirPods" …
    runner.stop_all()
    glasses.disconnect()
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional, TYPE_CHECKING

from ..glasses import Glasses
from ..voice import VoiceCommandHandler

if TYPE_CHECKING:
    from ..ai import MetaAIClient


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class App:
    """Abstract base class for all glasses apps.

    Sub-classes must set :attr:`name` and :attr:`description` as class
    attributes and implement :meth:`_register_commands`.

    Parameters
    ----------
    glasses:
        A connected :class:`~metaglasses.glasses.Glasses` instance.
    ai:
        Optional :class:`~metaglasses.ai.MetaAIClient`.  Most apps require
        this; pass ``None`` only for apps that work without an AI backend.
    """

    #: Short identifier used by :class:`AppRunner` (e.g. ``"pricing"``).
    name: str = ""
    #: One-line description shown in runner listings.
    description: str = ""

    def __init__(
        self,
        glasses: Glasses,
        ai: Optional["MetaAIClient"] = None,
    ) -> None:
        self.glasses = glasses
        self.ai = ai
        self._handler = VoiceCommandHandler(glasses)
        self._active = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Activate the app and begin listening for voice commands."""
        if self._active:
            return
        self._register_commands(self._handler)
        self._handler.start()
        self._active = True
        self._on_start()

    def stop(self) -> None:
        """Deactivate the app and stop listening."""
        if not self._active:
            return
        self._handler.stop()
        self._active = False
        self._on_stop()

    @property
    def is_active(self) -> bool:
        """``True`` if the app is currently running."""
        return self._active

    # ------------------------------------------------------------------
    # Hooks (override in sub-classes as needed)
    # ------------------------------------------------------------------

    def _register_commands(self, handler: VoiceCommandHandler) -> None:
        """Register all voice commands on *handler*.  Must be overridden."""
        raise NotImplementedError

    def _on_start(self) -> None:
        """Called once after the app becomes active.  Optional hook."""

    def _on_stop(self) -> None:
        """Called once after the app becomes inactive.  Optional hook."""

    def __repr__(self) -> str:
        state = "active" if self._active else "idle"
        return f"{self.__class__.__name__}(name={self.name!r}, state={state})"


# ---------------------------------------------------------------------------
# AppRunner
# ---------------------------------------------------------------------------

class AppRunner:
    """Registry and launcher for :class:`App` instances.

    Parameters
    ----------
    glasses:
        A connected :class:`~metaglasses.glasses.Glasses` instance.
    ai:
        Optional shared :class:`~metaglasses.ai.MetaAIClient`.
    """

    def __init__(
        self,
        glasses: Glasses,
        ai: Optional["MetaAIClient"] = None,
    ) -> None:
        self.glasses = glasses
        self.ai = ai
        self._apps: Dict[str, App] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, app: App) -> None:
        """Register *app* with the runner.

        Parameters
        ----------
        app:
            An :class:`App` instance.  Its :attr:`~App.name` must be unique.

        Raises
        ------
        ValueError
            If an app with the same name is already registered.
        """
        if not app.name:
            raise ValueError(f"{app!r} has no 'name' set.")
        if app.name in self._apps:
            raise ValueError(f"An app named {app.name!r} is already registered.")
        self._apps[app.name] = app

    def unregister(self, name: str) -> None:
        """Stop and unregister the app called *name*."""
        app = self._apps.pop(name, None)
        if app and app.is_active:
            app.stop()

    # ------------------------------------------------------------------
    # Launching
    # ------------------------------------------------------------------

    def launch(self, name: str) -> App:
        """Start the registered app called *name* and return it.

        Raises
        ------
        KeyError
            If no app with *name* is registered.
        """
        app = self._apps[name]
        app.start()
        return app

    def stop(self, name: str) -> None:
        """Stop the registered app called *name*."""
        self._apps[name].stop()

    def stop_all(self) -> None:
        """Stop every active app."""
        for app in self._apps.values():
            if app.is_active:
                app.stop()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_apps(self) -> List[dict]:
        """Return a list of dicts describing registered apps."""
        return [
            {
                "name": app.name,
                "description": app.description,
                "active": app.is_active,
            }
            for app in self._apps.values()
        ]

    def __repr__(self) -> str:
        names = list(self._apps.keys())
        return f"AppRunner(apps={names})"
