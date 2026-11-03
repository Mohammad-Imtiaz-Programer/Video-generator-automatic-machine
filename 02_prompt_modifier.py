"""
Prompt Modifier Module
---------------------------
Takes a raw scene `visual_prompt` from the script generator and rewrites
it according to /config/shariah_rules.json before it is sent to the image
generator: adult characters are described so they're framed without their
faces, child characters get the glowing/blurred-face treatment, and a
matching negative prompt is built so the image model is also told what to
avoid.
"""

import os
import json


class PromptModifier:
    def __init__(self, config_path: str = None):
        if not config_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config", "shariah_rules.json")
        with open(config_path, "r", encoding="utf-8") as f:
            self.rules = json.load(f)

    def apply_shariah_rules(self, raw_prompt: str) -> tuple:
        """Returns (enhanced_prompt, negative_prompt)."""
        shariah = self.rules.get("shariah_constraints", {})
        adult_framing = shariah.get("adult_characters", {}).get("framing", "")
        child_rule = shariah.get("child_characters", {}).get("facial_rule", "")
        global_negative = self.rules.get("global_negative_prompts", "")

        enhanced_prompt = (
            f"{raw_prompt}. Cartoon visual style. {adult_framing} {child_rule} "
            "No visible eyes, nose, or mouth."
        ).strip()

        return enhanced_prompt, global_negative
