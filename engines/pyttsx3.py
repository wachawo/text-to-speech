#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline TTS engine backed by pyttsx3 (espeak on Linux, SAPI5 on Windows)."""

import logging
import os
import tempfile
import threading
import time
from typing import Any

from libs.exceptions import EngineNotAvailableError, TTSException, ValidationError
from libs.languages import primary_language
from libs.tempfiles import safe_unlink

# Offline espeak; fast but text >10k chars stalls audio threads.
MAX_TEXT_LENGTH = 10_000

logger = logging.getLogger(__name__)

# The espeak driver behind pyttsx3 keeps global state and is not safe to run
# from several threads at once, so init/say/runAndWait/stop are serialised.
# The engine pool bounds synthesis across engines; this lock bounds this
# engine to one synthesis at a time.
ENGINE_LOCK = threading.Lock()

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


def language_tags(voice) -> list:
    """Return the lowercase language tags a pyttsx3 voice advertises.

    espeak reports `languages` as bytes with a leading priority byte
    (b'\x05en-us'); other drivers report plain strings. Both become 'en-us'.
    """
    tags = []
    for tag in getattr(voice, "languages", None) or []:
        if isinstance(tag, bytes):
            tag = tag.decode("utf-8", "ignore")
        # Drop the priority byte (and anything else unprintable) espeak prepends.
        tag = "".join(ch for ch in str(tag) if ch.isprintable()).strip().lower()
        if tag:
            tags.append(tag)
    return tags


def voice_matches_language(voice, language: str) -> bool:
    """Report whether a voice serves `language` (a lowercase 2-letter code or tag such as 'zh-cn').

    A language tag matches when the code is its prefix ('en' matches 'en-us');
    an id matches when the code equals it or its last path segment, or starts
    it before a '-' or '_' ('gmw/en', 'en', 'en-us', 'en_US').
    """
    if any(tag == language or tag.startswith(language) for tag in language_tags(voice)):
        return True
    voice_id = str(getattr(voice, "id", "") or "").lower()
    for candidate in (voice_id, voice_id.rsplit("/", 1)[-1]):
        if candidate == language or candidate.startswith(language + "-") or candidate.startswith(language + "_"):
            return True
    return False


def select_voice(voices: list, config: dict):
    """Pick the voice to use: config['voice'] by id or name, else by language or its language part, else the first.

    Returns:
        The chosen voice object, or None when the driver reports no voices.
    """
    if not voices:
        return None
    wanted = str(config.get("voice") or "").strip().lower()
    if wanted:
        for voice in voices:
            names = (str(getattr(voice, "id", "") or ""), str(getattr(voice, "name", "") or ""))
            if wanted in (name.lower() for name in names):
                return voice
        logger.warning(f"pyttsx3 voice '{wanted}' not found, selecting by language")
    language = str(config.get("language") or "").strip().lower()
    if language:
        voice = find_voice_for_language(voices, language)
        if voice is not None:
            return voice
    return voices[0]


def find_voice_for_language(voices: list, language: str) -> Any | None:
    """Return the first voice that serves `language`, else the first that serves its primary subtag.

    espeak lists a region voice only for some tags (en-gb, es-419), so a tag
    such as 'zh-cn' or 'pt-br' falls back to the 'zh' or 'pt' voice instead
    of the first voice, which is usually English. None when neither matches.
    """
    candidates = [language]
    primary = primary_language(language)
    if primary != language:
        candidates.append(primary)
    for code in candidates:
        for voice in voices:
            if voice_matches_language(voice, code):
                return voice
    return None


def generate(text: str, config: dict) -> bytes:
    """Synthesize text with the local pyttsx3 backend.

    Args:
        text: Text to synthesize.
        config: Configuration dict with 'rate', 'volume', 'language' and an
            optional 'voice' (a pyttsx3 voice id or name).

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
        # pyttsx3 can only write to a path, so synthesis goes through a scratch file.
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_filename = temp_file.name

        try:
            with ENGINE_LOCK:
                engine = pyttsx3.init()
                voice = select_voice(engine.getProperty("voices"), config)
                if voice is not None:
                    engine.setProperty("voice", voice.id)
                engine.setProperty("rate", config.get("rate", 150))
                engine.setProperty("volume", config.get("volume", 0.9))
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
