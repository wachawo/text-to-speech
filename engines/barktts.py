#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ultra-realistic TTS engine backed by Suno's Bark models.

Supports emotions, laughter, music and sound effects. Very slow on CPU and
memory hungry (10GB+ of model weights) — best used with a GPU.
"""

import logging
import os

# Local imports
from libs.exceptions import EngineNotAvailableError, TTSException, ValidationError
from libs.tempfiles import safe_unlink

# .env via find_dotenv (walks up from cwd) → then .env.local override.
try:
    from dotenv import find_dotenv, load_dotenv

    found = find_dotenv(usecwd=True)
    if found:
        load_dotenv(found)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_env_file = os.path.join(project_root, ".env.local")
    if os.path.exists(local_env_file):
        load_dotenv(local_env_file, override=True)
except ImportError:
    pass  # dotenv not installed, skip

logger = logging.getLogger(__name__)

# Bark generates ~14s of audio per minute on CPU; 5k chars is already heavy.
MAX_TEXT_LENGTH = 5_000

# Try to import Bark
try:
    import numpy as np
    from bark import SAMPLE_RATE, generate_audio, preload_models

    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    logger.warning("Bark TTS not available. Install with: pip install git+https://github.com/suno-ai/bark.git")


def is_available() -> bool:
    """Check if Bark TTS is available."""
    return AVAILABLE


def get_models_directory() -> str:
    """
    Get the directory for storing Bark TTS models.

    Priority:
    1. Environment variable BARKTTS_MODELS (from .env or export)
    2. cache/barktts directory in project root (if exists)
    3. Default: ~/.cache/suno/bark_v0

    Returns:
        Path to models directory
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    env_var = os.environ.get("BARKTTS_MODELS")
    if env_var:
        models_path = env_var.strip()
        # A relative override is anchored to the project root, not the cwd,
        # so `ttsgen` finds the same models from any working directory.
        if not os.path.isabs(models_path):
            models_path = os.path.join(project_root, models_path)
        return os.path.expanduser(models_path)

    barktts_dir = os.path.join(project_root, "cache", "barktts")
    if os.path.exists(barktts_dir) and os.path.isdir(barktts_dir):
        return barktts_dir

    return os.path.expanduser("~/.cache/suno/bark_v0")


def get_speaker_for_language(language: str) -> str:
    """
    Get appropriate speaker/voice for language.

    Bark uses speaker presets in format: v2/{language}_speaker_{number}

    Args:
        language: Language code

    Returns:
        Speaker preset string
    """
    speaker_map = {
        "en": "v2/en_speaker_6",  # English (clear female)
        "ru": "v2/ru_speaker_0",  # Russian
        "es": "v2/es_speaker_0",  # Spanish
        "de": "v2/de_speaker_0",  # German
        "fr": "v2/fr_speaker_0",  # French
        "zh": "v2/zh_speaker_0",  # Chinese
        "ja": "v2/ja_speaker_0",  # Japanese
        "ko": "v2/ko_speaker_0",  # Korean
        "hi": "v2/hi_speaker_0",  # Hindi
        "it": "v2/it_speaker_0",  # Italian
        "pt": "v2/pt_speaker_0",  # Portuguese
        "pl": "v2/pl_speaker_0",  # Polish
        "tr": "v2/tr_speaker_0",  # Turkish
    }

    return speaker_map.get(language, speaker_map["en"])


def generate(text: str, config: dict) -> bytes:
    """
    Generate TTS and return audio as bytes.

    Args:
        text: Text to synthesize (can include [laugh], [sigh], ♪ for music, etc.)
        config: Configuration dict with language

    Returns:
        Audio bytes in WAV format (24000 Hz, mono, 32-bit float)

    Raises:
        EngineNotAvailableError: Bark or one of its dependencies is missing.
        ValidationError: Text exceeds MAX_TEXT_LENGTH.
        TTSException: Out of GPU/host memory, or synthesis failed.

    Note:
        First run downloads models (10GB+), can take time.
        Generation is VERY slow on CPU (30-60s per sentence).
        Use GPU for practical speed.

    Special syntax:
        - [laugh] - Add laughter
        - [sigh] - Add sigh
        - ♪ music notes ♪ - Add music/singing
        - CAPITALIZATION - Emphasis
        - ... - Pauses
    """
    if not AVAILABLE:
        raise EngineNotAvailableError(
            "Bark TTS not available. Install with:\n"
            "   pip install git+https://github.com/suno-ai/bark.git\n"
            "See docs/BARKTTS.md for setup instructions."
        )

    if len(text) > MAX_TEXT_LENGTH:
        raise ValidationError(f"Text too long for barktts: {len(text)} > {MAX_TEXT_LENGTH}")

    try:
        # scipy/tempfile/torch are imported lazily: they are only needed on the
        # synthesis path, and Bark's stack is heavy enough that `ttsgen --list`
        # should not pay for it.
        import tempfile

        import scipy.io.wavfile

        language = config.get("language", "en")

        models_dir = get_models_directory()
        if models_dir != os.path.expanduser("~/.cache/suno/bark_v0"):
            # Bark resolves its weights under $XDG_CACHE_HOME/suno/bark_v0, so
            # point XDG_CACHE_HOME at the grandparent of the configured directory.
            cache_dir = os.path.dirname(os.path.dirname(models_dir))
            os.environ["XDG_CACHE_HOME"] = cache_dir
            logger.info(f"Using custom Bark TTS models directory: {models_dir}")

        # Fix for PyTorch 2.6+ weights_only security issue.
        # Bark checkpoints need these numpy globals allow-listed (actual
        # objects, not strings) or torch.load refuses to unpickle them.
        import torch

        torch_version = tuple(map(int, torch.__version__.split(".")[:2]))
        if torch_version >= (2, 6):
            torch.serialization.add_safe_globals([np.core.multiarray.scalar, np.dtype])

        # First run downloads the weights; later runs load them from cache.
        preload_models()

        history_prompt = get_speaker_for_language(language)

        # Bark returns a numpy waveform sampled at SAMPLE_RATE (24000 Hz).
        audio_array = generate_audio(text, history_prompt=history_prompt, text_temp=0.7, waveform_temp=0.7)

        # scipy.io.wavfile.write needs a real path, so encode through a
        # temporary file and hand the caller the resulting bytes.
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_filename = temp_file.name

        try:
            scipy.io.wavfile.write(temp_filename, SAMPLE_RATE, audio_array)

            with open(temp_filename, "rb") as f:
                audio_bytes = f.read()

            return audio_bytes
        finally:
            safe_unlink(temp_filename)

    except Exception as exc:
        error_msg = str(exc)

        if "No module named" in error_msg or "cannot import" in error_msg:
            raise EngineNotAvailableError(
                "Bark TTS dependencies missing. Install with:\n"
                "   pip install git+https://github.com/suno-ai/bark.git\n"
                "   pip install scipy\n"
                "See docs/BARKTTS.md for details."
            ) from exc

        if "CUDA" in error_msg or "GPU" in error_msg or "memory" in error_msg.lower():
            raise TTSException(
                f"Bark TTS GPU/memory error.\n"
                f"Bark requires significant memory (10GB+ for models).\n"
                f"Consider using CPU with smaller models or use different engine.\n"
                f"Error: {exc}"
            ) from exc

        raise TTSException(f"Bark TTS generation failed: {exc}") from exc


def main():
    """Module entrypoint placeholder — this file is import-only."""
    pass


if __name__ == "__main__":
    main()
