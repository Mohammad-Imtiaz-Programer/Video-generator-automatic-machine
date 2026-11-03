"""
Script Generator Module
---------------------------
Splits a story topic into a short, multi-scene storyboard (one visual
prompt + one line of dialogue per scene) using the Gemini API, via
Google's unified `google-genai` SDK (the old `google-generativeai`
package was retired in late 2025 — see requirements.txt).

The API key is read fresh on every call via settings_store, so a key
saved from the web UI's Settings panel is picked up immediately — no
server restart or .env edit needed. If it's unset, unreachable, or the
response can't be parsed, this falls back to a safe, hard-coded 3-scene
script — the pipeline must never crash just because a key is missing or
a free-tier quota ran out.
"""

import os
import json

from core_engine.settings_store import get_setting

try:
    from google import genai
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False

# "gemini-flash-latest" is a Google-maintained alias that always points at
# the current recommended free-tier Flash model, so this keeps working as
# Google retires/renames individual model versions over time. Pin an exact
# version instead (e.g. "gemini-2.5-flash") via the GEMINI_MODEL env var if
# you need reproducible output across runs.
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
SCENE_COUNT = 3


class ScriptGenerator:
    def __init__(self):
        self._client = None
        self._client_key = None

    def _get_client(self):
        if not _GENAI_AVAILABLE:
            return None
        api_key = get_setting("gemini_api_key", env_fallback="GEMINI_API_KEY")
        if not api_key:
            return None
        if self._client is None or self._client_key != api_key:
            try:
                self._client = genai.Client(api_key=api_key)
                self._client_key = api_key
            except Exception:
                self._client = None
        return self._client

    def _fallback_script(self, topic: str) -> list:
        """Hard-coded, guaranteed-safe script used whenever the API is
        unavailable. Keeps the whole pipeline functional at zero cost."""
        return [
            {
                "scene_id": 1,
                "visual_prompt": f"A cartoon character seen from behind, walking through a peaceful garden, in a scene inspired by {topic}.",
                "dialogue": f"Welcome to our story about {topic}."
            },
            {
                "scene_id": 2,
                "visual_prompt": "Close-up of two hands placing a wrapped gift on a wooden table, warm lighting, no faces in frame.",
                "dialogue": "Doing good deeds brings light into our hearts."
            },
            {
                "scene_id": 3,
                "visual_prompt": "A peaceful sunset over a quiet village, wide shot, no human figures in frame.",
                "dialogue": "May peace and blessings be upon everyone."
            }
        ]

    def generate_script(self, topic: str, language: str = "en") -> list:
        client = self._get_client()
        if not client:
            return self._fallback_script(topic)

        lang_name = "Bengali" if language == "bn" else "English"
        prompt = (
            f"Act as an Islamic children's-story writer. Write a {SCENE_COUNT}-scene "
            f"storyboard on the topic: '{topic}'.\n"
            f"Write the dialogue in {lang_name}.\n"
            "Strict visual rules for every scene's visual_prompt: adult characters must "
            "be described only by their hands, torso, back, or lower body (never a face "
            "or head); child characters must have a blank glowing-white or blurred face "
            "area; never mention music or musical instruments — ambient nature sound only.\n"
            "Respond with raw JSON ONLY — a JSON array of objects, no markdown fences, "
            "no commentary — where each object has exactly these keys: "
            '"scene_id" (integer), "visual_prompt" (string), "dialogue" (string, in '
            f"{lang_name})."
        )

        try:
            response = client.models.generate_content(
                model=DEFAULT_MODEL,
                contents=prompt,
            )
            raw_text = (response.text or "").strip()

            # Models sometimes wrap JSON in ```json ... ``` despite instructions not to.
            if raw_text.startswith("```"):
                raw_text = raw_text.strip("`")
                if raw_text.lower().startswith("json"):
                    raw_text = raw_text[4:]

            scenes = json.loads(raw_text.strip())
            if isinstance(scenes, list) and len(scenes) > 0:
                return scenes
            return self._fallback_script(topic)
        except Exception:
            return self._fallback_script(topic)
