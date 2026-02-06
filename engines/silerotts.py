"""
Silero TTS Engine

High-quality offline text-to-speech using Silero models.
Fast on CPU, excellent quality, particularly good for Russian.

Supports: Russian, English, German, Spanish, French, Ukrainian, and more.
"""

import io
import os
import logging

from libs.exceptions import EngineNotAvailableError, TTSException

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    # Get project root and load .env
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_file = os.path.join(project_root, ".env")
    if os.path.exists(env_file):
        load_dotenv(env_file)
except ImportError:
    pass  # dotenv not installed, skip

logger = logging.getLogger(__name__)

# Try to import Silero dependencies
try:
    import torch  # type: ignore
    import torchaudio  # type: ignore

    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    logger.warning(
        "Silero TTS not available. Install with: pip install torch torchaudio"
    )


def is_available() -> bool:
    """Check if Silero TTS is available."""
    return AVAILABLE


def get_model_info(language: str = "en") -> tuple:
    """
    Get model information for language.

    Args:
        language: Language code

    Returns:
        Tuple of (model_id, speaker, sample_rate)
    """
    # Language to model mapping
    language_models = {
        "ru": ("v3_1_ru", "aidar", 48000),  # Russian (excellent quality)
        "en": ("v3_en", "en_0", 48000),  # English
        "de": ("v3_de", "bernd_ungerer", 48000),  # German
        "es": ("v3_es", "es_0", 48000),  # Spanish
        "fr": ("v3_fr", "fr_0", 48000),  # French
        "ua": ("v3_ua", "mykyta", 48000),  # Ukrainian
        "uk": ("v3_ua", "mykyta", 48000),  # Ukrainian (alias)
    }

    # Default to English if language not found
    return language_models.get(language, language_models["en"])


def get_models_directory() -> str:
    """
    Get the directory for storing Silero models.

    Priority:
    1. Environment variable SILEROTTS_MODELS (from .env or export)
    2. .silerotts directory in project root (if exists)
    3. Default: ~/.cache/torch/hub/

    Returns:
        Path to models directory
    """
    # Get project root (parent of engines/ directory)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Priority 1: Check environment variable (from .env or export)
    env_var = os.environ.get("SILEROTTS_MODELS")
    if env_var:
        models_path = env_var.strip()
        # If relative path, resolve from project root
        if not os.path.isabs(models_path):
            models_path = os.path.join(project_root, models_path)
        return os.path.expanduser(models_path)

    # Priority 2: Check .silerotts directory in project root
    silerotts_dir = os.path.join(project_root, ".silerotts")
    if os.path.exists(silerotts_dir) and os.path.isdir(silerotts_dir):
        return silerotts_dir

    # Priority 3: Default - use torch default
    return os.path.expanduser("~/.cache/torch/hub")


def generate(text: str, config: dict) -> bytes:
    """
    Generate TTS and return audio as bytes.

    Args:
        text: Text to synthesize
        config: Configuration dict with language

    Returns:
        Audio bytes in WAV format (48000 Hz, 16-bit, mono)

    Note:
        First run will download the model from torch hub.
        Models are cached in:
        - SILERO_MODELS_DIR env variable (highest priority), or
        - ~/.silerotts/ directory (if exists), or
        - ~/.cache/torch/hub/ (default fallback)
    """
    if not AVAILABLE:
        raise EngineNotAvailableError(
            "Silero TTS not available. Install with: pip install torch torchaudio\n"
            "See docs/SILEROTTS.md for setup instructions."
        )
    language = config.get("language", "en")
    try:
        model_id, speaker, sample_rate = get_model_info(language)

        # Set custom models directory if configured
        models_dir = get_models_directory()
        if models_dir != os.path.expanduser("~/.cache/torch/hub"):
            torch.hub.set_dir(models_dir)
            logger.info(f"Using custom Silero models directory: {models_dir}")

        # Load model from torch hub (cached after first download)
        device = torch.device("cpu")  # Use CPU

        # torch.hub.load returns (model, example_text)
        result = torch.hub.load(
            repo_or_dir="snakers4/silero-models",
            model="silero_tts",
            language=(
                language if language in ["ru", "en", "de", "es", "fr", "ua"] else "en"
            ),
            speaker=model_id,
            verbose=False,
            trust_repo=True,
        )

        # Unpack result
        if isinstance(result, tuple) and len(result) >= 2:
            model = result[0]
            # example_text = result[1]
        else:
            raise TTSException(f"Unexpected torch.hub.load result: {type(result)}")

        # Check model
        if model is None:
            raise TTSException("Silero model failed to load")

        if not hasattr(model, "apply_tts"):
            raise TTSException(
                f"Model has no apply_tts method. Model type: {type(model)}"
            )

        # Note: model.to() returns None for some Silero models, use in-place
        model.to(device)

        # Generate audio
        audio_tensor = model.apply_tts(
            text=text, speaker=speaker, sample_rate=sample_rate
        )

        # Convert tensor to WAV bytes
        audio_buffer = io.BytesIO()

        # Ensure audio is 2D (channels, samples)
        if audio_tensor.dim() == 1:
            audio_tensor = audio_tensor.unsqueeze(0)

        # Save to buffer as WAV
        torchaudio.save(audio_buffer, audio_tensor, sample_rate, format="wav")

        audio_buffer.seek(0)
        return audio_buffer.getvalue()

    except Exception as e:
        error_msg = str(e)

        if "No module named" in error_msg or "cannot import" in error_msg:
            raise EngineNotAvailableError(
                "Silero TTS dependencies missing. Install with:\n"
                "   pip install torch torchaudio\n"
                "See docs/SILEROTTS.md for details."
            )

        if "model" in error_msg.lower() and "not found" in error_msg.lower():
            raise TTSException(f"Silero model not found for language.\n" f"Error: {e}")

        raise TTSException(f"Silero TTS generation failed: {e}")
