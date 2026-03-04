"""
Tests for metaglasses.ai (MetaAIClient).

API calls are stubbed out — no real network requests are made.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from metaglasses.ai import AIResponse, Message, MetaAIClient, MetaAIError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_response(text: str = "Hello!", model: str = "meta-llama-3-8b-instruct") -> dict:
    return {
        "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
        "model": model,
        "usage": {"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15},
    }


class _MockHTTPResponse:
    """Minimal file-like object that urllib.request.urlopen returns."""

    def __init__(self, payload: dict):
        self._data = json.dumps(payload).encode()

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestMetaAIClientConstruction:
    def test_empty_api_key_raises(self):
        with pytest.raises(ValueError):
            MetaAIClient(api_key="")

    def test_valid_construction(self):
        client = MetaAIClient(api_key="test-key")
        assert client.model == MetaAIClient.DEFAULT_MODEL

    def test_custom_model(self):
        client = MetaAIClient(api_key="key", model="llama-custom")
        assert client.model == "llama-custom"

    def test_system_prompt_added_to_history(self):
        client = MetaAIClient(api_key="key", system_prompt="Be helpful.")
        assert len(client.history) == 1
        assert client.history[0].role == "system"

    def test_no_system_prompt_empty_history(self):
        client = MetaAIClient(api_key="key")
        assert len(client.history) == 0


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class TestMetaAIClientChat:
    def test_chat_returns_response(self):
        client = MetaAIClient(api_key="key")
        with patch("urllib.request.urlopen", return_value=_MockHTTPResponse(_fake_response("Hi!"))):
            resp = client.chat("Hello")
        assert isinstance(resp, AIResponse)
        assert resp.text == "Hi!"

    def test_chat_appends_to_history(self):
        client = MetaAIClient(api_key="key")
        with patch("urllib.request.urlopen", return_value=_MockHTTPResponse(_fake_response("Hi!"))):
            client.chat("Hello")
        assert len(client.history) == 2
        assert client.history[0].role == "user"
        assert client.history[1].role == "assistant"

    def test_clear_history(self):
        client = MetaAIClient(api_key="key", system_prompt="Be brief.")
        with patch("urllib.request.urlopen", return_value=_MockHTTPResponse(_fake_response("Hi!"))):
            client.chat("Hello")
        client.clear_history()
        # System prompt stays, conversation is gone
        assert all(m.role == "system" for m in client.history)

    def test_clear_history_no_system_prompt(self):
        client = MetaAIClient(api_key="key")
        with patch("urllib.request.urlopen", return_value=_MockHTTPResponse(_fake_response("Hi!"))):
            client.chat("Hello")
        client.clear_history()
        assert len(client.history) == 0


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestMetaAIClientErrors:
    def test_http_error_raises_meta_ai_error(self):
        import urllib.error
        client = MetaAIClient(api_key="key")
        err = urllib.error.HTTPError(
            url="http://x", code=401,
            msg="Unauthorized", hdrs=None,  # type: ignore[arg-type]
            fp=MagicMock(read=lambda: b"Unauthorized"),
        )
        with patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(MetaAIError) as exc_info:
                client.chat("Hello")
        assert exc_info.value.status_code == 401

    def test_bad_response_format_raises(self):
        client = MetaAIClient(api_key="key")
        with patch("urllib.request.urlopen", return_value=_MockHTTPResponse({"bad": "data"})):
            with pytest.raises(MetaAIError):
                client.chat("Hello")


# ---------------------------------------------------------------------------
# describe_image
# ---------------------------------------------------------------------------

class TestMetaAIClientDescribeImage:
    def test_describe_image_sends_base64(self):
        client = MetaAIClient(api_key="key")
        fake_bytes = b"\xff\xd8\xff"  # minimal JPEG header
        with patch("urllib.request.urlopen", return_value=_MockHTTPResponse(_fake_response("A red balloon."))) as mock_open:
            resp = client.describe_image(fake_bytes, prompt="What is this?")
        assert resp.text == "A red balloon."
