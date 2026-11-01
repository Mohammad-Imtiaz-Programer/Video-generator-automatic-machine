"""
Visual Generator Module
---------------------------
Generates the scene image for a given (Shariah-modified) prompt using the
free-tier Hugging Face Inference API running Stable Diffusion 2.1.

Fallback handling (so the pipeline never crashes mid-render):
    - No HF token configured         -> skip the API call, use a local
                                         placeholder image.
    - API reports the model is still -> wait and retry, up to MAX_RETRIES
      "loading" (cold start, HTTP 503)  times.
    - API call fails for any other   -> fall back to the local placeholder.
      reason
"""

import os
import time
import requests
from PIL import Image, ImageDraw, ImageFont

HF_API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-2-1"
MAX_RETRIES = 3
RETRY_WAIT_SECONDS = 15
REQUEST_TIMEOUT = 60


class VisualGenerator:
    def __init__(self):
        self.hf_token = os.getenv("HUGGINGFACE_API_TOKEN", "")

    def _call_hf_api(self, prompt: str, negative_prompt: str, width: int, height: int, hf_token: str):
        headers = {"Authorization": f"Bearer {hf_token}"}
        payload = {
            "inputs": prompt,
            "parameters": {
                "negative_prompt": negative_prompt or "",
                # SD 2.1 is trained at <=1024px per side; we upscale to the
                # final aspect-ratio canvas afterwards.
                "width": min(width, 1024),
                "height": min(height, 1024),
            },
            "options": {"wait_for_model": True}
        }

        for _ in range(MAX_RETRIES):
            try:
                response = requests.post(
                    HF_API_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT
                )
                content_type = response.headers.get("content-type", "")
                if response.status_code == 200 and content_type.startswith("image"):
                    return response.content
                if response.status_code == 503:
                    # Model is warming up on Hugging Face's side — worth a retry.
                    time.sleep(RETRY_WAIT_SECONDS)
                    continue
                # Any other non-200 response: stop retrying, fall back.
                break
            except requests.RequestException:
                time.sleep(2)
                continue
        return None

    def _draw_placeholder(self, prompt: str, width: int, height: int, output_path: str) -> str:
        img = Image.new("RGB", (width, height), color=(30, 41, 59))
        draw = ImageDraw.Draw(img)
        text = f"Halal Scene\n{prompt[:60]}..."
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 28)
        except Exception:
            font = ImageFont.load_default()
        draw.multiline_text((40, height // 2 - 40), text, fill=(226, 232, 240), font=font, spacing=10)
        img.save(output_path)
        return output_path

    def generate_image(self, prompt: str, aspect_ratio: str, output_path: str, negative_prompt: str = "", hf_token_override: str = "") -> str:
        width, height = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)

        # একটা রিকোয়েস্টে পাঠানো (অ্যাপের Settings বক্সের) টোকেন থাকলে সেটাই
        # ব্যবহার হবে, না থাকলে .env-এর ডিফল্ট HUGGINGFACE_API_TOKEN।
        hf_token = hf_token_override or self.hf_token

        if hf_token:
            image_bytes = self._call_hf_api(prompt, negative_prompt, width, height, hf_token)
            if image_bytes:
                try:
                    with open(output_path, "wb") as f:
                        f.write(image_bytes)
                    Image.open(output_path).convert("RGB").resize((width, height)).save(output_path)
                    return output_path
                except Exception:
                    pass  # fall through to the placeholder below

        # Zero-cost fallback — guarantees the pipeline always produces an image.
        return self._draw_placeholder(prompt, width, height, output_path)
