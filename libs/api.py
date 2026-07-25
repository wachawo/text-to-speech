#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Public text-to-speech API — engines return bytes, this layer adds files and playback."""

import io
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import cast

# Local imports
from engines import get_engine_function

from . import playback

# TTSException/ValidationError are unused here but re-exported so callers can do
# `from libs.api import TTSException` without knowing about libs.exceptions.
from .exceptions import (  # noqa: F401
    EngineNotAvailableError,
    TTSException,
    ValidationError,
)
from .tools import (
    get_default_config,
    validate_engine,
    validate_language,
    validate_text,
)

# Makes the repository root importable when libs/ is used straight from a source
# checkout rather than from an installed wheel.
sys.path.insert(0, str(Path(__file__).parent.parent))

# Module logger only — a library must not call logging.basicConfig(), which would
# grab the root logger and turn the entrypoint's own basicConfig(**LOGGING) into a
# no-op (Python's default root level is already WARNING).
logger = logging.getLogger(__name__)

# Either a path to an audio file or the raw audio bytes themselves.
AudioSource = str | bytes


def text_to_speech_bytes(text: str, engine: str = "gtts", language: str = "en", voice: str | None = None) -> bytes:
    """Synthesize text with the given engine and return the raw audio bytes.

    Args:
        text: Text to synthesize.
        engine: Engine name (gtts, pyttsx3, pipertts, ...).
        language: Two-letter language code.
        voice: Engine-specific voice/speaker id (None = engine default).

    Returns:
        Audio bytes in whatever container the engine produces (MP3 or WAV).

    Raises:
        EngineNotAvailableError: If the engine module cannot be loaded.
        ValidationError: If text, engine or language fail validation.
    """
    validated_text = validate_text(text)
    validated_engine = validate_engine(engine)
    validated_language = validate_language(language)

    config = get_default_config()
    config.update({"engine": validated_engine, "language": validated_language, "voice": voice})

    generate_func = get_engine_function(validated_engine)
    if generate_func is None:
        raise EngineNotAvailableError(
            f"Engine '{validated_engine}' is not available. "
            f"Please check if the engine module exists and its dependencies are installed."
        )

    return cast(bytes, generate_func(validated_text, config))


def text_to_speech_file(
    text: str,
    filename: str | None = None,
    engine: str = "gtts",
    language: str = "en",
) -> str:
    """Synthesize text and write the audio to disk.

    Args:
        text: Text to synthesize.
        filename: Output path; when None a timestamped name is generated and the
            extension is inferred from the audio header (MP3 vs WAV).
        engine: Engine name.
        language: Two-letter language code.

    Returns:
        Path of the file that was written.
    """
    audio_bytes = text_to_speech_bytes(text, engine, language)

    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        extension = "mp3" if audio_bytes.startswith(b"ID3") or audio_bytes[0:2] == b"\xff\xfb" else "wav"
        filename = f"{timestamp}.{extension}"

    with open(filename, "wb") as f:
        f.write(audio_bytes)

    return filename


def text_to_speech_bytesio(text: str, engine: str = "gtts", language: str = "en") -> io.BytesIO:
    """Synthesize text and return the audio wrapped in an in-memory stream."""
    audio_bytes = text_to_speech_bytes(text, engine, language)
    return io.BytesIO(audio_bytes)


def play_audio_file(filename: str) -> None:
    """Play an audio file through the playback backend."""
    playback.play_file(filename)


def play_audio_bytes(audio_bytes: bytes) -> None:
    """Play in-memory audio through the playback backend."""
    playback.play_bytes(audio_bytes)


def play_audio(audio_source: AudioSource) -> None:
    """Play audio given either as a file path or as raw bytes."""
    playback.play(audio_source)
