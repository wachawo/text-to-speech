"""
TTS Tools and Utilities

Validation, configuration, functional programming helpers, and utilities.
"""

from engines import is_engine_available, get_engine_function
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Any, Optional, Union, cast
import io

from .exceptions import TTSException, EngineNotAvailableError, ValidationError
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logger = logging.getLogger(__name__)

# Type definitions
Config = Dict[str, Any]


def get_default_config() -> Config:
    """Get default configuration for TTS operations."""
    return {
        "engine": "gtts",
        "language": "en",
        "rate": 150,
        "volume": 0.9,
        "slow": False,
    }


def validate_text(text: str) -> str:
    """Validate and clean input text."""
    if not isinstance(text, str):
        raise ValidationError("Text must be a string")

    cleaned_text = text.strip()
    if not cleaned_text:
        raise ValidationError("Text cannot be empty")

    # Long text is the chunker's job (libs/cli.chunk_text). validate_text only
    # rejects pathological inputs that could exhaust memory or stall a worker
    # for hours. 1M chars ≈ a book chapter — far above realistic real-time use.
    if len(cleaned_text) > 1_000_000:
        raise ValidationError("Text too long (max 1,000,000 characters)")

    return cleaned_text


def validate_engine(engine: str) -> str:
    """
    Validate TTS engine type using dynamic engine loading.

    Checks if engine module exists in engines/ directory and if its
    dependencies are installed.
    """
    if not isinstance(engine, str) or not engine:
        raise ValidationError("Engine name must be a non-empty string")

    # Check if engine module exists and is available
    if not is_engine_available(engine):
        # Check if module file exists
        from pathlib import Path

        engine_file = Path(__file__).parent.parent / "engines" / f"{engine}.py"

        if not engine_file.exists():
            raise ValidationError(
                f"Engine '{engine}' not found.\n"
                f"Available engines: gtts, pyttsx3, piper (and any custom engines in engines/ directory)\n"
                f"To add '{engine}' engine: create engines/{engine}.py"
            )
        else:
            raise EngineNotAvailableError(
                f"Engine '{engine}' module found but dependencies not installed.\n"
                f"Check engines/{engine}.py for required packages."
            )

    return engine


def validate_language(language: str) -> str:
    """Validate language code."""
    if not isinstance(language, str) or len(language) != 2:
        raise ValidationError("Language must be a 2-character code")

    return language.lower()


def get_engine_generate_function(engine_name: str) -> Callable[..., Any]:
    """
    Get the generate function for an engine.

    Args:
        engine_name: Name of the engine

    Returns:
        Generate function that returns bytes
    """
    func = get_engine_function(engine_name)

    if not func:
        raise ValidationError(f"Engine {engine_name} has no generate function")

    return cast(Callable[..., Any], func)


def compose(*functions: Callable) -> Callable:
    """Compose multiple functions into a single function."""

    def composed(x: Any) -> Any:
        for f in reversed(functions):
            x = f(x)
        return x

    return composed


def with_engine(engine: str) -> Callable[..., Any]:
    """Create a function that uses the given engine."""

    def engine_wrapper(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            kwargs["engine"] = engine
            return func(*args, **kwargs)

        return wrapper

    return cast(Callable[..., Any], engine_wrapper)


def with_language(language: str) -> Callable[..., Any]:
    """Create a function that uses the given language."""

    def language_wrapper(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            kwargs["language"] = language
            return func(*args, **kwargs)

        return wrapper

    return cast(Callable[..., Any], language_wrapper)


def create_tts_pipeline(engine: str = "gtts", language: str = "en") -> Callable:
    """Create a TTS pipeline with predefined settings."""
    # Import here to avoid circular import
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from libs.api import (
        text_to_speech_file,
        text_to_speech_bytes,
        text_to_speech_bytesio,
    )

    def pipeline(
        text: str, output_format: str = "file", filename: Optional[str] = None
    ) -> Union[str, bytes, io.BytesIO]:
        if output_format == "file":
            return text_to_speech_file(text, filename, engine, language)
        elif output_format == "bytes":
            return text_to_speech_bytes(text, engine, language)
        elif output_format == "bytesio":
            return text_to_speech_bytesio(text, engine, language)
        else:
            raise ValidationError("output_format must be 'file', 'bytes', or 'bytesio'")

    return pipeline


def batch_tts(
    texts: List[str],
    engine: str = "gtts",
    language: str = "en",
    output_dir: str = "audio",
) -> List[str]:
    """Process multiple texts in batch."""
    if not isinstance(texts, list) or not texts:
        raise ValidationError("texts must be a non-empty list")

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    pipeline = create_tts_pipeline(engine, language)
    generated_files = []

    for i, text in enumerate(texts):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(output_dir, f"{timestamp}.mp3")

            result_filename = pipeline(text, "file", filename)
            generated_files.append(result_filename)
        except Exception as e:
            logger.error(f"Failed to process text {i}: {e}")
            raise TTSException(f"Batch processing failed at item {i}: {e}")

    return generated_files


def generate_timestamp_filename(prefix: str = "", extension: str = "mp3") -> str:
    """Generate filename with timestamp only."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if prefix:
        return f"{prefix}_{timestamp}.{extension}"
    else:
        return f"{timestamp}.{extension}"


def ensure_audio_directory(directory: str = "audio") -> str:
    """Ensure audio directory exists."""
    Path(directory).mkdir(parents=True, exist_ok=True)
    return directory
