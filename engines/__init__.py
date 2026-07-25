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
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

# Signature every engine module's `generate` must satisfy.
EngineFunction = Callable[[str, dict], bytes]


def get_engine_module_path(engine_name: str) -> Path | None:
    """Locate the module file backing an engine.

    Args:
        engine_name: Name of the engine (e.g. 'pipertts', 'gtts').

    Returns:
        Path to the module file, or None when no such file is shipped.
    """
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


def get_engine_voices(engine_name: str, language: str = "en") -> dict[str, object]:
    """Fetch the selectable voices of an engine for a given language.

    Engines that support multiple voices implement `list_voices(language) -> dict`
    with keys 'voices' (list) and 'default' (str|None). Engines without voice
    selection return an empty list.

    Args:
        engine_name: Name of the engine.
        language: Language code.

    Returns:
        Dict {'voices': [...], 'default': str|None}.
    """
    module = load_engine(engine_name)

    if module and hasattr(module, "list_voices"):
        voices: dict[str, object] = module.list_voices(language)
        return voices

    return {"voices": [], "default": None}


def main():
    """Module entrypoint placeholder — this file is import-only."""
    pass


if __name__ == "__main__":
    main()
