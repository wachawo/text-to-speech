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
import threading

from libs.cached_loader import load_cached
from libs.exceptions import CustomError, EngineNotAvailableError, TTSException, ValidationError
from libs.sample_resolver import list_sample_files, resolve_sample_path, sample_path_for_voice
from libs.tempfiles import safe_unlink

# Coqui xtts_v2 is the slowest engine but voice-cloning works on book-length text.
# Kept high deliberately — chunking and pacing are the caller's job.
MAX_TEXT_LENGTH = 1_000_000

logger = logging.getLogger(__name__)

DEFAULT_COQUITTS_MODELS = "cache/coquitts"
DEFAULT_COQUITTS_MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"
# Single source of truth shared with `ttsrec`. A fresh `ttsrec` writes here,
# `ttsgen --engine coquitts` reads from here. Override via COQUITTS_SAMPLE.
DEFAULT_COQUITTS_SAMPLE = str(os.path.expanduser("~/.config/ttsgen.wav"))

# Language codes xtts_v2 accepts (its config `languages`). Chinese is `zh-cn`,
# not the ISO 639-1 `zh` the rest of the project uses; see xtts_language().
XTTS_LANGUAGES = ("ar", "cs", "de", "en", "es", "fr", "hi", "hu", "it", "ja", "ko", "nl", "pl", "pt", "ru", "tr", "zh-cn")

# Cache TTS instances by (model_name, device) to avoid 15s reload of xtts_v2
# checkpoint on every synthesis call. Keyed by tuple → instance.
TTS_CACHE: dict = {}
# TTS_CACHE_LOCK guards the first load (and the one-time TTS_HOME setup) so
# concurrent first requests do not load the checkpoint twice. INFERENCE_LOCK
# serialises tts_to_file: one XTTS instance is not safe to drive from several
# threads at once. The engine pool bounds synthesis across engines; this lock
# bounds this engine to one synthesis at a time.
TTS_CACHE_LOCK = threading.Lock()
INFERENCE_LOCK = threading.Lock()

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


def xtts_language(language: str) -> str:
    """Map a request language to the code xtts expects.

    A code xtts lists is kept as is; Chinese (`zh`, or a `zh-*` tag xtts does
    not list) becomes `zh-cn`, since xtts rejects a bare `zh`; any other tag is
    reduced to its primary subtag ('pt-br' -> 'pt').
    """
    code = language.lower().replace("_", "-")
    if code in XTTS_LANGUAGES:
        return code
    primary = code.split("-", 1)[0]
    if primary == "zh":
        return "zh-cn"
    return primary


def list_languages() -> list[str] | None:
    """Return the languages the configured model (COQUITTS_MODEL) accepts, or None when that is not known.

    xtts lists its own codes plus `zh`, which xtts_language() sends as `zh-cn`;
    a single-language model such as `tts_models/de/thorsten/vits` accepts its
    language; any other multilingual model does not declare its languages here.
    """
    model_name = os.getenv("COQUITTS_MODEL", DEFAULT_COQUITTS_MODEL)
    if "xtts" in model_name and "multilingual" in model_name:
        return sorted([*XTTS_LANGUAGES, "zh"])
    parts = model_name.split("/")
    if len(parts) >= 2 and parts[0] == "tts_models" and parts[1] != "multilingual":
        return [parts[1]]
    return None


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


def get_tts(model_name: str, device: str):
    """Return the cached TTS instance for (model_name, device), loading it lazily.

    Double-checked locking so concurrent first-time requests load the
    checkpoint once. The models directory reaches Coqui only through the
    TTS_HOME environment variable (TTS.api.TTS builds its ModelManager without
    an output prefix), so it is set here, once, under the lock, and only when
    it differs from what is already in the environment.
    """

    def load_tts():
        """Point Coqui at the models directory, then load the checkpoint."""
        models_dir = get_models_directory()
        if os.environ.get("TTS_HOME") != models_dir:
            os.environ["TTS_HOME"] = models_dir
        logger.info(f"Coqui TTS models directory: {models_dir}")
        try:
            add_safe_globals([XttsConfig, XttsAudioConfig, BaseDatasetConfig, XttsArgs])
        except Exception:
            pass
        logger.info(f"Loading {model_name} on {device} (first call - ~15s for xtts_v2)...")
        with safe_globals([XttsConfig, XttsAudioConfig, BaseDatasetConfig, XttsArgs]):
            return TTS(model_name=model_name, progress_bar=False).to(device)

    return load_cached(TTS_CACHE, TTS_CACHE_LOCK, (model_name, device), load_tts)


def generate(text: str, config: dict) -> bytes:
    """Synthesize text by cloning the configured voice sample.

    The model is loaded once per (model, device) pair and kept in TTS_CACHE;
    the first call downloads the checkpoint if needed and takes ~15s.

    Args:
        text: Text to synthesize.
        config: Configuration dict with 'language' and optional 'voice' (a bare
            sample name under the samples directory, see
            libs.sample_resolver.sample_path_for_voice). Without 'voice' the
            COQUITTS_SAMPLE recording is cloned.

    Returns:
        Audio bytes in WAV format (22050 Hz by default).

    Raises:
        EngineNotAvailableError: Coqui TTS is not installed.
        ValidationError: Text exceeds MAX_TEXT_LENGTH or the voice name is invalid.
        CustomError: The reference voice sample WAV is missing.
        TTSException: Model lookup or synthesis failed.
    """
    if not is_available():
        raise EngineNotAvailableError(
            "Coqui TTS not available. Install with: pip install TTS\nSee docs/COQUITTS.md for setup instructions."
        )
    if len(text) > MAX_TEXT_LENGTH:
        raise ValidationError(f"Text too long for coquitts: {len(text)} > {MAX_TEXT_LENGTH}")
    voice = config.get("voice")
    if voice:
        sample_wav = sample_path_for_voice(voice)
        if not os.path.exists(sample_wav):
            raise CustomError(
                {
                    "error": "voice_sample_missing",
                    "message": f"Voice sample WAV not found for voice '{voice}': {sample_wav}",
                    "voice": voice,
                    "path": sample_wav,
                }
            )
    else:
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
        model_name = os.getenv("COQUITTS_MODEL", DEFAULT_COQUITTS_MODEL)
        language = config.get("language", "en")
        if "xtts" in model_name:
            language = xtts_language(language)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        tts = get_tts(model_name, device)
        # Coqui TTS can only write to a path, so synthesis goes through a scratch file.
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_filename = temp_file.name
        try:
            with INFERENCE_LOCK:
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


def list_voices(language: str = "en") -> dict:
    """List the sample WAV names selectable as `voice`, plus the default sample.

    Cheap on purpose: only a directory listing, no torch and no model load.

    Args:
        language: Ignored; cloned samples are not language-specific.

    Returns:
        Dict with 'voices' (sorted `*.wav` stems from the samples directory)
        and 'default' (stem of COQUITTS_SAMPLE, or None when it is unset).
    """
    default_sample = os.getenv("COQUITTS_SAMPLE")
    default = None
    if default_sample:
        default = os.path.basename(default_sample)
        if default.lower().endswith(".wav"):
            default = default[: -len(".wav")]
    return {"voices": list_sample_files(), "default": default}


def main():
    """Module entrypoint placeholder — this file is import-only."""
    pass


if __name__ == "__main__":
    main()
