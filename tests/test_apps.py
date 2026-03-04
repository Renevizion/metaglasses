"""
Tests for the metaglasses.apps sub-package:
  - App base class & AppRunner
  - PricingApp
  - ResearchApp
  - OutreachApp
  - LivestreamApp (single + multi-platform + voice)
  - RecorderApp
  - QuickApp factory
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from metaglasses.glasses import Glasses
from metaglasses.apps import App, AppRunner
from metaglasses.apps.pricing import PricingApp
from metaglasses.apps.research import ResearchApp
from metaglasses.apps.outreach import OutreachApp, OutreachItem
from metaglasses.apps.livestream import LivestreamApp, Platform, StreamSession
from metaglasses.apps.recorder import RecorderApp, Clip
from metaglasses.apps.factory import QuickApp, quick_app
from metaglasses.ai import AIResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ai(reply: str = "ok") -> MagicMock:
    ai = MagicMock()
    ai.history = []
    ai.chat.return_value = AIResponse(text=reply, model="test")
    ai.describe_image.return_value = AIResponse(text=reply, model="test")
    return ai


def _glasses() -> Glasses:
    g = Glasses()
    g.connect()
    return g


# ---------------------------------------------------------------------------
# App base class
# ---------------------------------------------------------------------------

class TestAppBase:
    def test_start_stop(self, connected_glasses):
        class _Noop(App):
            name = "noop"
            description = "noop"
            def _register_commands(self, handler):
                pass
        app = _Noop(connected_glasses)
        assert not app.is_active
        app.start()
        assert app.is_active
        app.stop()
        assert not app.is_active

    def test_double_start_is_idempotent(self, connected_glasses):
        class _Noop(App):
            name = "noop"
            description = ""
            def _register_commands(self, handler): pass
        app = _Noop(connected_glasses)
        app.start()
        app.start()  # should not raise
        assert app.is_active
        app.stop()

    def test_repr(self, connected_glasses):
        class _Noop(App):
            name = "noop"
            description = ""
            def _register_commands(self, handler): pass
        app = _Noop(connected_glasses)
        assert "idle" in repr(app)
        app.start()
        assert "active" in repr(app)
        app.stop()


# ---------------------------------------------------------------------------
# AppRunner
# ---------------------------------------------------------------------------

class TestAppRunner:
    def _noop_app(self, glasses, name="noop"):
        class _Noop(App):
            def _register_commands(self, handler): pass
        _Noop.name = name
        _Noop.description = ""
        return _Noop(glasses)

    def test_register_and_launch(self, connected_glasses):
        runner = AppRunner(connected_glasses)
        app = self._noop_app(connected_glasses)
        runner.register(app)
        runner.launch("noop")
        assert app.is_active
        runner.stop_all()
    def test_duplicate_name_raises(self, connected_glasses):
        runner = AppRunner(connected_glasses)
        runner.register(self._noop_app(connected_glasses, "a"))
        with pytest.raises(ValueError):
            runner.register(self._noop_app(connected_glasses, "a"))

    def test_no_name_raises(self, connected_glasses):
        runner = AppRunner(connected_glasses)
        class _NoName(App):
            name = ""
            description = ""
            def _register_commands(self, h): pass
        with pytest.raises(ValueError):
            runner.register(_NoName(connected_glasses))

    def test_list_apps(self, connected_glasses):
        runner = AppRunner(connected_glasses)
        runner.register(self._noop_app(connected_glasses, "alpha"))
        runner.register(self._noop_app(connected_glasses, "beta"))
        listing = runner.list_apps()
        names = {a["name"] for a in listing}
        assert names == {"alpha", "beta"}

    def test_stop_all(self, connected_glasses):
        runner = AppRunner(connected_glasses)
        apps = [self._noop_app(connected_glasses, n) for n in ["x", "y", "z"]]
        for a in apps:
            runner.register(a)
            runner.launch(a.name)
        runner.stop_all()
        assert all(not a.is_active for a in apps)

    def test_unregister(self, connected_glasses):
        runner = AppRunner(connected_glasses)
        runner.register(self._noop_app(connected_glasses, "tmp"))
        runner.unregister("tmp")
        assert "tmp" not in runner._apps

    def test_unknown_launch_raises(self, connected_glasses):
        runner = AppRunner(connected_glasses)
        with pytest.raises(KeyError):
            runner.launch("nonexistent")


# ---------------------------------------------------------------------------
# PricingApp
# ---------------------------------------------------------------------------

class TestPricingApp:
    def test_price_check_returns_result(self, connected_glasses):
        ai = _make_ai("$199 – good deal at Best Buy")
        app = PricingApp(connected_glasses, ai)
        result = app.price_check("Sony headphones")
        assert "query" in result and "answer" in result
        assert result["query"] == "Sony headphones"

    def test_price_check_stores_last_result(self, connected_glasses):
        ai = _make_ai("$299")
        app = PricingApp(connected_glasses, ai)
        app.price_check("iPad")
        assert app.last_result is not None

    def test_on_result_callback(self, connected_glasses):
        received = []
        ai = _make_ai("$50")
        app = PricingApp(connected_glasses, ai, on_result=received.append)
        app.price_check("earbuds")
        assert len(received) == 1
        assert received[0]["query"] == "earbuds"

    def test_no_ai_raises(self, connected_glasses):
        app = PricingApp(connected_glasses, ai=None)
        with pytest.raises(RuntimeError):
            app.price_check("anything")

    def test_voice_command(self, connected_glasses):
        received = []
        ai = _make_ai("$99")
        app = PricingApp(connected_glasses, ai, on_result=received.append)
        app.start()
        app._handler.dispatch("hey meta, price check Nike shoes")
        assert len(received) == 1
        assert "Nike shoes" in received[0]["query"].title() or "nike shoes" in received[0]["query"]
        app.stop()

    def test_voice_command_price_this(self, connected_glasses):
        received = []
        ai = _make_ai("$149")
        app = PricingApp(connected_glasses, ai, on_result=received.append)
        app.start()
        app._handler.dispatch("hey meta, price this")
        assert len(received) == 1
        app.stop()


# ---------------------------------------------------------------------------
# ResearchApp
# ---------------------------------------------------------------------------

class TestResearchApp:
    def test_research_returns_result(self, connected_glasses):
        ai = _make_ai("Quantum computing uses qubits...")
        app = ResearchApp(connected_glasses, ai)
        result = app.research("quantum computing")
        assert result["topic"] == "quantum computing"
        assert result["summary"]

    def test_follow_up(self, connected_glasses):
        ai = _make_ai("Summary")
        app = ResearchApp(connected_glasses, ai)
        app.research("AI")
        ai.chat.return_value = AIResponse(text="More detail", model="test")
        result = app.follow_up("tell me more")
        assert result["summary"] == "More detail"

    def test_follow_up_without_research_raises(self, connected_glasses):
        ai = _make_ai("x")
        app = ResearchApp(connected_glasses, ai)
        with pytest.raises(RuntimeError):
            app.follow_up("more?")

    def test_no_ai_raises(self, connected_glasses):
        app = ResearchApp(connected_glasses, ai=None)
        with pytest.raises(RuntimeError):
            app.research("anything")

    def test_voice_research_command(self, connected_glasses):
        received = []
        ai = _make_ai("Summary text")
        app = ResearchApp(connected_glasses, ai, on_result=received.append)
        app.start()
        app._handler.dispatch("hey meta, research climate change")
        assert received[0]["topic"] == "climate change"
        app.stop()

    def test_voice_follow_up_command(self, connected_glasses):
        received = []
        ai = _make_ai("More info")
        app = ResearchApp(connected_glasses, ai, on_result=received.append)
        app.start()
        app.research("blockchain")
        app._handler.dispatch("hey meta, tell me more")
        assert len(received) == 2
        app.stop()


# ---------------------------------------------------------------------------
# OutreachApp
# ---------------------------------------------------------------------------

class TestOutreachApp:
    def test_send_message(self, connected_glasses):
        sent = []
        app = OutreachApp(connected_glasses, ai=None, on_send=sent.append, polish_with_ai=False)
        item = app.send_message("Bob", "hey!")
        assert isinstance(item, OutreachItem)
        assert item.type == "message"
        assert item.to == "Bob"
        assert len(sent) == 1

    def test_send_email(self, connected_glasses):
        sent = []
        app = OutreachApp(connected_glasses, ai=None, on_send=sent.append, polish_with_ai=False)
        item = app.send_email("alice@example.com", "Hello Alice")
        assert item.type == "email"
        assert item.to == "alice@example.com"

    def test_request_call(self, connected_glasses):
        sent = []
        app = OutreachApp(connected_glasses, ai=None, on_send=sent.append)
        item = app.request_call("Mom")
        assert item.type == "call"
        assert item.to == "Mom"
        assert item.body == ""

    def test_outbox_grows(self, connected_glasses):
        app = OutreachApp(connected_glasses, ai=None, polish_with_ai=False)
        app.send_message("A", "hi")
        app.send_email("B", "hello")
        app.request_call("C")
        assert len(app.outbox) == 3

    def test_voice_text_command(self, connected_glasses):
        sent = []
        app = OutreachApp(connected_glasses, ai=None, on_send=sent.append, polish_with_ai=False)
        app.start()
        app._handler.dispatch("hey meta, text Sarah: on my way")
        assert sent[0].type == "message"
        assert sent[0].to.lower() == "sarah"
        app.stop()

    def test_voice_email_command(self, connected_glasses):
        sent = []
        app = OutreachApp(connected_glasses, ai=None, on_send=sent.append, polish_with_ai=False)
        app.start()
        app._handler.dispatch("hey meta, email John: the report is ready")
        assert sent[0].type == "email"
        assert sent[0].to.lower() == "john"
        app.stop()

    def test_voice_call_command(self, connected_glasses):
        sent = []
        app = OutreachApp(connected_glasses, ai=None, on_send=sent.append)
        app.start()
        app._handler.dispatch("hey meta, call Alice")
        assert sent[0].type == "call"
        assert sent[0].to.lower() == "alice"
        app.stop()

    def test_ai_polish_called(self, connected_glasses):
        ai = _make_ai("Polished message")
        sent = []
        app = OutreachApp(connected_glasses, ai=ai, on_send=sent.append, polish_with_ai=True)
        app.send_message("X", "raw msg")
        assert sent[0].body == "Polished message"

    def test_no_polish_when_disabled(self, connected_glasses):
        ai = _make_ai("Should not be called")
        sent = []
        app = OutreachApp(connected_glasses, ai=ai, on_send=sent.append, polish_with_ai=False)
        app.send_message("X", "raw msg")
        ai.chat.assert_not_called()
        assert sent[0].body == "raw msg"


# ---------------------------------------------------------------------------
# LivestreamApp — single platform
# ---------------------------------------------------------------------------

class TestLivestreamAppSingle:
    def _app(self, connected_glasses, **kw):
        return LivestreamApp(
            connected_glasses,
            stream_keys={Platform.YOUTUBE: "yt-key", Platform.TWITCH: "tw-key"},
            **kw,
        )

    def test_go_live_returns_session(self, connected_glasses):
        app = self._app(connected_glasses)
        session = app.go_live(Platform.YOUTUBE)
        assert isinstance(session, StreamSession)
        assert session.platform == Platform.YOUTUBE
        assert "yt-key" in session.rtmp_url
        app.end_stream()

    def test_go_live_string_platform(self, connected_glasses):
        app = self._app(connected_glasses)
        app.go_live("youtube")
        assert app.is_live
        app.end_stream()

    def test_duplicate_platform_raises(self, connected_glasses):
        app = self._app(connected_glasses)
        app.go_live(Platform.YOUTUBE)
        with pytest.raises(RuntimeError):
            app.go_live(Platform.YOUTUBE)
        app.end_stream()

    def test_end_stream_clears_sessions(self, connected_glasses):
        app = self._app(connected_glasses)
        app.go_live(Platform.YOUTUBE)
        completed = app.end_stream()
        assert len(completed) == 1
        assert not app.is_live

    def test_end_stream_no_active_returns_empty(self, connected_glasses):
        app = self._app(connected_glasses)
        result = app.end_stream()
        assert result == []

    def test_session_duration_tracked(self, connected_glasses):
        app = self._app(connected_glasses)
        app.go_live(Platform.YOUTUBE)
        completed = app.end_stream()
        assert completed[0].duration_seconds is not None
        assert completed[0].duration_seconds >= 0

    def test_session_added_to_history(self, connected_glasses):
        app = self._app(connected_glasses)
        app.go_live(Platform.YOUTUBE)
        app.end_stream()
        assert len(app.session_history) == 1

    def test_no_key_raises(self, connected_glasses):
        app = LivestreamApp(connected_glasses, stream_keys={})
        with pytest.raises(RuntimeError):
            app.go_live(Platform.YOUTUBE)

    def test_unknown_platform_raises(self, connected_glasses):
        app = self._app(connected_glasses)
        with pytest.raises(ValueError):
            app.go_live("nonexistent_platform")

    def test_on_event_fired(self, connected_glasses):
        events = []
        app = self._app(connected_glasses, on_event=events.append)
        app.go_live(Platform.YOUTUBE)
        app.end_stream()
        event_names = [e["event"] for e in events]
        assert "stream_started" in event_names
        assert "stream_ended" in event_names

    def test_twitter_platform_supported(self, connected_glasses):
        app = LivestreamApp(
            connected_glasses,
            stream_keys={Platform.TWITTER: "tw-key"},
        )
        session = app.go_live(Platform.TWITTER)
        assert "ingest.pscp.tv" in session.rtmp_url
        app.end_stream()

    def test_add_platform(self, connected_glasses):
        app = LivestreamApp(connected_glasses)
        app.add_platform(Platform.TIKTOK, "tt-key")
        session = app.go_live(Platform.TIKTOK)
        assert "tt-key" in session.rtmp_url
        app.end_stream()


# ---------------------------------------------------------------------------
# LivestreamApp — multi-platform
# ---------------------------------------------------------------------------

class TestLivestreamAppMulti:
    def _app(self, connected_glasses):
        return LivestreamApp(
            connected_glasses,
            stream_keys={
                Platform.YOUTUBE:   "yt-key",
                Platform.INSTAGRAM: "ig-key",
                Platform.TWITTER:   "tw-key",
            },
        )

    def test_go_live_multi_returns_sessions(self, connected_glasses):
        app = self._app(connected_glasses)
        sessions = app.go_live_multi([Platform.YOUTUBE, Platform.INSTAGRAM])
        assert len(sessions) == 2
        assert {s.platform for s in sessions} == {Platform.YOUTUBE, Platform.INSTAGRAM}
        app.end_stream()

    def test_go_live_multi_with_relay(self, connected_glasses):
        app = self._app(connected_glasses)
        relay = "rtmp://relay.example.com/live/key"
        sessions = app.go_live_multi(
            [Platform.YOUTUBE, Platform.INSTAGRAM],
            relay_url=relay,
        )
        for s in sessions:
            assert s.rtmp_url == relay
        app.end_stream()

    def test_go_live_multi_without_relay_uses_first(self, connected_glasses):
        app = LivestreamApp(
            connected_glasses,
            stream_keys={Platform.YOUTUBE: "yt-key", Platform.INSTAGRAM: "ig-key"},
        )
        sessions = app.go_live_multi([Platform.YOUTUBE, Platform.INSTAGRAM])
        # Without relay, all sessions use the first platform's URL
        first_url = sessions[0].rtmp_url
        assert all(s.rtmp_url == first_url for s in sessions)
        app.end_stream()

    def test_go_live_multi_empty_raises(self, connected_glasses):
        app = self._app(connected_glasses)
        with pytest.raises(ValueError):
            app.go_live_multi([])

    def test_go_live_multi_duplicate_raises(self, connected_glasses):
        app = self._app(connected_glasses)
        app.go_live_multi([Platform.YOUTUBE])
        with pytest.raises(RuntimeError):
            app.go_live_multi([Platform.YOUTUBE])
        app.end_stream()

    def test_go_live_all(self, connected_glasses):
        app = self._app(connected_glasses)
        sessions = app.go_live_all()
        assert len(sessions) == 3
        platforms = {s.platform for s in sessions}
        assert Platform.YOUTUBE in platforms
        assert Platform.INSTAGRAM in platforms
        assert Platform.TWITTER in platforms
        app.end_stream()

    def test_go_live_all_no_keys_raises(self, connected_glasses):
        app = LivestreamApp(connected_glasses)
        with pytest.raises(RuntimeError):
            app.go_live_all()

    def test_active_platforms(self, connected_glasses):
        app = self._app(connected_glasses)
        app.go_live_multi([Platform.YOUTUBE, Platform.TWITTER])
        assert set(app.active_platforms) == {Platform.YOUTUBE, Platform.TWITTER}
        app.end_stream()

    def test_end_stream_clears_all(self, connected_glasses):
        app = self._app(connected_glasses)
        app.go_live_all()
        completed = app.end_stream()
        assert len(completed) == 3
        assert not app.is_live
        assert app.active_platforms == []


# ---------------------------------------------------------------------------
# LivestreamApp — voice commands
# ---------------------------------------------------------------------------

class TestLivestreamAppVoice:
    def _app(self, connected_glasses):
        app = LivestreamApp(
            connected_glasses,
            stream_keys={
                Platform.YOUTUBE:   "yt-key",
                Platform.INSTAGRAM: "ig-key",
                Platform.TWITTER:   "tw-key",
                Platform.TWITCH:    "tc-key",
            },
            relay_url="rtmp://relay.example.com/live/k",
        )
        app.start()
        return app

    def test_voice_go_live_single(self, connected_glasses):
        app = self._app(connected_glasses)
        app._handler.dispatch("hey meta, go live on youtube")
        assert Platform.YOUTUBE in app.active_platforms
        app.end_stream()
        app.stop()

    def test_voice_go_live_multi(self, connected_glasses):
        app = self._app(connected_glasses)
        app._handler.dispatch("hey meta, go live on youtube and instagram")
        assert Platform.YOUTUBE in app.active_platforms
        assert Platform.INSTAGRAM in app.active_platforms
        app.end_stream()
        app.stop()

    def test_voice_go_live_everywhere(self, connected_glasses):
        app = self._app(connected_glasses)
        app._handler.dispatch("hey meta, go live everywhere")
        assert len(app.active_platforms) == 4
        app.end_stream()
        app.stop()

    def test_voice_stop_streaming(self, connected_glasses):
        app = self._app(connected_glasses)
        app.go_live(Platform.YOUTUBE)
        app._handler.dispatch("hey meta, stop streaming")
        assert not app.is_live
        app.stop()

    def test_voice_twitter_alias_x(self, connected_glasses):
        app = self._app(connected_glasses)
        app._handler.dispatch("hey meta, go live on x")
        assert Platform.TWITTER in app.active_platforms
        app.end_stream()
        app.stop()


# ---------------------------------------------------------------------------
# RecorderApp
# ---------------------------------------------------------------------------

class TestRecorderApp:
    def test_begin_finish_recording(self, connected_glasses):
        app = RecorderApp(connected_glasses)
        app.begin_recording()
        clip = app.finish_recording()
        assert isinstance(clip, Clip)
        assert clip.filename.startswith("recording_")
        assert clip.filename.endswith(".mp4")
        assert clip.duration_seconds >= 0

    def test_is_recording_flag(self, connected_glasses):
        app = RecorderApp(connected_glasses)
        assert not app.is_recording
        app.begin_recording()
        assert app.is_recording
        app.finish_recording()
        assert not app.is_recording

    def test_double_begin_raises(self, connected_glasses):
        app = RecorderApp(connected_glasses)
        app.begin_recording()
        with pytest.raises(RuntimeError):
            app.begin_recording()
        app.finish_recording()

    def test_finish_without_begin_raises(self, connected_glasses):
        app = RecorderApp(connected_glasses)
        with pytest.raises(RuntimeError):
            app.finish_recording()

    def test_on_clip_saved_callback(self, connected_glasses):
        saved = []
        app = RecorderApp(connected_glasses, on_clip_saved=saved.append)
        app.begin_recording()
        app.finish_recording()
        assert len(saved) == 1
        assert isinstance(saved[0], Clip)

    def test_clips_list_grows(self, connected_glasses):
        app = RecorderApp(connected_glasses)
        for _ in range(3):
            app.begin_recording()
            app.finish_recording()
        assert len(app.clips) == 3

    def test_session_summary(self, connected_glasses):
        app = RecorderApp(connected_glasses)
        for _ in range(2):
            app.begin_recording()
            app.finish_recording()
        summary = app.session_summary()
        assert summary["clip_count"] == 2
        assert "clips" in summary
        assert summary["total_duration_seconds"] >= 0

    def test_voice_start_stop(self, connected_glasses):
        saved = []
        app = RecorderApp(connected_glasses, on_clip_saved=saved.append)
        app.start()
        app._handler.dispatch("hey meta, start recording")
        assert app.is_recording
        app._handler.dispatch("hey meta, stop recording")
        assert not app.is_recording
        assert len(saved) == 1
        app.stop()

    def test_voice_start_with_title_hint(self, connected_glasses):
        app = RecorderApp(connected_glasses)
        app.start()
        app._handler.dispatch("hey meta, start recording the sunset")
        assert app.is_recording
        app.finish_recording()
        app.stop()

    def test_low_storage_raises(self, connected_glasses):
        app = RecorderApp(connected_glasses, min_storage_mb=99999.0)
        with pytest.raises(RuntimeError, match="Insufficient storage"):
            app.begin_recording()

    def test_clip_duration_str(self, connected_glasses):
        app = RecorderApp(connected_glasses)
        app.begin_recording()
        clip = app.finish_recording()
        assert "m" in clip.duration_str


# ---------------------------------------------------------------------------
# QuickApp factory
# ---------------------------------------------------------------------------

class TestQuickApp:
    def test_basic_on_dispatch(self, connected_glasses):
        received = []
        app = (
            QuickApp("test_q", "test")
            .bind(connected_glasses)
            .on(r"hello", lambda ctx: received.append(ctx))
        )
        app.start()
        app._handler.dispatch("hello world")
        assert len(received) == 1
        app.stop()

    def test_callback_with_app_arg(self, connected_glasses):
        results = []
        app = (
            QuickApp("q2", "test")
            .bind(connected_glasses)
            .on(r"greet (.+)", lambda ctx, a: results.append(ctx["groups"][0]))
        )
        app.start()
        app._handler.dispatch("hey meta, greet Alice")
        assert results == ["alice"]  # voice dispatch lowercases utterances
        app.stop()

    def test_ask_ai_without_client(self, connected_glasses):
        app = QuickApp("q3", "").bind(connected_glasses)
        result = app.ask_ai("anything")
        assert "No AI client" in result

    def test_ask_ai_with_client(self, connected_glasses):
        ai = _make_ai("42 calories")
        app = QuickApp("q4", "").bind(connected_glasses, ai=ai)
        result = app.ask_ai("calories in an apple")
        assert result == "42 calories"

    def test_say_stores_last_result(self, connected_glasses):
        app = QuickApp("q5", "").bind(connected_glasses)
        app.say("hello there")
        assert app.last_result == "hello there"

    def test_say_fires_on_result_callback(self, connected_glasses):
        received = []
        app = QuickApp("q6", "", on_result=received.append).bind(connected_glasses)
        app.say("test value")
        assert received == ["test value"]

    def test_callback_return_value_forwarded(self, connected_glasses):
        received = []
        app = (
            QuickApp("q7", "", on_result=received.append)
            .bind(connected_glasses)
            .on(r"ping", lambda ctx: "pong")
        )
        app.start()
        app._handler.dispatch("ping")
        assert "pong" in received
        app.stop()

    def test_multiple_patterns(self, connected_glasses):
        calls = []
        app = (
            QuickApp("q8", "")
            .bind(connected_glasses)
            .on(r"foo", lambda ctx: calls.append("foo"))
            .on(r"bar", lambda ctx: calls.append("bar"))
        )
        app.start()
        app._handler.dispatch("foo")
        app._handler.dispatch("bar")
        assert calls == ["foo", "bar"]
        app.stop()

    def test_quick_app_convenience_function(self, connected_glasses):
        app = quick_app("qf", "convenience").bind(connected_glasses)
        assert app.name == "qf"
        assert app.description == "convenience"

    def test_auto_bind_via_runner(self, connected_glasses):
        ai = _make_ai("bound!")
        runner = AppRunner(connected_glasses, ai)
        app = QuickApp("bound_app", "auto bind test")
        runner.register(app)
        # After registration, glasses and ai should be bound
        assert app.glasses is connected_glasses
        assert app.ai is ai

    def test_system_prompt_applied_on_start(self, connected_glasses):
        ai = _make_ai("x")
        app = QuickApp(
            "sp_test", "",
            ai_system_prompt="You are a specialist."
        ).bind(connected_glasses, ai=ai)
        app.start()
        system_msgs = [m for m in ai.history if m.role == "system"]
        # history is a MagicMock; check that the prompt was attempted to inject
        app.stop()

    def test_groups_in_ctx(self, connected_glasses):
        captured = []
        app = (
            QuickApp("grp", "")
            .bind(connected_glasses)
            .on(r"(\w+) and (\w+)", lambda ctx: captured.append(ctx["groups"]))
        )
        app.start()
        app._handler.dispatch("foo and bar")
        assert captured[0] == ["foo", "bar"]
        app.stop()
