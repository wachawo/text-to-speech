#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline TTS engine backed by Silero torch.hub models.

Fast on CPU with excellent quality; ships voices for Russian, English,
German, Spanish, French, Ukrainian and more.
"""

import io
import logging
import os
import wave

import numpy as np

# Local imports
from libs.exceptions import EngineNotAvailableError, TTSException, ValidationError

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

# Silero is fast offline; protect single calls from runaway memory.
MAX_TEXT_LENGTH = 50_000

# Cache loaded models by (model_id, device) to avoid re-running torch.hub.load
# on every call. Mirrors engines/coquitts.py:TTS_CACHE. Without this, each
# synthesis re-instantiates the model (seconds), defeating Silero's fast path.
TTS_CACHE: dict = {}

# Try to import Silero dependencies
try:
    # torchaudio is no longer used for encoding (see generate()), but is kept as
    # an availability probe: it is part of Silero's dependency footprint.
    import torch  # type: ignore
    import torchaudio  # type: ignore  # noqa: F401

    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    logger.warning("Silero TTS not available. Install with: pip install torch torchaudio")


def is_available() -> bool:
    """Check if Silero TTS is available."""
    return AVAILABLE


def get_model_info(language: str = "en") -> tuple:
    """
    Get model information for language.

    Args:
        language: Language code

    Returns:
        Tuple of (model_id, speaker, sample_rate)
    """
    language_models = {
        "ru": ("v3_1_ru", "aidar", 48000),  # Russian (excellent quality)
        "en": ("v3_en", "en_0", 48000),  # English
        "de": ("v3_de", "bernd_ungerer", 48000),  # German
        "es": ("v3_es", "es_0", 48000),  # Spanish
        "fr": ("v3_fr", "fr_0", 48000),  # French
        "ua": ("v3_ua", "mykyta", 48000),  # Ukrainian
        "uk": ("v3_ua", "mykyta", 48000),  # Ukrainian (alias)
    }

    # Default to English if language not found
    return language_models.get(language, language_models["en"])


def get_models_directory() -> str:
    """
    Get the directory for storing Silero models.

    Priority:
    1. Environment variable SILEROTTS_MODELS (from .env or export)
    2. cache/silerotts directory in project root (if exists)
    3. Default: ~/.cache/torch/hub/

    Returns:
        Path to models directory
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    env_var = os.environ.get("SILEROTTS_MODELS")
    if env_var:
        models_path = env_var.strip()
        # A relative override is anchored to the project root, not the cwd,
        # so `ttsgen` finds the same models from any working directory.
        if not os.path.isabs(models_path):
            models_path = os.path.join(project_root, models_path)
        return os.path.expanduser(models_path)

    silerotts_dir = os.path.join(project_root, "cache", "silerotts")
    if os.path.exists(silerotts_dir) and os.path.isdir(silerotts_dir):
        return silerotts_dir

    return os.path.expanduser("~/.cache/torch/hub")


def load_model(language: str) -> tuple:
    """Load (and cache) the Silero model for a language.

    Returns:
        Tuple of (model, default_speaker, sample_rate). The model is cached in
        TTS_CACHE by (model_id, device) so repeated calls are cheap.
    """
    model_id, default_speaker, sample_rate = get_model_info(language)
    device = torch.device("cpu")
    cache_key = (model_id, str(device))
    model = TTS_CACHE.get(cache_key)
    if model is None:
        models_dir = get_models_directory()
        if models_dir != os.path.expanduser("~/.cache/torch/hub"):
            torch.hub.set_dir(models_dir)
            logger.info(f"Using custom Silero models directory: {models_dir}")

        logger.info(f"Loading Silero {model_id} on {device} (first call)...")
        # torch.hub.load returns (model, example_text).
        # trust_repo=True suppresses the interactive y/n prompt that torch.hub
        # raises before executing hubconf.py from snakers4/silero-models. We
        # accept this exposure because: (1) the model itself is shipped from
        # the same repo, so refusing the prompt blocks all SileroTTS usage;
        # (2) the model directory is pinned via torch.hub.set_dir() to the
        # configured SILEROTTS_MODELS, so the fetched code only runs when the
        # user explicitly opts in by installing this engine.
        result = torch.hub.load(
            repo_or_dir="snakers4/silero-models",
            model="silero_tts",
            language=(language if language in ["ru", "en", "de", "es", "fr", "ua"] else "en"),
            speaker=model_id,
            verbose=False,
            trust_repo=True,
        )

        if isinstance(result, tuple) and len(result) >= 2:
            model = result[0]
        else:
            raise TTSException(f"Unexpected torch.hub.load result: {type(result)}")

        if model is None:
            raise TTSException("Silero model failed to load")

        if not hasattr(model, "apply_tts"):
            raise TTSException(f"Model has no apply_tts method. Model type: {type(model)}")

        # Note: model.to() returns None for some Silero models, use in-place
        model.to(device)
        TTS_CACHE[cache_key] = model

    return model, default_speaker, sample_rate


def list_voices(language: str = "en") -> dict:
    """List the speaker voices available for a language's Silero model.

    Returns:
        Dict with 'voices' (list of speaker ids, e.g. baya/kseniya for ru) and
        'default' (the speaker used when no voice is requested).
    """
    if not AVAILABLE:
        raise EngineNotAvailableError(
            "Silero TTS not available. Install with: pip install torch torchaudio\n"
            "See docs/SILEROTTS.md for setup instructions."
        )
    model, default_speaker, unused_rate = load_model(language)
    speakers = list(getattr(model, "speakers", []) or [])
    return {"voices": speakers, "default": default_speaker}


def generate(text: str, config: dict) -> bytes:
    """
    Generate TTS and return audio as bytes.

    Args:
        text: Text to synthesize
        config: Configuration dict with language and optional voice

    Returns:
        Audio bytes in WAV format (48000 Hz, 16-bit, mono)

    Raises:
        EngineNotAvailableError: torch / torchaudio are not installed.
        ValidationError: Text is too long, unpronounceable, or the voice is unknown.
        TTSException: Model could not be loaded, or synthesis failed.

    Note:
        First run will download the model from torch hub.
        Models are cached in:
        - SILERO_MODELS_DIR env variable (highest priority), or
        - cache/silerotts/ directory (if exists), or
        - ~/.cache/torch/hub/ (default fallback)
    """
    if not AVAILABLE:
        raise EngineNotAvailableError(
            "Silero TTS not available. Install with: pip install torch torchaudio\n"
            "See docs/SILEROTTS.md for setup instructions."
        )
    if len(text) > MAX_TEXT_LENGTH:
        raise ValidationError(f"Text too long for silerotts: {len(text)} > {MAX_TEXT_LENGTH}")
    language = config.get("language", "en")
    try:
        model, default_speaker, sample_rate = load_model(language)

        # Pick the speaker: requested voice or the language default. Validate
        # against the model's speaker list (when exposed) so an unknown voice is
        # a 400, not a confusing engine error.
        speaker = config.get("voice") or default_speaker
        speakers = getattr(model, "speakers", None)
        if speakers and speaker not in speakers:
            raise ValidationError(
                f"Unknown voice '{speaker}' for language '{language}'. " f"Available: {', '.join(sorted(speakers))}"
            )

        # Generate audio (float32 mono waveform in [-1, 1]).
        audio_tensor = model.apply_tts(text=text, speaker=speaker, sample_rate=sample_rate)

        # Encode WAV with the stdlib `wave` module instead of torchaudio.save():
        # in torchaudio >= 2.9 save() routes through the torchcodec backend, whose
        # encoder cannot write to a file-like object (it needs a real path +
        # extension) and raises "Couldn't allocate AVFormatContext" on a BytesIO.
        samples = audio_tensor.squeeze().detach().cpu().numpy()
        pcm16 = (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
        audio_buffer = io.BytesIO()
        with wave.open(audio_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm16)
        return audio_buffer.getvalue()

    except ValueError as exc:
        # Silero's process_simple_text raises a bare ValueError (no message) when
        # the text has no pronounceable content left after its internal cleaning:
        # digits/punctuation/whitespace only, or characters outside the model's
        # alphabet (e.g. Latin text routed to the Russian v3_1_ru model). This is
        # bad input, not an engine failure — raise ValidationError so the HTTP API
        # returns 400 instead of a 500 with a traceback.
        if str(exc):
            raise TTSException(f"Silero TTS generation failed: {exc}") from exc
        raise ValidationError(
            f"Silero TTS could not process the text for language '{language}': "
            "it contains no pronounceable characters for this model (e.g. only "
            "digits, punctuation, or characters from a different alphabet). "
            f"Text: {text!r}"
        ) from exc

    except ValidationError:
        # Unknown-voice (and text) validation errors are already actionable 400s —
        # do not wrap them as generic engine failures below.
        raise

    except Exception as exc:
        error_msg = str(exc)

        if "No module named" in error_msg or "cannot import" in error_msg:
            raise EngineNotAvailableError(
                "Silero TTS dependencies missing. Install with:\n"
                "   pip install torch torchaudio\n"
                "See docs/SILEROTTS.md for details."
            ) from exc

        if "model" in error_msg.lower() and "not found" in error_msg.lower():
            raise TTSException(f"Silero model not found for language.\n" f"Error: {exc}") from exc

        raise TTSException(f"Silero TTS generation failed: {exc}") from exc


def main():
    """Module entrypoint placeholder — this file is import-only."""
    pass


if __name__ == "__main__":
    main()
