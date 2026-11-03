---
title: Halal Cartoon Factory
emoji: 🎬
colorFrom: gray
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# Halal Cartoon Factory

A Flask web app that turns a short Islamic story topic into a finished,
multi-scene cartoon `.mp4` — script, voiceover, scene art, and a face-safety
pass — all built on free-tier tools, with no background music. Runs as a
normal web page, so "installing" it on a phone just means opening the URL.

## How a request flows

```
topic + format  ->  01_script_generator   (Gemini: topic -> 3 scenes)
                ->  02_prompt_modifier    (adds Shariah framing + negative prompt)
                ->  03_voice_generator    (gTTS: dialogue -> scene_N.mp3)
                ->  04_visual_generator   (Hugging Face SD -> scene_N.png, with
                                            a local fallback image if no token
                                            is set or the API call fails)
                ->  05_safety_filter      (MediaPipe + OpenCV: blur/mask any
                                            face the image model slipped in)
                ->  06_video_renderer     (MoviePy: each image shown for its
                                            own audio's exact duration, then
                                            concatenated -> final .mp4)
```

Generation runs as a background job: the browser starts it, gets a job ID
back immediately, and polls every few seconds for progress — so it survives
a locked phone screen or a flaky mobile connection, and works regardless of
any particular host's request-timeout limit.

Every job gets its own UUID folder under `/assets`, so concurrent requests
never collide, and the final `.mp4` is served statically from
`/output/<filename>`.

## Run it live, from anywhere (Hugging Face Spaces)

This is the recommended way to use it from your phone away from home, or
from any laptop, anywhere — no server running on your own machine required.

1. Create a free account at https://huggingface.co (no credit card needed).
2. Click **New Space** → give it a name → SDK: **Docker** → Hardware:
   **CPU basic** (free: 2 vCPU / 16 GB RAM).
3. Upload every file in this project to the Space (drag-and-drop in the
   Space's "Files" tab, or `git push` to the Space's repo — Spaces are
   plain git repos).
4. Wait for the "Building" status to turn into "Running" (a few minutes
   the first time).
5. Open the Space's URL — `https://<your-username>-<space-name>.hf.space`
   — from any phone or laptop, on any network. That's your permanent link.
6. In the app, tap the gear icon (top-right) and paste in your Gemini key
   and Hugging Face token, then **Save Keys**. No code or `.env` editing
   needed.

**About key persistence:** a free Space's filesystem can reset when it goes
to sleep from inactivity and later wakes back up, which would clear keys
saved from the Settings panel (just re-paste them — it takes a few
seconds). If you'd rather they survive restarts, open your Space's
**Settings → Variables and secrets** and add `GEMINI_API_KEY` /
`HUGGINGFACE_API_TOKEN` there instead — the app already checks for these as
a fallback whenever a key isn't set in the Settings panel.

## Run it locally (same WiFi only, or for development)

```bash
cd halal-cartoon-factory
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python backend_server/server.py
```

Then open **http://localhost:5000** — or, to reach it from your phone on
the same WiFi, find your computer's local IP (`ipconfig` on Windows,
`ipconfig getifaddr en0` on Mac, `hostname -I` on Linux) and open
`http://<that-ip>:5000` on the phone instead. Either way, you can set your
API keys from the in-app Settings panel instead of editing `.env`.

## Getting free API keys

- **Gemini API key** (optional — without it the app uses a built-in
  fallback script instead of an AI-written one): https://aistudio.google.com/apikey
- **Hugging Face token** (optional — without it the app draws a simple
  placeholder image per scene instead of generated art): https://huggingface.co/settings/tokens

## Notes on what's enforced automatically

- **No faces, ever.** Every generated image goes through a second,
  independent face-detection pass (`05_safety_filter.py`) that blurs and
  masks any face region the image model produced, regardless of what the
  prompt asked for.
- **No background music, ever.** The renderer only ever mixes the
  voiceover track (plus, optionally, your own ambient sound — see below).
  There is no code path that adds music.
- **Optional ambient sound:** drop your own royalty-free `.mp3`/`.wav`
  files (wind, water, birds, etc.) into `assets/ambient/`. If that folder
  has files, one is mixed in quietly under the narration on each run. If
  it's empty (the default), videos are pure voiceover — always a safe
  choice.

## Good to know

- The `mediapipe` dependency is optional. If it fails to install on your
  platform/Python version, delete that line from `requirements.txt` — the
  safety filter automatically falls back to its built-in OpenCV detector,
  with no code changes needed.
- Hugging Face's free inference API can take 10–30 seconds to "wake up" a
  model on a cold start; `04_visual_generator.py` retries automatically
  before falling back to a placeholder image.
- Job progress is tracked in memory, so this app must run as a single
  process (the Dockerfile already does this). If you ever front it with
  Gunicorn/uWSGI using multiple workers, swap the in-memory `jobs` dict in
  `server.py` for a shared store (SQLite, Redis, etc.) first.

## Fixed / added vs. your original draft

- `script.js` was sending `{ topic, aspect_ratio, language }` but only
  `aspectRatio` (camelCase) was ever declared — `aspect_ratio` was
  `undefined` and this would have thrown at submit time. Fixed.
- `04_visual_generator.py`'s Hugging Face URL was wrapped in Markdown link
  syntax (`[https://...](https://...)`), which isn't a valid URL string in
  Python. Now a plain string, with retry handling for model cold starts.
- `google-generativeai` reached end-of-life on 2025-11-30; the script
  generator now uses Google's current unified SDK, `google-genai`.
- `core_engine/__init__.py` didn't exist, so `server.py`'s
  `from core_engine import ...` wouldn't have worked, and files starting
  with a digit (`01_script_generator.py`) can't be `import`ed directly
  anyway. Added an `__init__.py` that loads each numbered file via
  `importlib`.
- The safety filter used `mp.solutions.face_detection`, MediaPipe's
  deprecated legacy API. Rewritten against the current MediaPipe **Tasks**
  API, with an always-on OpenCV pass as a guaranteed fallback.
- **API keys now live in a Settings panel in the UI** (`/api/settings`,
  backed by `core_engine/settings_store.py`), instead of requiring `.env`
  edits — useful once this is deployed somewhere you can't easily SSH into.
- **Generation is now an async background job** (`POST /api/generate-video`
  returns a `job_id` immediately; the frontend polls `GET
  /api/job-status/<job_id>`), instead of one long synchronous request —
  needed for reliability on mobile networks and because most hosts
  (including free tiers) cap how long a single HTTP request can stay open.
- Added a **Dockerfile** + Hugging Face Spaces frontmatter (top of this
  file) so the app can be deployed with a few clicks and reached from
  anywhere, not just a local network.
