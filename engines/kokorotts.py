#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline ONNX TTS engine backed by kokoro-onnx (Kokoro 82M v1.0).

Multi-language (English/French/Italian/Japanese/Mandarin/Spanish/Hindi/Portuguese),
multi-voice, fast on CPU.

A voice is one name from the voices file (`af_bella`) or a weighted mix of up to
MAX_MIX_VOICES names (`af_bella(2)+af_sky(1)`), blended as the weighted sum of
their style vectors. The first letter of a name is its language (`a` en-us,
`b` en-gb, `j` ja, ...), the second its gender.

See: https://github.com/nazdridoy/kokoro-tts (CLI upstream this engine wraps)
     https://github.com/thewh1teagle/kokoro-onnx (Python bindings)
"""

import io
import logging
import math
import os
import re
import threading
from collections.abc import Collection, Sequence
from typing import Any

# numpy is a base dependency of the package, unlike kokoro_onnx, so it needs no
# guard: list_voices() reads the voices file even where the engine is not installed.
import numpy as np

# Local imports
from libs.cached_loader import load_cached
from libs.exceptions import EngineNotAvailableError, TTSException, ValidationError
from libs.languages import normalize_language, primary_language

logger = logging.getLogger(__name__)

# Kokoro is offline ONNX (~10x realtime CPU). Bound single calls so a runaway
# input doesn't blow memory; chunking remains the CLI's job.
MAX_TEXT_LENGTH = 50_000

DEFAULT_KOKOROTTS_MODELS = "cache/kokorotts"
DEFAULT_KOKOROTTS_MODEL = "kokoro-v1.0.onnx"
DEFAULT_KOKOROTTS_VOICES = "voices-v1.0.bin"
DEFAULT_KOKOROTTS_SPEED = 1.0

# 2-char ISO-ish code -> (kokoro lang code, default voice). A tag such as
# 'pt-br' is looked up by its primary subtag.
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

# 2-char language code -> first letters of the voices listed for it.
LANGUAGE_PREFIXES = {
    "en": ("a", "b"),
    "es": ("e",),
    "fr": ("f",),
    "hi": ("h",),
    "it": ("i",),
    "ja": ("j",),
    "pt": ("p",),
    "zh": ("z",),
}
MAX_MIX_VOICES = 4
# One component of a voice spec: `af_bella` or `af_bella(2.5)`. Possessive
# quantifiers and a weight group without whitespace keep matching linear; the
# earlier overlapping form backtracked polynomially on an unclosed parenthesis.
VOICE_COMPONENT_RE = re.compile(r"(?P<name>[a-z]{2}_[a-z0-9]+)\s*+(?:\(\s*+(?P<weight>[^()\s]*+)\s*+\))?")
# A weight is a plain ASCII decimal: float() alone would also take "1_0", "nan"
# and non-ASCII digits.
WEIGHT_RE = re.compile(r"[0-9]*\.?[0-9]+(?:[eE]-?[0-9]+)?")

# Cache voices_path -> sorted voice names, so validating a voice does not
# reopen the voices archive on every request.
VOICE_NAMES_CACHE: dict = {}
VOICE_NAMES_LOCK = threading.Lock()

# Cache (model_path, voices_path) → Kokoro instance. Loading the ONNX model
# costs ~1-3s on CPU; reuse across calls within one process.
KOKORO_CACHE: dict = {}
# Guards the first load only: two concurrent first requests must not both
# build the ONNX session. Inference needs no lock, onnxruntime's run() is
# thread-safe, so the engine pool alone bounds parallel synthesis.
KOKORO_CACHE_LOCK = threading.Lock()
# onnxruntime itself is thread-safe, but Kokoro phonemizes through espeak-ng,
# a C library with global state, so one synthesis at a time per process.
INFERENCE_LOCK = threading.Lock()

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


def get_kokoro(model_path: str, voices_path: str):
    """Return the cached Kokoro instance for the file pair, loading it lazily.

    Double-checked locking so concurrent first-time requests load the model once.
    """

    def load_kokoro():
        """Build the ONNX session for the model and voices files."""
        logger.info(f"Loading Kokoro model: {model_path}")
        return Kokoro(model_path, voices_path)

    return load_cached(KOKORO_CACHE, KOKORO_CACHE_LOCK, (model_path, voices_path), load_kokoro)


def voice_names(voices_path: str) -> tuple[str, ...]:
    """Return the sorted voice names stored in the voices file, read once per path.

    The voices file is an .npz archive keyed by voice name; only its index is
    read, no ONNX session is built and kokoro_onnx is not needed.
    """

    def read_names() -> tuple[str, ...]:
        """Read the member names of the voices archive."""
        with np.load(voices_path, allow_pickle=False) as archive:
            return tuple(sorted(archive.files))

    return load_cached(VOICE_NAMES_CACHE, VOICE_NAMES_LOCK, voices_path, read_names)


def list_languages() -> list[str]:
    """Return the languages Kokoro has voices for; any other code is spoken as English."""
    return sorted(LANGUAGE_MAP)


def language_voices(language: str, names: Collection[str]) -> list[str]:
    """Return the names whose first letter belongs to the language (en for unknown codes)."""
    prefixes = LANGUAGE_PREFIXES.get(primary_language(language), LANGUAGE_PREFIXES["en"])
    return [name for name in names if name[:1] in prefixes]


def default_voice(language: str, voices: Sequence[str]) -> str | None:
    """Return the LANGUAGE_MAP default when it is among the voices, else the first voice."""
    unused_lang_code, preferred = LANGUAGE_MAP.get(primary_language(language), LANGUAGE_MAP["en"])
    if preferred in voices:
        return preferred
    return voices[0] if voices else None


def env_voice_spec() -> str:
    """Return KOKOROTTS_VOICE, the voice spec for requests that name none, or ''."""
    return os.environ.get("KOKOROTTS_VOICE", "").strip()


def list_voices(language: str = "en") -> dict:
    """List the voices selectable for a language, plus its default voice.

    Cheap on purpose: reads only the voices file index, never the ONNX model.

    Args:
        language: Language code or tag (looked up by its primary subtag);
            unknown codes list the English voices.

    Returns:
        Dict with 'voices' (sorted names), 'default' (the voice used when none
        is requested: KOKOROTTS_VOICE, else the language default, or None) and
        'mix' (True when voices can be blended).
    """
    unused_model_path, voices_path = get_model_paths()
    if not os.path.exists(voices_path):
        return {"voices": [], "default": None, "mix": False}
    voices = language_voices(language, voice_names(voices_path))
    default = env_voice_spec() or default_voice(language, voices)
    return {"voices": voices, "default": default, "mix": bool(voices)}


def parse_voice_component(component: str) -> tuple[str, float]:
    """Parse one `name` or `name(weight)` component of a voice spec."""
    if not component:
        raise ValidationError("Empty voice in mix")
    match = VOICE_COMPONENT_RE.fullmatch(component)
    if not match:
        raise ValidationError(f"Invalid voice: '{component}'")
    name, weight_text = match.group("name"), match.group("weight")
    if weight_text is None:
        return name, 1.0
    weight = float(weight_text) if WEIGHT_RE.fullmatch(weight_text) else math.nan
    if not math.isfinite(weight) or weight <= 0:
        raise ValidationError(f"Invalid weight '{weight_text}' for voice '{name}', expected a positive number")
    return name, weight


def parse_voice_spec(spec: str) -> list[tuple[str, float]]:
    """Parse `af_bella` or `af_bella(2)+af_sky(1)` into (name, weight) pairs.

    Weights default to 1 and are normalized to sum to 1.

    Raises:
        ValidationError: The spec is empty or malformed, has more than
            MAX_MIX_VOICES components, or repeats a name.
    """
    if not spec.strip():
        raise ValidationError("Voice is empty")
    parts = [part.strip() for part in spec.split("+")]
    if len(parts) > MAX_MIX_VOICES:
        raise ValidationError(f"Too many voices in mix: {len(parts)} > {MAX_MIX_VOICES}")
    components = [parse_voice_component(part) for part in parts]
    names = [name for name, unused_weight in components]
    for name in names:
        if names.count(name) > 1:
            raise ValidationError(f"Repeated voice in mix: '{name}'")
    # Scale by the largest weight first so huge weights cannot overflow the sum.
    largest = max(weight for unused_name, weight in components)
    scaled = [(name, weight / largest) for name, weight in components]
    total = sum(weight for unused_name, weight in scaled)
    return [(name, weight / total) for name, weight in scaled]


def resolve_voice(spec: str, known_names: Collection[str]) -> list[tuple[str, float]]:
    """Parse a voice spec and check that every name exists in the voices file.

    Raises:
        ValidationError: The spec is malformed or names an unknown voice.
    """
    components = parse_voice_spec(spec)
    for name, unused_weight in components:
        if name not in known_names:
            raise ValidationError(f"Unknown voice '{name}' for kokorotts")
    return components


def lang_code_for(language: str, components: Sequence[tuple[str, float]]) -> str:
    """Return the kokoro lang code: the language's, but en-gb for English led by a b* voice or asked for as 'en-gb'."""
    lang_code, unused_voice = LANGUAGE_MAP.get(primary_language(language), LANGUAGE_MAP["en"])
    if lang_code == "en-us" and (components[0][0].startswith("b") or normalize_language(language) == "en-gb"):
        return "en-gb"
    return lang_code


def voice_argument(kokoro: Any, components: Sequence[tuple[str, float]]) -> str | np.ndarray:
    """Return the `voice` for Kokoro.create(): the name, or the weighted style blend of a mix."""
    if len(components) == 1:
        return components[0][0]
    weighted = [weight * np.asarray(kokoro.get_voice_style(name), dtype=np.float32) for name, weight in components]
    return np.sum(weighted, axis=0).astype(np.float32)


def requested_voice_spec(config: dict, language: str, names: Collection[str]) -> str:
    """Return the voice spec to use: config['voice'], else KOKOROTTS_VOICE, else the language default."""
    requested = (config.get("voice") or "").strip()
    if requested:
        return requested
    env_voice = env_voice_spec()
    if env_voice:
        return env_voice
    fallback = LANGUAGE_MAP.get(primary_language(language), LANGUAGE_MAP["en"])[1]
    return default_voice(language, language_voices(language, names)) or fallback


def resolve_requested_voice(config: dict, language: str, names: Collection[str]) -> list[tuple[str, float]]:
    """Resolve the voice for a request, blaming KOKOROTTS_VOICE when it is the bad value.

    A voice the client sent is the client's error (ValidationError, a 400); a
    voice taken from KOKOROTTS_VOICE for a request that named none is a server
    misconfiguration, so it surfaces as a TTSException that names the variable.
    """
    spec = requested_voice_spec(config, language, names)
    try:
        return resolve_voice(spec, names)
    except ValidationError as exc:
        if not (config.get("voice") or "").strip() and spec == env_voice_spec():
            raise TTSException(f"KOKOROTTS_VOICE is invalid: {exc}") from exc
        raise


def generate(text: str, config: dict) -> bytes:
    """
    Generate TTS and return audio as bytes.

    Args:
        text: Text to synthesize.
        config: Configuration dict with `language` (code or tag) and optional
            `voice`, a voice spec (`af_bella` or `af_bella(2)+af_sky(1)`); without
            it KOKOROTTS_VOICE is used, then the language's default voice.

    Returns:
        Audio bytes in WAV format (24000 Hz, 16-bit PCM, mono).

    Raises:
        EngineNotAvailableError: kokoro-onnx / soundfile are not installed.
        ValidationError: Text exceeds MAX_TEXT_LENGTH, or the voice spec is
            malformed or names an unknown voice.
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
    try:
        speed = float(os.environ.get("KOKOROTTS_SPEED", "").strip() or DEFAULT_KOKOROTTS_SPEED)
    except ValueError:
        speed = DEFAULT_KOKOROTTS_SPEED

    model_path, voices_path = get_model_paths()
    if not os.path.exists(model_path) or not os.path.exists(voices_path):
        raise TTSException(get_download_instructions())

    # Validated against the voices file before the ONNX session is built, so a
    # bad voice costs no model load.
    names = voice_names(voices_path)
    components = resolve_requested_voice(config, language, names)
    lang_code = lang_code_for(language, components)

    kokoro = get_kokoro(model_path, voices_path)
    voice = voice_argument(kokoro, components)

    try:
        with INFERENCE_LOCK:
            samples, sample_rate = kokoro.create(text, voice=voice, speed=speed, lang=lang_code)
    except Exception as exc:
        raise TTSException(f"Kokoro TTS generation failed ({type(exc).__name__}): {exc}") from exc

    return samples_to_wav_bytes(samples, int(sample_rate))


def main():
    """Module entrypoint placeholder — this file is import-only."""
    pass


if __name__ == "__main__":
    main()
