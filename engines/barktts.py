"""
Bark TTS Engine

Ultra-realistic text-to-speech by Suno AI.
Supports emotions, laughter, music, and sound effects.

Note: Very slow on CPU, requires significant memory (10GB+ models).
Best used with GPU.
"""

import io
import logging
import sys
import os

from libs.exceptions import EngineNotAvailableError, TTSException
from libs.tempfiles import safe_unlink

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    # Get project root and load .env
    _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _env_file = os.path.join(_project_root, ".env")
    if os.path.exists(_env_file):
        load_dotenv(_env_file)
except ImportError:
    pass  # dotenv not installed, skip

logger = logging.getLogger(__name__)

# Try to import Bark
try:
    from bark import SAMPLE_RATE, generate_audio, preload_models
    import numpy as np

    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    logger.warning(
        "Bark TTS not available. Install with: pip install git+https://github.com/suno-ai/bark.git"
    )


def is_available() -> bool:
    """Check if Bark TTS is available."""
    return AVAILABLE


def get_models_directory() -> str:
    """
    Get the directory for storing Bark TTS models.

    Priority:
    1. Environment variable BARKTTS_MODELS (from .env or export)
    2. .barktts directory in project root (if exists)
    3. Default: ~/.cache/suno/bark_v0

    Returns:
        Path to models directory
    """
    # Get project root (parent of engines/ directory)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Priority 1: Check environment variable (from .env or export)
    env_var = os.environ.get("BARKTTS_MODELS")
    if env_var:
        models_path = env_var.strip()
        # If relative path, resolve from project root
        if not os.path.isabs(models_path):
            models_path = os.path.join(project_root, models_path)
        return os.path.expanduser(models_path)

    # Priority 2: Check .barktts directory in project root
    barktts_dir = os.path.join(project_root, ".barktts")
    if os.path.exists(barktts_dir) and os.path.isdir(barktts_dir):
        return barktts_dir

    # Priority 3: Default - use Bark default
    return os.path.expanduser("~/.cache/suno/bark_v0")


def get_speaker_for_language(language: str) -> str:
    """
    Get appropriate speaker/voice for language.

    Bark uses speaker presets in format: v2/{language}_speaker_{number}

    Args:
        language: Language code

    Returns:
        Speaker preset string
    """
    # Speaker presets for different languages
    speaker_map = {
        "en": "v2/en_speaker_6",  # English (clear female)
        "ru": "v2/ru_speaker_0",  # Russian
        "es": "v2/es_speaker_0",  # Spanish
        "de": "v2/de_speaker_0",  # German
        "fr": "v2/fr_speaker_0",  # French
        "zh": "v2/zh_speaker_0",  # Chinese
        "ja": "v2/ja_speaker_0",  # Japanese
        "ko": "v2/ko_speaker_0",  # Korean
        "hi": "v2/hi_speaker_0",  # Hindi
        "it": "v2/it_speaker_0",  # Italian
        "pt": "v2/pt_speaker_0",  # Portuguese
        "pl": "v2/pl_speaker_0",  # Polish
        "tr": "v2/tr_speaker_0",  # Turkish
    }

    return speaker_map.get(language, speaker_map["en"])


def generate(text: str, config: dict) -> bytes:
    """
    Generate TTS and return audio as bytes.

    Args:
        text: Text to synthesize (can include [laugh], [sigh], ♪ for music, etc.)
        config: Configuration dict with language

    Returns:
        Audio bytes in WAV format (24000 Hz, mono, 32-bit float)

    Note:
        First run downloads models (10GB+), can take time.
        Generation is VERY slow on CPU (30-60s per sentence).
        Use GPU for practical speed.

    Special syntax:
        - [laugh] - Add laughter
        - [sigh] - Add sigh
        - ♪ music notes ♪ - Add music/singing
        - CAPITALIZATION - Emphasis
        - ... - Pauses
    """
    if not AVAILABLE:
        raise EngineNotAvailableError(
            "Bark TTS not available. Install with:\n"
            "   pip install git+https://github.com/suno-ai/bark.git\n"
            "See docs/BARK.md for setup instructions."
        )

    try:
        import scipy.io.wavfile
        import tempfile

        language = config.get("language", "en")

        # Set custom models directory if configured
        models_dir = get_models_directory()
        if models_dir != os.path.expanduser("~/.cache/suno/bark_v0"):
            # Bark uses XDG_CACHE_HOME for models
            # Set to custom directory/suno/bark_v0
            cache_dir = os.path.dirname(
                os.path.dirname(models_dir)
            )  # Remove /suno/bark_v0
            os.environ["XDG_CACHE_HOME"] = cache_dir
            logger.info(f"Using custom Bark TTS models directory: {models_dir}")

        # Fix for PyTorch 2.6+ weights_only security issue
        # Bark models require weights_only=False or safe_globals
        import torch
        import numpy as np

        torch_version = tuple(map(int, torch.__version__.split(".")[:2]))
        if torch_version >= (2, 6):
            # Add numpy globals to safe list for Bark models
            # Must pass actual objects, not strings
            torch.serialization.add_safe_globals([np.core.multiarray.scalar, np.dtype])

        # Preload models (first run downloads, subsequent runs load from cache)
        # This can take time on first run
        preload_models()

        # Get speaker for language
        history_prompt = get_speaker_for_language(language)

        # Generate audio
        # Bark returns numpy array with sample rate 24000
        audio_array = generate_audio(
            text, history_prompt=history_prompt, text_temp=0.7, waveform_temp=0.7
        )

        # Convert numpy array to WAV bytes
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_filename = temp_file.name

        try:
            # Save as WAV
            scipy.io.wavfile.write(temp_filename, SAMPLE_RATE, audio_array)

            # Read back as bytes
            with open(temp_filename, "rb") as f:
                audio_bytes = f.read()

            return audio_bytes
        finally:
            safe_unlink(temp_filename)

    except Exception as e:
        error_msg = str(e)

        if "No module named" in error_msg or "cannot import" in error_msg:
            raise EngineNotAvailableError(
                "Bark TTS dependencies missing. Install with:\n"
                "   pip install git+https://github.com/suno-ai/bark.git\n"
                "   pip install scipy\n"
                "See docs/BARK.md for details."
            )

        if "CUDA" in error_msg or "GPU" in error_msg or "memory" in error_msg.lower():
            raise TTSException(
                f"Bark TTS GPU/memory error.\n"
                f"Bark requires significant memory (10GB+ for models).\n"
                f"Consider using CPU with smaller models or use different engine.\n"
                f"Error: {e}"
            )

        raise TTSException(f"Bark TTS generation failed: {e}")
