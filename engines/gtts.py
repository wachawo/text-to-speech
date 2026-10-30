#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Online TTS engine backed by Google Text-to-Speech (gTTS)."""

import io
import logging
import threading

from libs.exceptions import EngineNotAvailableError, TTSException, ValidationError

# Google rate-limits gTTS aggressively (one HTTP request per <=200-char chunk).
# Above ~5k chars a single ttsgen run starts triggering bans.
MAX_TEXT_LENGTH = 5_000

logger = logging.getLogger(__name__)

# One request to Google at a time per process: the rate limit above is per
# client, and parallel chunks from several server threads reach it sooner.
INFERENCE_LOCK = threading.Lock()

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
        ValidationError: Text exceeds MAX_TEXT_LENGTH, has nothing to pronounce, or
            gTTS does not speak the language.
        TTSException: The remote synthesis call failed.
    """
    if not AVAILABLE:
        raise EngineNotAvailableError("gTTS not available")

    if len(text) > MAX_TEXT_LENGTH:
        raise ValidationError(f"Text too long for gtts: {len(text)} > {MAX_TEXT_LENGTH}")

    language = config.get("language", "en")
    slow = config.get("slow", False)
    try:
        tts = gTTS(text=text, lang=language, slow=slow)
    except ValueError as exc:
        # gTTS checks the language against its built-in table (gtts.lang.tts_langs,
        # no network) in the constructor, and documents ValueError as the one
        # answer to a language it does not speak.
        raise ValidationError(f"Language '{language}' is not supported by gtts") from exc
    except Exception as exc:
        raise TTSException(f"gTTS generation failed: {exc}") from exc

    try:
        audio_buffer = io.BytesIO()
        with INFERENCE_LOCK:
            tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)

        return audio_buffer.getvalue()

    except AssertionError as exc:
        # gTTS drops punctuation before it asks Google, and asserts that
        # something is left ("No text to send to TTS API") before any request:
        # a text of only "..." is the caller's, not a failed synthesis.
        raise ValidationError("Text cannot be empty for gtts: nothing in it can be pronounced") from exc
    except Exception as exc:
        raise TTSException(f"gTTS generation failed: {exc}") from exc


def main():
    """Module entrypoint placeholder — this file is import-only."""
    pass


if __name__ == "__main__":
    main()
