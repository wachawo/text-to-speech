#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Online TTS engine backed by Google Text-to-Speech (gTTS)."""

import io
import logging

from libs.exceptions import EngineNotAvailableError, TTSException, ValidationError
from libs.languages import is_language_code, primary_language

# Google rate-limits gTTS aggressively (one HTTP request per <=200-char chunk).
# Above ~5k chars a single ttsgen run starts triggering bans.
MAX_TEXT_LENGTH = 5_000

# Tags gTTS lists but folds into their language part with a deprecation warning
# on every call (gtts.lang._fallback_deprecated_lang): there is no Canadian
# French or European Portuguese voice, so they are left out and served as
# 'fr' / 'pt' directly, the same as 'pt-br'.
GTTS_FOLDED_TAGS = ("fr-ca", "pt-pt")

logger = logging.getLogger(__name__)

# Optional dependency: absence only disables this engine, it must not break import.
try:
    from gtts import gTTS  # type: ignore

    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    logger.warning("gTTS not available. Install with: pip install gtts")


def is_available() -> bool:
    """Report whether the gTTS dependency is installed."""
    return AVAILABLE


def get_gtts_languages() -> dict[str, str]:
    """Return gTTS's own language table (lowercased tag -> tag as gTTS spells it), or {} when it cannot be read.

    `gtts.lang.tts_langs()` is a static table shipped with the package, so
    reading it makes no network call. GTTS_FOLDED_TAGS are left out.
    """
    try:
        from gtts.lang import tts_langs  # type: ignore

        languages = {str(tag).lower(): str(tag) for tag in tts_langs()}
        return {code: tag for code, tag in languages.items() if code not in GTTS_FOLDED_TAGS}
    except Exception as exc:
        logger.debug(f"gTTS language table unavailable: {type(exc).__name__}: {exc}")
        return {}


def list_languages() -> list[str] | None:
    """Return the lowercased language tags gTTS serves, or None when its language table cannot be read.

    A tag no request can carry (the 3-letter `yue`) is left out: the request
    schema refuses it anyway, so listing it would only advertise a language
    that can never be asked for.
    """
    languages = get_gtts_languages()
    if not languages:
        return None
    codes = sorted(code for code in languages if is_language_code(code))
    return codes or None


def gtts_language(language: str) -> str:
    """Map a request language to the tag gTTS expects.

    A tag gTTS lists is matched without regard to case ('zh-cn' -> 'zh-CN');
    a tag it does not list, or one of GTTS_FOLDED_TAGS, falls back to its
    primary subtag when that one is listed ('pt-br' and 'pt-pt' -> 'pt');
    anything else is passed on unchanged, as before.
    """
    languages = get_gtts_languages()
    code = language.lower().replace("_", "-")
    if code in languages:
        return languages[code]
    primary = primary_language(code)
    if primary in languages:
        return languages[primary]
    return language


def generate(text: str, config: dict) -> bytes:
    """Synthesize text through Google Text-to-Speech.

    Args:
        text: Text to synthesize.
        config: Configuration dict with 'language' and 'slow'.

    Returns:
        Audio bytes in MP3 format.

    Raises:
        EngineNotAvailableError: gTTS is not installed.
        ValidationError: Text exceeds MAX_TEXT_LENGTH.
        TTSException: The remote synthesis call failed.
    """
    if not AVAILABLE:
        raise EngineNotAvailableError("gTTS not available")

    if len(text) > MAX_TEXT_LENGTH:
        raise ValidationError(f"Text too long for gtts: {len(text)} > {MAX_TEXT_LENGTH}")

    try:
        language = gtts_language(config.get("language", "en"))
        slow = config.get("slow", False)

        tts = gTTS(text=text, lang=language, slow=slow)
        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)

        return audio_buffer.getvalue()

    except Exception as exc:
        raise TTSException(f"gTTS generation failed: {exc}") from exc


def main():
    """Module entrypoint placeholder — this file is import-only."""
    pass


if __name__ == "__main__":
    main()
