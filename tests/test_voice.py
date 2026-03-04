"""
Tests for metaglasses.voice (VoiceCommandHandler).
"""

import time

import pytest

from metaglasses.glasses import Glasses, GlassesNotConnectedError
from metaglasses.voice import VoiceCommandHandler


class TestVoiceCommandRegistration:
    def test_decorator_registers_command(self, connected_glasses):
        handler = VoiceCommandHandler(connected_glasses)
        calls = []

        @handler.command("take a photo")
        def cb(ctx):
            calls.append(ctx)

        assert len(handler._commands) == 1

    def test_register_method(self, connected_glasses):
        handler = VoiceCommandHandler(connected_glasses)
        calls = []
        handler.register("start recording", lambda ctx: calls.append(ctx))
        assert len(handler._commands) == 1

    def test_pattern_override(self, connected_glasses):
        handler = VoiceCommandHandler(connected_glasses)
        calls = []
        handler.register("video", lambda ctx: calls.append(ctx), pattern=r"(start|stop) (recording|video)")
        matched = handler.dispatch("start recording")
        assert matched
        assert len(calls) == 1


class TestVoiceCommandDispatch:
    def test_dispatch_matches_exact_phrase(self, connected_glasses):
        handler = VoiceCommandHandler(connected_glasses)
        calls = []
        handler.register("take a photo", lambda ctx: calls.append(ctx))

        matched = handler.dispatch("take a photo")
        assert matched
        assert len(calls) == 1

    def test_dispatch_case_insensitive(self, connected_glasses):
        handler = VoiceCommandHandler(connected_glasses)
        calls = []
        handler.register("take a photo", lambda ctx: calls.append(ctx))

        assert handler.dispatch("TAKE A PHOTO")
        assert len(calls) == 1

    def test_dispatch_strips_wake_word(self, connected_glasses):
        handler = VoiceCommandHandler(connected_glasses, wake_word="hey meta")
        calls = []
        handler.register("take a photo", lambda ctx: calls.append(ctx))

        matched = handler.dispatch("hey meta, take a photo")
        assert matched
        assert len(calls) == 1

    def test_dispatch_no_match_returns_false(self, connected_glasses):
        handler = VoiceCommandHandler(connected_glasses)
        handler.register("take a photo", lambda ctx: None)

        assert not handler.dispatch("start recording")

    def test_dispatch_multiple_matches(self, connected_glasses):
        handler = VoiceCommandHandler(connected_glasses)
        calls = []
        handler.register("photo", lambda ctx: calls.append("A"))
        handler.register("photo", lambda ctx: calls.append("B"))

        handler.dispatch("take a photo now")
        assert len(calls) == 2

    def test_ctx_contains_utterance(self, connected_glasses):
        handler = VoiceCommandHandler(connected_glasses)
        received = []
        handler.register("hello", lambda ctx: received.append(ctx))
        handler.dispatch("hello world")
        assert received[0]["utterance"] == "hello world"


class TestVoiceCommandLifecycle:
    def test_start_requires_connection(self):
        g = Glasses()
        handler = VoiceCommandHandler(g)
        with pytest.raises(GlassesNotConnectedError):
            handler.start()

    def test_start_stop(self, connected_glasses):
        handler = VoiceCommandHandler(connected_glasses)
        handler.start()
        assert handler.is_running
        handler.stop()
        assert not handler.is_running

    def test_double_start_raises(self, connected_glasses):
        handler = VoiceCommandHandler(connected_glasses)
        handler.start()
        try:
            with pytest.raises(RuntimeError):
                handler.start()
        finally:
            handler.stop()

    def test_empty_wake_word_matches_any(self, connected_glasses):
        handler = VoiceCommandHandler(connected_glasses, wake_word="")
        calls = []
        handler.register("hello", lambda ctx: calls.append(ctx))
        handler.dispatch("hello there")
        assert len(calls) == 1
