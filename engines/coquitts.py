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
from libs.exceptions import CustomError, EngineNotAvailableError, TTSException, ValidationError

# Coqui xtts_v2 is the slowest engine but voice-cloning works on book-length text.
# Kept high deliberately — chunking and pacing are the caller's job.
MAX_TEXT_LENGTH = 1_000_000
from libs.sample_resolver import resolve_sample_path
from libs.tempfiles import safe_unlink

# .env via find_dotenv (walks up from cwd) → then .env.local override.
try:
    from dotenv import find_dotenv, load_dotenv
except ImportError:

    def find_dotenv(*args, **kwargs):
        return ""

    def load_dotenv(*args, **kwargs):
        pass


found = find_dotenv(usecwd=True)
if found:
    load_dotenv(found)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
local_env_file = os.path.join(project_root, ".env.local")
if os.path.exists(local_env_file):
    load_dotenv(local_env_file, override=True)

logger = logging.getLogger(__name__)

DEFAULT_COQUITTS_PATH   = ".coquitts"
DEFAULT_COQUITTS_MODEL  = "tts_models/multilingual/multi-dataset/xtts_v2"
# Single source of truth shared with `ttsrec`. A fresh `ttsrec` writes here,
# `ttsgen --engine coquitts` reads from here. Override via COQUITTS_SAMPLE.
DEFAULT_COQUITTS_SAMPLE = str(os.path.expanduser("~/.config/ttsgen.wav"))

# Cache TTS instances by (model_name, device) to avoid 15s reload of xtts_v2
# checkpoint on every synthesis call. Keyed by tuple → instance.
_TTS_CACHE: dict = {}

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
    coquitts_path = os.getenv("COQUITTS_PATH", DEFAULT_COQUITTS_PATH)
    if coquitts_path:
        return os.path.abspath(os.path.expanduser(coquitts_path))
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
    if len(text) > MAX_TEXT_LENGTH:
        raise ValidationError(f"Text too long for coquitts: {len(text)} > {MAX_TEXT_LENGTH}")
    sample_wav = resolve_sample_path(os.getenv("COQUITTS_SAMPLE", DEFAULT_COQUITTS_SAMPLE))
    if not os.path.exists(sample_wav):
        raise CustomError(
            {
                "error": "voice_sample_missing",
                "message": (
                    f"Voice sample WAV not found: {sample_wav}\n"
                    f"\n"
                    f"xtts_v2 needs a 5-10s recording of a target voice. Create one with:\n"
                    f"    ttsrec                           # record into the configured path\n"
                    f"    ttsrec {sample_wav}\n"
                    f"    ttsrec /path/to/your_voice.wav\n"
                    f"\n"
                    f"Or set COQUITTS_SAMPLE in .env / .env.local to an existing recording."
                ),
                "path": sample_wav,
            }
        )
    try:
        language = config.get("language", "en")
        model_name = os.getenv("COQUITTS_MODEL", DEFAULT_COQUITTS_MODEL)
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
        device = "cuda" if torch.cuda.is_available() else "cpu"
        cache_key = (model_name, device)
        tts = _TTS_CACHE.get(cache_key)
        if tts is None:
            logger.info(f"Loading {model_name} on {device} (first call — ~15s for xtts_v2)...")
            with safe_globals([XttsConfig, XttsAudioConfig, BaseDatasetConfig, XttsArgs]):
                tts = TTS(model_name=model_name, progress_bar=False).to(device)
            _TTS_CACHE[cache_key] = tts
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
                    speaker_wav=sample_wav,
                )
            else:
                tts.tts_to_file(text=text, file_path=temp_filename)
            # Read and return bytes
            if not os.path.exists(temp_filename) or os.path.getsize(temp_filename) == 0:
                raise TTSException("Coqui TTS failed to generate audio")
            with open(temp_filename, "rb") as f:
                return f.read()
        finally:
            safe_unlink(temp_filename)
    except Exception as e:
        if "model" in str(e).lower() and "not found" in str(e).lower():
            raise TTSException(f"Coqui TTS model not found.\n" f"Error: {e}")
        raise TTSException(f"Coqui TTS generation failed: {e}")
