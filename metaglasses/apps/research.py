"""
ResearchApp — AI-powered research assistant on your glasses.

Workflow
--------
1. The user says **"hey meta, research <topic>"**.
2. The app sends the topic to Meta AI and returns a structured summary.
3. The result is stored in :attr:`ResearchApp.last_result` and passed to an
   optional ``on_result`` callback.
4. Follow-up questions are supported: **"hey meta, tell me more"** deepens
   the last research topic.

Typical usage::

    from metaglasses import Glasses, MetaAIClient
    from metaglasses.apps.research import ResearchApp

    glasses = Glasses()
    glasses.connect()
    ai = MetaAIClient(api_key="...")

    app = ResearchApp(glasses, ai, on_result=lambda r: print(r["summary"]))
    app.start()
    app.research("quantum computing")
    app.follow_up("explain qubits in simple terms")
    app.stop()
    glasses.disconnect()
"""

from __future__ import annotations

import re
from typing import Callable, Optional

from ..apps import App
from ..voice import VoiceCommandHandler


class ResearchApp(App):
    """Voice-activated AI research assistant.

    Parameters
    ----------
    glasses:
        A connected :class:`~metaglasses.glasses.Glasses` instance.
    ai:
        A :class:`~metaglasses.ai.MetaAIClient`.
    on_result:
        Optional callback invoked with a ``dict`` containing ``"topic"``
        and ``"summary"`` keys whenever a research result is ready.
    """

    name = "research"
    description = "Research any topic via voice and get an AI summary"

    _SYSTEM_PROMPT = (
        "You are a research assistant running on smart glasses. "
        "When asked to research a topic, provide a concise but thorough "
        "summary: key facts, current state, and why it matters. "
        "Structure your answer in 3-5 short paragraphs. "
        "When asked a follow-up, build on the previous context."
    )

    def __init__(
        self,
        glasses,
        ai=None,
        on_result: Optional[Callable[[dict], None]] = None,
    ) -> None:
        super().__init__(glasses, ai)
        self.on_result = on_result
        self.last_result: Optional[dict] = None
        self._current_topic: Optional[str] = None

        if self.ai and not any(m.role == "system" for m in self.ai.history):
            from ..ai import Message
            self.ai._history.insert(0, Message(role="system", content=self._SYSTEM_PROMPT))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def research(self, topic: str) -> dict:
        """Research *topic* and return a summary.

        Parameters
        ----------
        topic:
            The subject to research (e.g. ``"climate change mitigation"``).

        Returns
        -------
        dict
            ``{"topic": topic, "summary": "<AI summary text>"}``

        Raises
        ------
        RuntimeError
            If no AI client was provided.
        """
        if self.ai is None:
            raise RuntimeError("ResearchApp requires an AI client (ai= argument).")
        self._current_topic = topic
        # Clear only user/assistant messages, preserving the system prompt
        self.ai._history = [m for m in self.ai._history if m.role == "system"]
        response = self.ai.chat(f"Research this topic for me: {topic}")
        result = {"topic": topic, "summary": response.text}
        self.last_result = result
        if self.on_result:
            self.on_result(result)
        return result

    def follow_up(self, question: str) -> dict:
        """Ask a follow-up question about the last researched topic.

        Parameters
        ----------
        question:
            A follow-up question (e.g. ``"what are the main challenges?"``).

        Returns
        -------
        dict
            ``{"topic": question, "summary": "<AI answer text>"}``

        Raises
        ------
        RuntimeError
            If no AI client was provided, or if no research session is active.
        """
        if self.ai is None:
            raise RuntimeError("ResearchApp requires an AI client (ai= argument).")
        if self._current_topic is None:
            raise RuntimeError("No active research topic. Call research() first.")
        response = self.ai.chat(question)
        result = {"topic": question, "summary": response.text}
        self.last_result = result
        if self.on_result:
            self.on_result(result)
        return result

    # ------------------------------------------------------------------
    # App internals
    # ------------------------------------------------------------------

    def _register_commands(self, handler: VoiceCommandHandler) -> None:
        handler.register(
            "research",
            self._handle_research,
            pattern=r"research\s+(.+)",
        )
        handler.register(
            "tell me more",
            self._handle_follow_up,
            pattern=r"(tell me more|follow up|more details?|go deeper)\s*(.*)",
        )

    def _handle_research(self, ctx: dict) -> None:
        m = re.search(r"research\s+(.+)", ctx["matched_text"], re.IGNORECASE)
        topic = m.group(1).strip() if m else ctx["matched_text"]
        self.research(topic)

    def _handle_follow_up(self, ctx: dict) -> None:
        m = re.search(
            r"(?:tell me more|follow up|more details?|go deeper)\s*(.*)",
            ctx["matched_text"],
            re.IGNORECASE,
        )
        question = (m.group(1).strip() if m and m.group(1).strip() else "tell me more")
        self.follow_up(question)
