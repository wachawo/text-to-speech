#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audio playback backed by pygame — the only module in the project that touches it."""

import logging
import os
import tempfile
import warnings
import wave

# Local imports
from .exceptions import EngineNotAvailableError, TTSException, ValidationError
from .tempfiles import safe_unlink

logger = logging.getLogger(__name__)

# Either a path to an audio file or the raw audio bytes themselves.
AudioSource = str | bytes

# Mixer settings used when the source carries no header we can inspect (MP3).
DEFAULT_SAMPLE_RATE = 44100
DEFAULT_CHANNELS = 2

# Mixer settings used when a WAV header is present but unreadable; most engines
# in this project emit 22050 Hz mono, so it is the least surprising guess.
FALLBACK_SAMPLE_RATE = 22050
FALLBACK_CHANNELS = 1

# Small buffer keeps per-chunk playback latency low in the streaming CLI pipeline.
MIXER_BUFFER = 2048

try:
    os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    # pygame imports the deprecated pkg_resources at import time, which prints a
    # UserWarning. Silence just that one message — keep all other warnings intact.
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="pkg_resources is deprecated", category=UserWarning)
        import pygame
        from pygame import mixer

    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    logger.warning("pygame not available. Audio playback will not work.")


def is_available() -> bool:
    """Report whether pygame could be imported and playback is possible."""
    return PYGAME_AVAILABLE


def play_file(filename: str) -> None:
    """Play an audio file, reinitializing the mixer to match the file's sample rate.

    Args:
        filename: Path to a WAV or MP3 file.

    Raises:
        EngineNotAvailableError: If pygame is not installed.
        ValidationError: If the file does not exist.
        TTSException: If the mixer or the decoder rejects the file.
    """
    if not PYGAME_AVAILABLE:
        raise EngineNotAvailableError("pygame not available for audio playback")

    if not os.path.exists(filename):
        raise ValidationError(f"Audio file not found: {filename}")

    try:
        sample_rate = DEFAULT_SAMPLE_RATE
        channels = DEFAULT_CHANNELS

        if filename.endswith(".wav"):
            try:
                with wave.open(filename, "rb") as wf:
                    sample_rate = wf.getframerate()
                    channels = wf.getnchannels()
            except Exception as exc:
                logger.warning(
                    f"Could not read WAV header from {filename}, assuming "
                    f"{FALLBACK_SAMPLE_RATE}Hz/{FALLBACK_CHANNELS}ch: {type(exc).__name__}: {exc}"
                )
                sample_rate = FALLBACK_SAMPLE_RATE
                channels = FALLBACK_CHANNELS

        # A mixer left over from a previous file may run at another sample rate.
        try:
            mixer.quit()
        except pygame.error:
            pass

        mixer.init(frequency=sample_rate, size=-16, channels=channels, buffer=MIXER_BUFFER)
        mixer.music.load(filename)
        mixer.music.play()

        while mixer.music.get_busy():
            pygame.time.wait(100)
        mixer.music.unload()
        mixer.quit()
    except Exception as exc:
        raise TTSException(f"Audio playback failed: {exc}") from exc


def play_bytes(audio_bytes: bytes) -> None:
    """Play in-memory audio by spooling it to a temp file with the right extension."""
    if not PYGAME_AVAILABLE:
        raise EngineNotAvailableError("pygame not available for audio playback")

    # pygame picks its decoder from the extension, so sniff the container header.
    suffix = ".mp3"
    if audio_bytes.startswith(b"RIFF"):
        suffix = ".wav"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
        temp_filename = temp_file.name
        temp_file.write(audio_bytes)
        temp_file.flush()

    try:
        play_file(temp_filename)
    finally:
        safe_unlink(temp_filename)


def play(audio_source: AudioSource) -> None:
    """Play audio given either as a file path or as raw bytes.

    Args:
        audio_source: Either a file path (str) or audio bytes (bytes).

    Raises:
        ValidationError: If the argument is neither str nor bytes.
    """
    if isinstance(audio_source, str):
        play_file(audio_source)
    elif isinstance(audio_source, bytes):
        play_bytes(audio_source)
    else:
        raise ValidationError(f"Invalid audio source type: {type(audio_source)}")
