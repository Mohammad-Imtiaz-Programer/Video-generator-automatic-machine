"""
Core Engine package initializer.

Scene-processing modules are numbered (01_script_generator.py,
02_prompt_modifier.py, ...) so their filenames read as a clear pipeline
order in a file browser. A name that starts with a digit isn't a valid
Python identifier though, so these files can't be imported with a plain
`import core_engine.01_script_generator` statement.

This loader uses importlib to load each numbered file directly by its
path and re-exports the class it defines, so the rest of the app can
simply do:

    from core_engine import ScriptGenerator, PromptModifier, ...
"""

import importlib.util
import os

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_class(file_name: str, class_name: str, module_alias: str):
    file_path = os.path.join(_PACKAGE_DIR, file_name)
    spec = importlib.util.spec_from_file_location(f"core_engine.{module_alias}", file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, class_name)


ScriptGenerator = _load_class("01_script_generator.py", "ScriptGenerator", "script_generator")
PromptModifier = _load_class("02_prompt_modifier.py", "PromptModifier", "prompt_modifier")
VoiceGenerator = _load_class("03_voice_generator.py", "VoiceGenerator", "voice_generator")
VisualGenerator = _load_class("04_visual_generator.py", "VisualGenerator", "visual_generator")
SafetyFilter = _load_class("05_safety_filter.py", "SafetyFilter", "safety_filter")
VideoRenderer = _load_class("06_video_renderer.py", "VideoRenderer", "video_renderer")

__all__ = [
    "ScriptGenerator", "PromptModifier", "VoiceGenerator",
    "VisualGenerator", "SafetyFilter", "VideoRenderer",
]
