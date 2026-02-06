"""
Coqui TTS Engine

High-quality text-to-speech using Coqui TTS (formerly Mozilla TTS).
Supports voice cloning, multi-speaker models, and emotion control.

IMPORTANT: Requires Python 3.9-3.11 (NOT compatible with Python 3.12+)

Note: Works best with GPU. CPU mode is very slow.
"""

import tempfile
import os
import logging
import torch
from torch.serialization import add_safe_globals, safe_globals
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import XttsAudioConfig, XttsArgs
from TTS.config.shared_configs import BaseDatasetConfig
from libs.exceptions import EngineNotAvailableError, TTSException

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    # Get project root and load .env
except ImportError:

    def load_dotenv(*args, **kwargs):
        pass


project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_file = os.path.join(project_root, ".env")
if os.path.exists(env_file):
    load_dotenv(env_file)
else:
    load_dotenv()

logger = logging.getLogger(__name__)

COQUITTS_PATH = os.getenv("COQUITTS_PATH", ".coquitts")
COQUITTS_MODEL = os.getenv(
    "COQUITTS_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2"
)
COQUITTS_SAMPLE = os.getenv("COQUITTS_SAMPLE", "samples/1.wav")

# Try to import Coqui TTS
try:
    from TTS.api import TTS

    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    logger.warning("Coqui TTS not available. Install with: pip install TTS")


def is_available() -> bool:
    """Check if Coqui TTS is available."""
    return AVAILABLE


def get_models_directory() -> str:
    if COQUITTS_PATH:
        return os.path.abspath(os.path.expanduser(COQUITTS_PATH))
    local_dir = os.path.join(os.getcwd(), ".coquitts")
    if os.path.isdir(local_dir):
        return os.path.abspath(local_dir)
    return os.path.abspath(os.path.expanduser("~/.local/share/tts"))


def generate(text: str, config: dict) -> bytes:
    """
    Generate TTS and return audio as bytes.

    Args:
        text: Text to synthesize
        config: Configuration dict with language

    Returns:
        Audio bytes in WAV format (22050 Hz by default)

    Note:
        First run will download the model (can be slow).
        Generation is slow on CPU, fast on GPU.
    """
    if not is_available():
        raise EngineNotAvailableError(
            "Coqui TTS not available. Install with: pip install TTS\n"
            "See docs/COQUITTS.md for setup instructions."
        )
    if not os.path.exists(COQUITTS_SAMPLE):
        raise TTSException(f"Sample WAV not found: {COQUITTS_SAMPLE}")
    try:
        language = config.get("language", "en")
        model_name = COQUITTS_MODEL
        # Set custom models directory if configured
        models_dir = get_models_directory()
        # Coqui TTS uses TTS_HOME for model cache
        os.environ["TTS_HOME"] = models_dir
        os.environ["XDG_DATA_HOME"] = models_dir
        logger.info(f"Coqui TTS models directory: {models_dir}")
        try:
            add_safe_globals([XttsConfig, XttsAudioConfig, BaseDatasetConfig, XttsArgs])
        except Exception:
            pass
        # Initialize TTS
        device = "cuda" if torch.cuda.is_available() else "cpu"
        # This will download model on first use
        with safe_globals([XttsConfig, XttsAudioConfig, BaseDatasetConfig, XttsArgs]):
            tts = TTS(model_name=model_name, progress_bar=False).to(device)
        # Generate to temporary file (Coqui TTS requires file output)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_filename = temp_file.name
        try:
            # Generate audio
            # For multilingual models, specify language
            if "multilingual" in model_name:
                # tts.tts_to_file(text=text, file_path=temp_filename, language=language)
                tts.tts_to_file(
                    text=text,
                    file_path=temp_filename,
                    language=language,
                    speaker_wav=COQUITTS_SAMPLE,
                )
            else:
                tts.tts_to_file(text=text, file_path=temp_filename)
            # Read and return bytes
            if not os.path.exists(temp_filename) or os.path.getsize(temp_filename) == 0:
                raise TTSException("Coqui TTS failed to generate audio")
            with open(temp_filename, "rb") as f:
                return f.read()
        finally:
            if os.path.exists(temp_filename):
                os.unlink(temp_filename)
    except Exception as e:
        if "model" in str(e).lower() and "not found" in str(e).lower():
            raise TTSException(f"Coqui TTS model not found.\n" f"Error: {e}")
        raise TTSException(f"Coqui TTS generation failed: {e}")
