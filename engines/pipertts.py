#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline TTS engine backed by Piper ONNX voice models.

Fast, natural-sounding synthesis with voices for 50+ languages. Returns
WAV bytes; file I/O and playback belong to the API layer.
"""

import io
import json
import logging
import os
import re
import threading
import wave

# Local imports
from libs.cached_loader import load_cached
from libs.exceptions import EngineNotAvailableError, TTSException, ValidationError
from libs.languages import normalize_language, primary_language

logger = logging.getLogger(__name__)

# Offline ONNX, ~300x realtime — large texts are fine but bound memory.
MAX_TEXT_LENGTH = 50_000

# Language -> the Piper voice the engine uses for it when installed (the table
# in docs/PIPERTTS.md). Another language takes any installed voice of its own;
# with none installed it is spoken with the English voice.
LEGACY_VOICES = {
    "en": "en_US-lessac-medium",
    "ru": "ru_RU-ruslan-medium",
    "es": "es_ES-davefx-medium",
    "de": "de_DE-thorsten-medium",
    "fr": "fr_FR-siwis-medium",
    "it": "it_IT-riccardo-medium",
    "uk": "uk_UA-ukrainian_tts-medium",
    "zh": "zh_CN-huayan-medium",
}

# A Piper voice file stem: <family>_<REGION>-<name>-<quality>, as in rhasspy/piper-voices.
VOICE_STEM_RE = re.compile(r"(?P<family>[a-z]{2,3})_(?P<region>[A-Z]{2})-(?P<name>[^-]+)-(?P<quality>[a-z_]+)")

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
# Voices kept loaded at once. A request may name any installed voice, so the
# cache is bounded; 8 is what the 8-language table could load before voices
# were selectable (about 60 MB each for a medium voice). The voice loaded
# earliest is dropped when one more loads.
VOICE_CACHE_SIZE = 8


def get_voice(voice_path: str):
    """Return cached PiperVoice for `voice_path`, loading lazily.

    Cache key is the normalised absolute path so a relative fallback
    (e.g. `./voices/en.onnx`) and an absolute path that resolve to the
    same file don't load the same ONNX twice. Double-checked locking
    so two concurrent first-time requests don't both pay the load cost.
    At most VOICE_CACHE_SIZE voices stay loaded.
    """
    key = os.path.abspath(os.path.expanduser(voice_path))
    return load_cached(VOICE_CACHE, VOICE_CACHE_LOCK, key, lambda: PiperVoice.load(key), VOICE_CACHE_SIZE)


def is_available() -> bool:
    """Check if Piper TTS is available."""
    return AVAILABLE


def get_models_directory() -> str:
    """
    Get the directory for storing Piper TTS models.

    Priority:
    1. Environment variable PIPERTTS_MODELS (from .env or export)
    2. cache/pipertts directory in project root (if exists)
    3. Default: .piper/voices in project root

    Returns:
        Path to models directory
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    env_var = os.environ.get("PIPERTTS_MODELS")
    if env_var:
        models_path = env_var.strip()
        # A relative override is anchored to the project root, not the cwd,
        # so `ttsgen` finds the same voices from any working directory.
        if not os.path.isabs(models_path):
            models_path = os.path.join(project_root, models_path)
        return os.path.expanduser(models_path)

    pipertts_dir = os.path.join(project_root, "cache", "pipertts")
    if os.path.exists(pipertts_dir) and os.path.isdir(pipertts_dir):
        return pipertts_dir

    return os.path.join(project_root, ".piper", "voices")


def voice_search_dirs() -> list[str]:
    """Return the directories searched for voice files, in lookup order and without repeats.

    The configured models directory comes first, then the common locations
    Piper's own tooling writes to.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        get_models_directory(),
        os.path.join(project_root, ".piper", "voices"),  # Project directory
        os.path.join(os.path.expanduser("~"), ".local", "share", "piper", "voices"),  # User home
        "/usr/share/piper/voices",  # System-wide
        "./voices",  # Current directory
    ]
    return list(dict.fromkeys(candidates))


def list_installed_voices() -> dict[str, str]:
    """Map the stem of every installed voice (`en_GB-alan-low`) to its .onnx path.

    A voice found in several directories keeps the path of the first one in
    voice_search_dirs(), the file get_voice_path() would load. Only directory
    listings; no model is opened. A directory that exists but cannot be read
    (a fallback such as ./voices without permissions) is logged and skipped,
    so it does not hide the voices of the others.
    """
    voices: dict[str, str] = {}
    for voice_dir in voice_search_dirs():
        if not os.path.isdir(voice_dir):
            continue
        try:
            file_names = os.listdir(voice_dir)
        except OSError as exc:
            logger.warning(f"Skipping unreadable Piper voice directory {voice_dir}: {type(exc).__name__}: {str(exc)}")
            continue
        for file_name in sorted(file_names):
            if file_name.endswith(".onnx"):
                voices.setdefault(file_name[: -len(".onnx")], os.path.join(voice_dir, file_name))
    return voices


def voice_languages(stem: str, voice_path: str | None = None) -> list[str] | None:
    """Return the languages of a voice: its family and family-region ('en', 'en-gb').

    The stem is parsed first (`en_GB-alan-low`); a file named otherwise is
    described by `language.family` in its `.onnx.json` config. None when
    neither says.
    """
    match = VOICE_STEM_RE.fullmatch(stem)
    if match:
        family = match.group("family")
        return [family, f"{family}-{match.group('region').lower()}"]
    if voice_path is None:
        return None
    try:
        with open(f"{voice_path}.json", encoding="utf-8") as config_file:
            family = json.load(config_file)["language"]["family"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return [str(family).lower()] if family else None


def voice_family(stem: str, voice_path: str | None = None) -> str | None:
    """Return the language family of a voice ('en' for `en_GB-alan-low`), or None when it is not known."""
    languages = voice_languages(stem, voice_path)
    return languages[0] if languages else None


def pick_voice(stems: list[str]) -> str | None:
    """Pick one of several voices of a language: a `medium` one first, then the first by name."""
    ordered = sorted(stems, key=lambda stem: (not stem.endswith("-medium"), stem))
    return ordered[0] if ordered else None


def find_installed_voice(language: str, installed: dict[str, str]) -> str | None:
    """Return the stem of the installed voice to use for `language`, or None when no installed voice fits.

    Order: a voice of the same family and region for a tag such as 'en-gb';
    the voice LEGACY_VOICES names for the language when it is installed (the
    8 languages keep the voice they always had); any installed voice of the
    family, `medium` first.
    """
    code = normalize_language(language)
    family = primary_language(code)
    if code != family:
        regional = [stem for stem, path in installed.items() if code in (voice_languages(stem, path) or [])]
        legacy_stem = LEGACY_VOICES.get(family)
        if legacy_stem in regional:
            return legacy_stem
        if regional:
            return pick_voice(regional)
    legacy_stem = LEGACY_VOICES.get(family)
    if legacy_stem in installed:
        return legacy_stem
    return pick_voice([stem for stem, path in installed.items() if voice_family(stem, path) == family])


def legacy_voice_path(language: str) -> str:
    """Resolve the LEGACY_VOICES file for a language (English for others), the lookup before any voice could be picked.

    Returns:
        The first existing file in voice_search_dirs(), else the path in the
        configured models directory, so callers can report a precise
        FileNotFoundError with download instructions.
    """
    voice_name = LEGACY_VOICES.get(primary_language(language), LEGACY_VOICES["en"])
    for voice_dir in voice_search_dirs():
        voice_path = os.path.join(voice_dir, f"{voice_name}.onnx")
        if os.path.exists(voice_path):
            return voice_path
    # Nothing on disk - point at the configured directory so the error message
    # names the place the installer would populate.
    return os.path.join(get_models_directory(), f"{voice_name}.onnx")


def get_model_path(model: str) -> str:
    """Return the .onnx path of an installed voice named by its stem.

    Raises:
        ValidationError: No installed voice has that stem. The stem is looked
            up, never joined into a path, so it cannot point outside the voice
            directories.
    """
    installed = list_installed_voices()
    if model not in installed:
        raise ValidationError(f"Unknown pipertts model '{model}'")
    return installed[model]


def get_voice_path(language: str = "en", model: str | None = None) -> str:
    """Resolve the .onnx voice file to use for a request.

    Args:
        language: Language code or tag. A tag with a region ('en-gb') takes an
            installed voice of that region first; then the language's voice
            from LEGACY_VOICES when installed; then any installed voice of the
            language; and when none is installed, the LEGACY_VOICES lookup as
            before (English for a language outside it).
        model: The stem of an installed voice (`en_GB-alan-low`); when given it
            wins over the language.

    Returns:
        Path to the voice model. The path of the configured models directory is
        returned even when no file exists there, so callers can report a precise
        FileNotFoundError with download instructions.

    Raises:
        ValidationError: `model` names no installed voice.
    """
    if model is not None:
        return get_model_path(model)
    installed = list_installed_voices()
    stem = find_installed_voice(language, installed)
    if stem is not None:
        return installed[stem]
    return legacy_voice_path(language)


def list_models() -> list[dict]:
    """Describe the installed voices, each one a model a request may name by its stem.

    Only directory listings and, for a file whose name does not parse, its
    small `.onnx.json`; no voice is loaded.
    """
    return [
        {"id": stem, "languages": voice_languages(stem, path), "installed": True}
        for stem, path in sorted(list_installed_voices().items())
    ]


def list_languages(model: str | None = None) -> list[str] | None:
    """Return the languages of the installed voices (their families), or of one voice when `model` is given.

    A language without an installed voice behaves as before: one outside the
    LEGACY_VOICES table is spoken with the English voice, and a table language
    whose voice is missing gets its download instructions. None for a `model`
    that is not installed or whose language is not known. None as well when no installed voice has a known language (none is
    installed yet): the engine then declares nothing, so TTS_LANGUAGE_STRICT
    lets the request through to generate(), which answers with the download
    instructions of the missing voice.
    """
    installed = list_installed_voices()
    if model is not None:
        if model not in installed:
            return None
        return voice_languages(model, installed[model])
    families = {voice_family(stem, path) for stem, path in installed.items()}
    languages = sorted(family for family in families if family)
    return languages or None


def default_model(language: str | None = None) -> str | None:
    """Return the voice a request without `model` uses for `language`.

    None without a language, since the voice depends on it, and None when the
    voice get_voice_path() resolves is not installed.
    """
    if language is None:
        return None
    voice_path = get_voice_path(language)
    if not os.path.exists(voice_path):
        return None
    return os.path.basename(voice_path)[: -len(".onnx")]


def voice_download_path(stem: str) -> str | None:
    """Return the folder of a voice in rhasspy/piper-voices (`en/en_GB/alan/low`), or None for a stem that does not parse."""
    match = VOICE_STEM_RE.fullmatch(stem)
    if match is None:
        return None
    family = match.group("family")
    return f"{family}/{family}_{match.group('region')}/{match.group('name')}/{match.group('quality')}"


def get_download_instructions(language: str, model: str | None = None) -> str:
    """Build the multi-option help text shown when a voice model is missing.

    Args:
        language: Language code, looked up by its primary subtag; unknown codes
            describe the English voice.
        model: The stem of the voice that was asked for, described instead of
            the language's voice.

    Returns:
        Human-readable instructions covering the installer, wget and curl.
    """
    model_name = model or LEGACY_VOICES.get(primary_language(language), LEGACY_VOICES["en"])
    model_path = voice_download_path(model_name)
    if model_path is None:
        model_name = LEGACY_VOICES["en"]
        model_path = voice_download_path(model_name) or ""

    base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"

    voice_dir = get_models_directory()
    subject = f"model '{model}'" if model else f"language '{language}'"

    return (
        f"Piper voice model not found for {subject}.\n\n"
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
        config: Configuration dict with language and optional model (the stem
            of an installed voice, see list_models(); None picks the voice by
            language)

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
    model = config.get("model")
    # Resolved before the try below, so an unknown model stays a ValidationError (400).
    voice_path = get_model_path(model) if model else None
    try:
        voice_path = voice_path or get_voice_path(language)
        logger.info(f"Piper voice: {voice_path}")

        # Cached load: PiperVoice.load is the dominant cost (~1.5s); the
        # cache turns subsequent calls into pure synthesis (~tens of ms).
        voice = get_voice(voice_path)

        # Generate audio to BytesIO
        audio_buffer = io.BytesIO()
        with wave.open(audio_buffer, "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)

        audio_buffer.seek(0)
        return audio_buffer.getvalue()

    except FileNotFoundError as exc:
        instructions = get_download_instructions(language, model)
        raise TTSException(f"{instructions}\n\nError: {exc}") from exc
    except Exception as exc:
        raise TTSException(f"Piper TTS generation failed: {exc}") from exc


def main():
    """Module entrypoint placeholder — this file is import-only."""
    pass


if __name__ == "__main__":
    main()
