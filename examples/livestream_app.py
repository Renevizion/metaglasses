"""
Example: Livestream to a single platform, multiple platforms, or everywhere at once.

    python examples/livestream_app.py
"""

from metaglasses import Glasses, GlassesConnectionError
from metaglasses.apps.livestream import LivestreamApp, Platform


def on_event(event: dict) -> None:
    print(f"  [event] {event}")


def main():
    glasses = Glasses()
    try:
        glasses.connect()
    except GlassesConnectionError as exc:
        print(f"[ERROR] {exc}")
        return

    # Configure stream keys for each platform you want to use
    app = LivestreamApp(
        glasses,
        stream_keys={
            Platform.YOUTUBE:   "yt-stream-key-xxxx",
            Platform.INSTAGRAM: "ig-stream-key-xxxx",
            Platform.TWITTER:   "tw-stream-key-xxxx",
            Platform.TWITCH:    "twitch-stream-key-xxxx",
        },
        # Optional: relay URL fans the single glasses output out to all platforms
        relay_url="rtmp://live.restream.io/live/re_YOUR_RELAY_KEY",
        on_event=on_event,
    )
    app.start()

    # ── Single platform ──────────────────────────────────────────────────────
    print("\n── Single platform: YouTube ──")
    session = app.go_live(Platform.YOUTUBE)
    print(f"  Live on {session.platform.value}  →  {session.rtmp_url}")
    sessions = app.end_stream()
    print(f"  Ended {len(sessions)} stream(s)")

    # ── Two platforms at once ────────────────────────────────────────────────
    print("\n── Two platforms: Instagram + Twitter ──")
    sessions = app.go_live_multi([Platform.INSTAGRAM, Platform.TWITTER])
    print(f"  Active platforms: {[s.platform.value for s in sessions]}")
    print(f"  Active via relay: {sessions[0].rtmp_url}")
    app.end_stream()

    # ── All configured platforms at once ────────────────────────────────────
    print("\n── All platforms at once ──")
    sessions = app.go_live_all()
    print(f"  Streaming to: {[s.platform.value for s in sessions]}")
    app.end_stream()

    # ── Voice command simulation ─────────────────────────────────────────────
    print("\n── Voice command simulation ──")
    print("  dispatching: 'hey meta, go live on youtube and instagram'")
    app._handler.dispatch("hey meta, go live on youtube and instagram")
    print(f"  Active platforms: {[p.value for p in app.active_platforms]}")
    app.end_stream()

    print("\n  dispatching: 'hey meta, go live everywhere'")
    app._handler.dispatch("hey meta, go live everywhere")
    print(f"  Active platforms: {[p.value for p in app.active_platforms]}")
    app._handler.dispatch("hey meta, stop streaming")

    app.stop()
    glasses.disconnect()
    print("\nDone.")


if __name__ == "__main__":
    main()
