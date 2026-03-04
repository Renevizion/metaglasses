"""
Example: Record clips with auto-naming and session summary.

    python examples/recorder_app.py
"""

import time

from metaglasses import Glasses, GlassesConnectionError
from metaglasses.apps.recorder import RecorderApp


def main():
    glasses = Glasses()
    try:
        glasses.connect()
    except GlassesConnectionError as exc:
        print(f"[ERROR] {exc}")
        return

    app = RecorderApp(
        glasses,
        on_clip_saved=lambda c: print(f"  🎬 Saved: {c.filename}  ({c.duration_str})"),
    )
    app.start()

    # Record two clips programmatically
    print("Recording clip 1…")
    app.begin_recording()
    time.sleep(0.05)   # simulate brief recording
    clip1 = app.finish_recording()
    print(f"  media_id: {clip1.media_id}")

    print("Recording clip 2…")
    app.begin_recording()
    time.sleep(0.05)
    clip2 = app.finish_recording()

    # Voice command simulations
    print("\nVoice command simulations:")
    print("  'hey meta, start recording street art'")
    app._handler.dispatch("hey meta, start recording street art")
    time.sleep(0.02)
    print("  'hey meta, stop recording'")
    app._handler.dispatch("hey meta, stop recording")

    # Session summary
    summary = app.session_summary()
    print(f"\nSession: {summary['clip_count']} clip(s)  "
          f"({summary['total_duration_seconds']:.2f}s total)")
    for clip in summary["clips"]:
        print(f"  {clip['filename']}  {clip['duration']}")

    app.stop()
    glasses.disconnect()
    print("Done.")


if __name__ == "__main__":
    main()
