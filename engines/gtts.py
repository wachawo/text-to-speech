"""
gTTS Engine

Online text-to-speech using Google Text-to-Speech.
"""

from libs.exceptions import EngineNotAvailableError, TTSException
import io
import logging

logger = logging.getLogger(__name__)

# Try to import gTTS
try:
    from gtts import gTTS  # type: ignore

    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    logger.warning("gTTS not available. Install with: pip install gtts")


def is_available() -> bool:
    """Check if gTTS is available."""
    return AVAILABLE


def generate(text: str, config: dict) -> bytes:
    """
    Generate TTS and return audio as bytes.

    Args:
        text: Text to synthesize
        config: Configuration dict with language, slow

    Returns:
        Audio bytes in MP3 format
    """
    if not AVAILABLE:
        raise EngineNotAvailableError("gTTS not available")

    try:
        language = config.get("language", "en")
        slow = config.get("slow", False)

        tts = gTTS(text=text, lang=language, slow=slow)
        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)

        return audio_buffer.getvalue()

    except Exception as e:
        raise TTSException(f"gTTS generation failed: {e}")
