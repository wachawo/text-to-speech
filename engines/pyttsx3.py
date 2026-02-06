"""
pyttsx3 TTS Engine

Offline text-to-speech using espeak backend.
"""

from libs.exceptions import EngineNotAvailableError, TTSException
import os
import tempfile
import time
import logging
import sys
from pathlib import Path as PathLib

# Add libs to path
sys.path.insert(0, str(PathLib(__file__).parent.parent / "libs"))

logger = logging.getLogger(__name__)

# Try to import pyttsx3
try:
    import pyttsx3  # type: ignore

    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    logger.warning("pyttsx3 not available. Install with: pip install pyttsx3")


def is_available() -> bool:
    """Check if pyttsx3 is available."""
    return AVAILABLE


def generate(text: str, config: dict) -> bytes:
    """
    Generate TTS and return audio as bytes.

    Args:
        text: Text to synthesize
        config: Configuration dict with language, rate, volume

    Returns:
        Audio bytes in WAV format
    """
    if not AVAILABLE:
        raise EngineNotAvailableError("pyttsx3 not available")

    try:
        # Initialize engine
        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        if voices:
            engine.setProperty("voice", voices[0].id)
        engine.setProperty("rate", config.get("rate", 150))
        engine.setProperty("volume", config.get("volume", 0.9))

        # Generate to temporary file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_filename = temp_file.name

        try:
            engine.save_to_file(text, temp_filename)
            engine.runAndWait()

            # Give time for file writing (Linux espeak issue)
            time.sleep(0.5)
            engine.stop()

            # Read and return bytes
            if not os.path.exists(temp_filename) or os.path.getsize(temp_filename) == 0:
                raise TTSException("pyttsx3 failed to generate audio")

            with open(temp_filename, "rb") as f:
                return f.read()
        finally:
            if os.path.exists(temp_filename):
                os.unlink(temp_filename)

    except Exception as e:
        raise TTSException(f"pyttsx3 generation failed: {e}")
