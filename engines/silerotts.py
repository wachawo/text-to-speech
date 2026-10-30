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
from libs.cli import chunk_text
from libs.exceptions import EngineNotAvailableError, TTSException, ValidationError
from libs.models import models_directory

logger = logging.getLogger(__name__)

# Silero is fast offline; protect single calls from runaway memory.
MAX_TEXT_LENGTH = 50_000

# One apply_tts call voices at most 5000 mel frames, about 62.5 s of speech:
# every transformer in the v3 models adds a positional table of 5000 rows. The
# cap is on speech, not characters, so where it falls depends on the voice and
# the punctuation: ordinary English prose on en_1 stopped at about 780
# characters, "Oh... Oh... " at 250. Longer text is voiced in pieces of at most
# this many characters (cut at sentence, then comma, then word boundaries).
# Most text stays well under the cap at 150 characters, but not all: "Why? "
# repeated gave 53.7 s for 125 characters on en_1, so 150 of it run past. A
# piece Silero refuses as too long is cut again (see synthesize_piece) rather
# than refused, so this size only decides how often that happens.
SILERO_CHUNK_CHARS = 150

# Silero wraps EVERY RuntimeError of the model call, the speech cap and a real
# fault such as running out of memory alike, in one bare Exception whose
# message ends in SILERO_TOO_LONG. The message alone cannot tell bad input from
# a broken server; the RuntimeError it was raised while handling can: the cap
# is the 5000-row positional table failing to add to a longer sequence ("The
# size of tensor a (5519) must match the size of tensor b (5000) at
# non-singleton dimension 0", measured on v3_en and v3_1_ru).
SILERO_TOO_LONG = "probably it's too long"
SILERO_POSITION_CAP = "must match the size of tensor b (5000)"

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

    Priority (libs.models.models_directory):
    1. Environment variable SILEROTTS_MODELS (from .env or export); a relative
       value is anchored on the project root, not the cwd
    2. cache/silerotts directory in project root (if exists)
    3. Default: ~/.cache/torch/hub/

    Returns:
        Path to models directory
    """
    return models_directory("silerotts")


def load_model(language: str) -> tuple:
    """Load (and cache) the Silero model for a language.

    Returns:
        Tuple of (model, default_speaker, sample_rate). The model is cached in
        TTS_CACHE by (model_id, device) so repeated calls are cheap.
    """
    model_id, default_speaker, sample_rate = get_model_info(language)
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
            # The hub's language key is the suffix of the model id ('v3_ua' -> 'ua'),
            # so the 'uk' alias asks for the Ukrainian model under the hub's name.
            language=model_id.rsplit("_", 1)[-1],
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


def is_speech_cap_refusal(exc: BaseException) -> bool:
    """Tell Silero's refusal of a text past one call's speech cap from any other failure it wraps.

    Only the cap is the caller's input; anything else Silero reports with the
    same message (out of memory, a broken torch runtime) is this server's fault
    and must stay a TTSException, so a balancer fails over instead of relaying
    a 400 to the caller.
    """
    cause = exc.__cause__ or exc.__context__
    return SILERO_TOO_LONG in str(exc) and isinstance(cause, RuntimeError) and SILERO_POSITION_CAP in str(cause)


def synthesize_piece(model, piece: str, speaker: str, sample_rate: int) -> bytes:
    """Voice one piece and return it as 16-bit PCM.

    Returns b"" for a piece with nothing to pronounce (Silero's bare ValueError),
    so the pieces around it still play. A piece that runs past the speech cap
    is cut in half at a boundary and each half voiced on its own: short
    sentences pack more speech into SILERO_CHUNK_CHARS than prose does. Only a
    piece that cannot be cut any more is a ValidationError.
    """
    try:
        # Generate audio (float32 mono waveform in [-1, 1]).
        with INFERENCE_LOCK:
            audio_tensor = model.apply_tts(text=piece, speaker=speaker, sample_rate=sample_rate)
    except ValueError as exc:
        if str(exc):
            raise
        return b""
    except Exception as exc:
        if not is_speech_cap_refusal(exc):
            raise
        halves = chunk_text(piece, max_len=max(1, len(piece) // 2))
        if len(halves) < 2:
            raise ValidationError(
                f"Text too long for silerotts: {piece!r} runs past the 62.5 s of speech one "
                "Silero call can voice and has nothing left to cut it at"
            ) from exc
        return b"".join(synthesize_piece(model, half, speaker, sample_rate) for half in halves)
    samples = audio_tensor.squeeze().detach().cpu().numpy()
    return (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()


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
        - SILEROTTS_MODELS env variable (highest priority), or
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

        # One call per piece, joined as PCM: a text past one call's speech cap
        # was a 500 at any length under MAX_TEXT_LENGTH. Short text stays one
        # piece and one call; blank text reaches Silero as is and gets its
        # refusal below. A piece with nothing to pronounce (only digits, say)
        # voices nothing, as it did inside the whole text.
        pieces = chunk_text(text, max_len=SILERO_CHUNK_CHARS) or [text]
        pcm16 = b"".join(synthesize_piece(model, piece, speaker, sample_rate) for piece in pieces)
        if not pcm16:
            # Nothing in any piece was pronounceable: the refusal below, as for
            # a short text Silero voices nothing of.
            raise ValueError()

        # Encode WAV with the stdlib `wave` module instead of torchaudio.save():
        # in torchaudio >= 2.9 save() routes through the torchcodec backend, whose
        # encoder cannot write to a file-like object (it needs a real path +
        # extension) and raises "Couldn't allocate AVFormatContext" on a BytesIO.
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
