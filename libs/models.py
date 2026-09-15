#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Engine and model listing shared by `ttsgen --list` and the HTTP server."""

import logging
import os
from pathlib import Path

ENGINES_DIR = Path(__file__).resolve().parent.parent / "engines"

ENGINE_NOTES = {
    "gtts": "cloud — no local models",
    "pyttsx3": "uses system espeak voices",
}


def engine_model_sources() -> dict[str, tuple[str, list[str]]]:
    """Map each engine to its model directory and the glob patterns that find its models.

    Environment is read here, at call time, so config files loaded after import
    (ttsgen.conf, .env) are honoured.
    """
    return {
        "pipertts": (os.getenv("PIPERTTS_MODELS", "cache/pipertts"), ["*.onnx"]),
        "silerotts": (os.getenv("SILEROTTS_MODELS", "cache/silerotts"), ["**/*.pt", "**/*.jit"]),
        "coquitts": (os.getenv("COQUITTS_MODELS", "cache/coquitts"), ["tts/*"]),
        "barktts": (os.getenv("BARKTTS_MODELS", "cache/barktts"), ["**/*.pt"]),
        "kokorotts": (os.getenv("KOKOROTTS_MODELS", "cache/kokorotts"), ["*.onnx", "*.bin"]),
    }


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

    # Silence engine-loader probe warnings — status column already reports it.
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
    """Module entrypoint placeholder — this file is import-only."""
    pass


if __name__ == "__main__":
    main()
