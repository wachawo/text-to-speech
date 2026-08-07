#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline TTS engine backed by pyttsx3 (espeak on Linux, SAPI5 on Windows)."""

import logging
import os
import tempfile
import time

from libs.exceptions import EngineNotAvailableError, TTSException, ValidationError
from libs.tempfiles import safe_unlink

# Offline espeak; fast but text >10k chars stalls audio threads.
MAX_TEXT_LENGTH = 10_000

logger = logging.getLogger(__name__)

# Optional dependency: absence only disables this engine, it must not break import.
try:
    import pyttsx3  # type: ignore

    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    logger.warning("pyttsx3 not available. Install with: pip install pyttsx3")


def is_available() -> bool:
    """Report whether the pyttsx3 dependency is installed."""
    return AVAILABLE


def generate(text: str, config: dict) -> bytes:
    """Synthesize text with the local pyttsx3 backend.

    Args:
        text: Text to synthesize.
        config: Configuration dict with 'rate' and 'volume'.

    Returns:
        Audio bytes in WAV format.

    Raises:
        EngineNotAvailableError: pyttsx3 is not installed.
        ValidationError: Text exceeds MAX_TEXT_LENGTH.
        TTSException: The backend produced no audio or failed outright.
    """
    if not AVAILABLE:
        raise EngineNotAvailableError("pyttsx3 not available")

    if len(text) > MAX_TEXT_LENGTH:
        raise ValidationError(f"Text too long for pyttsx3: {len(text)} > {MAX_TEXT_LENGTH}")

    try:
        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        if voices:
            engine.setProperty("voice", voices[0].id)
        engine.setProperty("rate", config.get("rate", 150))
        engine.setProperty("volume", config.get("volume", 0.9))

        # pyttsx3 can only write to a path, so synthesis goes through a scratch file.
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_filename = temp_file.name

        try:
            engine.save_to_file(text, temp_filename)
            engine.runAndWait()

            # espeak on Linux returns from runAndWait() before the file is flushed.
            time.sleep(0.5)
            engine.stop()

            if not os.path.exists(temp_filename) or os.path.getsize(temp_filename) == 0:
                raise TTSException("pyttsx3 failed to generate audio")

            with open(temp_filename, "rb") as wav_file:
                return wav_file.read()
        finally:
            safe_unlink(temp_filename)

    except Exception as exc:
        raise TTSException(f"pyttsx3 generation failed: {exc}") from exc


def main():
    """Module entrypoint placeholder — this file is import-only."""
    pass


if __name__ == "__main__":
    main()
