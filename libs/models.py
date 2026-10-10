#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Engine and model listing shared by `ttsgen --list` and the HTTP server."""

import logging
import os
from pathlib import Path

ENGINES_DIR = Path(__file__).resolve().parent.parent / "engines"

# The directory holding engines/, libs/ and install/. Relative model
# directories are anchored here, never on the current working directory, so
# every entry point finds the same models wherever it is started from.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Where each engine keeps its models: the environment key that overrides the
# location, the project-local directory used when it exists, and the fallback
# used otherwise. Relative entries are taken from the project root.
MODEL_DIRECTORIES = {
    "pipertts": ("PIPERTTS_MODELS", "cache/pipertts", ".piper/voices"),
    "silerotts": ("SILEROTTS_MODELS", "cache/silerotts", "~/.cache/torch/hub"),
    "coquitts": ("COQUITTS_MODELS", "cache/coquitts", "cache/coquitts"),
    "barktts": ("BARKTTS_MODELS", "cache/barktts", "~/.cache/suno/bark_v0"),
    "kokorotts": ("KOKOROTTS_MODELS", "cache/kokorotts", "~/.local/share/ttsgen/kokorotts"),
}

# The glob patterns that find an engine's models inside its directory.
MODEL_PATTERNS = {
    "pipertts": ["*.onnx"],
    "silerotts": ["**/*.pt", "**/*.jit"],
    "coquitts": ["tts/*"],
    "barktts": ["**/*.pt"],
    "kokorotts": ["*.onnx", "*.bin"],
}

ENGINE_NOTES = {
    "gtts": "cloud - no local models",
    "pyttsx3": "uses system espeak voices",
}


def project_path(value: str) -> str:
    """Expand `~` in a path and anchor it on the project root when it is relative.

    Args:
        value: A path from the environment, a config file or a default.

    Returns:
        The path itself when it is absolute, else the path under PROJECT_ROOT.
    """
    path = os.path.expanduser(value.strip())
    if os.path.isabs(path):
        return path
    return os.path.join(PROJECT_ROOT, path)


def models_directory(engine: str) -> str:
    """Resolve the model directory of an engine, the same way for every caller.

    The engines, `ttsgen --list` and the installers all come here, so they
    agree on one directory whatever the working directory is.

    Args:
        engine: A key of MODEL_DIRECTORIES.

    Returns:
        The configured directory when its environment key is set, else the
        project-local directory when it exists, else the engine's fallback.
    """
    env_key, project_dir, fallback = MODEL_DIRECTORIES[engine]
    configured = os.environ.get(env_key, "").strip()
    if configured:
        return project_path(configured)
    local_dir = project_path(project_dir)
    if os.path.isdir(local_dir):
        return local_dir
    return project_path(fallback)


def engine_model_sources() -> dict[str, tuple[str, list[str]]]:
    """Map each engine to its model directory and the glob patterns that find its models.

    Environment is read here, at call time, so config files loaded after import
    (ttsgen.conf, .env) are honoured.
    """
    return {engine: (models_directory(engine), MODEL_PATTERNS[engine]) for engine in MODEL_DIRECTORIES}


def model_display_name(engine: str, rel: Path) -> str:
    """Render a glob match into a grep-friendly model identifier.

    coqui caches models as tts/tts_models--multilingual--multi-dataset--xtts_v2/.
    We strip the tts/ prefix and restore '/' so the displayed name matches the
    string users put in COQUITTS_MODEL.
    """
    display = str(rel)
    if engine == "coquitts":
        display = display.removeprefix("tts/").replace("--", "/")
    return display


def collect_engine_rows() -> list[tuple[str, str, str]]:
    """Build the (engine, status, model) rows shown by --list, one row per model."""
    # Imported lazily: loading the engine package probes every optional dependency,
    # which is wasted work for runs that never reach --list.
    from engines import is_engine_available

    engine_names = sorted(p.stem for p in ENGINES_DIR.glob("*.py") if p.name != "__init__.py")
    model_sources = engine_model_sources()

    # Silence engine-loader probe warnings - status column already reports it.
    engines_logger = logging.getLogger("engines")
    prev_level = engines_logger.level
    engines_logger.setLevel(logging.ERROR)

    rows: list[tuple[str, str, str]] = []
    for name in engine_names:
        status = "installed" if is_engine_available(name) else "missing"

        # Cloud / system-voice engines have no on-disk model files.
        if name in ENGINE_NOTES:
            rows.append((name, status, ENGINE_NOTES[name]))
            continue

        # Engine deps not present → no point looking for models.
        if status == "missing" or name not in model_sources:
            rows.append((name, status, "-"))
            continue

        model_dir, patterns = model_sources[name]
        models_path = Path(model_dir)
        files: list[Path] = []
        if models_path.exists():
            for pattern in patterns:
                files.extend(sorted(models_path.glob(pattern)))
        if not files:
            rows.append((name, status, "-"))
        else:
            for model_file in files:
                rel = model_file.relative_to(models_path) if model_file.is_relative_to(models_path) else model_file
                rows.append((name, status, model_display_name(name, rel)))

    engines_logger.setLevel(prev_level)
    return rows


def main():
    """Module entrypoint placeholder - this file is import-only."""
    pass


if __name__ == "__main__":
    main()
