# Lovable.dev Wiring Prompt

> Copy everything below the horizontal rule and paste it into Lovable.dev as
> your first message / project prompt.  Do **not** paste this intro paragraph.

---

Build me a **web app dashboard for controlling Ray-Ban Meta Smart Glasses**.

The glasses backend server is already running locally and exposes a REST API.
All endpoints return JSON and include `Access-Control-Allow-Origin: *`, so you
can call them directly from the browser with `fetch()` — **no proxy, no
backend, no API keys needed in the frontend**.

---

## Backend base URL

```js
const BASE_URL = "http://localhost:8765";
```

> Note for the developer: change `localhost` to the server's local IP address
> (e.g. `192.168.1.42`) if the app is opened on a phone or a different device
> than the one running the server.

---

## API endpoints

### `GET /health`
Server liveness check.
```json
// Response
{"status": "ok"}
```

### `GET /status`
Current glasses state.
```json
// Response
{
  "connected": true,
  "firmware": "2.0.0",
  "battery_pct": 85,
  "storage_used_mb": 1024,
  "storage_total_mb": 32000,
  "capture_mode": "photo",
  "is_charging": false
}
```

### `POST /capture/photo`
Take a photo with the glasses.
```json
// No request body needed
// Response
{"media_id": "photo_20260313_032136"}
```

### `POST /capture/video/start`
Start video recording.
```json
// No request body needed
// Response
{}
```
Returns `409 Conflict` if recording is already in progress.

### `POST /capture/video/stop`
Stop video recording.
```json
// No request body needed
// Response
{"media_id": "video_20260313_032200"}
```

### `POST /ai/chat`
Send a message to Meta AI and get a response.
```json
// Request body
{"message": "What restaurants are nearby?"}

// Response
{"text": "Here are some nearby restaurants…", "model": "meta-ai"}
```
Returns `503` if the server was started without a Meta AI API key.

### Error responses
All error responses follow this shape:
```json
{"error": "human-readable description"}
```

---

## UI to build

Build a clean, modern **single-page dashboard** with four sections:

### 1. Status Bar (top of page)
- Polls `GET /status` every 5 seconds automatically.
- Shows:
  - A green dot labeled **"Connected"** or a red dot labeled **"Disconnected"**
    based on the `connected` field.
  - Battery percentage with a battery icon (use a filled/partial/empty icon
    to represent the level).
  - Firmware version in small grey text.
  - Storage usage as a progress bar: `storage_used_mb / storage_total_mb`.
- If the server is unreachable, show a yellow banner: *"Server not reachable —
  is mobile_bridge.py running?"*

### 2. Camera Controls
Two buttons side-by-side:

**Take Photo**
- Calls `POST /capture/photo` when clicked.
- While the request is in-flight, show a loading spinner inside the button.
- On success, show a toast notification: *"📸 Photo saved — ID: photo_…"*
- On error, show the error message in red below the button.

**Start / Stop Recording**
- Toggles between "▶ Start Recording" and "⏹ Stop Recording".
- Calls `POST /capture/video/start` or `POST /capture/video/stop` as
  appropriate.
- While in-flight, disable the button and show a spinner.
- On successful stop, show a toast: *"🎬 Video saved — ID: video_…"*

### 3. AI Chat
A chat interface:
- A scrollable message list (most recent at the bottom).
- A text input at the bottom with a "Send" button (also submittable with Enter).
- On send:
  1. Add the user's message as a right-aligned chat bubble (blue background).
  2. Show a typing indicator (three animated dots).
  3. Call `POST /ai/chat` with `{"message": "<user input>"}`.
  4. Replace the typing indicator with the AI response as a left-aligned
     bubble (dark background).
  5. If the server returns `503`, show: *"AI is not configured — start the
     server with META_AI_API_KEY=your-key"*
- Clear the input after sending.

### 4. Activity Log
A scrollable list showing the last 50 actions, newest first:
- Each entry has a timestamp, an icon, and a description.
- Log entries to create:
  - Every `GET /status` poll result — show battery % and connected status.
  - Every photo taken — show the returned `media_id`.
  - Every video start / stop — show start time or saved `media_id`.
  - Every AI message sent and reply received.
  - Any errors (shown in red).

---

## Design

- **Theme:** Dark background (`#0f0f0f`), card surfaces (`#1a1a1a`), primary
  accent colour Meta blue (`#0082fb`).
- **Font:** System font stack (no external font imports needed).
- **Layout:** Responsive. On desktop, show Status Bar full-width on top, then
  Camera Controls and AI Chat side-by-side, then Activity Log full-width at
  the bottom. On mobile, stack all sections vertically.
- **Loading states:** Always show a spinner or disabled state while a request
  is in-flight.  Never leave the user wondering if the button worked.
- **Error states:** Show errors inline near the relevant control, in red, with
  a small ✕ to dismiss.

---

## Code notes

- Use plain `fetch()` — no Axios or other HTTP library is needed.
- Keep all API calls in a single `api.ts` (or `api.js`) file with one
  exported function per endpoint, so it's easy to change `BASE_URL` in one
  place.
- Poll `/status` with `setInterval` (5000 ms).  Clear the interval on
  component unmount.
- No authentication is required — the server is intentionally open on the
  local network.
