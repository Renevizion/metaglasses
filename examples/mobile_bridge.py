"""
mobile_bridge.py — Run the metaglasses Python SDK as a bridge server.

This example shows how to use :class:`~metaglasses.bridge.MobileBridge`
to receive glasses events from your iOS or Android companion app and process
them with the full metaglasses SDK.

Architecture
------------
Your mobile app (iOS / Android) uses the official Meta Wearables Device
Access Toolkit (MWDAT) to pair with the glasses and receive events over BLE.
It then forwards those events to this Python process via simple HTTP POSTs.

    Glasses  ←BLE→  Mobile App (MWDAT)  ←HTTP→  This Python script
                                                   ↓
                                           VoiceCommandHandler
                                           MetaAIClient (cloud)
                                           AppRunner / Apps

Usage
-----
Start this script on your laptop or phone running Python:

    python examples/mobile_bridge.py

Then configure your mobile app to POST events to:

    http://<your-laptop-ip>:8765/event      ← glasses events
    http://<your-laptop-ip>:8765/media      ← captured photos/videos
    GET  http://<your-laptop-ip>:8765/response  ← poll for TTS replies

Mobile app quick-start (iOS Swift)
------------------------------------
After calling ``Wearables.shared.startRegistration()`` and pairing succeeds,
forward every event like this::

    func forwardEvent(_ event: [String: Any]) {
        guard let url = URL(string: "http://192.168.1.x:8765/event") else { return }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try? JSONSerialization.data(withJSONObject: event)
        URLSession.shared.dataTask(with: req).resume()
    }
"""

import os
import signal
import sys
import time

from metaglasses import Glasses, MetaAIClient, VoiceCommandHandler
from metaglasses.bridge import MobileBridge

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HOST = "0.0.0.0"   # Accept connections from the mobile app over Wi-Fi
PORT = 8765
API_KEY = os.environ.get("META_AI_API_KEY", "")

# ---------------------------------------------------------------------------
# Set up the glasses and bridge
# ---------------------------------------------------------------------------

glasses = Glasses(on_event=lambda e: print(f"[glasses event] {e}"))
bridge = MobileBridge(
    glasses,
    host=HOST,
    port=PORT,
    on_media=lambda data, meta: print(
        f"[media received] {len(data)} bytes, metadata={meta}"
    ),
)

# Start the HTTP server (background thread)
bridge.start()
print(f"Bridge server listening on {HOST}:{PORT}")

# Mark the glasses as connected via the mobile bridge
glasses.connect_via_bridge(bridge)
print(f"Glasses: {glasses}")

# ---------------------------------------------------------------------------
# Wire up voice commands
# ---------------------------------------------------------------------------

handler = VoiceCommandHandler(glasses, wake_word="hey meta")

@handler.command("take a photo")
def snap(ctx):
    media_id = glasses.take_photo()
    reply = f"Photo taken! ID: {media_id}"
    print(reply)
    bridge.send_response(reply)

@handler.command("start recording", pattern=r"start (recording|video)")
def rec_start(ctx):
    try:
        glasses.start_video()
        bridge.send_response("Recording started.")
    except RuntimeError as e:
        bridge.send_response(f"Error: {e}")

@handler.command("stop recording", pattern=r"stop (recording|video)")
def rec_stop(ctx):
    media_id = glasses.stop_video()
    reply = f"Recording saved. ID: {media_id}"
    print(reply)
    bridge.send_response(reply)

handler.start()
print("Voice command handler started. Waiting for events from mobile app…")

# ---------------------------------------------------------------------------
# Optional: wire up Meta AI
# ---------------------------------------------------------------------------

if API_KEY:
    ai = MetaAIClient(
        api_key=API_KEY,
        system_prompt=(
            "You are a helpful assistant running on smart glasses. "
            "Give concise answers of 1-2 sentences."
        ),
    )

    @handler.command("ask meta", pattern=r"ask(?:\s+meta)?[,\s]+(.+)")
    def ask_meta(ctx):
        question = ctx.get("matched_text", "")
        response = ai.chat(question)
        print(f"[AI] {response.text}")
        bridge.send_response(response.text)

    print("Meta AI connected.")
else:
    print(
        "Tip: set META_AI_API_KEY=your-key to enable AI voice responses.\n"
        "     Voice commands for photo, video, and events still work without it."
    )

# ---------------------------------------------------------------------------
# Keep running until interrupted
# ---------------------------------------------------------------------------

def _shutdown(sig, frame):
    print("\nShutting down…")
    handler.stop()
    glasses.disconnect()
    bridge.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, _shutdown)
signal.signal(signal.SIGTERM, _shutdown)

print("Ready. Press Ctrl+C to stop.")
while True:
    time.sleep(1)
