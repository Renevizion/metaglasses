"""
Meta AI integration for Ray-Ban Meta Smart Glasses (Generation 2).

The Ray-Ban Meta glasses expose Meta AI as a first-class feature via the
``Hey Meta`` wake word.  This module lets you build custom AI-powered
experiences on top of that foundation by calling the Meta AI API directly.

Typical usage::

    from metaglasses import MetaAIClient

    client = MetaAIClient(api_key="YOUR_API_KEY")
    response = client.chat("What's the weather like in Paris today?")
    print(response["text"])
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class MetaAIError(Exception):
    """Raised when the Meta AI API returns an error response."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Message:
    """A single message in a conversation."""
    role: str                    # "user" | "assistant" | "system"
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AIResponse:
    """Response from the Meta AI API."""
    text: str
    model: str
    usage: Dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"


# ---------------------------------------------------------------------------
# MetaAIClient
# ---------------------------------------------------------------------------

class MetaAIClient:
    """Client for the Meta AI API.

    Parameters
    ----------
    api_key:
        Your Meta developer API key.  Generate one at
        https://developers.meta.com.
    model:
        Model identifier to use.  Defaults to ``"meta-llama-3-8b-instruct"``.
    base_url:
        Base URL for the Meta AI API endpoint.
    system_prompt:
        Optional system-level instruction prepended to every conversation.
    """

    DEFAULT_MODEL = "meta-llama-3-8b-instruct"
    DEFAULT_BASE_URL = "https://api.meta.ai/v1"

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        system_prompt: Optional[str] = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key must not be empty.")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._history: List[Message] = []
        if system_prompt:
            self._history.append(Message(role="system", content=system_prompt))

    # ------------------------------------------------------------------
    # One-shot query
    # ------------------------------------------------------------------

    def chat(self, user_message: str) -> AIResponse:
        """Send *user_message* and return the assistant's reply.

        Conversation history is maintained automatically so that follow-up
        questions work naturally.

        Parameters
        ----------
        user_message:
            The text the user wants to send to Meta AI.

        Returns
        -------
        AIResponse
            An :class:`AIResponse` with the following fields:

            * ``text`` — the assistant's reply as a string
            * ``model`` — model identifier used for this response
            * ``usage`` — token-usage dict (``prompt_tokens``, ``completion_tokens``, ``total_tokens``)
            * ``finish_reason`` — ``"stop"``, ``"length"``, etc.

        Raises
        ------
        MetaAIError
            If the API returns an error.
        """
        self._history.append(Message(role="user", content=user_message))
        payload = self._build_payload(stream=False)
        raw = self._post("/chat/completions", payload)
        response = self._parse_response(raw)
        self._history.append(Message(role="assistant", content=response.text))
        return response

    def stream(self, user_message: str) -> Iterator[str]:
        """Stream the assistant's reply token-by-token.

        Yields each text chunk as it arrives from the API.

        Parameters
        ----------
        user_message:
            The text the user wants to send.

        Yields
        ------
        str
            Successive text chunks from the streaming response.
        """
        self._history.append(Message(role="user", content=user_message))
        payload = self._build_payload(stream=True)
        accumulated = ""
        for chunk in self._stream_post("/chat/completions", payload):
            accumulated += chunk
            yield chunk
        self._history.append(Message(role="assistant", content=accumulated))

    # ------------------------------------------------------------------
    # Vision (describe a photo from the glasses)
    # ------------------------------------------------------------------

    def describe_image(self, image_bytes: bytes, prompt: str = "Describe what you see.") -> AIResponse:
        """Send an image captured by the glasses to Meta AI for description.

        Parameters
        ----------
        image_bytes:
            Raw JPEG bytes from the glasses camera.
        prompt:
            Text instruction to accompany the image.

        Returns
        -------
        AIResponse
        """
        import base64
        b64 = base64.b64encode(image_bytes).decode()
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    ],
                }
            ],
        }
        raw = self._post("/chat/completions", payload)
        return self._parse_response(raw)

    # ------------------------------------------------------------------
    # History management
    # ------------------------------------------------------------------

    def clear_history(self) -> None:
        """Clear the conversation history (keeps the system prompt, if any)."""
        self._history = [m for m in self._history if m.role == "system"]

    @property
    def history(self) -> List[Message]:
        """Read-only view of the current conversation history."""
        return list(self._history)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_payload(self, stream: bool) -> dict:
        return {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in self._history],
            "stream": stream,
        }

    def _post(self, path: str, payload: dict) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            raise MetaAIError(f"Meta AI API error {exc.code}: {body}", status_code=exc.code) from exc

    def _stream_post(self, path: str, payload: dict) -> Iterator[str]:
        url = f"{self.base_url}{path}"
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                for raw_line in resp:
                    line = raw_line.decode().strip()
                    if line.startswith("data: "):
                        chunk_json = line[6:]
                        if chunk_json == "[DONE]":
                            return
                        try:
                            chunk = json.loads(chunk_json)
                            text = chunk["choices"][0]["delta"].get("content", "")
                            if text:
                                yield text
                        except (KeyError, json.JSONDecodeError):
                            continue
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            raise MetaAIError(f"Meta AI API error {exc.code}: {body}", status_code=exc.code) from exc

    def _parse_response(self, raw: dict) -> AIResponse:
        try:
            text = raw["choices"][0]["message"]["content"]
            model = raw.get("model", self.model)
            usage = raw.get("usage", {})
            finish_reason = raw["choices"][0].get("finish_reason", "stop")
            return AIResponse(text=text, model=model, usage=usage, finish_reason=finish_reason)
        except (KeyError, IndexError) as exc:
            raise MetaAIError(f"Unexpected API response format: {raw}") from exc
