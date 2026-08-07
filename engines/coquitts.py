#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Voice-cloning TTS engine backed by the Idiap community fork of Coqui TTS.

Supports multi-speaker and multilingual models (xtts_v2 by default) and needs
Python 3.11+ with `coqui-tts` and `transformers>=4.46,<5.0`. Works best with a
GPU; CPU mode is very slow.
"""

import logging
import os
import tempfile

from libs.exceptions import CustomError, EngineNotAvailableError, TTSException, ValidationError
from libs.sample_resolver import resolve_sample_path
from libs.tempfiles import safe_unlink

# Coqui xtts_v2 is the slowest engine but voice-cloning works on book-length text.
# Kept high deliberately — chunking and pacing are the caller's job.
MAX_TEXT_LENGTH = 1_000_000

# .env via find_dotenv (walks up from cwd) then .env.local override.
try:
    from dotenv import find_dotenv, load_dotenv
except ImportError:

    def find_dotenv(*args, **kwargs):
        """Return an empty path when python-dotenv is not installed."""
        return ""

    def load_dotenv(*args, **kwargs):
        """Do nothing when python-dotenv is not installed."""
        pass


found = find_dotenv(usecwd=True)
if found:
    load_dotenv(found)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
local_env_file = os.path.join(project_root, ".env.local")
if os.path.exists(local_env_file):
    load_dotenv(local_env_file, override=True)

logger = logging.getLogger(__name__)

DEFAULT_COQUITTS_MODELS = "cache/coquitts"
DEFAULT_COQUITTS_MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"
# Single source of truth shared with `ttsrec`. A fresh `ttsrec` writes here,
# `ttsgen --engine coquitts` reads from here. Override via COQUITTS_SAMPLE.
DEFAULT_COQUITTS_SAMPLE = str(os.path.expanduser("~/.config/ttsgen.wav"))

# Cache TTS instances by (model_name, device) to avoid 15s reload of xtts_v2
# checkpoint on every synthesis call. Keyed by tuple → instance.
TTS_CACHE: dict = {}

# Heavy/optional deps (torch + the Idiap `coqui-tts` fork) live inside the
# try/except so the module still imports with AVAILABLE=False when they're
# absent — the engine-plugin contract. generate() uses these as module globals.
try:
    import torch
    from torch.serialization import add_safe_globals, safe_globals
    from TTS.api import TTS
    from TTS.config.shared_configs import BaseDatasetConfig
    from TTS.tts.configs.xtts_config import XttsConfig
    from TTS.tts.models.xtts import XttsArgs, XttsAudioConfig

    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    logger.warning("Coqui TTS not available. Install with: pip install coqui-tts[codec]")


def is_available() -> bool:
    """Report whether torch and the coqui-tts fork are installed."""
    return AVAILABLE


def get_models_directory() -> str:
    """Resolve the absolute directory holding the Coqui model checkpoints.

    Returns:
        COQUITTS_MODELS when set, else a project-local `cache/coquitts` if it
        exists, else the Coqui default `~/.local/share/tts`.
    """
    coquitts_path = os.getenv("COQUITTS_MODELS", DEFAULT_COQUITTS_MODELS)
    if coquitts_path:
        return os.path.abspath(os.path.expanduser(coquitts_path))
    local_dir = os.path.join(os.getcwd(), "cache", "coquitts")
    if os.path.isdir(local_dir):
        return os.path.abspath(local_dir)
    return os.path.abspath(os.path.expanduser("~/.local/share/tts"))


def generate(text: str, config: dict) -> bytes:
    """Synthesize text by cloning the configured voice sample.

    The model is loaded once per (model, device) pair and kept in TTS_CACHE;
    the first call downloads the checkpoint if needed and takes ~15s.

    Args:
        text: Text to synthesize.
        config: Configuration dict with 'language'.

    Returns:
        Audio bytes in WAV format (22050 Hz by default).

    Raises:
        EngineNotAvailableError: Coqui TTS is not installed.
        ValidationError: Text exceeds MAX_TEXT_LENGTH.
        CustomError: The reference voice sample WAV is missing.
        TTSException: Model lookup or synthesis failed.
    """
    if not is_available():
        raise EngineNotAvailableError(
            "Coqui TTS not available. Install with: pip install TTS\nSee docs/COQUITTS.md for setup instructions."
        )
    if len(text) > MAX_TEXT_LENGTH:
        raise ValidationError(f"Text too long for coquitts: {len(text)} > {MAX_TEXT_LENGTH}")
    sample_wav = resolve_sample_path(os.getenv("COQUITTS_SAMPLE", DEFAULT_COQUITTS_SAMPLE))
    if not os.path.exists(sample_wav):
        raise CustomError(
            {
                "error": "voice_sample_missing",
                "message": (
                    f"Voice sample WAV not found: {sample_wav}\n"
                    f"\n"
                    f"xtts_v2 needs a 5-10s recording of a target voice. Create one with:\n"
                    f"    ttsrec                           # record into the configured path\n"
                    f"    ttsrec {sample_wav}\n"
                    f"    ttsrec /path/to/your_voice.wav\n"
                    f"\n"
                    f"Or set COQUITTS_SAMPLE in .env / .env.local to an existing recording."
                ),
                "path": sample_wav,
            }
        )
    try:
        language = config.get("language", "en")
        model_name = os.getenv("COQUITTS_MODEL", DEFAULT_COQUITTS_MODEL)
        models_dir = get_models_directory()
        # Coqui TTS uses TTS_HOME for model cache
        os.environ["TTS_HOME"] = models_dir
        os.environ["XDG_DATA_HOME"] = models_dir
        logger.info(f"Coqui TTS models directory: {models_dir}")
        try:
            add_safe_globals([XttsConfig, XttsAudioConfig, BaseDatasetConfig, XttsArgs])
        except Exception:
            pass
        device = "cuda" if torch.cuda.is_available() else "cpu"
        cache_key = (model_name, device)
        tts = TTS_CACHE.get(cache_key)
        if tts is None:
            logger.info(f"Loading {model_name} on {device} (first call — ~15s for xtts_v2)...")
            with safe_globals([XttsConfig, XttsAudioConfig, BaseDatasetConfig, XttsArgs]):
                tts = TTS(model_name=model_name, progress_bar=False).to(device)
            TTS_CACHE[cache_key] = tts
        # Coqui TTS can only write to a path, so synthesis goes through a scratch file.
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_filename = temp_file.name
        try:
            if "multilingual" in model_name:
                tts.tts_to_file(
                    text=text,
                    file_path=temp_filename,
                    language=language,
                    speaker_wav=sample_wav,
                )
            else:
                tts.tts_to_file(text=text, file_path=temp_filename)
            if not os.path.exists(temp_filename) or os.path.getsize(temp_filename) == 0:
                raise TTSException("Coqui TTS failed to generate audio")
            with open(temp_filename, "rb") as wav_file:
                return wav_file.read()
        finally:
            safe_unlink(temp_filename)
    except Exception as exc:
        if "model" in str(exc).lower() and "not found" in str(exc).lower():
            raise TTSException(f"Coqui TTS model not found.\nError: {exc}") from exc
        raise TTSException(f"Coqui TTS generation failed: {exc}") from exc


def main():
    """Module entrypoint placeholder — this file is import-only."""
    pass


if __name__ == "__main__":
    main()
