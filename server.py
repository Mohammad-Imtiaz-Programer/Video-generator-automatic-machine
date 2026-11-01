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

Every job gets its own UUID-named folder under /assets, so concurrent
requests never collide, and the final .mp4 is served statically from
/output/<filename>.
"""

import os
import uuid
import traceback
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from core_engine import (
    ScriptGenerator, PromptModifier, VoiceGenerator,
    VisualGenerator, SafetyFilter, VideoRenderer
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_FOLDER = os.path.join(BASE_DIR, "frontend_ui")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = Flask(__name__, static_folder=FRONTEND_FOLDER, template_folder=FRONTEND_FOLDER)
CORS(app)

# Engine components are instantiated once and reused across requests.
script_gen = ScriptGenerator()
prompt_mod = PromptModifier()
voice_gen = VoiceGenerator()
visual_gen = VisualGenerator()
safety_filter = SafetyFilter()
renderer = VideoRenderer()

VALID_ASPECT_RATIOS = {"9:16", "16:9"}
VALID_LANGUAGES = {"en", "bn"}
MAX_TOPIC_LENGTH = 500


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


@app.route("/api/generate-video", methods=["POST"])
def generate_video():
    data = request.get_json(silent=True) or {}
    topic = (data.get("topic") or "").strip()
    aspect_ratio = data.get("aspect_ratio", "16:9")
    language = data.get("language", "en")

    # ঐচ্ছিক: অ্যাপের Settings বক্স থেকে পাঠানো API কী। খালি থাকলে নিচের
    # জেনারেটরগুলো নিজে থেকেই .env-এর ডিফল্ট কী (থাকলে) ব্যবহার করবে।
    gemini_api_key = (data.get("gemini_api_key") or "").strip()
    huggingface_api_token = (data.get("huggingface_api_token") or "").strip()

    if not topic:
        return jsonify({"success": False, "error": "A story topic is required."}), 400
    if len(topic) > MAX_TOPIC_LENGTH:
        return jsonify({"success": False, "error": f"Topic must be under {MAX_TOPIC_LENGTH} characters."}), 400
    if aspect_ratio not in VALID_ASPECT_RATIOS:
        return jsonify({"success": False, "error": "Invalid aspect_ratio."}), 400
    if language not in VALID_LANGUAGES:
        return jsonify({"success": False, "error": "Invalid language."}), 400

    job_id = str(uuid.uuid4())[:8]
    job_dir = os.path.join(ASSETS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    try:
        scenes = script_gen.generate_script(topic, language, api_key_override=gemini_api_key)
        processed_scenes = []

        for scene in scenes:
            scene_id = scene["scene_id"]
            raw_prompt = scene["visual_prompt"]
            dialogue = scene["dialogue"]

            enhanced_prompt, negative_prompt = prompt_mod.apply_shariah_rules(raw_prompt)

            audio_path = os.path.join(job_dir, f"scene_{scene_id}.mp3")
            voice_gen.generate_voiceover(dialogue, audio_path, language)

            raw_image_path = os.path.join(job_dir, f"scene_{scene_id}.png")
            visual_gen.generate_image(
                enhanced_prompt, aspect_ratio, raw_image_path,
                negative_prompt=negative_prompt, hf_token_override=huggingface_api_token
            )

            safe_image_path = safety_filter.enforce_face_safety(raw_image_path)

            processed_scenes.append({
                "scene_id": scene_id,
                "image_path": safe_image_path,
                "audio_path": audio_path
            })

        final_filename = f"halal_cartoon_{job_id}.mp4"
        final_path = os.path.join(OUTPUT_DIR, final_filename)
        renderer.render_final_video(processed_scenes, final_path, aspect_ratio)

        return jsonify({
            "success": True,
            "video_url": f"/output/{final_filename}",
            "job_id": job_id
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
