"""
TTS API Module

Main public API for text-to-speech operations.
Engines return bytes, API handles file saving and playback.
"""

from . import playback
from .tools import (
    get_default_config,
    validate_text,
    validate_engine,
    validate_language,
)
from engines import get_engine_function
import io
import sys
from datetime import datetime
from pathlib import Path
from typing import Union, Optional, cast
import logging

# Import exceptions for export
from .exceptions import EngineNotAvailableError

# Import dynamic engine loader
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import tools

# Import playback

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Type definitions
AudioSource = Union[str, bytes]


def text_to_speech_bytes(
    text: str, engine: str = "gtts", language: str = "en"
) -> bytes:
    """
    Convert text to speech and return as bytes.

    Args:
        text: Text to synthesize
        engine: Engine name (gtts, pyttsx3, piper, etc.)
        language: Language code

    Returns:
        Audio bytes

    Raises:
        EngineNotAvailableError: If engine is not available
    """
    validated_text = validate_text(text)
    validated_engine = validate_engine(engine)
    validated_language = validate_language(language)

    config = get_default_config()
    config.update({"engine": validated_engine, "language": validated_language})

    # Get engine generate function
    generate_func = get_engine_function(validated_engine)

    if generate_func is None:
        raise EngineNotAvailableError(
            f"Engine '{validated_engine}' is not available. "
            f"Please check if the engine module exists and its dependencies are installed."
        )

    # Generate audio bytes
    return cast(bytes, generate_func(validated_text, config))


def text_to_speech_file(
    text: str,
    filename: Optional[str] = None,
    engine: str = "gtts",
    language: str = "en",
) -> str:
    """
    Convert text to speech and save to file.

    Args:
        text: Text to synthesize
        filename: Output filename (auto-generated if None)
        engine: Engine name
        language: Language code

    Returns:
        Path to saved file
    """
    # Generate audio bytes
    audio_bytes = text_to_speech_bytes(text, engine, language)

    # Auto-generate filename if not provided
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Determine extension based on content
        extension = (
            "mp3"
            if audio_bytes.startswith(b"ID3") or audio_bytes[0:2] == b"\xff\xfb"
            else "wav"
        )
        filename = f"{timestamp}.{extension}"

    # Save to file
    with open(filename, "wb") as f:
        f.write(audio_bytes)

    return filename


def text_to_speech_bytesio(
    text: str, engine: str = "gtts", language: str = "en"
) -> io.BytesIO:
    """Convert text to speech and return as BytesIO object."""
    audio_bytes = text_to_speech_bytes(text, engine, language)
    return io.BytesIO(audio_bytes)


def play_audio_file(filename: str) -> None:
    """Play audio from file."""
    playback.play_file(filename)


def play_audio_bytes(audio_bytes: bytes) -> None:
    """Play audio from bytes."""
    playback.play_bytes(audio_bytes)


def play_audio(audio_source: AudioSource) -> None:
    """Play audio from file or bytes."""
    playback.play(audio_source)
