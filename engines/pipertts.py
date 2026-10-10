#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline TTS engine backed by Piper ONNX voice models.

Fast, natural-sounding synthesis with voices for 50+ languages. Returns
WAV bytes; file I/O and playback belong to the API layer.
"""

import io
import logging
import os
import threading
import wave

# Local imports
from libs.cached_loader import load_cached
from libs.exceptions import EngineNotAvailableError, TTSException, ValidationError
from libs.models import models_directory

logger = logging.getLogger(__name__)

# Offline ONNX, ~300x realtime — large texts are fine but bound memory.
MAX_TEXT_LENGTH = 50_000

# Where the voices are published, pinned to one tag of rhasspy/piper-voices.
VOICES_BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"

# The one voice per language, and the only table of them: the engine selects
# by it, the download instructions name it and install/pipertts.py offers it.
# language -> (path under VOICES_BASE_URL, file basename, installer label)
VOICES = {
    "en": ("en/en_US/lessac/medium", "en_US-lessac-medium", "English (lessac, female)"),
    "ru": ("ru/ru_RU/ruslan/medium", "ru_RU-ruslan-medium", "Russian (ruslan, male)"),
    "es": ("es/es_ES/davefx/medium", "es_ES-davefx-medium", "Spanish (davefx)"),
    "de": ("de/de_DE/thorsten/medium", "de_DE-thorsten-medium", "German (thorsten)"),
    "fr": ("fr/fr_FR/siwis/medium", "fr_FR-siwis-medium", "French (siwis)"),
    "it": ("it/it_IT/paola/medium", "it_IT-paola-medium", "Italian (paola)"),
    "uk": ("uk/uk_UA/ukrainian_tts/medium", "uk_UA-ukrainian_tts-medium", "Ukrainian (ukrainian_tts)"),
    "zh": ("zh/zh_CN/huayan/medium", "zh_CN-huayan-medium", "Chinese (huayan)"),
}

# Try to import Piper
try:
    from piper import PiperVoice  # type: ignore

    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    logger.warning("Piper TTS not available. Install with: pip install piper-tts")

# Process-wide PiperVoice cache keyed by absolute voice path. ONNX session
# load is ~1.5s on CPU even for medium voices; reload on every request
# dwarfs the synthesis itself (issue #11). Safe to share across requests.
VOICE_CACHE: dict = {}
VOICE_CACHE_LOCK = threading.Lock()
# One cached PiperVoice serves every request, and its per-call settings fall
# back to the shared voice.config, so one synthesis at a time per process.
INFERENCE_LOCK = threading.Lock()


def get_voice(voice_path: str):
    """Return cached PiperVoice for `voice_path`, loading lazily.

    Cache key is the normalised absolute path so a relative fallback
    (e.g. `./voices/en.onnx`) and an absolute path that resolve to the
    same file don't load the same ONNX twice. Double-checked locking
    so two concurrent first-time requests don't both pay the load cost.
    """
    key = os.path.abspath(os.path.expanduser(voice_path))
    return load_cached(VOICE_CACHE, VOICE_CACHE_LOCK, key, lambda: PiperVoice.load(key))


def is_available() -> bool:
    """Check if Piper TTS is available."""
    return AVAILABLE


def get_models_directory() -> str:
    """
    Get the directory for storing Piper TTS models.

    Priority (libs.models.models_directory):
    1. Environment variable PIPERTTS_MODELS (from .env or export); a relative
       value is anchored on the project root, not the cwd
    2. cache/pipertts directory in project root (if exists)
    3. Default: .piper/voices in project root

    Returns:
        Path to models directory
    """
    return models_directory("pipertts")


def get_voice_path(language: str = "en") -> str:
    """Resolve the .onnx voice file to use for a language.

    Args:
        language: Two-character language code; unknown codes fall back to English.

    Returns:
        Path to the voice model. The path of the configured models directory is
        returned even when no file exists there, so callers can report a precise
        FileNotFoundError with download instructions.
    """
    voice_name = VOICES.get(language, VOICES["en"])[1]

    models_dir = get_models_directory()

    # The configured models directory wins when it holds the voice.
    voice_path = os.path.join(models_dir, f"{voice_name}.onnx")
    if os.path.exists(voice_path):
        return voice_path

    # Fallback: check other common locations
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    voice_dirs = [
        os.path.join(project_root, ".piper", "voices"),  # Project directory
        os.path.join(os.path.expanduser("~"), ".local", "share", "piper", "voices"),  # User home
        "/usr/share/piper/voices",  # System-wide
        "./voices",  # Current directory
    ]

    for voice_dir in voice_dirs:
        voice_path = os.path.join(voice_dir, f"{voice_name}.onnx")
        if os.path.exists(voice_path):
            return voice_path

    # Nothing on disk — point at the configured directory so the error message
    # names the place the installer would populate.
    return os.path.join(models_dir, f"{voice_name}.onnx")


def get_download_instructions(language: str) -> str:
    """Build the multi-option help text shown when a voice model is missing.

    Args:
        language: Two-character language code; unknown codes describe the English voice.

    Returns:
        Human-readable instructions covering the installer, wget and curl.
    """
    model_path, model_name, unused_label = VOICES.get(language, VOICES["en"])

    base_url = VOICES_BASE_URL

    voice_dir = get_models_directory()

    return (
        f"Piper voice model not found for language '{language}'.\n\n"
        f"Option 1 - Use installer (recommended):\n"
        f"   ttsgen --install pipertts\n\n"
        f"Option 2 - Manual download with wget:\n"
        f"   mkdir -p {voice_dir}\n"
        f"   wget -P {voice_dir} {base_url}/{model_path}/{model_name}.onnx\n"
        f"   wget -P {voice_dir} {base_url}/{model_path}/{model_name}.onnx.json\n\n"
        f"Option 3 - Manual download with curl:\n"
        f"   mkdir -p {voice_dir}\n"
        f"   curl -L -o {voice_dir}/{model_name}.onnx {base_url}/{model_path}/{model_name}.onnx\n"
        f"   curl -L -o {voice_dir}/{model_name}.onnx.json {base_url}/{model_path}/{model_name}.onnx.json\n\n"
        f"See docs/PIPERTTS.md for more details"
    )


def generate(text: str, config: dict) -> bytes:
    """
    Generate TTS and return audio as bytes.

    Args:
        text: Text to synthesize
        config: Configuration dict with language

    Returns:
        Audio bytes in WAV format (22050 Hz, mono, 16-bit)

    Raises:
        EngineNotAvailableError: piper-tts is not installed.
        ValidationError: Text exceeds MAX_TEXT_LENGTH.
        TTSException: Voice model missing, or synthesis failed.
    """
    if not AVAILABLE:
        raise EngineNotAvailableError(
            "Piper TTS not available. Install with: pip install piper-tts\n" "See docs/PIPERTTS.md for setup instructions."
        )
    if len(text) > MAX_TEXT_LENGTH:
        raise ValidationError(f"Text too long for pipertts: {len(text)} > {MAX_TEXT_LENGTH}")
    language = config.get("language", "en")
    try:
        voice_path = get_voice_path(language)
        logger.info(f"Piper voice: {voice_path}")

        # Cached load: PiperVoice.load is the dominant cost (~1.5s); the
        # cache turns subsequent calls into pure synthesis (~tens of ms).
        voice = get_voice(voice_path)

        # Generate audio to BytesIO
        audio_buffer = io.BytesIO()
        with INFERENCE_LOCK, wave.open(audio_buffer, "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)

        audio_buffer.seek(0)
        return audio_buffer.getvalue()

    except FileNotFoundError as exc:
        instructions = get_download_instructions(language)
        raise TTSException(f"{instructions}\n\nError: {exc}") from exc
    except Exception as exc:
        raise TTSException(f"Piper TTS generation failed: {exc}") from exc


def main():
    """Module entrypoint placeholder — this file is import-only."""
    pass


if __name__ == "__main__":
    main()
