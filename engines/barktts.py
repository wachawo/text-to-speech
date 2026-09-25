#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ultra-realistic TTS engine backed by Suno's Bark models.

Supports emotions, laughter, music and sound effects. Very slow on CPU and
memory hungry (10GB+ of model weights) — best used with a GPU.
"""

import logging
import os
import threading

# Local imports
from libs.cached_loader import load_cached
from libs.exceptions import EngineNotAvailableError, TTSException, ValidationError
from libs.languages import primary_language
from libs.tempfiles import safe_unlink

logger = logging.getLogger(__name__)

# Bark generates ~14s of audio per minute on CPU; 5k chars is already heavy.
MAX_TEXT_LENGTH = 5_000

# Language -> Bark speaker preset (v2/{language}_speaker_{number}).
SPEAKER_PRESETS = {
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

# Try to import Bark. scipy is part of the probe: generate() cannot encode
# the waveform without it, so `ttsgen --list` must not advertise the engine
# when it is missing.
try:
    import numpy as np
    import scipy.io.wavfile
    from bark import SAMPLE_RATE, generate_audio, preload_models

    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    logger.warning("Bark TTS not available. Install with: pip install git+https://github.com/suno-ai/bark.git")

# PRELOAD_LOCK guards the first preload_models() so concurrent first requests
# do not load the 10GB of weights twice; PRELOAD_CACHE holds a single "models"
# entry once they are in, and MODELS_PRELOADED mirrors it for callers that
# read a flag. INFERENCE_LOCK serialises generate_audio: Bark keeps its models
# in module globals and is not safe to drive from several threads at once.
# The engine pool bounds synthesis across engines; this lock bounds this
# engine to one synthesis at a time.
PRELOAD_LOCK = threading.Lock()
PRELOAD_CACHE: dict = {}
MODELS_PRELOADED = False
INFERENCE_LOCK = threading.Lock()


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
        language: Language code; a tag such as 'pt-br' is looked up by its
            primary subtag, and an unknown code gets the English speaker.

    Returns:
        Speaker preset string
    """
    return SPEAKER_PRESETS.get(primary_language(language), SPEAKER_PRESETS["en"])


def list_languages() -> list[str]:
    """Return the languages that have a Bark speaker preset; any other code gets the English speaker."""
    return sorted(SPEAKER_PRESETS)


def ensure_models_loaded() -> None:
    """Run Bark's preload_models() once per process, under the preload lock.

    Bark resolves its cache directory from XDG_CACHE_HOME when `bark.generation`
    is imported, which happened at engine import, so BARKTTS_MODELS cannot
    relocate the weights from here (see docs/BARKTTS.md); it is only reported.
    """

    def preload() -> bool:
        """Allow-list the numpy globals Bark checkpoints need, then preload."""
        global MODELS_PRELOADED
        models_dir = get_models_directory()
        if models_dir != os.path.expanduser("~/.cache/suno/bark_v0"):
            logger.info(f"BARKTTS_MODELS is {models_dir}, but Bark loads its weights from ~/.cache/suno/bark_v0")

        # Fix for PyTorch 2.6+ weights_only security issue.
        # Bark checkpoints need these numpy globals allow-listed (actual
        # objects, not strings) or torch.load refuses to unpickle them.
        # numpy 2.x moved `core` to `_core`; the old name only warns.
        import torch

        torch_version = tuple(map(int, torch.__version__.split(".")[:2]))
        if torch_version >= (2, 6):
            np_core = getattr(np, "_core", None) or np.core
            torch.serialization.add_safe_globals([np_core.multiarray.scalar, np.dtype])

        # First run downloads the weights; later runs load them from cache.
        preload_models()
        MODELS_PRELOADED = True
        return True

    load_cached(PRELOAD_CACHE, PRELOAD_LOCK, "models", preload)


def to_pcm16(audio_array):
    """Return a float waveform in -1..1 as int16 samples; anything else is passed through.

    Bark returns float32, and scipy would write a float WAV (format 3), which
    the stdlib `wave` module behind the streaming and history code cannot read.
    """
    samples = np.asarray(audio_array)
    if not np.issubdtype(samples.dtype, np.floating):
        return audio_array
    return (np.clip(samples, -1.0, 1.0) * 32767.0).astype(np.int16)


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
        # tempfile/torch are imported lazily: they are only needed on the
        # synthesis path, and Bark's stack is heavy enough that `ttsgen --list`
        # should not pay for it.
        import tempfile

        language = config.get("language", "en")

        ensure_models_loaded()

        history_prompt = get_speaker_for_language(language)

        # Bark returns a numpy waveform sampled at SAMPLE_RATE (24000 Hz).
        with INFERENCE_LOCK:
            audio_array = generate_audio(text, history_prompt=history_prompt, text_temp=0.7, waveform_temp=0.7)

        # scipy.io.wavfile.write needs a real path, so encode through a
        # temporary file and hand the caller the resulting bytes.
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_filename = temp_file.name

        try:
            scipy.io.wavfile.write(temp_filename, SAMPLE_RATE, to_pcm16(audio_array))

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
