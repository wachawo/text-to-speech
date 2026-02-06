"""
Piper TTS Engine

High-quality offline text-to-speech using Piper.
Fast, natural-sounding voices with support for 50+ languages.
"""

from libs.exceptions import EngineNotAvailableError, TTSException
import io
import wave
import logging
import os

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

# Try to import Piper
try:
    from piper import PiperVoice  # type: ignore

    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    logger.warning("Piper TTS not available. Install with: pip install piper-tts")


def is_available() -> bool:
    """Check if Piper TTS is available."""
    return AVAILABLE


def get_models_directory() -> str:
    """
    Get the directory for storing Piper TTS models.

    Priority:
    1. Environment variable PIPERTTS_MODELS (from .env or export)
    2. .pipertts directory in project root (if exists)
    3. Default: .piper/voices in project root

    Returns:
        Path to models directory
    """
    # Get project root (parent of engines/ directory)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Priority 1: Check environment variable (from .env or export)
    env_var = os.environ.get("PIPERTTS_MODELS")
    if env_var:
        models_path = env_var.strip()
        # If relative path, resolve from project root
        if not os.path.isabs(models_path):
            models_path = os.path.join(project_root, models_path)
        return os.path.expanduser(models_path)

    # Priority 2: Check .pipertts directory in project root
    pipertts_dir = os.path.join(project_root, ".pipertts")
    if os.path.exists(pipertts_dir) and os.path.isdir(pipertts_dir):
        return pipertts_dir

    # Priority 3: Default - use .piper/voices in project
    return os.path.join(project_root, ".piper", "voices")


def get_voice_path(language: str = "en") -> str:
    """Get path to voice model for specified language."""
    voice_models = {
        "en": "en_US-lessac-medium",
        "ru": "ru_RU-ruslan-medium",
        "es": "es_ES-davefx-medium",
        "de": "de_DE-thorsten-medium",
        "fr": "fr_FR-siwis-medium",
        "it": "it_IT-riccardo-medium",
        "uk": "uk_UA-ukrainian_tts-medium",
        "zh": "zh_CN-huayan-medium",
    }

    voice_name = voice_models.get(language, voice_models["en"])

    # Get models directory
    models_dir = get_models_directory()

    # Check in models directory first
    voice_path = os.path.join(models_dir, f"{voice_name}.onnx")
    if os.path.exists(voice_path):
        return voice_path

    # Fallback: check other common locations
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    voice_dirs = [
        os.path.join(project_root, ".piper", "voices"),  # Project directory
        os.path.join(
            os.path.expanduser("~"), ".local", "share", "piper", "voices"
        ),  # User home
        "/usr/share/piper/voices",  # System-wide
        "./voices",  # Current directory
    ]

    for voice_dir in voice_dirs:
        voice_path = os.path.join(voice_dir, f"{voice_name}.onnx")
        if os.path.exists(voice_path):
            return voice_path

    # Default to models directory if not found
    return os.path.join(models_dir, f"{voice_name}.onnx")


def get_download_instructions(language: str) -> str:
    """Generate download instructions for voice model."""
    voice_models = {
        "en": ("en_US-lessac-medium", "en/en_US/lessac/medium"),
        "ru": ("ru_RU-ruslan-medium", "ru/ru_RU/ruslan/medium"),
        "es": ("es_ES-davefx-medium", "es/es_ES/davefx/medium"),
        "de": ("de_DE-thorsten-medium", "de/de_DE/thorsten/medium"),
        "fr": ("fr_FR-siwis-medium", "fr/fr_FR/siwis/medium"),
    }
    model_name, model_path = voice_models.get(
        language, ("en_US-lessac-medium", "en/en_US/lessac/medium")
    )

    base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"

    # Get models directory
    voice_dir = get_models_directory()

    return (
        f"Piper voice model not found for language '{language}'.\n\n"
        f"Option 1 - Use installation script (recommended):\n"
        f"   ./bin/install_pipertts.sh\n\n"
        f"Option 2 - Manual download with wget:\n"
        f"   mkdir -p {voice_dir}\n"
        f"   wget -P {voice_dir} {base_url}/{model_path}/{model_name}.onnx\n"
        f"   wget -P {voice_dir} {base_url}/{model_path}/{model_name}.onnx.json\n\n"
        f"Option 3 - Manual download with curl:\n"
        f"   mkdir -p {voice_dir}\n"
        f"   curl -L -o {voice_dir}/{model_name}.onnx {base_url}/{model_path}/{model_name}.onnx\n"
        f"   curl -L -o {voice_dir}/{model_name}.onnx.json {base_url}/{model_path}/{model_name}.onnx.json\n\n"
        f"See docs/PIPERTTS.md for more details"
    )


def generate(text: str, config: dict) -> bytes:
    """
    Generate TTS and return audio as bytes.

    Args:
        text: Text to synthesize
        config: Configuration dict with language

    Returns:
        Audio bytes in WAV format (22050 Hz, mono, 16-bit)
    """
    if not AVAILABLE:
        raise EngineNotAvailableError(
            "Piper TTS not available. Install with: pip install piper-tts\n"
            "See docs/PIPER.md for setup instructions."
        )
    language = config.get("language", "en")
    try:
        voice_path = get_voice_path(language)
        logger.info(voice_path)

        # Load voice model
        voice = PiperVoice.load(voice_path)

        # Generate audio to BytesIO
        audio_buffer = io.BytesIO()
        with wave.open(audio_buffer, "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)

        audio_buffer.seek(0)
        return audio_buffer.getvalue()

    except FileNotFoundError as e:
        instructions = get_download_instructions(language)
        raise TTSException(f"{instructions}\n\nError: {e}")
    except Exception as e:
        raise TTSException(f"Piper TTS generation failed: {e}")
