"""
OutreachApp — compose and send messages, emails, and call requests via voice.

Workflow
--------
* **Message**: say *"hey meta, text John: running five minutes late"*
* **Email**: say *"hey meta, email Sarah: the report is attached"*
* **Call**: say *"hey meta, call mom"*

The app drafts the content (optionally polished by Meta AI), stores it in
:attr:`OutreachApp.outbox`, and invokes your ``on_send`` callback so you can
wire it to any messaging back-end (Twilio, SMTP, WhatsApp, etc.).

Typical usage::

    from metaglasses import Glasses, MetaAIClient
    from metaglasses.apps.outreach import OutreachApp

    def send_handler(item):
        print(f"[{item['type'].upper()}] To: {item['to']} | Body: {item['body']}")

    glasses = Glasses()
    glasses.connect()
    ai = MetaAIClient(api_key="...")

    app = OutreachApp(glasses, ai, on_send=send_handler)
    app.start()
    app.send_message("Alex", "I'll be there in 10 minutes")
    app.send_email("boss@example.com", "Quick update: project is on track")
    app.request_call("Alice")
    app.stop()
    glasses.disconnect()
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, List, Literal, Optional

from ..apps import App
from ..voice import VoiceCommandHandler


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

OutreachType = Literal["message", "email", "call"]


@dataclass
class OutreachItem:
    """Represents a single outreach action."""
    type: OutreachType
    to: str
    body: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sent: bool = False


# ---------------------------------------------------------------------------
# OutreachApp
# ---------------------------------------------------------------------------

class OutreachApp(App):
    """Voice-activated messaging, email, and call app.

    Parameters
    ----------
    glasses:
        A connected :class:`~metaglasses.glasses.Glasses` instance.
    ai:
        An optional :class:`~metaglasses.ai.MetaAIClient`.  When provided,
        drafted messages are polished by the AI before being handed off.
    on_send:
        Callback invoked with each :class:`OutreachItem` ready to be sent.
        Wire this to your messaging back-end (Twilio, SMTP, etc.).
    polish_with_ai:
        If ``True`` (default) and an AI client is available, raw voice
        transcripts are cleaned up and made more professional before sending.
    """

    name = "outreach"
    description = "Send messages, emails, and call requests via voice"

    _SYSTEM_PROMPT = (
        "You are a communication assistant on smart glasses. "
        "When given a raw voice-dictated message, lightly polish it for "
        "clarity and tone while preserving the original intent. "
        "Return only the polished message text, nothing else."
    )

    def __init__(
        self,
        glasses,
        ai=None,
        on_send: Optional[Callable[[OutreachItem], None]] = None,
        polish_with_ai: bool = True,
    ) -> None:
        super().__init__(glasses, ai)
        self.on_send = on_send
        self.polish_with_ai = polish_with_ai
        self.outbox: List[OutreachItem] = []

        if self.ai and not any(m.role == "system" for m in self.ai.history):
            from ..ai import Message
            self.ai._history.insert(0, Message(role="system", content=self._SYSTEM_PROMPT))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send_message(self, to: str, body: str) -> OutreachItem:
        """Compose and queue an SMS/instant message.

        Parameters
        ----------
        to:
            Recipient name or phone number.
        body:
            Message text (will be AI-polished if ``polish_with_ai`` is set).

        Returns
        -------
        OutreachItem
            The queued outreach item.
        """
        body = self._maybe_polish(body, hint="SMS")
        item = OutreachItem(type="message", to=to, body=body)
        return self._dispatch(item)

    def send_email(self, to: str, body: str) -> OutreachItem:
        """Compose and queue an email.

        Parameters
        ----------
        to:
            Recipient name or email address.
        body:
            Email body text (will be AI-polished if ``polish_with_ai`` is set).

        Returns
        -------
        OutreachItem
        """
        body = self._maybe_polish(body, hint="professional email")
        item = OutreachItem(type="email", to=to, body=body)
        return self._dispatch(item)

    def request_call(self, to: str) -> OutreachItem:
        """Queue a call request to *to*.

        Parameters
        ----------
        to:
            Contact name or phone number.

        Returns
        -------
        OutreachItem
        """
        item = OutreachItem(type="call", to=to, body="")
        return self._dispatch(item)

    # ------------------------------------------------------------------
    # App internals
    # ------------------------------------------------------------------

    def _register_commands(self, handler: VoiceCommandHandler) -> None:
        # "text / message <name>: <body>" or "text <name> <body>"
        handler.register(
            "text",
            self._handle_message,
            pattern=r"(?:text|message|send message to)\s+([^:]+?)[\s:,]+(.+)",
        )
        # "email <name>: <body>"
        handler.register(
            "email",
            self._handle_email,
            pattern=r"(?:email|send email to)\s+([^:]+?)[\s:,]+(.+)",
        )
        # "call <name>"
        handler.register(
            "call",
            self._handle_call,
            pattern=r"(?:call|ring|phone)\s+(.+)",
        )

    def _handle_message(self, ctx: dict) -> None:
        m = re.search(
            r"(?:text|message|send message to)\s+([^:]+?)[\s:,]+(.+)",
            ctx["matched_text"],
            re.IGNORECASE,
        )
        if m:
            self.send_message(m.group(1).strip(), m.group(2).strip())

    def _handle_email(self, ctx: dict) -> None:
        m = re.search(
            r"(?:email|send email to)\s+([^:]+?)[\s:,]+(.+)",
            ctx["matched_text"],
            re.IGNORECASE,
        )
        if m:
            self.send_email(m.group(1).strip(), m.group(2).strip())

    def _handle_call(self, ctx: dict) -> None:
        m = re.search(r"(?:call|ring|phone)\s+(.+)", ctx["matched_text"], re.IGNORECASE)
        if m:
            self.request_call(m.group(1).strip())

    def _maybe_polish(self, body: str, hint: str = "") -> str:
        if not self.polish_with_ai or self.ai is None:
            return body
        prompt = f"Polish this {hint} message: {body}"
        try:
            response = self.ai.chat(prompt)
            return response.text.strip()
        except Exception:
            return body

    def _dispatch(self, item: OutreachItem) -> OutreachItem:
        self.outbox.append(item)
        if self.on_send:
            self.on_send(item)
        return item
