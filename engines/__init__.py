#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dynamic discovery and loading of the optional TTS engine modules.

There is no static registry: every ``engines/<name>.py`` file is a candidate
engine and must implement ``is_available() -> bool`` and
``generate(text: str, config: dict) -> bytes``. An engine is only handed to
callers when its optional dependencies are importable.
"""

import importlib
import logging
import re
import traceback
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

# Local imports
from libs.model_ids import is_model_id

logger = logging.getLogger(__name__)

# Signature every engine module's `generate` must satisfy.
EngineFunction = Callable[[str, dict], bytes]

# What an engine name may look like: the stem of an engines/<name>.py file.
ENGINE_NAME_REGEX = re.compile(r"[a-z0-9_]{1,32}")


def get_engine_module_path(engine_name: str) -> Path | None:
    """Locate the module file backing an engine.

    Args:
        engine_name: Name of the engine (e.g. 'pipertts', 'gtts').

    Returns:
        Path to the module file, or None when no such file is shipped.
    """
    # A module name and nothing else: the name can arrive from a query
    # string, and anything with a separator or a dot must not reach the
    # filesystem lookup or import_module.
    if not isinstance(engine_name, str) or not ENGINE_NAME_REGEX.fullmatch(engine_name):
        return None
    # The package file itself (and any other underscore module) is not an
    # engine: get_supported_engines() leaves __init__.py out, and importing it
    # as `engines.__init__` would run the package code a second time.
    if engine_name.startswith("_"):
        return None
    engines_dir = Path(__file__).parent
    module_path = engines_dir / f"{engine_name}.py"

    if module_path.exists():
        return module_path

    return None


def load_engine(engine_name: str) -> object | None:
    """Import an engine module and return it only if its dependencies are installed.

    Args:
        engine_name: Name of the engine.

    Returns:
        The imported module, or None when it is missing, broken or unavailable.
    """
    if not get_engine_module_path(engine_name):
        logger.warning(f"Engine module not found: {engine_name}.py")
        return None

    try:
        module = importlib.import_module(f".{engine_name}", package="engines")

        # An engine reports False here when its optional dependencies are absent.
        if hasattr(module, "is_available") and module.is_available():
            return module
        else:
            logger.debug(f"Engine {engine_name} module found but dependencies not available")
            return None

    except ImportError as exc:
        logger.warning(f"Failed to import engine {engine_name}: {exc}")
        return None
    except Exception as exc:
        logger.warning(f"Error loading engine {engine_name}: {exc}")
        return None


def get_available_engines() -> dict[str, object]:
    """Collect every engine whose dependencies are installed in this environment.

    Returns:
        Mapping of engine name to the imported module.
    """
    engines_dir = Path(__file__).parent
    available = {}

    for py_file in engines_dir.glob("*.py"):
        if py_file.name == "__init__.py":
            continue

        engine_name = py_file.stem
        module = load_engine(engine_name)

        if module:
            available[engine_name] = module

    return available


def get_supported_engines() -> list:
    """List all engine names shipped as modules, regardless of installed deps.

    Returns:
        Sorted list of engine names (module stems) found in engines/.
    """
    engines_dir = Path(__file__).parent
    names = [py_file.stem for py_file in engines_dir.glob("*.py") if py_file.name != "__init__.py"]
    return sorted(names)


def is_engine_available(engine_name: str) -> bool:
    """Report whether an engine can be used right now.

    Args:
        engine_name: Name of the engine.

    Returns:
        True when the module exists and its dependencies are importable.
    """
    module = load_engine(engine_name)
    return module is not None


def get_engine_function(engine_name: str) -> EngineFunction | None:
    """Fetch the synthesis callable of an engine.

    Args:
        engine_name: Name of the engine.

    Returns:
        The engine's `generate` function, or None when the engine is unavailable.
    """
    module = load_engine(engine_name)

    if module and hasattr(module, "generate"):
        generate_func: EngineFunction = module.generate
        return generate_func

    return None


def get_engine_module(engine_name: str) -> ModuleType | None:
    """Import an engine module without the is_available() gate.

    A catalogue such as the kokorotts language table or the coquitts sample
    directory is readable whether or not the engine's dependencies are
    installed, since every engine guards its optional imports.

    Args:
        engine_name: Name of the engine.

    Returns:
        The imported module, or None when no engines/<name>.py matches
        ENGINE_NAME_REGEX.
    """
    if not get_engine_module_path(engine_name):
        return None
    return importlib.import_module(f".{engine_name}", package="engines")


def get_engine_voices(engine_name: str, language: str = "en", model: str | None = None) -> dict[str, object]:
    """Fetch the selectable voices of an engine for a given language.

    Engines that support multiple voices implement `list_voices(language) -> dict`
    with keys 'voices' (list) and 'default' (str|None), and optionally 'mix'
    (bool), True when the engine blends voices ('af_bella(2)+af_sky(1)'); a
    missing 'mix' counts as False. Engines without voice selection return an
    empty list.

    Args:
        engine_name: Name of the engine.
        language: Language code.
        model: A model id from the engine's list_models(), passed on as
            `list_voices(language, model)`; None keeps the one-argument call.

    Returns:
        Dict {'voices': [...], 'default': str|None}, plus 'mix' when the
        engine reports it.
    """
    # Imported without the is_available() gate: an engine whose listing really
    # needs its dependencies raises EngineNotAvailableError itself.
    module = get_engine_module(engine_name)

    if module is not None and hasattr(module, "list_voices"):
        if model is None:
            voices: dict[str, object] = module.list_voices(language)
        else:
            voices = module.list_voices(language, model)
        return voices

    return {"voices": [], "default": None}


def log_hook_failure(engine_name: str, hook: str, exc: Exception) -> None:
    """Log a discovery hook that raised, as a warning with the exception type, message and traceback."""
    logger.warning(f"Engine {engine_name} {hook} failed: {type(exc).__name__}: {str(exc)}\n{traceback.format_exc()}")


def get_engine_languages(engine_name: str, model: str | None = None) -> list[str] | None:
    """Fetch the language codes an engine declares through its optional `list_languages()` hook.

    The hook reads only constants or metadata and never loads a model. None
    means "not declared": the engine has no hook, the module is missing, or
    the hook failed (logged as a warning), and callers then let every code
    through to the engine, as before hooks existed.

    Args:
        engine_name: Name of the engine.
        model: A model id; the hook then describes that model. None keeps the
            no-argument call and describes the engine's default.

    Returns:
        The lowercased codes the engine serves, or None when not declared.
    """
    try:
        module = get_engine_module(engine_name)
        if module is None or not hasattr(module, "list_languages"):
            return None
        languages = module.list_languages() if model is None else module.list_languages(model)
        if languages is None:
            return None
        return [str(code).lower() for code in languages]
    except Exception as exc:
        log_hook_failure(engine_name, "list_languages", exc)
        return None


def list_engine_models(engine_name: str) -> list[dict]:
    """Fetch the models a request may name for an engine, letting a failing import or hook raise.

    Each item is {'id': str, 'languages': list[str]|None, 'installed': bool}.
    The hook reads only file names and metadata and never loads a model. The
    model check of a request uses this form, so a server-side failure (an
    unreadable models directory) is not mistaken for an engine without models.

    Args:
        engine_name: Name of the engine.

    Returns:
        The models, or [] when the engine has no hook or no module.

    Raises:
        Exception: Whatever the engine import or its `list_models()` hook raised.
    """
    module = get_engine_module(engine_name)
    if module is None or not hasattr(module, "list_models"):
        return []
    return filter_requestable_models(engine_name, [dict(item) for item in module.list_models()])


def filter_requestable_models(engine_name: str, models: list[dict]) -> list[dict]:
    """Keep the models whose id a request may send (libs.model_ids.MODEL_ID_REGEX), logging each one left out.

    A file such as `my model.onnx` or `_x.onnx` is on disk, but the request
    schema refuses its id, so listing it would advertise a model no request can
    name.
    """
    requestable = []
    for item in models:
        if is_model_id(item.get("id")):
            requestable.append(item)
        else:
            logger.info(f"Engine {engine_name} model {str(item.get('id'))[:128]!r} left out: not a valid model id")
    return requestable


def list_engine_model_ids(engine_name: str) -> list[str] | None:
    """Return the ids from the engine's optional `list_model_ids()` hook, or None when it has none.

    The hook answers the ids alone, without the `installed` state that
    `list_models()` may need a directory walk for (silerotts), so checking a
    requested model stays cheap. Ids a request cannot send are left out.

    Raises:
        Exception: Whatever the engine import or the hook raised.
    """
    module = get_engine_module(engine_name)
    if module is None or not hasattr(module, "list_model_ids"):
        return None
    return [str(model_id) for model_id in module.list_model_ids() if is_model_id(model_id)]


def get_engine_models(engine_name: str) -> list[dict]:
    """Fetch the models of an engine for discovery, as list_engine_models() does, with failures logged.

    Args:
        engine_name: Name of the engine.

    Returns:
        The models, or [] when the engine has no hook, the module is missing
        or the hook failed (logged as a warning).
    """
    try:
        return list_engine_models(engine_name)
    except Exception as exc:
        log_hook_failure(engine_name, "list_models", exc)
        return []


def get_engine_default_model(engine_name: str, language: str | None = None) -> str | None:
    """Return the model a request without `model` uses, from the optional `default_model(language)` hook.

    Args:
        engine_name: Name of the engine.
        language: Language code, for engines whose model depends on it.

    Returns:
        The model id, or None when it depends on the language and none was
        given, the engine has no models, or the hook failed (logged).
    """
    try:
        module = get_engine_module(engine_name)
        if module is None or not hasattr(module, "default_model"):
            return None
        model = module.default_model(language)
        return str(model) if model is not None else None
    except Exception as exc:
        log_hook_failure(engine_name, "default_model", exc)
        return None


def get_engine_capabilities(engine_name: str) -> dict | None:
    """Describe what an engine offers, from its module alone: models, languages, voices and output.

    Only the discovery hooks run (file names, small configs, constants): no
    model is loaded, so the answer is cheap and works without the engine's
    dependencies. `default_for` of a model lists the declared languages whose
    requests use it when they name no model.

    Args:
        engine_name: Name of the engine.

    Returns:
        Dict with 'models', 'default_model', 'model_selectable', 'languages',
        'voice_selectable', 'output_format' and 'max_text_length', or None when
        no engines/<name>.py matches the name.

    Raises:
        Exception: A shipped engine module that fails to import; it is broken,
            not unknown, so the error is not turned into None.
    """
    module = get_engine_module(engine_name)
    if module is None:
        return None
    models = get_engine_models(engine_name)
    languages = get_engine_languages(engine_name)
    for item in models:
        item["default_for"] = []
    if models and languages:
        by_id = {item.get("id"): item for item in models}
        for language in languages:
            model_id = get_engine_default_model(engine_name, language)
            if model_id in by_id:
                by_id[model_id]["default_for"].append(language)
    return {
        "models": models,
        "default_model": get_engine_default_model(engine_name),
        "model_selectable": bool(models),
        "languages": languages,
        "voice_selectable": hasattr(module, "list_voices"),
        "output_format": getattr(module, "OUTPUT_FORMAT", "wav"),
        "max_text_length": getattr(module, "MAX_TEXT_LENGTH", None),
    }


def main():
    """Module entrypoint placeholder — this file is import-only."""
    pass


if __name__ == "__main__":
    main()
