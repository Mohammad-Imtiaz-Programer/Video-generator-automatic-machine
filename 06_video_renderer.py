"""
Video Renderer Module
---------------------------
Takes every scene's (image, voiceover-audio) pair and renders the final
.mp4: each image is shown for exactly the duration of its own voiceover,
every scene is concatenated in order, and the result is exported with
H.264 video / AAC audio.

Ambient sound (optional, zero-cost, never music):
    Per the Shariah audio rule, background MUSIC is never mixed in — that
    rule is not negotiable. If you'd like natural ambient sound (wind,
    water, birds, etc.) under the narration, drop your own royalty-free
    .mp3/.wav files into /assets/ambient/. When that folder has files, one
    is picked at random for each run, trimmed to the voiceover's length,
    and mixed in at low volume under the voice. If the folder is empty (the
    default), the final video has pure voiceover only, which is always a
    safe, compliant option.
"""

import os
import random
import glob
from moviepy.editor import (
    ImageClip, AudioFileClip, CompositeAudioClip, concatenate_videoclips
)

AMBIENT_VOLUME = 0.12  # kept low so it never competes with the voiceover


class VideoRenderer:
    def _ambient_dir(self) -> str:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, "assets", "ambient")

    def _pick_ambient_track(self):
        ambient_dir = self._ambient_dir()
        tracks = glob.glob(os.path.join(ambient_dir, "*.mp3")) + \
            glob.glob(os.path.join(ambient_dir, "*.wav"))
        return random.choice(tracks) if tracks else None

    def _build_scene_audio(self, voice_clip, duration: float):
        ambient_path = self._pick_ambient_track()
        if not ambient_path:
            return voice_clip
        try:
            ambient_raw = AudioFileClip(ambient_path)
            ambient_clip = ambient_raw.subclip(0, min(duration, ambient_raw.duration)).volumex(AMBIENT_VOLUME)
            return CompositeAudioClip([ambient_clip, voice_clip]).set_duration(duration)
        except Exception:
            return voice_clip  # ambient track failed to load -> voice only

    def render_final_video(self, scene_data: list, output_filepath: str, aspect_ratio: str = "16:9") -> str:
        if not scene_data:
            raise ValueError("No scenes to render.")

        width, height = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
        clips = []

        for scene in scene_data:
            voice_clip = AudioFileClip(scene["audio_path"])
            duration = voice_clip.duration
            final_audio = self._build_scene_audio(voice_clip, duration)

            image_clip = (
                ImageClip(scene["image_path"])
                .set_duration(duration)
                .set_audio(final_audio)
                .resize((width, height))
            )
            clips.append(image_clip)

        final_video = concatenate_videoclips(clips, method="compose")
        os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
        final_video.write_videofile(
            output_filepath, fps=24, codec="libx264", audio_codec="aac", logger=None
        )

        for clip in clips:
            clip.close()
        final_video.close()
        return output_filepath
