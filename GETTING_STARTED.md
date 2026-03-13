# Getting Started

> **Read this first.**  It answers: *"What exactly do I do with this repo?"*

---

## The one-sentence answer

`metaglasses` is the **Python backend server** that sits between your app
(wherever you built it) and your Ray-Ban Meta Smart Glasses.  You start this
server once, and then your app calls it over HTTP.

---

## Pick your path

You are in one of two situations:

| | Path A | Path B |
|---|---|---|
| **Situation** | "I want to build a Lovable.dev app (or any web app) that controls the glasses" | "I already have the glasses and want to wire them up and test right now" |
| **Time to working demo** | ~15 minutes | ~10 minutes + pairing your glasses |
| **Do I need the glasses first?** | ❌ No — you can test with a simulated connection | ✅ Yes |
| **Jump to** | [Path A →](#path-a-build-a-loveabledev-app) | [Path B →](#path-b-connect-your-glasses-right-now) |

Both paths start with the same two steps.

---

## Step 0 — Start the backend server (everyone does this)

Open a terminal and run these four commands once:

```bash
# 1.  Clone this repo (skip if you already have it)
git clone https://github.com/Renevizion/metaglasses.git
cd metaglasses

# 2.  Install
pip install -e .

# 3.  Start the server
python examples/mobile_bridge.py
```

You should see:

```
Bridge server listening on 0.0.0.0:8765
Glasses: Glasses(connected=True, ...)
Voice command handler started.
Ready. Press Ctrl+C to stop.
```

Leave that terminal running.  The server is now live at
**`http://localhost:8765`**.

### ✅ Verify it's running

Open a new terminal tab (or a browser) and check:

```bash
curl http://localhost:8765/health
# → {"status": "ok"}

curl http://localhost:8765/status
# → {"connected": true, "battery_pct": 85, "firmware": "2.0.0", ...}
```

Or just open <http://localhost:8765/health> in your browser.

> **No glasses yet?**  That's fine.  The server runs in simulation mode by
> default — it acts as if a pair of glasses is connected so you can build and
> test your app immediately.  Real glasses events will replace the simulated
> ones once you complete Path B.

---

## Path A — Build a Lovable.dev app

1. **The server is running** (Step 0 above). ✅

2. **Open [lovable.dev](https://lovable.dev)** and create a new project.

3. **Paste the wiring prompt.**
   Open [`lovable_prompt.md`](lovable_prompt.md) in this repo, copy the
   entire contents, and paste it into the Lovable.dev chat / initial prompt
   box.  That prompt tells Lovable exactly what the API looks like and what
   UI to build — you don't need to write any code yourself.

4. **Let Lovable generate the app.**  It will produce a React/TypeScript
   dashboard with:
   - A live status bar (battery, firmware, connected indicator)
   - Take Photo and Start/Stop Recording buttons
   - An AI chat panel (talks to Meta AI via the glasses)
   - An activity log

5. **Change the API base URL** if your server is not on the same machine.
   In the generated code, find the line:

   ```js
   const BASE_URL = "http://localhost:8765";
   ```

   Change `localhost` to your laptop's local IP address (e.g.
   `192.168.1.42`) if your phone or another device is running the Lovable
   app.  You can find your IP with `ipconfig` (Windows) or
   `ifconfig` / `ip addr` (Mac/Linux).

6. **Click the buttons in Lovable's preview.**  The calls go to your running
   Python server.  You'll see activity in the terminal where
   `mobile_bridge.py` is running.

7. **Deploy the Lovable app** (Lovable → Publish) whenever you're ready to
   use it from your phone.  Update `BASE_URL` to your server's public or
   local-network address.

> **With AI features:**  add your Meta AI key before starting the server:
> ```bash
> META_AI_API_KEY=your-key-here python examples/mobile_bridge.py
> ```
> The `/ai/chat` endpoint will then return real AI responses.

### 📱 Getting the Lovable app onto your iPhone (no Xcode, no MobaJump needed)

> **🔊 Prefer to be talked through it?**
> Open [`examples/voice_guide.html`](examples/voice_guide.html) in your browser.
> It reads each step aloud using your browser's built-in voice.
> Hit the 🔇 button any time to silence it.

The Lovable.dev app is a **web app** — it runs in any browser, including
Safari on your iPhone.  You do **not** need Xcode, a Mac, or MobaJump for
this part.

**Steps:**

1. In Lovable.dev click **Share → Publish**.  Your app gets a URL like
   `https://your-project.lovable.app`.

2. Open that URL in **Safari** on your iPhone (it must be Safari for the
   "Add to Home Screen" option to appear).

3. Tap the **Share icon** (box with an arrow) at the bottom of Safari.

4. Scroll down and tap **"Add to Home Screen"**.

5. Give it a name (e.g. *"Meta Glasses"*) and tap **Add**.

The app now appears on your home screen like a native app — full screen, no
browser chrome.  It opens straight to the dashboard.

**Before you do step 1**, make sure `BASE_URL` in the generated code points
to your server's address on your local network (e.g. `http://192.168.1.42:8765`),
not `localhost`, because your iPhone and your laptop need to share the same
Wi-Fi network.

> **What about MobaJump?**
>
> MobaJump ([mobajump.com](https://mobajump.com)) is a sideloading service for
> **native iOS `.ipa` files** — apps built with Swift/Xcode that you want to
> install on your iPhone without a paid Apple Developer account or a newer Mac.
>
> You do **not** need it for the Lovable dashboard (that's a web app, not an
> `.ipa`).  MobaJump becomes relevant later if you build a native MWDAT bridge
> companion app in Swift that talks to the glasses over Bluetooth — that's the
> Phase 5 path in [SETUP_GUIDE.md](SETUP_GUIDE.md#phase-5--connect-via-the-official-meta-mobile-sdk-mwdat).
> At that point you'd build the `.ipa` on any machine (even a CI service) and
> use MobaJump to sideload it onto your phone.  Until then, the web-app PWA
> path above is all you need.

---

## Path B — Connect your glasses right now

### What you need

- [ ] Ray-Ban Meta Smart Glasses (Gen 2) paired to your phone
- [ ] Meta View app installed and glasses connected
- [ ] Python running on the **same device as your phone** (Android via
  Termux) or on a **laptop on the same Wi-Fi network**

### Steps

1. **The server is running on your laptop** (Step 0 above). ✅

2. **Find your laptop's local IP address.**

   ```bash
   # macOS / Linux
   ipconfig getifaddr en0       # Wi-Fi
   # or
   ip addr show | grep "inet "

   # Windows
   ipconfig | findstr "IPv4"
   ```

   Example result: `192.168.1.42`

3. **Configure your mobile companion app** to forward glasses events to the
   server.

   The quickest way today is to use the MWDAT path described in
   [SETUP_GUIDE.md — Phase 5](SETUP_GUIDE.md#phase-5--connect-via-the-official-meta-mobile-sdk-mwdat).
   In short, your iOS or Android app POSTs every glasses event to:

   ```
   POST http://192.168.1.42:8765/event
   ```

   iOS Swift snippet:

   ```swift
   func forwardEvent(_ event: [String: Any]) {
       guard let url = URL(string: "http://192.168.1.42:8765/event") else { return }
       var req = URLRequest(url: url)
       req.httpMethod = "POST"
       req.setValue("application/json", forHTTPHeaderField: "Content-Type")
       req.httpBody = try? JSONSerialization.data(withJSONObject: event)
       URLSession.shared.dataTask(with: req).resume()
   }
   ```

   Android Kotlin snippet:

   ```kotlin
   fun forwardEvent(event: Map<String, Any>) {
       val json = JSONObject(event).toString()
       val body = json.toRequestBody("application/json".toMediaType())
       val request = Request.Builder()
           .url("http://192.168.1.42:8765/event")
           .post(body)
           .build()
       OkHttpClient().newCall(request).enqueue(...)
   }
   ```

4. **Put on the glasses and say a command**, e.g. *"Hey Meta, take a photo"*.
   Watch the terminal where `mobile_bridge.py` is running — you should see
   the event arrive and be processed.

5. **Test an endpoint directly** from your phone browser or any HTTP client:

   ```
   POST http://192.168.1.42:8765/capture/photo
   → {"media_id": "photo_20260313_032136"}
   ```

6. **From here**, either:
   - Follow **Path A** above to build a Lovable.dev UI on top of the
     working glasses connection, **or**
   - Write Python apps directly using the SDK — see the examples in
     [`examples/`](examples/) and the full API in [`README.md`](README.md).

---

## All REST endpoints at a glance

Your app (Lovable.dev or any other) calls these.  All return JSON.
CORS is open (`*`), so browser apps work without a proxy.

| Endpoint | Method | Request body | Response |
|---|---|---|---|
| `/health` | GET | — | `{"status":"ok"}` |
| `/status` | GET | — | `{"connected":true,"battery_pct":85,"firmware":"2.0.0",…}` |
| `/capture/photo` | POST | — | `{"media_id":"photo_…"}` |
| `/capture/video/start` | POST | — | `{}` |
| `/capture/video/stop` | POST | — | `{"media_id":"video_…"}` |
| `/ai/chat` | POST | `{"message":"…"}` | `{"text":"…","model":"…"}` |
| `/event` | POST | glasses event dict | `{}` |
| `/response` | GET | — | `{"responses":["…"]}` |

---

## Troubleshooting

**"Connection refused" when the Lovable app calls the server**
- Make sure `mobile_bridge.py` is still running in your terminal.
- If the Lovable preview runs on a different machine, use your laptop's IP
  instead of `localhost`.
- If you're on a corporate/campus Wi-Fi, the network may block
  device-to-device connections — use a personal hotspot instead.

**"No AI client configured" error from `/ai/chat`**
- You need a Meta AI API key.  Start the server with:
  ```bash
  META_AI_API_KEY=your-key python examples/mobile_bridge.py
  ```

**The server starts but glasses events don't arrive**
- This is expected until you complete Phase 4/5 in
  [SETUP_GUIDE.md](SETUP_GUIDE.md).  The server is working in simulation
  mode.  Real glasses events require the MWDAT mobile companion app bridge.

**The Lovable app shows "server not reachable"**
- Visit <http://localhost:8765/health> in the browser on the *same device*
  the Lovable preview is running on.  If that fails, the server isn't running.
- If it works in the browser but not in the Lovable preview, check the
  `BASE_URL` constant in the generated code.

---

## What's next

Once everything is wired up end-to-end, explore:

- [`examples/voice_guide.html`](examples/voice_guide.html) — open in any browser; a step-by-step voice guide (browser speech synthesis) that talks you through Lovable → MobaJump → iPhone → glasses. Hit 🔇 any time to mute it.
- [`README.md`](README.md) — full SDK reference and built-in apps
- [`examples/quick_apps.py`](examples/quick_apps.py) — spin up 5 custom
  voice-command apps in ~30 lines
- [`SETUP_GUIDE.md`](SETUP_GUIDE.md) — run everything on your Android
  phone via Termux, wire real BLE, manage API keys
