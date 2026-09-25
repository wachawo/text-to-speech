#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validation, default config and functional helpers shared by the API and the CLIs."""

import io
import logging
import os
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, cast

# Local imports
from engines import (
    ENGINE_NAME_REGEX,
    get_engine_function,
    get_engine_languages,
    get_engine_module_path,
    get_supported_engines,
    is_engine_available,
    list_engine_model_ids,
    list_engine_models,
)

from .exceptions import EngineNotAvailableError, TTSException, ValidationError
from .languages import LANGUAGE_CODE_ERROR, is_language_code, language_supported, normalize_language

# Makes the repository root importable when libs/ is used straight from a source
# checkout rather than from an installed wheel.
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

# Engine configuration passed down to `engines.<name>.generate()`.
Config = dict[str, Any]

# Text longer than this is rejected outright. Long text is the chunker's job
# (libs/cli.chunk_text); this limit only stops pathological inputs that would
# exhaust memory or stall a worker for hours. 1M chars is roughly a book chapter.
MAX_TEXT_LENGTH = 1_000_000

# How many model ids an "Unknown model" message lists before it says "(+N more)".
MAX_LISTED_MODELS = 20


def get_default_config() -> Config:
    """Return the baseline engine config that callers then override per request."""
    return {
        "engine": "gtts",
        "language": "en",
        "rate": 150,
        "volume": 0.9,
        "slow": False,
    }


def validate_text(text: str) -> str:
    """Return the input text stripped of surrounding whitespace.

    Args:
        text: Raw text supplied by the caller.

    Returns:
        The trimmed text.

    Raises:
        ValidationError: If the value is not a string, is blank, or exceeds
            MAX_TEXT_LENGTH characters.
    """
    if not isinstance(text, str):
        raise ValidationError("Text must be a string")

    cleaned_text = text.strip()
    if not cleaned_text:
        raise ValidationError("Text cannot be empty")

    if len(cleaned_text) > MAX_TEXT_LENGTH:
        raise ValidationError("Text too long (max 1,000,000 characters)")

    return cleaned_text


def validate_engine(engine: str) -> str:
    """Return the engine name after confirming its module loads and its deps are installed.

    Args:
        engine: Engine name, matching a module in the engines/ package.

    Returns:
        The engine name unchanged.

    Raises:
        ValidationError: If the name is empty or no engines/<engine>.py exists.
        EngineNotAvailableError: If the module exists but its dependencies do not.
    """
    if not isinstance(engine, str) or not engine:
        raise ValidationError("Engine name must be a non-empty string")

    if not is_engine_available(engine):
        # Distinguish "no such engine" from "engine present, deps missing" so the
        # message tells the user whether to write a module or run pip.
        # get_engine_module_path applies the engine-name rule, so the package
        # file engines/__init__.py or a path does not count as a shipped engine.
        if get_engine_module_path(engine) is None:
            supported = ", ".join(get_supported_engines())
            raise ValidationError(
                f"Engine '{engine}' not found.\n"
                f"Available engines: {supported} (and any custom engines in engines/ directory)\n"
                f"To add '{engine}' engine: create engines/{engine}.py"
            )
        else:
            raise EngineNotAvailableError(
                f"Engine '{engine}' module found but dependencies not installed.\n"
                f"Check engines/{engine}.py for required packages."
            )

    return engine


def validate_language(language: str) -> str:
    """Return a normalized language code: a lowercased 2-character code or a tag such as 'zh-cn'.

    Raises:
        ValidationError: If the value is neither a string of exactly two
            characters nor a tag such as 'zh-cn', 'pt_BR' or 'es-419'.
    """
    if not is_language_code(language):
        raise ValidationError(LANGUAGE_CODE_ERROR)

    return normalize_language(language)


def validate_engine_language(engine: str, language: str, model: str | None = None) -> None:
    """Refuse a language the engine (or the model named by `model`) declares it does not serve.

    Engines that do not declare their languages (no `list_languages()` hook,
    or a hook that returns None) accept every code, as does an unknown engine,
    which validate_engine reports on its own. A tag passes when the engine
    lists it or its primary subtag ('en-gb' for an engine that lists 'en').

    Raises:
        ValidationError: The engine lists its languages and `language` is not among them.
    """
    languages = get_engine_languages(engine) if model is None else get_engine_languages(engine, model)
    if language_supported(language, languages):
        return
    supported = ", ".join(languages or [])
    subject = f"engine '{engine}'" if model is None else f"engine '{engine}' model '{model}'"
    raise ValidationError(f"Language '{language}' is not supported by {subject}. Supported: {supported}")


def validate_model(engine: str, model: str | None) -> str | None:
    """Return a model the engine lists, or None for the engine default.

    The id is only compared with the ids the engine lists (its optional
    `list_model_ids()` hook, else `list_models()`); it is never used as a
    path, so a crafted value cannot reach the filesystem, and the messages
    name no path.

    Args:
        engine: Engine name.
        model: A model id from the engine's list_models(), or None / '' for
            the engine default.

    Raises:
        ValidationError: The engine does not exist, has no selectable models,
            or does not list `model`.
        TTSException: The engine's model listing failed on the server (an
            unreadable models directory), which is not the client's error.
    """
    if model is None or model == "":
        return None
    if not get_engine_module_path(engine):
        # The name comes from a query string on /api/voices; echo it only when
        # it is a well-formed engine name, never a forged log line or a long URL.
        if isinstance(engine, str) and ENGINE_NAME_REGEX.fullmatch(engine):
            raise ValidationError(f"Engine '{engine}' not found")
        raise ValidationError("Engine not found")
    try:
        model_ids = list_engine_model_ids(engine)
        if model_ids is None:
            model_ids = [str(item.get("id")) for item in list_engine_models(engine)]
    except Exception as exc:
        raise TTSException(f"Engine '{engine}' could not list its models: {type(exc).__name__}: {str(exc)}") from exc
    if not model_ids:
        raise ValidationError(f"Engine '{engine}' has no selectable models")
    if model in model_ids:
        return model
    listed = ", ".join(model_ids[:MAX_LISTED_MODELS])
    more = f" (+{len(model_ids) - MAX_LISTED_MODELS} more)" if len(model_ids) > MAX_LISTED_MODELS else ""
    raise ValidationError(f"Unknown model '{model}' for engine '{engine}'. Available: {listed}{more}")


def get_engine_generate_function(engine_name: str) -> Callable[..., Any]:
    """Look up the `generate(text, config)` callable of an engine.

    Args:
        engine_name: Engine name, matching a module in the engines/ package.

    Returns:
        The engine's generate function, which returns audio bytes.

    Raises:
        ValidationError: If the engine exposes no generate function.
    """
    func = get_engine_function(engine_name)

    if not func:
        raise ValidationError(f"Engine {engine_name} has no generate function")

    return cast(Callable[..., Any], func)


def compose(*functions: Callable) -> Callable:
    """Combine callables right-to-left, so compose(f, g)(x) evaluates f(g(x))."""

    def composed(x: Any) -> Any:
        """Apply every wrapped function to x, last argument first."""
        for f in reversed(functions):
            x = f(x)
        return x

    return composed


def with_engine(engine: str) -> Callable[..., Any]:
    """Build a decorator that pins the `engine` keyword of the function it wraps."""

    def engine_wrapper(func: Callable[..., Any]) -> Callable[..., Any]:
        """Wrap func so every call is forced to use the captured engine."""

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Inject engine=<captured> and delegate to the wrapped function."""
            kwargs["engine"] = engine
            return func(*args, **kwargs)

        return wrapper

    return cast(Callable[..., Any], engine_wrapper)


def with_language(language: str) -> Callable[..., Any]:
    """Build a decorator that pins the `language` keyword of the function it wraps."""

    def language_wrapper(func: Callable[..., Any]) -> Callable[..., Any]:
        """Wrap func so every call is forced to use the captured language."""

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Inject language=<captured> and delegate to the wrapped function."""
            kwargs["language"] = language
            return func(*args, **kwargs)

        return wrapper

    return cast(Callable[..., Any], language_wrapper)


def create_tts_pipeline(engine: str = "gtts", language: str = "en") -> Callable:
    """Build a synthesis callable with the engine and language already bound.

    Args:
        engine: Engine name used for every call of the returned pipeline.
        language: Language code (two letters or a tag such as 'zh-cn') used for every call.

    Returns:
        A callable `(text, output_format="file", filename=None)` returning a
        path, raw bytes or a BytesIO depending on output_format.
    """
    # Imported inside the function: libs.api imports this module at load time, so a
    # module-level import here would be circular.
    from libs.api import (
        text_to_speech_bytes,
        text_to_speech_bytesio,
        text_to_speech_file,
    )

    def pipeline(text: str, output_format: str = "file", filename: str | None = None) -> str | bytes | io.BytesIO:
        """Synthesize text with the bound engine/language in the requested form.

        Raises:
            ValidationError: If output_format is not file, bytes or bytesio.
        """
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
    texts: list[str],
    engine: str = "gtts",
    language: str = "en",
    output_dir: str = "audio",
) -> list[str]:
    """Synthesize several texts into timestamped MP3 files under output_dir.

    Args:
        texts: Non-empty list of texts, synthesized sequentially.
        engine: Engine name used for every item.
        language: Language code (two letters or a tag such as 'zh-cn') used for every item.
        output_dir: Destination directory, created if missing.

    Returns:
        Paths of the generated files, in input order.

    Raises:
        ValidationError: If texts is not a non-empty list.
        TTSException: On the first item that fails; earlier files are kept.
    """
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
        except Exception as exc:
            logger.error(f"Failed to process text {i}: {exc}")
            raise TTSException(f"Batch processing failed at item {i}: {exc}") from exc

    return generated_files


def generate_timestamp_filename(prefix: str = "", extension: str = "mp3") -> str:
    """Build a `[prefix_]YYYYmmdd_HHMMSS.<extension>` filename from the current time."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if prefix:
        return f"{prefix}_{timestamp}.{extension}"
    else:
        return f"{timestamp}.{extension}"


def ensure_audio_directory(directory: str = "audio") -> str:
    """Create the audio output directory if needed and return its path."""
    Path(directory).mkdir(parents=True, exist_ok=True)
    return directory
