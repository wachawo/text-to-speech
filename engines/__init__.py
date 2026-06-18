"""
TTS Engines Package

Dynamic engine loading system. Each engine is a separate module that can be
optionally installed. Engines are loaded dynamically based on availability.

Engine Interface:
    Each engine module must implement:
    - is_available() -> bool
    - generate(text: str, config: dict) -> bytes
"""

import importlib
from pathlib import Path
from typing import Optional, Callable, Dict
import logging

logger = logging.getLogger(__name__)

# Type definitions
EngineFunction = Callable[[str, dict], bytes]


def get_engine_module_path(engine_name: str) -> Optional[Path]:
    """
    Check if engine module file exists.

    Args:
        engine_name: Name of the engine (e.g., 'pipertts', 'gtts')

    Returns:
        Path to the module file if exists, None otherwise
    """
    engines_dir = Path(__file__).parent
    module_path = engines_dir / f"{engine_name}.py"

    if module_path.exists():
        return module_path

    return None


def load_engine(engine_name: str) -> Optional[object]:
    """
    Dynamically load an engine module.

    Args:
        engine_name: Name of the engine

    Returns:
        Loaded module object or None if unavailable
    """
    # Check if module file exists
    if not get_engine_module_path(engine_name):
        logger.warning(f"Engine module not found: {engine_name}.py")
        return None

    try:
        # Try to import the engine module
        module = importlib.import_module(f".{engine_name}", package="engines")

        # Check if it's available (dependencies installed)
        if hasattr(module, "is_available") and module.is_available():
            return module
        else:
            logger.warning(f"Engine {engine_name} module found but dependencies not available")
            return None

    except ImportError as e:
        logger.warning(f"Failed to import engine {engine_name}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Error loading engine {engine_name}: {e}")
        return None


def get_available_engines() -> Dict[str, object]:
    """
    Get all available engines.

    Returns:
        Dictionary of {engine_name: module} for available engines
    """
    engines_dir = Path(__file__).parent
    available = {}

    # Find all .py files in engines directory
    for py_file in engines_dir.glob("*.py"):
        if py_file.name == "__init__.py":
            continue

        engine_name = py_file.stem
        module = load_engine(engine_name)

        if module:
            available[engine_name] = module

    return available


def get_supported_engines() -> list:
    """
    List all engine names shipped as modules, regardless of installed deps.

    Returns:
        Sorted list of engine names (module stems) found in engines/.
    """
    engines_dir = Path(__file__).parent
    names = [py_file.stem for py_file in engines_dir.glob("*.py") if py_file.name != "__init__.py"]
    return sorted(names)


def is_engine_available(engine_name: str) -> bool:
    """
    Check if an engine is available.

    Args:
        engine_name: Name of the engine

    Returns:
        True if engine is available, False otherwise
    """
    module = load_engine(engine_name)
    return module is not None


def get_engine_function(engine_name: str) -> Optional[EngineFunction]:
    """
    Get the generate function for an engine.

    Args:
        engine_name: Name of the engine

    Returns:
        Generate function or None if unavailable
    """
    module = load_engine(engine_name)

    if module and hasattr(module, "generate"):
        generate_func: EngineFunction = module.generate
        return generate_func

    return None
