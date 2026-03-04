"""
Example: Register custom voice commands.

Run with:
    python examples/voice_commands.py
"""

import time

from metaglasses import Glasses, VoiceCommandHandler, GlassesConnectionError


def main():
    glasses = Glasses()
    try:
        glasses.connect()
    except GlassesConnectionError as exc:
        print(f"[ERROR] {exc}")
        return

    handler = VoiceCommandHandler(glasses, wake_word="hey meta")

    @handler.command("take a photo")
    def on_photo(ctx):
        media_id = glasses.take_photo()
        print(f"  [photo] Captured! media_id={media_id}")

    @handler.command("start recording", pattern=r"start (recording|video)")
    def on_start_rec(ctx):
        glasses.start_video()
        print("  [video] Recording started.")

    @handler.command("stop recording", pattern=r"stop (recording|video)")
    def on_stop_rec(ctx):
        media_id = glasses.stop_video()
        print(f"  [video] Recording stopped. media_id={media_id}")

    handler.start()
    print("Listening for voice commands (say 'hey meta, take a photo', etc.)")
    print("Press Ctrl-C to quit.\n")

    # Simulate a recognised utterance for demonstration purposes
    print("--- Simulating: 'hey meta, take a photo' ---")
    handler.dispatch("hey meta, take a photo")

    print("--- Simulating: 'hey meta, start recording' ---")
    handler.dispatch("hey meta, start recording")

    print("--- Simulating: 'hey meta, stop video' ---")
    handler.dispatch("hey meta, stop video")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    handler.stop()
    glasses.disconnect()
    print("Goodbye!")


if __name__ == "__main__":
    main()
