#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline ONNX TTS engine backed by kokoro-onnx (Kokoro 82M v1.0).

Multi-language (English/French/Italian/Japanese/Mandarin/Spanish/Hindi/Portuguese),
multi-voice, fast on CPU.

See: https://github.com/nazdridoy/kokoro-tts (CLI upstream this engine wraps)
     https://github.com/thewh1teagle/kokoro-onnx (Python bindings)
"""

import io
import logging
import os

# Local imports
from libs.exceptions import EngineNotAvailableError, TTSException, ValidationError

# Centralised config loader handles ./ttsgen.conf > ~/.config/ttsgen.conf > .env > defaults
try:
    from libs.config import load_config

    load_config()
except ImportError:
    pass  # libs.config or dotenv not available — engine will fall back to env / defaults.

logger = logging.getLogger(__name__)

# Kokoro is offline ONNX (~10x realtime CPU). Bound single calls so a runaway
# input doesn't blow memory; chunking remains the CLI's job.
MAX_TEXT_LENGTH = 50_000

DEFAULT_KOKOROTTS_MODELS = "cache/kokorotts"
DEFAULT_KOKOROTTS_MODEL = "kokoro-v1.0.onnx"
DEFAULT_KOKOROTTS_VOICES = "voices-v1.0.bin"
DEFAULT_KOKOROTTS_SPEED = 1.0

# 2-char ISO-ish code → (kokoro lang code, default voice).
# Voice list: https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md
LANGUAGE_MAP = {
    "en": ("en-us", "af_sarah"),
    "fr": ("fr-fr", "ff_siwis"),
    "it": ("it", "if_sara"),
    "ja": ("ja", "jf_alpha"),
    "zh": ("cmn", "zf_xiaobei"),
    "es": ("es", "ef_dora"),
    "hi": ("hi", "hf_alpha"),
    "pt": ("pt-br", "pf_dora"),
}

# Cache (model_path, voices_path) → Kokoro instance. Loading the ONNX model
# costs ~1-3s on CPU; reuse across calls within one process.
KOKORO_CACHE: dict = {}

# Both kokoro_onnx (ONNX runtime + model wrapper) and soundfile (WAV encoder)
# are required for synthesis. If either is missing the engine is unusable —
# report False from is_available() so `ttsgen --list` doesn't lie.
try:
    import soundfile  # type: ignore  # noqa: F401
    from kokoro_onnx import Kokoro  # type: ignore

    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    logger.warning("Kokoro TTS not available. Install with: ttsgen --install kokorotts")


def is_available() -> bool:
    """Check if Kokoro TTS is available."""
    return AVAILABLE


def get_models_directory() -> str:
    """
    Resolve directory containing kokoro-v1.0.onnx and voices-v1.0.bin.

    Priority:
    1. KOKOROTTS_MODELS env (from CLI flag, ttsgen.conf, .env)
    2. cache/kokorotts/ in project root (if exists)
    3. ~/.local/share/ttsgen/kokorotts (default)
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    env_var = os.environ.get("KOKOROTTS_MODELS", "").strip()
    if env_var:
        models_path = env_var
        if not os.path.isabs(models_path):
            models_path = os.path.join(project_root, models_path)
        return os.path.expanduser(models_path)

    project_dir = os.path.join(project_root, DEFAULT_KOKOROTTS_MODELS)
    if os.path.isdir(project_dir):
        return project_dir

    return os.path.expanduser("~/.local/share/ttsgen/kokorotts")


def get_model_paths() -> tuple[str, str]:
    """Return absolute paths to (model_file, voices_file)."""
    models_dir = get_models_directory()
    model_name = os.environ.get("KOKOROTTS_MODEL", DEFAULT_KOKOROTTS_MODEL).strip() or DEFAULT_KOKOROTTS_MODEL
    voices_name = os.environ.get("KOKOROTTS_VOICES", DEFAULT_KOKOROTTS_VOICES).strip() or DEFAULT_KOKOROTTS_VOICES
    return os.path.join(models_dir, model_name), os.path.join(models_dir, voices_name)


def get_download_instructions() -> str:
    """Generate user-facing instructions for downloading the model files."""
    models_dir = get_models_directory()
    base_url = "https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0"
    return (
        f"Kokoro TTS model files not found in {models_dir}.\n\n"
        f"Option 1 - Use installer (recommended):\n"
        f"   ttsgen --install kokorotts\n\n"
        f"Option 2 - Manual download:\n"
        f"   mkdir -p {models_dir}\n"
        f"   wget -P {models_dir} {base_url}/{DEFAULT_KOKOROTTS_MODEL}\n"
        f"   wget -P {models_dir} {base_url}/{DEFAULT_KOKOROTTS_VOICES}\n\n"
        f"See docs/KOKOROTTS.md for more details."
    )


def samples_to_wav_bytes(samples, sample_rate: int) -> bytes:
    """Encode numpy float samples to WAV bytes (16-bit PCM).

    `soundfile` import is guarded at module level in the AVAILABLE check,
    so by the time generate() reaches us we know it imports cleanly.
    """
    import soundfile as sf  # type: ignore

    buf = io.BytesIO()
    sf.write(buf, samples, sample_rate, format="WAV", subtype="PCM_16")
    buf.seek(0)
    return buf.getvalue()


def generate(text: str, config: dict) -> bytes:
    """
    Generate TTS and return audio as bytes.

    Args:
        text: Text to synthesize.
        config: Configuration dict with `language` (2-char code).

    Returns:
        Audio bytes in WAV format (24000 Hz, 16-bit PCM, mono).

    Raises:
        EngineNotAvailableError: kokoro-onnx / soundfile are not installed.
        ValidationError: Text exceeds MAX_TEXT_LENGTH.
        TTSException: Model files are missing, or synthesis failed.
    """
    if not AVAILABLE:
        raise EngineNotAvailableError(
            "Kokoro TTS not available. Install with:\n"
            "   ttsgen --install kokorotts\n"
            "See docs/KOKOROTTS.md for setup instructions."
        )
    if len(text) > MAX_TEXT_LENGTH:
        raise ValidationError(f"Text too long for kokorotts: {len(text)} > {MAX_TEXT_LENGTH}")

    language = config.get("language", "en")
    lang_code, default_voice = LANGUAGE_MAP.get(language, LANGUAGE_MAP["en"])

    voice = os.environ.get("KOKOROTTS_VOICE", "").strip() or default_voice
    try:
        speed = float(os.environ.get("KOKOROTTS_SPEED", "").strip() or DEFAULT_KOKOROTTS_SPEED)
    except ValueError:
        speed = DEFAULT_KOKOROTTS_SPEED

    model_path, voices_path = get_model_paths()
    if not os.path.exists(model_path) or not os.path.exists(voices_path):
        raise TTSException(get_download_instructions())

    cache_key = (model_path, voices_path)
    kokoro = KOKORO_CACHE.get(cache_key)
    if kokoro is None:
        logger.info(f"Loading Kokoro model: {model_path}")
        kokoro = Kokoro(model_path, voices_path)
        KOKORO_CACHE[cache_key] = kokoro

    try:
        samples, sample_rate = kokoro.create(text, voice=voice, speed=speed, lang=lang_code)
    except Exception as exc:
        raise TTSException(f"Kokoro TTS generation failed ({type(exc).__name__}): {exc}") from exc

    return samples_to_wav_bytes(samples, int(sample_rate))


def main():
    """Module entrypoint placeholder — this file is import-only."""
    pass


if __name__ == "__main__":
    main()
