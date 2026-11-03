"""
Voice Generator Module
---------------------------
Generates one voiceover .mp3 per scene using gTTS (Google Text-to-Speech)
— a free service that needs no API key, only outbound internet access.
Supports any language gTTS supports; the UI currently offers English
("en") and Bengali ("bn").
"""

import os
from gtts import gTTS


class VoiceGenerator:
    def generate_voiceover(self, text: str, output_path: str, lang: str = "en") -> str:
        if not text or not text.strip():
            raise ValueError("Cannot generate a voiceover for empty dialogue text.")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        try:
            tts = gTTS(text=text.strip(), lang=lang, slow=False)
            tts.save(output_path)
            return output_path
        except Exception as e:
            raise RuntimeError(f"Failed to generate voiceover (lang='{lang}'): {e}")
