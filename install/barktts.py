#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bark TTS installer — torch + bark + scipy + numpy, optional model pre-download."""

import logging
import shutil
import traceback

from install.common import (
    choose_from,
    error,
    info,
    install_torch_choice,
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
    """Return True when there is room for Bark's ~15 GB of weights, or the user insists."""
    free_bytes = shutil.disk_usage(str(project_root())).free
    free_gb = free_bytes // (1024**3)
    if free_gb < REQUIRED_GB:
        warn(f"Low disk space: {free_gb} GB available. Bark requires ~{REQUIRED_GB} GB.")
        return prompt_yes_no("Continue anyway?", default=False, non_interactive=non_interactive)
    return True


def predownload() -> int:
    """Fetch every Bark checkpoint up front. Returns 0 on success, 1 on failure.

    PyTorch 2.6+ defaults `torch.load` to `weights_only=True`, which rejects the
    numpy scalars stored in Bark's checkpoints, so they are allow-listed first.
    """
    try:
        # Late imports: torch, numpy and bark are pip-installed by install() above.
        import numpy as np
        import torch

        torch_version = tuple(int(x) for x in torch.__version__.split(".")[:2])
        if torch_version >= (2, 6):
            info("Detected PyTorch 2.6+, applying compatibility fix...")
            torch.serialization.add_safe_globals([np.core.multiarray.scalar, np.dtype])

        from bark import preload_models

        info("Downloading Bark models (text encoder ~1GB, coarse ~5GB, fine ~5GB)...")
        preload_models()
        success("All models downloaded and cached at ~/.cache/suno/bark_v0/")
        return 0
    except Exception as exc:
        error(f"Pre-download failed: {type(exc).__name__}: {str(exc)}\n{traceback.format_exc()}")
        return 1


def install(non_interactive: bool = False) -> int:
    """Install torch, Bark and its extras, optionally pre-downloading the weights.

    Returns 0 on success, 1 if a requested pre-download failed.
    """
    info("Bark TTS Installer")

    if not warn_no_venv(non_interactive):
        warn("Installation cancelled.")
        return 0

    if not check_disk_space(non_interactive):
        warn("Installation cancelled.")
        return 0

    info(
        "Note: Bark caches models in ~/.cache/suno/bark_v0/ (hardcoded by upstream); "
        "setting BARKTTS_MODELS won't relocate the cache, only the engine config."
    )

    install_torch_choice(non_interactive=non_interactive)

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
        exit_code = predownload()
        if exit_code != 0:
            return exit_code

    success("\nInstallation complete!")
    info("Usage:")
    logger.info('  ttsgen "Hello world" --engine barktts')
    logger.info('  ttsgen "That\'s funny [laugh]" --engine barktts')
    logger.info('  ttsgen "Hello" --engine barktts --file output.wav')
    return 0


def main():
    """Module entrypoint placeholder — this file is import-only."""
    pass


if __name__ == "__main__":
    main()
