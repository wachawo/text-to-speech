#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Online TTS engine backed by Google Text-to-Speech (gTTS)."""

import io
import logging

from libs.exceptions import EngineNotAvailableError, TTSException, ValidationError

# Google rate-limits gTTS aggressively (one HTTP request per <=200-char chunk).
# Above ~5k chars a single ttsgen run starts triggering bans.
MAX_TEXT_LENGTH = 5_000

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
        language = config.get("language", "en")
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
