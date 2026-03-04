# metaglasses

> **Python SDK for building apps on Ray-Ban Meta Smart Glasses (Generation 2)**

`metaglasses` gives you a clean, high-level Python interface to the Ray-Ban
Meta Smart Glasses.  It wraps the Bluetooth LE connection, media management,
voice-command dispatch, and the Meta AI API into simple building blocks — plus
a full **ready-to-run apps layer** that lets you spin up specialized apps as
fast as you can think of them.

---

## 🚀 How to launch this

> **This is a Python project — there is no `npm run dev`.**  
> You need Python 3.10+ installed, not Node.js.  
> Get Python at [python.org/downloads](https://python.org/downloads) if you don't have it.

```bash
# 1 — Clone and enter the repo
git clone https://github.com/Renevizion/metaglasses.git
cd metaglasses

# 2 — Install the SDK
pip install -e .

# 3 — Run any example (no glasses needed — works in simulation mode)
python examples/quick_apps.py

# To use real AI features, add your Meta AI API key:
META_AI_API_KEY=your-key-here python examples/research_app.py
```

**That's it for your computer.**  To get it running on your phone and talking to
your actual glasses, see the full guide:
👉 **[SETUP_GUIDE.md](SETUP_GUIDE.md)** — covers Android (Termux), API keys,
real Bluetooth wiring, and practical workarounds.

---

## Table of Contents

1. [🚀 How to launch this](#-how-to-launch-this)
2. [Hardware overview](#hardware-overview)
3. [**Real-world setup guide →**](SETUP_GUIDE.md)
4. [Apps — the fast way to build](#apps--the-fast-way-to-build)
   - [Built-in apps](#built-in-apps)
   - [Livestream to one or all platforms](#livestream-to-one-or-all-platforms)
   - [Rapid-fire custom apps with QuickApp](#rapid-fire-custom-apps-with-quickapp)
   - [AppRunner — manage many apps at once](#apprunner--manage-many-apps-at-once)
5. [Core SDK usage](#core-sdk-usage)
   - [Connecting to the glasses](#connecting-to-the-glasses)
   - [Capturing photos & videos](#capturing-photos--videos)
   - [Managing media](#managing-media)
   - [Voice commands](#voice-commands)
   - [Meta AI integration](#meta-ai-integration)
6. [Examples](#examples)
7. [Development setup](#development-setup)
8. [Architecture](#architecture)
9. [Roadmap](#roadmap)
10. [Contributing](#contributing)
11. [License](#license)

---

## Hardware overview

| Feature | Specification |
|---|---|
| Cameras | 12 MP ultra-wide (5-camera array) |
| Audio | Open-ear speakers + 5-mic array |
| Connectivity | Bluetooth 5.3 + Wi-Fi 6 (for media transfer) |
| Storage | Up to 32 GB internal |
| Battery | ~4 h continuous use / ~36 h standby |
| AI | Meta AI on-device + cloud via "Hey Meta" wake word |
| Companion app | Meta View (Android / iOS) |

---

## Apps — the fast way to build

The `metaglasses.apps` layer is designed for exactly this scenario:  
**rapid-fire app creation** — you have an idea, you want it running in minutes.

---

### Built-in apps

Five production-ready apps are included out of the box:

| App | Voice trigger | What it does |
|---|---|---|
| `PricingApp` | *"hey meta, price check AirPods"* | AI price lookup for products by name or camera |
| `ResearchApp` | *"hey meta, research quantum computing"* | AI research summary + follow-up questions |
| `OutreachApp` | *"hey meta, text Sarah: on my way"* | Voice-compose messages, emails & calls |
| `LivestreamApp` | *"hey meta, go live on youtube"* | RTMP streaming to any platform or all at once |
| `RecorderApp` | *"hey meta, start recording"* | Auto-named clip recording with session tracking |

```python
import os
from metaglasses import Glasses, MetaAIClient, AppRunner
from metaglasses import PricingApp, ResearchApp, OutreachApp, RecorderApp
from metaglasses.apps.livestream import LivestreamApp, Platform

glasses = Glasses()
glasses.connect()
ai = MetaAIClient(api_key=os.environ["META_AI_API_KEY"])

runner = AppRunner(glasses, ai)
runner.register(PricingApp(glasses, ai))
runner.register(ResearchApp(glasses, ai))
runner.register(OutreachApp(glasses, ai, on_send=lambda item: print(item)))
runner.register(RecorderApp(glasses, on_clip_saved=lambda c: print(c.filename)))

# Launch them all — they listen simultaneously
for app in runner.list_apps():
    runner.launch(app["name"])

# Now just talk to your glasses…
# "hey meta, price check Sony WH-1000XM5"
# "hey meta, research the history of jazz"
# "hey meta, text Alex: running late"
# "hey meta, start recording"

runner.stop_all()
glasses.disconnect()
```

---

### Livestream to one or all platforms

Stream to a **single platform**, **multiple simultaneously**, or **everywhere at once**.

```python
from metaglasses.apps.livestream import LivestreamApp, Platform

app = LivestreamApp(
    glasses,
    stream_keys={
        Platform.YOUTUBE:   "yt-stream-key",
        Platform.INSTAGRAM: "ig-stream-key",
        Platform.TWITTER:   "tw-stream-key",
        Platform.TWITCH:    "twitch-stream-key",
    },
    # Point all streams at a relay service so the glasses only push once
    relay_url="rtmp://live.restream.io/live/re_YOUR_KEY",
)
app.start()

# Single platform
app.go_live(Platform.YOUTUBE)
app.end_stream()

# Two platforms at once
app.go_live_multi([Platform.INSTAGRAM, Platform.TWITTER])
app.end_stream()

# All configured platforms at once
app.go_live_all()
app.end_stream()

# Voice: "hey meta, go live on youtube and instagram"
# Voice: "hey meta, go live everywhere"
# Voice: "hey meta, stop streaming"
```

**Supported platforms:** YouTube · Twitch · Instagram · Facebook · TikTok · Twitter/X · Custom RTMP

---

### Rapid-fire custom apps with QuickApp

Don't want to write a full sub-class?  Use `QuickApp` to define any
specialized app in **3-5 lines** with a fluent builder:

```python
from metaglasses import AppRunner
from metaglasses.apps.factory import QuickApp, quick_app

# Nutrition assistant
nutrition = (
    QuickApp("nutrition", "Calorie & nutrition info",
             ai_system_prompt="You are a certified nutritionist. Be concise.")
    .on(r"(?:calories|nutrition|how healthy is)\s+(.+)",
        lambda ctx, app: app.say(app.ask_ai(f"Nutrition info for: {ctx['groups'][0]}")))
    .on(r"is .+ healthy",
        lambda ctx, app: app.say(app.ask_ai(ctx["matched_text"])))
)

# Wine sommelier
wine = (
    QuickApp("wine", "Wine pairings and recommendations",
             ai_system_prompt="You are a world-class sommelier.")
    .on(r"(?:recommend|suggest|pair)\s+(?:a\s+)?wine\s*(.*)",
        lambda ctx, app: app.say(app.ask_ai(f"Recommend a wine for: {ctx['groups'][0]}")))
)

# Stock ticker
stocks = quick_app("stocks", "Stock price lookups",
                   ai_system_prompt="You are a financial assistant.") \
    .on(r"(?:price of|stock)\s+([A-Za-z]+)",
        lambda ctx, app: app.say(app.ask_ai(f"Price of {ctx['groups'][0]}")))

# Language translator
translator = (
    QuickApp("translator", "Instant translation")
    .on(r"translate (.+) to (\w+)",
        lambda ctx, app: app.say(app.ask_ai(
            f"Translate '{ctx['groups'][0]}' to {ctx['groups'][1]}")))
    .on(r"how do you say (.+) in (\w+)",
        lambda ctx, app: app.say(app.ask_ai(
            f"How do you say '{ctx['groups'][0]}' in {ctx['groups'][1]}?")))
)

# Register all at once — AppRunner auto-binds glasses & AI to QuickApps
runner = AppRunner(glasses, ai)
for a in [nutrition, wine, stocks, translator]:
    runner.register(a)
    runner.launch(a.name)

# All 4 specialized apps are now listening simultaneously
runner.stop_all()
```

Every `QuickApp` gets:
- **`app.ask_ai(prompt)`** — send a question to your AI client and get back a string
- **`app.say(text)`** — store result + fire your `on_result` callback (wire to TTS)
- **`ctx["groups"]`** — regex capture groups from the voice utterance
- **Auto-bind** via `AppRunner.register()` — no need to pass glasses/ai manually

---

### AppRunner — manage many apps at once

```python
runner = AppRunner(glasses, ai)

# Register apps
runner.register(my_app_1)
runner.register(my_app_2)

# Launch individual apps
runner.launch("pricing")
runner.launch("recorder")

# Inspect what's running
for info in runner.list_apps():
    print(f"{info['name']:12s} active={info['active']}")

# Stop everything
runner.stop_all()

# Remove an app
runner.unregister("pricing")
```

---

## Core SDK usage

### Connecting to the glasses

```python
from metaglasses import Glasses

glasses = Glasses()
glasses.connect()

print(glasses.status())
# {'connected': True, 'firmware': '2.0.0', 'battery_pct': 85, ...}

media_id = glasses.take_photo()
print(f"Captured photo: {media_id}")

glasses.disconnect()
```

---

## Installation

### From source (this repo)

```bash
git clone https://github.com/Renevizion/metaglasses.git
cd metaglasses
pip install -e .
```

### With optional extras

| Extra | What it adds | Command |
|---|---|---|
| `ble` | Real Bluetooth LE transport (`bleak`) | `pip install -e ".[ble]"` |
| `voice` | On-device speech recognition (`whisper`) | `pip install -e ".[voice]"` |
| `all` | Everything above | `pip install -e ".[all]"` |
| `dev` | Testing tools | `pip install -e ".[dev]"` |

> **Prerequisites for BLE on Linux:** run `sudo apt install libbluetooth-dev`
> and make sure your user is in the `bluetooth` group.

---

## Usage

### Connecting to the glasses

```python
from metaglasses import Glasses, GlassesConnectionError

def on_event(event: dict):
    print("Event:", event)

glasses = Glasses(
    device_name="Ray-Ban Meta",   # Bluetooth advertised name
    timeout=15.0,                 # seconds to wait for discovery
    auto_reconnect=True,
    on_event=on_event,
)

try:
    glasses.connect()
except GlassesConnectionError as e:
    print(f"Could not connect: {e}")
    raise SystemExit(1)

# Always disconnect when done
glasses.disconnect()
```

---

### Capturing photos & videos

```python
# Take a photo (returns a media ID)
media_id = glasses.take_photo()

# Record a video
glasses.start_video()
import time; time.sleep(10)
media_id = glasses.stop_video()

# Livestream over RTMP
glasses.start_livestream("rtmp://live.example.com/my-stream-key")
# ... broadcast ...
glasses.stop_livestream()
```

---

### Managing media

```python
from metaglasses import MediaManager

mgr = MediaManager(glasses)

# List everything on the glasses
photos = mgr.list_photos()
videos = mgr.list_videos()
print(mgr.count())  # {'photos': 42, 'videos': 7}

# Download all to a local folder
paths = mgr.download_all(dest_dir="~/Pictures/Glasses")

# Delete everything from the glasses after downloading
mgr.delete_all()
```

---

### Voice commands

```python
from metaglasses import VoiceCommandHandler

handler = VoiceCommandHandler(glasses, wake_word="hey meta")

@handler.command("take a photo")
def snap(ctx):
    media_id = glasses.take_photo()
    print(f"Photo taken! id={media_id}")

@handler.command("start recording", pattern=r"start (recording|video)")
def rec_start(ctx):
    glasses.start_video()

@handler.command("stop recording", pattern=r"stop (recording|video)")
def rec_stop(ctx):
    glasses.stop_video()

handler.start()

# You can also dispatch utterances manually (useful for testing)
handler.dispatch("hey meta, take a photo")

handler.stop()
```

You can also register commands without the decorator:

```python
handler.register("good morning", lambda ctx: print("Good morning!"))
```

---

### Meta AI integration

```python
import os
from metaglasses import MetaAIClient

client = MetaAIClient(
    api_key=os.environ["META_AI_API_KEY"],
    system_prompt="You are a helpful assistant on smart glasses. Be concise.",
)

# Single-turn query
response = client.chat("What's the capital of France?")
print(response.text)  # "Paris."

# Streaming
for chunk in client.stream("Tell me a short joke."):
    print(chunk, end="", flush=True)

# Vision — describe an image captured by the glasses
with open("photo.jpg", "rb") as f:
    resp = client.describe_image(f.read(), prompt="What do you see?")
print(resp.text)

# Conversation history
print(client.history)
client.clear_history()
```

---

## Examples

Ready-to-run example scripts live in the [`examples/`](examples/) folder:

| Script | Description |
|---|---|
| [`basic_connection.py`](examples/basic_connection.py) | Connect and print device info |
| [`photo_capture.py`](examples/photo_capture.py) | Capture a photo and download it |
| [`voice_commands.py`](examples/voice_commands.py) | Register and dispatch voice commands |
| [`ai_assistant.py`](examples/ai_assistant.py) | Ask Meta AI questions via voice |
| [`pricing_app.py`](examples/pricing_app.py) | Price-check products by voice or camera |
| [`research_app.py`](examples/research_app.py) | Research any topic via voice |
| [`outreach_app.py`](examples/outreach_app.py) | Send messages, emails, calls via voice |
| [`livestream_app.py`](examples/livestream_app.py) | Stream to one or all platforms at once |
| [`recorder_app.py`](examples/recorder_app.py) | Record auto-named clips with session tracking |
| [`quick_apps.py`](examples/quick_apps.py) | Rapid-fire 5 specialized apps in ~30 lines |

Run any example with:

```bash
python examples/basic_connection.py
# or with an AI key:
META_AI_API_KEY=your-key python examples/quick_apps.py
```

---

## Development setup

```bash
# Clone
git clone https://github.com/Renevizion/metaglasses.git
cd metaglasses

# Create virtual environment
python -m venv .venv && source .venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run the test suite
pytest

# Run a specific test file
pytest tests/test_glasses.py -v
```

---

## Architecture

```
metaglasses/
├── glasses.py          # Core device connection & control (BLE transport layer)
├── media.py            # Photo / video listing, download & deletion
├── voice.py            # Voice-command registration & dispatch
├── ai.py               # Meta AI API client (chat, streaming, vision)
└── apps/
    ├── __init__.py     # App base class + AppRunner registry
    ├── pricing.py      # PricingApp  — price lookups
    ├── research.py     # ResearchApp — AI research & summaries
    ├── outreach.py     # OutreachApp — messages, email, calls
    ├── livestream.py   # LivestreamApp — multi-platform RTMP
    ├── recorder.py     # RecorderApp — auto-named clip recording
    └── factory.py      # QuickApp — rapid custom app builder

examples/
├── basic_connection.py
├── photo_capture.py
├── voice_commands.py
├── ai_assistant.py
├── pricing_app.py
├── research_app.py
├── outreach_app.py
├── livestream_app.py
├── recorder_app.py
└── quick_apps.py       # ← start here to see rapid app creation

tests/
├── conftest.py
├── test_glasses.py
├── test_media.py
├── test_voice.py
├── test_ai.py
└── test_apps.py        # covers all 5 apps + QuickApp + AppRunner
```

The SDK is transport-agnostic.  The `glasses.py` module contains clearly-marked
placeholder methods (`_discover`, `_fetch_device_info`, `_set_led`) that you
replace with real `bleak` Bluetooth LE calls once you have hardware available.

---

## Roadmap

- [ ] Real BLE transport layer using `bleak`
- [ ] Wi-Fi media-transfer protocol (faster bulk download)
- [ ] On-device speech recognition via `whisper.cpp`
- [ ] Text-to-speech playback through the glasses speaker
- [ ] Async (`asyncio`) API
- [ ] CLI tool (`metaglasses status`, `metaglasses download-all`, …)
- [ ] Companion Android/iOS helper app for bridging BLE ↔ Wi-Fi
- [ ] More built-in apps: `TranslatorApp`, `NavigationApp`, `CalendarApp`, `ShoppingApp`
- [ ] Restream.io / relay auto-provisioning for multi-platform live

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Make your changes and add tests
4. Run `pytest` to confirm all tests pass
5. Open a pull request

---

## License

MIT — see [LICENSE](LICENSE) for details.