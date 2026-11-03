"""
Halal Cartoon Factory — Backend Server
===========================================
Flask API that orchestrates the full multi-scene generation pipeline:

    topic + options
        -> script (per-scene visual prompt + dialogue)
        -> Shariah-compliant prompt rewriting
        -> per-scene voiceover (gTTS)
        -> per-scene image (Hugging Face Stable Diffusion, with local fallback)
        -> per-scene face-safety pass (MediaPipe / OpenCV)
        -> final video render (MoviePy, audio-exact scene durations)

Generation runs in a background thread per job, and the frontend polls
/api/job-status/<job_id> for progress. This matters for two reasons:
  1. Rendering can take one to a few minutes — well past the request
     timeout most hosting platforms (including free tiers) enforce on a
     single HTTP request.
  2. On a phone, especially on mobile data, a multi-minute held-open
     connection is fragile (locking the screen, a network blip, switching
     apps can all kill it). Short polling requests are far more reliable.

API keys (Gemini, Hugging Face) can be set two ways, checked in this
order: a value saved via the Settings panel in the UI (POST /api/settings,
stored in config/api_keys.json), or the GEMINI_API_KEY /
HUGGINGFACE_API_TOKEN environment variables. See core_engine/settings_store.py.
"""

import os
import time
import uuid
import threading
import traceback
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from core_engine import (
    ScriptGenerator, PromptModifier, VoiceGenerator,
    VisualGenerator, SafetyFilter, VideoRenderer
)
from core_engine.settings_store import get_setting, save_settings, mask

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_FOLDER = os.path.join(BASE_DIR, "frontend_ui")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = Flask(__name__, static_folder=FRONTEND_FOLDER, template_folder=FRONTEND_FOLDER)
CORS(app)

# Engine components are instantiated once and reused across requests.
# (They each read API keys fresh per call via settings_store, so saving a
# new key from the UI takes effect immediately — no re-instantiation needed.)
script_gen = ScriptGenerator()
prompt_mod = PromptModifier()
voice_gen = VoiceGenerator()
visual_gen = VisualGenerator()
safety_filter = SafetyFilter()
renderer = VideoRenderer()

VALID_ASPECT_RATIOS = {"9:16", "16:9"}
VALID_LANGUAGES = {"en", "bn"}
MAX_TOPIC_LENGTH = 500

# ---------------------------------------------------------------------------
# In-memory job tracking.
#
# NOTE: this only works correctly as a single process. If you ever put this
# behind Gunicorn/uWSGI with multiple worker processes, each worker would
# have its own separate `jobs` dict and polling would randomly 404 depending
# on which worker handled which request. Run with one process (the
# Dockerfile does this), or swap this dict for a shared store (SQLite,
# Redis, etc.) if you need multiple workers.
# ---------------------------------------------------------------------------
jobs = {}
jobs_lock = threading.Lock()
JOB_RETENTION_SECONDS = 2 * 60 * 60  # prune finished jobs after 2 hours


def _set_job(job_id, **fields):
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id].update(fields)


def _prune_old_jobs():
    cutoff = time.time() - JOB_RETENTION_SECONDS
    with jobs_lock:
        stale = [jid for jid, j in jobs.items() if j.get("created_at", 0) < cutoff]
        for jid in stale:
            jobs.pop(jid, None)


def _run_generation_job(job_id: str, topic: str, aspect_ratio: str, language: str):
    job_dir = os.path.join(ASSETS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    try:
        _set_job(job_id, stage="Writing the script...")
        scenes = script_gen.generate_script(topic, language)
        processed_scenes = []
        total = len(scenes)

        for i, scene in enumerate(scenes, start=1):
            scene_id = scene["scene_id"]
            raw_prompt = scene["visual_prompt"]
            dialogue = scene["dialogue"]

            enhanced_prompt, negative_prompt = prompt_mod.apply_shariah_rules(raw_prompt)

            _set_job(job_id, stage=f"Scene {i}/{total}: recording voiceover...")
            audio_path = os.path.join(job_dir, f"scene_{scene_id}.mp3")
            voice_gen.generate_voiceover(dialogue, audio_path, language)

            _set_job(job_id, stage=f"Scene {i}/{total}: generating artwork...")
            raw_image_path = os.path.join(job_dir, f"scene_{scene_id}.png")
            visual_gen.generate_image(
                enhanced_prompt, aspect_ratio, raw_image_path, negative_prompt=negative_prompt
            )

            _set_job(job_id, stage=f"Scene {i}/{total}: running face-safety check...")
            safe_image_path = safety_filter.enforce_face_safety(raw_image_path)

            processed_scenes.append({
                "scene_id": scene_id,
                "image_path": safe_image_path,
                "audio_path": audio_path
            })

        _set_job(job_id, stage="Rendering final video...")
        final_filename = f"halal_cartoon_{job_id}.mp4"
        final_path = os.path.join(OUTPUT_DIR, final_filename)
        renderer.render_final_video(processed_scenes, final_path, aspect_ratio)

        _set_job(
            job_id,
            status="done",
            stage="Complete",
            video_url=f"/output/{final_filename}",
        )

    except Exception as e:
        traceback.print_exc()
        _set_job(job_id, status="error", stage="Failed", error=str(e))


@app.route("/")
def index():
    return send_from_directory(FRONTEND_FOLDER, "index.html")


@app.route("/frontend_ui/<path:filename>")
def serve_frontend(filename):
    return send_from_directory(FRONTEND_FOLDER, filename)


@app.route("/output/<path:filename>")
def serve_output(filename):
    return send_from_directory(OUTPUT_DIR, filename)


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Settings (API keys), editable from the UI instead of .env / code.
# ---------------------------------------------------------------------------

@app.route("/api/settings", methods=["GET"])
def get_settings():
    gemini_key = get_setting("gemini_api_key", env_fallback="GEMINI_API_KEY")
    hf_token = get_setting("huggingface_api_token", env_fallback="HUGGINGFACE_API_TOKEN")
    return jsonify({
        "gemini_api_key_set": bool(gemini_key),
        "gemini_api_key_masked": mask(gemini_key),
        "huggingface_api_token_set": bool(hf_token),
        "huggingface_api_token_masked": mask(hf_token),
    })


@app.route("/api/settings", methods=["POST"])
def update_settings():
    data = request.get_json(silent=True) or {}
    gemini_api_key = (data.get("gemini_api_key") or "").strip()
    huggingface_api_token = (data.get("huggingface_api_token") or "").strip()

    # Blank fields are treated as "leave unchanged" so saving one key never
    # wipes the other.
    fields = {}
    if gemini_api_key:
        fields["gemini_api_key"] = gemini_api_key
    if huggingface_api_token:
        fields["huggingface_api_token"] = huggingface_api_token

    if not fields:
        return jsonify({"success": False, "error": "No key provided."}), 400

    save_settings(**fields)
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# Video generation (async, job-based).
# ---------------------------------------------------------------------------

@app.route("/api/generate-video", methods=["POST"])
def generate_video():
    data = request.get_json(silent=True) or {}
    topic = (data.get("topic") or "").strip()
    aspect_ratio = data.get("aspect_ratio", "16:9")
    language = data.get("language", "en")

    if not topic:
        return jsonify({"success": False, "error": "A story topic is required."}), 400
    if len(topic) > MAX_TOPIC_LENGTH:
        return jsonify({"success": False, "error": f"Topic must be under {MAX_TOPIC_LENGTH} characters."}), 400
    if aspect_ratio not in VALID_ASPECT_RATIOS:
        return jsonify({"success": False, "error": "Invalid aspect_ratio."}), 400
    if language not in VALID_LANGUAGES:
        return jsonify({"success": False, "error": "Invalid language."}), 400

    _prune_old_jobs()

    job_id = str(uuid.uuid4())[:8]
    with jobs_lock:
        jobs[job_id] = {
            "status": "processing",
            "stage": "Queued...",
            "video_url": None,
            "error": None,
            "created_at": time.time(),
        }

    thread = threading.Thread(
        target=_run_generation_job,
        args=(job_id, topic, aspect_ratio, language),
        daemon=True,
    )
    thread.start()

    return jsonify({"success": True, "job_id": job_id})


@app.route("/api/job-status/<job_id>")
def job_status(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        return jsonify({"success": False, "error": "Unknown job_id (it may have expired)."}), 404
    return jsonify({"success": True, **job})


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=debug_mode, threaded=True)
