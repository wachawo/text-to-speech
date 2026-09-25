#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline TTS engine backed by Silero torch.hub models.

Fast on CPU with excellent quality; ships voices for Russian, English,
German, Spanish, French, Ukrainian and more.
"""

import io
import logging
import os
import threading
import wave

import numpy as np

# Local imports
from libs.cached_loader import load_cached
from libs.exceptions import EngineNotAvailableError, TTSException, ValidationError
from libs.languages import primary_language

logger = logging.getLogger(__name__)

# Silero is fast offline; protect single calls from runaway memory.
MAX_TEXT_LENGTH = 50_000

# Cache loaded models by (model_id, device) to avoid re-running torch.hub.load
# on every call. Mirrors engines/coquitts.py:TTS_CACHE. Without this, each
# synthesis re-instantiates the model (seconds), defeating Silero's fast path.
TTS_CACHE: dict = {}
# TTS_CACHE_LOCK guards the first load (and the one-time torch.hub.set_dir) so
# concurrent first requests do not fetch the model twice. INFERENCE_LOCK
# serialises apply_tts: one Silero torch model is not safe to drive from
# several threads at once. The engine pool bounds synthesis across engines;
# this lock bounds this engine to one synthesis at a time.
TTS_CACHE_LOCK = threading.Lock()
INFERENCE_LOCK = threading.Lock()

# Silero model id -> (language key in snakers4/silero-models, default speaker,
# sample rate). The language key is what torch.hub.load expects as `language`.
MODEL_CATALOG: dict[str, tuple[str, str, int]] = {
    "v3_1_ru": ("ru", "aidar", 48000),  # Russian (excellent quality)
    "v3_en": ("en", "en_0", 48000),  # English
    "v3_de": ("de", "bernd_ungerer", 48000),  # German
    "v3_es": ("es", "es_0", 48000),  # Spanish
    "v3_fr": ("fr", "fr_0", 48000),  # French
    "v3_ua": ("ua", "mykyta", 48000),  # Ukrainian
}

# Request language -> model id. `uk` (ISO 639-1) is an alias for Silero's `ua`.
LANGUAGE_DEFAULT_MODELS: dict[str, str] = {
    "ru": "v3_1_ru",
    "en": "v3_en",
    "de": "v3_de",
    "es": "v3_es",
    "fr": "v3_fr",
    "ua": "v3_ua",
    "uk": "v3_ua",
}

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
        language: Language code; a tag such as 'ru-ru' is looked up by its
            primary subtag.

    Returns:
        Tuple of (model_id, speaker, sample_rate)
    """
    # Default to English if language not found
    model_id = LANGUAGE_DEFAULT_MODELS.get(primary_language(language), LANGUAGE_DEFAULT_MODELS["en"])
    unused_hub_language, speaker, sample_rate = MODEL_CATALOG[model_id]
    return model_id, speaker, sample_rate


def model_languages(model_id: str) -> list[str]:
    """Return the request languages served by a catalogued model: its hub language plus any alias ('ua' and 'uk')."""
    return sorted(language for language, default_id in LANGUAGE_DEFAULT_MODELS.items() if default_id == model_id)


def list_languages(model: str | None = None) -> list[str] | None:
    """Return the request languages that have a Silero model; any other code falls back to English.

    With `model`, the languages of that model, or None when it is not in MODEL_CATALOG.
    """
    if model is None:
        return sorted(LANGUAGE_DEFAULT_MODELS)
    if model not in MODEL_CATALOG:
        return None
    return model_languages(model)


def default_model(language: str | None = None) -> str | None:
    """Return the model a request without `model` uses for `language`.

    None when no language is given, since the model depends on it; an unknown
    language gets the English model, as get_model_info() does.
    """
    if language is None:
        return None
    return LANGUAGE_DEFAULT_MODELS.get(primary_language(language), LANGUAGE_DEFAULT_MODELS["en"])


def list_downloaded_files() -> set[str]:
    """Return the names of the `*.pt` files under the models directory (one walk, no torch)."""
    names: set[str] = set()
    for unused_root, unused_dirs, files in os.walk(get_models_directory()):
        names.update(name for name in files if name.endswith(".pt"))
    return names


def list_models() -> list[dict]:
    """Describe the catalogued Silero models; `installed` is True when `<id>.pt` is already downloaded.

    Only a directory walk: torch.hub is not called and no model is loaded, so
    a model that is not installed yet is downloaded on its first request, as
    the language defaults are today.
    """
    downloaded = list_downloaded_files()
    return [
        {"id": model_id, "languages": model_languages(model_id), "installed": f"{model_id}.pt" in downloaded}
        for model_id in MODEL_CATALOG
    ]


def get_hub_language(model_id: str) -> str:
    """Return the snakers4/silero-models language key that holds `model_id`.

    torch.hub.load looks the speaker up under this key, so it has to match the
    model rather than the request language: the `uk` alias loads `v3_ua`,
    which lives under `ua`.
    """
    hub_language, unused_speaker, unused_rate = MODEL_CATALOG[model_id]
    return hub_language


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


def resolve_model_info(language: str, model: str | None = None) -> tuple[str, str, int]:
    """Return (model_id, default_speaker, sample_rate) for a request.

    Args:
        language: Request language; picks the model when `model` is None.
        model: A model id from MODEL_CATALOG, or None for the language default.

    Raises:
        ValidationError: `model` is not in MODEL_CATALOG.
    """
    if model is None:
        model_id, speaker, sample_rate = get_model_info(language)
        return model_id, speaker, sample_rate
    if model not in MODEL_CATALOG:
        raise ValidationError(f"Unknown silerotts model '{model}'. Available: {', '.join(MODEL_CATALOG)}")
    unused_hub_language, speaker, sample_rate = MODEL_CATALOG[model]
    return model, speaker, sample_rate


def load_model(language: str, model: str | None = None) -> tuple:
    """Load (and cache) the Silero model for a language, or the model named by `model`.

    Returns:
        Tuple of (model, default_speaker, sample_rate). The model is cached in
        TTS_CACHE by (model_id, device) so repeated calls are cheap.

    Raises:
        ValidationError: `model` is not in MODEL_CATALOG.
    """
    model_id, default_speaker, sample_rate = resolve_model_info(language, model)
    device = torch.device("cpu")

    def load_silero():
        """Pin the torch hub directory, then fetch and check the model."""
        # torch.hub.load takes no directory argument; the hub dir is process
        # state set through set_dir, so it is set once here, under the lock,
        # and only when it differs from the current one.
        models_dir = get_models_directory()
        if models_dir != os.path.expanduser("~/.cache/torch/hub") and torch.hub.get_dir() != models_dir:
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
            language=get_hub_language(model_id),
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
        return model

    model = load_cached(TTS_CACHE, TTS_CACHE_LOCK, (model_id, str(device)), load_silero)
    return model, default_speaker, sample_rate


def list_voices(language: str = "en", model: str | None = None) -> dict:
    """List the speaker voices available for a language's Silero model, or for the model named by `model`.

    Unlike the discovery hooks this loads the model: the speakers are read
    from it.

    Returns:
        Dict with 'voices' (list of speaker ids, e.g. baya/kseniya for ru) and
        'default' (the speaker used when no voice is requested).
    """
    if not AVAILABLE:
        raise EngineNotAvailableError(
            "Silero TTS not available. Install with: pip install torch torchaudio\n"
            "See docs/SILEROTTS.md for setup instructions."
        )
    silero_model, default_speaker, unused_rate = load_model(language, model)
    speakers = list(getattr(silero_model, "speakers", []) or [])
    return {"voices": speakers, "default": default_speaker}


def generate(text: str, config: dict) -> bytes:
    """
    Generate TTS and return audio as bytes.

    Args:
        text: Text to synthesize
        config: Configuration dict with language, optional voice and optional
            model (a MODEL_CATALOG id; None picks the model by language)

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
        model, default_speaker, sample_rate = load_model(language, config.get("model"))

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
        with INFERENCE_LOCK:
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
