#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bark TTS installer — torch + bark + scipy + numpy, optional model pre-download."""

import logging
import shutil
import sys
import traceback

from install.common import (
    choose_from,
    error,
    info,
    pip_install,
    project_root,
    prompt_yes_no,
    success,
    warn,
    warn_no_venv,
)

logger = logging.getLogger(__name__)

REQUIRED_GB = 15


def check_disk_space(non_interactive: bool) -> bool:
    free_bytes = shutil.disk_usage(str(project_root())).free
    free_gb = free_bytes // (1024 ** 3)
    if free_gb < REQUIRED_GB:
        warn(f"Low disk space: {free_gb} GB available. Bark requires ~{REQUIRED_GB} GB.")
        return prompt_yes_no("Continue anyway?", default=False, non_interactive=non_interactive)
    return True


def install_torch(non_interactive: bool) -> None:
    if non_interactive:
        info("\nInstalling PyTorch (CPU)...")
        pip_install(
            ["torch", "torchaudio"],
            extra_args=["--index-url", "https://download.pytorch.org/whl/cpu"],
        )
        return
    options = [
        "CPU only (works but VERY slow — 60–180s per sentence)",
        "GPU with CUDA (recommended — 10–30s per sentence)",
    ]
    choice = choose_from("\nSelect installation type:", options, default=1)
    if choice == 2:
        info("\nInstalling PyTorch with CUDA support...")
        pip_install(
            ["torch", "torchaudio"],
            extra_args=["--index-url", "https://download.pytorch.org/whl/cu118"],
        )
    else:
        info("\nInstalling PyTorch (CPU)...")
        pip_install(
            ["torch", "torchaudio"],
            extra_args=["--index-url", "https://download.pytorch.org/whl/cpu"],
        )


def predownload() -> int:
    """Trigger Bark's preload_models() with PyTorch 2.6+ safe-globals workaround."""
    try:
        import torch
        import numpy as np

        torch_version = tuple(int(x) for x in torch.__version__.split(".")[:2])
        if torch_version >= (2, 6):
            info("Detected PyTorch 2.6+, applying compatibility fix...")
            torch.serialization.add_safe_globals([np.core.multiarray.scalar, np.dtype])

        from bark import preload_models  # noqa: WPS433 — late import after pip install
        info("Downloading Bark models (text encoder ~1GB, coarse ~5GB, fine ~5GB)...")
        preload_models()
        success("All models downloaded and cached at ~/.cache/suno/bark_v0/")
        return 0
    except Exception as exc:
        error(f"Pre-download failed: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return 1


def install(non_interactive: bool = False) -> int:
    info("Bark TTS Installer")

    if sys.version_info[:2] < (3, 8):
        error(f"Python 3.8+ required. You have {sys.version_info.major}.{sys.version_info.minor}.")
        return 1

    if not warn_no_venv(non_interactive):
        warn("Installation cancelled.")
        return 0

    if not check_disk_space(non_interactive):
        warn("Installation cancelled.")
        return 0

    install_torch(non_interactive)

    info("\nInstalling Bark from GitHub...")
    pip_install(["git+https://github.com/suno-ai/bark.git"])

    info("\nInstalling additional dependencies...")
    pip_install(["scipy", "numpy"])

    if non_interactive:
        return 0

    options = [
        "Download models now (~30–60 min, 10–15 GB)",
        "Skip (download on first use)",
    ]
    choice = choose_from("\nPre-download models?", options, default=2)
    if choice == 1:
        rc = predownload()
        if rc != 0:
            return rc

    success("\nInstallation complete!")
    info("Usage:")
    print('  ttsgen "Hello world" --engine barktts')
    print('  ttsgen "That\'s funny [laugh]" --engine barktts')
    print('  ttsgen "Hello" --engine barktts --file output.wav')
    return 0


def main():
    pass


if __name__ == "__main__":
    main()
