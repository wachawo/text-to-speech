#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kokoro TTS installer — pip + model + voices download from upstream releases.

Wraps `kokoro-onnx` (https://github.com/thewh1teagle/kokoro-onnx) which is the
Python binding behind the `nazdridoy/kokoro-tts` CLI. Two artifacts are needed:
    - kokoro-v1.0.onnx   (~310 MB) — TTS model
    - voices-v1.0.bin    (~25 MB)  — voice embeddings

Both are mirrored on the nazdridoy release tag we pin to.
"""

import logging
import sys
from pathlib import Path

from install.common import (
    choose_from,
    download_file,
    info,
    pip_install,
    project_root,
    prompt_yes_no,
    resolve_models_dir,
    success,
    warn,
    warn_no_venv,
)

logger = logging.getLogger(__name__)

RELEASE_BASE = "https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0"
MODEL_FILE = "kokoro-v1.0.onnx"
VOICES_FILE = "voices-v1.0.bin"


def check_python_version() -> bool:
    """kokoro-onnx supports Python 3.10–3.12 (3.13+ not yet, see upstream)."""
    major, minor = sys.version_info[:2]
    if major != 3 or minor < 10:
        warn(f"kokoro-onnx recommends Python 3.10–3.12. You have {major}.{minor}.")
        return False
    if minor >= 13:
        warn(f"kokoro-onnx may not yet support Python {major}.{minor}. Continuing anyway.")
    return True


def models_dir(non_interactive: bool = False) -> Path:
    """Resolve (and create) the directory that holds the Kokoro ONNX model and voices."""
    return resolve_models_dir(
        engine_label="Kokoro TTS",
        env_key="KOKOROTTS_MODELS",
        default_dir=Path.home() / ".local" / "share" / "ttsgen" / "kokorotts",
        project_dir=project_root() / "cache" / "kokorotts",
        non_interactive=non_interactive,
    )


def select_runtime(non_interactive: bool) -> str:
    """Choose onnxruntime flavor. Returns the pip package name."""
    if non_interactive:
        return "onnxruntime"
    options = [
        "CPU only (onnxruntime, works everywhere)",
        "GPU with CUDA (onnxruntime-gpu, NVIDIA only)",
    ]
    choice = choose_from("\nSelect ONNX Runtime build:", options, default=1)
    return "onnxruntime-gpu" if choice == 2 else "onnxruntime"


def install(non_interactive: bool = False) -> int:
    """Install kokoro-onnx plus a runtime, then download the model and voice files.

    Returns 0 on success, 1 if the user declines an unsupported Python version.
    """
    info("Kokoro TTS Installer")

    if not check_python_version() and not non_interactive:
        if not prompt_yes_no("Continue anyway?", default=False):
            return 1

    if not warn_no_venv(non_interactive):
        warn("Installation cancelled.")
        return 0

    target = models_dir(non_interactive=non_interactive)
    info(f"Models directory: {target}")

    runtime_pkg = select_runtime(non_interactive)
    info(f"\nInstalling {runtime_pkg}...")
    pip_install([runtime_pkg])

    info("\nInstalling kokoro-onnx + soundfile...")
    pip_install(["kokoro-onnx", "soundfile"])

    info("\nDownloading Kokoro model files...")
    for fname in (MODEL_FILE, VOICES_FILE):
        download_file(f"{RELEASE_BASE}/{fname}", target / fname, label=fname)

    success("\nInstallation complete!")
    info(f"Models in: {target}")
    info("Usage:")
    logger.info('  ttsgen "Hello world" --engine kokorotts')
    logger.info('  ttsgen "Bonjour" --engine kokorotts --language fr')
    logger.info('  KOKOROTTS_VOICE=am_adam ttsgen "Hi" --engine kokorotts')
    return 0


def main():
    """Module entrypoint placeholder — this file is import-only."""
    pass


if __name__ == "__main__":
    main()
