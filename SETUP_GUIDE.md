# Real-World Setup Guide

> **The honest, no-fluff guide to getting `metaglasses` running on your phone
> and actually talking to your Ray-Ban Meta Smart Glasses.**
>
> This is not a "hello world in 30 seconds" tutorial.  It explains exactly
> what works today, what is still stubbed out, and the real steps you need to
> take to go from zero to live glasses apps.

---

## Table of Contents

1. [The honest picture](#the-honest-picture)
2. [Everything you'll need](#everything-youll-need)
3. [Phase 1 — Run it on your computer right now](#phase-1--run-it-on-your-computer-right-now)
4. [Phase 2 — Get it running on your Android phone](#phase-2--get-it-running-on-your-android-phone)
5. [Phase 3 — Wire in your real API keys](#phase-3--wire-in-your-real-api-keys)
6. [Phase 4 — Bridge to your actual glasses (the hard part)](#phase-4--bridge-to-your-actual-glasses-the-hard-part)
7. [What each built-in app needs to go real](#what-each-built-in-app-needs-to-go-real)
8. [Workarounds that work today without Phase 4](#workarounds-that-work-today-without-phase-4)
9. [FAQ](#faq)

---

## The honest picture

Here is exactly what the SDK does today vs. what still needs work:

| Capability | Status | Notes |
|---|---|---|
| Build & test your app logic | ✅ **Works now** | Full simulation mode — no glasses required |
| Meta AI chat / research / vision | ✅ **Works now** | Needs a Meta AI API key |
| Livestream RTMP (YouTube, Instagram, Twitter…) | ✅ **Works now** | Needs stream keys; you set up the RTMP push URL in Meta View manually |
| Voice command logic | ✅ **Works now** | Dispatch / matching / callbacks all work; audio capture is stubbed |
| Outreach (messages, email, calls) | ✅ **Works now** | Needs you to wire `on_send` to your own messaging backend (Twilio, SMTP, etc.) |
| Run on Android phone | ✅ **Works now** | Via Termux — see Phase 2 |
| Bluetooth connection to real glasses | ⚠️ **Stubbed** | `_discover()` always returns `True`; real BLE calls are not implemented yet |
| Auto photo/video trigger from glasses | ⚠️ **Stubbed** | `take_photo()` / `start_video()` exist but don't send real BLE commands yet |
| Live audio capture from glasses mic | ⚠️ **Stubbed** | `_listen_loop()` idles; real audio feed not wired up yet |
| Privacy LED control | ⚠️ **Stubbed** | `_set_led()` is a no-op until BLE is wired |

**Bottom line:** You can build, test, and run every app's logic end-to-end right
now.  The last mile — actual Bluetooth commands to the glasses — requires the
BLE bridge work described in Phase 4.

---

## Everything you'll need

### Hardware

- [x] **Ray-Ban Meta Smart Glasses (Gen 2)** — you need these
- [x] **A device to run Python on** — pick one:
  - **Android phone** (recommended for portability) — free via Termux
  - **Laptop** (best for development) — any OS
  - **Raspberry Pi Zero 2W** ($15) — great "pocket server" that stays with you

### Accounts & keys you need to create

| Service | Why you need it | Where to get it | Cost |
|---|---|---|---|
| **Meta AI API key** | Powers every AI feature (research, pricing, outreach polish) | [developers.meta.com](https://developers.meta.com) | Free tier available |
| **YouTube Live stream key** | Go live on YouTube | YouTube Studio → Go Live → Stream Settings | Free |
| **Instagram Live stream key** | Go live on Instagram | Instagram → Professional Dashboard → Live Producer | Free (need Creator/Business account) |
| **Twitter/X stream key** | Go live on Twitter | Twitter Media Studio → Broadcast | Free |
| **Restream.io account** *(optional but recommended)* | Fan a single RTMP push out to multiple platforms at once | [restream.io](https://restream.io) | Free tier available |
| **Twilio account** *(if using OutreachApp for SMS)* | Send real text messages | [twilio.com](https://twilio.com) | ~$0.0075/SMS |

### Software

- **Python 3.10 or newer**  
  Check: `python3 --version`  
  Get it: [python.org/downloads](https://python.org/downloads)

- **pip** (comes with Python)

- **Git**  
  Get it: [git-scm.com](https://git-scm.com)

- **Meta View app** on your phone  
  This is the official companion app for the glasses — you still need it for
  initial pairing, firmware updates, and (for now) to configure the RTMP
  stream key for livestreaming.

### Optional but useful

- **Restream Desktop** or `ffmpeg` — for testing RTMP streams locally
- **Termux:API** (Android) — lets your phone's Python code send real SMS, emails
- **A Bluetooth LE USB dongle** (if your laptop has weak BLE) — ~$10 on Amazon

---

## Phase 1 — Run it on your computer right now

This works **today, with no glasses and no API keys**.

```bash
# 1. Clone the repo
git clone https://github.com/Renevizion/metaglasses.git
cd metaglasses

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate       # macOS / Linux
# or on Windows:
# .venv\Scripts\activate

# 3. Install the SDK
pip install -e .

# 4. Run the built-in tests to confirm everything works
pip install -e ".[dev]"
pytest
# Expected: 139 passed

# 5. Run any example in simulation mode
python examples/recorder_app.py
python examples/livestream_app.py
python examples/quick_apps.py
```

Everything runs in **simulation mode** — the `Glasses` object pretends to be
connected, `take_photo()` returns a fake media ID, etc.  All your app logic
(voice matching, AI calls, event callbacks) is real and fully testable.

---

## Phase 2 — Get it running on your Android phone

The glasses pair to your phone.  Running the SDK on the same phone gives you
the lowest-latency path to real BLE communication.

### Step-by-step: Android via Termux

1. **Install Termux** from F-Droid (not the Play Store — the Play Store version
   is outdated):  
   [f-droid.org/packages/com.termux](https://f-droid.org/packages/com.termux/)

2. **Install Termux:API** from F-Droid (enables sending real SMS, calls, etc.):  
   [f-droid.org/packages/com.termux.api](https://f-droid.org/packages/com.termux.api/)
   - Also install the companion Android app: search "Termux:API" on F-Droid

3. **Open Termux and bootstrap your environment:**

   ```bash
   # Update packages
   pkg update && pkg upgrade -y

   # Install Python, git, and Bluetooth tools
   pkg install python git clang libffi openssl -y

   # Install pip packages
   pip install --upgrade pip

   # Clone the repo
   git clone https://github.com/Renevizion/metaglasses.git
   cd metaglasses

   # Install the SDK (no extras needed to start)
   pip install -e .
   ```

4. **Test that it runs:**

   ```bash
   python examples/quick_apps.py
   ```

5. **Keep Termux running in the background:**  
   Install the "Termux:Boot" app from F-Droid so your Python process can start
   automatically when you turn on your phone.

### Running on iOS

iOS is significantly more restricted:

- **Pythonista 3** ($10 from App Store) can run Python but BLE access is
  limited and there is no `bleak` support.
- **The practical path for iPhone users** is to run the SDK on a small computer
  (a laptop, or a Raspberry Pi in your bag) connected to the same Wi-Fi
  as your phone and glasses.

---

## Phase 3 — Wire in your real API keys

Once the SDK is running (Phase 1 or Phase 2), replace the placeholders with
real credentials.  **Never hardcode keys in source files** — use environment
variables.

### 3a. Meta AI API key

1. Go to [developers.meta.com](https://developers.meta.com) and create a
   developer account.
2. Create an app and generate an API key under **Meta AI API**.
3. Set it in your environment:

   ```bash
   # Linux / macOS / Termux
   export META_AI_API_KEY="your-key-here"

   # Or add to ~/.bashrc / ~/.zshrc so it persists
   echo 'export META_AI_API_KEY="your-key-here"' >> ~/.bashrc
   ```

4. Test it:

   ```bash
   META_AI_API_KEY=your-key python examples/research_app.py
   ```

### 3b. Livestream stream keys

Get a stream key from each platform you want to use:

| Platform | Where to find your stream key |
|---|---|
| YouTube | YouTube Studio → **Go Live** → **Stream** tab → copy "Stream key" |
| Instagram | Instagram app → **Professional Dashboard** → **Live Producer** → copy stream key |
| Twitter/X | Twitter Media Studio → **Broadcast** → copy stream key |
| TikTok | TikTok LIVE Studio → Settings → copy stream key |
| Twitch | Twitch Dashboard → **Settings** → **Stream** → copy primary stream key |

Then pass them to `LivestreamApp`:

```python
from metaglasses.apps.livestream import LivestreamApp, Platform

app = LivestreamApp(
    glasses,
    stream_keys={
        Platform.YOUTUBE:   "xxxx-xxxx-xxxx-xxxx",
        Platform.INSTAGRAM: "xxxx-xxxx-xxxx-xxxx",
        Platform.TWITTER:   "xxxx-xxxx-xxxx-xxxx",
    },
    # Optional: use Restream.io relay to push once → all platforms
    relay_url="rtmp://live.restream.io/live/re_YOUR_RESTREAM_KEY",
)
```

**For multi-platform streaming** (YouTube + Instagram + Twitter simultaneously)
you have two options:

- **Restream.io** (easiest): Create a free account at [restream.io](https://restream.io),
  connect your YouTube/Instagram/Twitter accounts, and copy your Restream RTMP
  URL + key.  Set that as `relay_url` above.
  
- **Self-hosted relay** (advanced): Install `nginx` with the `nginx-rtmp-module`
  on a server or even your phone.  Configure it to push to multiple destinations.

### 3c. OutreachApp — SMS, email, calls

The `OutreachApp` stores items in `app.outbox` and calls your `on_send`
callback.  You wire that callback to a real backend:

**SMS via Twilio:**
```python
from twilio.rest import Client as TwilioClient

twilio = TwilioClient("YOUR_ACCOUNT_SID", "YOUR_AUTH_TOKEN")

def send_handler(item):
    if item.type == "message":
        twilio.messages.create(
            body=item.body,
            from_="+15551234567",   # your Twilio number
            to=item.to,
        )
    elif item.type == "call":
        twilio.calls.create(
            url="http://demo.twilio.com/docs/voice.xml",
            from_="+15551234567",
            to=item.to,
        )

app = OutreachApp(glasses, ai, on_send=send_handler)
```

**SMS on Android via Termux:API** (no Twilio account needed):
```python
import subprocess

def send_handler(item):
    if item.type == "message":
        subprocess.run([
            "termux-sms-send",
            "-n", item.to,
            item.body,
        ])

app = OutreachApp(glasses, ai, on_send=send_handler)
```

**Email via Gmail:**
```python
import smtplib
from email.mime.text import MIMEText

def send_handler(item):
    if item.type == "email":
        msg = MIMEText(item.body)
        msg["Subject"] = "From your glasses"
        msg["From"] = "you@gmail.com"
        msg["To"] = item.to
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login("you@gmail.com", "YOUR_APP_PASSWORD")
            server.send_message(msg)

app = OutreachApp(glasses, ai, on_send=send_handler)
```

> **Gmail note:** Use an [App Password](https://support.google.com/accounts/answer/185833),
> not your real password.  Enable 2FA first, then create an App Password
> under your Google Account → Security → App passwords.

---

## Phase 4 — Bridge to your actual glasses (the hard part)

This is the part where I have to be straight with you.

### Why this is non-trivial

Ray-Ban Meta Glasses communicate with the Meta View companion app over a
**proprietary, undocumented Bluetooth LE protocol**.  Meta has not released
an official developer SDK for low-level glasses control.  This means:

- There is no official `glasses.take_photo()` BLE command you can just call.
- The SDK's `_discover()`, `_fetch_device_info()`, `_set_led()`, and
  `_listen_loop()` methods are all **stubs** that need real BLE code.

### The three realistic paths forward

#### Path A — Wait for the official Meta developer platform *(lowest effort)*

Meta is actively building developer tools for the glasses.  They have announced
programs like **Meta Orion** and a developer-focused ecosystem.  If you can wait,
this is the cleanest path — when they release an official API, you just drop it
into the stub methods.

**What to watch:**  
- [developers.meta.com/horizon/glasses](https://developers.meta.com/horizon/glasses)  
- Meta Connect announcements

#### Path B — Reverse-engineer the BLE protocol *(advanced, most control)*

The glasses BLE protocol has been partially reverse-engineered by the community.
Here's what that would take:

1. **Set up a BLE sniffer:**
   - On Android: use the built-in HCI log (`Settings → Developer Options →
     Enable Bluetooth HCI snoop log`) then use Wireshark or nRF Sniffer.
   - On a PC: use Ubertooth One (hardware dongle, ~$120) for over-the-air
     capture.

2. **Capture normal Meta View ↔ Glasses traffic** while using the app.

3. **Decode the packets** to understand the GATT services and characteristic
   UUIDs used for each command.

4. **Implement it in Python** using `bleak`:

   ```python
   # This is what the real connect() would look like
   import asyncio
   from bleak import BleakScanner, BleakClient

   async def connect_real(self):
       device = await BleakScanner.find_device_by_name("Ray-Ban Meta")
       async with BleakClient(device) as client:
           self._client = client
           self._connected = True
           # Read device info from GATT characteristics
           battery = await client.read_gatt_char("BATTERY_LEVEL_UUID")
           ...
   ```

5. **Install the BLE extra:**
   ```bash
   pip install -e ".[ble]"
   ```

Resources to get you started:
- Search GitHub for `ray-ban meta ble protocol` — several community projects have documented GATT characteristics
- [Wireshark BLE tutorial](https://wiki.wireshark.org/Bluetooth)
- [bleak documentation](https://bleak.readthedocs.io) — the Python BLE library used in this SDK

#### Path C — Use Meta View as a bridge *(practical right now)*

The Meta View app already handles BLE communication.  You can build on top of
it rather than replacing it:

1. **Configure your RTMP stream URL in Meta View** once (manually).  
   Then `LivestreamApp` just controls the session — you pre-set the destination
   in the app.

2. **Use the "Hey Meta" feature** for voice.  The glasses already transcribe
   voice and send it to Meta AI.  You can set up Meta AI automations that call
   webhooks, which your Python process receives.

3. **Use the glasses camera as a regular camera.**  Photos and videos sync to
   your phone via the Meta View app.  A Python script on your phone (with
   Termux:API) can watch the gallery folder and process new files automatically:

   ```python
   import time
   from pathlib import Path
   from metaglasses.apps.pricing import PricingApp

   GALLERY = Path("/storage/emulated/0/DCIM/RayBan")
   seen = set()

   while True:
       for f in GALLERY.glob("*.jpg"):
           if f not in seen:
               seen.add(f)
               result = app.price_from_image(f.read_bytes())
               print(result["answer"])
       time.sleep(2)
   ```

---

## What each built-in app needs to go real

| App | Works today | What you need for full hardware integration |
|---|---|---|
| **PricingApp** | ✅ AI lookups work with API key | BLE (Phase 4) to trigger on button press; gallery watcher works today |
| **ResearchApp** | ✅ AI research works with API key | BLE for voice capture; Meta View bridge works today |
| **OutreachApp** | ✅ Logic + AI polish work | Twilio / Termux:API for real sends (see Phase 3c) |
| **LivestreamApp** | ✅ RTMP push works with stream keys | Stream keys (see Phase 3b); multi-platform via Restream |
| **RecorderApp** | ✅ Session tracking works | BLE `start_video()` command (Phase 4); Meta View bridge works today |
| **QuickApp** | ✅ AI lookups + callbacks work | BLE for hardware triggers |

---

## Workarounds that work today without Phase 4

You don't have to wait for BLE to get real value.  Here's what you can do right
now:

### 1. Gallery watcher — react to new photos/videos automatically
The glasses sync media to your phone via Meta View.  Python watches the folder:

```python
# watch_gallery.py — run on your Android phone in Termux
import time
from pathlib import Path
from metaglasses import Glasses, MetaAIClient
from metaglasses.apps.pricing import PricingApp

glasses = Glasses()
glasses.connect()   # simulation mode is fine for this
ai = MetaAIClient(api_key="YOUR_KEY")
app = PricingApp(glasses, ai, on_result=lambda r: print(r["answer"]))

GALLERY = Path("/storage/emulated/0/DCIM/RayBan")
seen = set(GALLERY.glob("*.jpg"))

print("Watching for new photos from glasses…")
while True:
    current = set(GALLERY.glob("*.jpg"))
    for new_file in current - seen:
        print(f"New photo: {new_file.name}")
        app.price_from_image(new_file.read_bytes())
    seen = current
    time.sleep(2)
```

### 2. Voice via phone microphone
Until the BLE audio bridge is built, trigger voice commands from your
phone's microphone using `whisper`:

```bash
pip install openai-whisper pyaudio
```

```python
# voice_bridge.py
import whisper
import sounddevice as sd
import numpy as np
from metaglasses.apps.research import ResearchApp

model = whisper.load_model("tiny")   # fast, runs on phone

def listen_and_dispatch(app, duration=3):
    print("Listening…")
    audio = sd.rec(int(duration * 16000), samplerate=16000, channels=1, dtype="float32")
    sd.wait()
    result = model.transcribe(audio.flatten())
    utterance = result["text"]
    print(f"Heard: {utterance}")
    app._handler.dispatch(utterance)

# Wire it to your app
glasses = Glasses()
glasses.connect()
ai_app = ResearchApp(glasses, ai)
ai_app.start()

while True:
    listen_and_dispatch(ai_app)
```

### 3. Manual trigger script
The simplest path — map the glasses' physical buttons to Python commands
using the button events Meta View fires.  Not automated, but it works today.

### 4. LivestreamApp — works right now with your stream keys
This is the one app that needs **no BLE at all**.  Configure your RTMP stream
key in `LivestreamApp`, and when you call `app.go_live(Platform.YOUTUBE)`,
it will push the RTMP stream from the glasses through the Meta View app's
RTMP output.

> **Important:** You still need to configure the RTMP output URL once in Meta
> View → More → Device Settings → Live.  After that, `LivestreamApp` controls
> which URL to use, and the stream starts/stops via the SDK.

---

## FAQ

**Q: Do I need a jailbroken phone?**  
No.  Termux is a legitimate Android app from F-Droid.  No root is required for
phases 1–3.  Phase 4 (BLE reverse engineering) does not require root either —
the HCI snoop log option is a standard Android developer option.

**Q: Will this break my Meta View app or my glasses?**  
No.  The SDK runs alongside Meta View; it doesn't replace it.  In simulation
mode nothing touches your glasses at all.  Once BLE is wired up (Phase 4),
you'd be directly connecting to the glasses instead of Meta View — you would
need to close Meta View first to avoid two apps fighting over the BLE connection.

**Q: Can I run this 24/7 on my phone?**  
Yes.  Termux supports background processes.  Use `nohup` or run the script
inside `tmux` so it keeps running after you lock your screen:

```bash
pkg install tmux
tmux new-session -s glasses
python my_apps.py
# Ctrl-B then D to detach; it keeps running
# tmux attach -t glasses  to return
```

**Q: What's the minimum phone spec?**  
Any Android phone from ~2019 or newer with BLE 5.0.  The AI calls go to
the cloud, so phone CPU doesn't need to be fast.  `whisper tiny` for
voice recognition needs about 512 MB of RAM.

**Q: I have an iPhone.  Can I still use this?**  
You can run phases 1–3 on a laptop and do everything except on-device BLE.
Full iPhone support is on the roadmap but not available yet.

**Q: Do my stream keys expire?**  
YouTube Live and Twitch give you permanent stream keys unless you regenerate
them.  Instagram and TikTok keys can expire or change periodically — check
the platform settings if a stream suddenly fails.

**Q: How do I update the SDK when new features land?**

```bash
cd metaglasses
git pull origin main
pip install -e .
```

**Q: Where do I report bugs or ask for help?**  
Open an issue at [github.com/Renevizion/metaglasses/issues](https://github.com/Renevizion/metaglasses/issues).
