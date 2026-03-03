"""
Example: Capture a photo and download it to your computer.

Run with:
    python examples/photo_capture.py
"""

import tempfile

from metaglasses import Glasses, MediaManager, GlassesConnectionError


def main():
    glasses = Glasses()
    try:
        glasses.connect()
    except GlassesConnectionError as exc:
        print(f"[ERROR] Could not connect: {exc}")
        return

    print("Connected. Taking a photo…")

    # Capture
    media_id = glasses.take_photo()
    print(f"  Captured media ID: {media_id}")

    # List and download
    mgr = MediaManager(glasses)
    photos = mgr.list_photos()
    print(f"  Photos on device : {len(photos)}")

    dest = tempfile.mkdtemp(prefix="meta_glasses_")
    downloaded = mgr.download_all(dest_dir=dest)
    print(f"  Downloaded {len(downloaded)} file(s) to: {dest}")

    glasses.disconnect()
    print("Done.")


if __name__ == "__main__":
    main()
