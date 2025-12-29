"""
Audio Playback Module

Handles audio playback using pygame.
"""

import os
import tempfile
import logging
from typing import Union

from .exceptions import EngineNotAvailableError, TTSException, ValidationError

# Configure logging
logger = logging.getLogger(__name__)

# Type definitions
AudioSource = Union[str, bytes]

# Try to import pygame
try:
    os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    import pygame
    from pygame import mixer

    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    logger.warning("pygame not available. Audio playback will not work.")


def is_available() -> bool:
    """Check if pygame is available for playback."""
    return PYGAME_AVAILABLE


def play_file(filename: str) -> None:
    """Play audio from file."""
    if not PYGAME_AVAILABLE:
        raise EngineNotAvailableError("pygame not available for audio playback")

    if not os.path.exists(filename):
        raise ValidationError(f"Audio file not found: {filename}")

    try:
        # Detect sample rate from WAV header for proper playback
        sample_rate = 44100  # Default
        channels = 2

        if filename.endswith(".wav"):
            try:
                import wave

                with wave.open(filename, "rb") as wf:
                    sample_rate = wf.getframerate()
                    channels = wf.getnchannels()
            except Exception:
                # If can't read, use defaults
                sample_rate = 22050
                channels = 1

        # Quit and reinitialize mixer with correct settings
        try:
            mixer.quit()
        except pygame.error:
            pass

        mixer.init(frequency=sample_rate, size=-16, channels=channels, buffer=2048)
        mixer.music.load(filename)
        mixer.music.play()

        while mixer.music.get_busy():
            pygame.time.wait(100)
        mixer.music.unload()
        mixer.quit()
    except Exception as e:
        raise TTSException(f"Audio playback failed: {e}")


def play_bytes(audio_bytes: bytes) -> None:
    """Play audio from bytes."""
    if not PYGAME_AVAILABLE:
        raise EngineNotAvailableError("pygame not available for audio playback")

    # Detect file format from bytes header
    suffix = ".mp3"
    if audio_bytes.startswith(b"RIFF"):
        suffix = ".wav"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
        temp_filename = temp_file.name
        temp_file.write(audio_bytes)
        temp_file.flush()

    try:
        # Use the improved play_file function
        play_file(temp_filename)
    finally:
        if os.path.exists(temp_filename):
            os.unlink(temp_filename)


def play(audio_source: AudioSource) -> None:
    """
    Play audio from file path or bytes.

    Args:
        audio_source: Either a file path (str) or audio bytes (bytes)
    """
    if isinstance(audio_source, str):
        play_file(audio_source)
    elif isinstance(audio_source, bytes):
        play_bytes(audio_source)
    else:
        raise ValidationError(f"Invalid audio source type: {type(audio_source)}")
