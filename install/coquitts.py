#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Coqui TTS installer — pip + optional model pre-download with PyTorch 2.6+ workaround."""

import logging
import os
import sys
import traceback
from pathlib import Path

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

DEFAULT_MODEL  = "tts_models/multilingual/multi-dataset/xtts_v2"
ENGLISH_MODEL  = "tts_models/en/ljspeech/tacotron2-DDC"
DEFAULT_SAMPLE = "samples/1.wav"

logger = logging.getLogger(__name__)


def check_python_version() -> bool:
    """Coqui TTS requires Python 3.9–3.11."""
    major, minor = sys.version_info[:2]
    if major != 3 or minor < 9 or minor > 11:
        error(f"Coqui TTS requires Python 3.9–3.11. You have {major}.{minor}.")
        warn("Either install a compatible Python or skip this engine.")
        return False
    return True


def check_sample_file() -> None:
    """Warn if COQUITTS_SAMPLE points to a missing file (xtts_v2 needs it at synthesis time)."""
    sample = os.environ.get("COQUITTS_SAMPLE", DEFAULT_SAMPLE)
    sample_path = Path(sample)
    if not sample_path.is_absolute():
        sample_path = project_root() / sample
    if not sample_path.exists():
        warn(f"COQUITTS_SAMPLE points to {sample_path} which doesn't exist.")
        warn("xtts_v2 requires a voice sample WAV at synthesis time. Place a 5–10s clean recording there.")


def predownload_model(model_name: str) -> int:
    """Download and load a Coqui model. Returns exit code."""
    try:
        from torch.serialization import add_safe_globals
        try:
            from TTS.tts.configs.xtts_config import XttsConfig
            from TTS.tts.models.xtts import XttsAudioConfig, XttsArgs
            from TTS.config.shared_configs import BaseDatasetConfig
            add_safe_globals([XttsConfig, XttsAudioConfig, BaseDatasetConfig, XttsArgs])
        except ImportError:
            pass

        from TTS.api import TTS
        info(f"\nDownloading {model_name}...")
        TTS(model_name, progress_bar=True, gpu=False)
        success("Download complete!")
        return 0
    except Exception as exc:
        error(f"Download failed: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return 1


def install(non_interactive: bool = False) -> int:
    info("Coqui TTS Installer")

    if not check_python_version():
        return 1

    if not warn_no_venv(non_interactive):
        warn("Installation cancelled.")
        return 0

    info("\nInstalling Coqui TTS (transformers pinned to 4.33.0 for compatibility)...")
    pip_install(["TTS", "transformers==4.33.0"])

    # Resolve model from env (COQUITTS_MODEL) — primary source of truth.
    env_model = os.environ.get("COQUITTS_MODEL", "").strip()

    if env_model:
        info(f"\nUsing model from COQUITTS_MODEL env: {env_model}")
        if "xtts" in env_model.lower():
            warn("\nIMPORTANT: License Agreement")
            print("The xtts model requires accepting a license:")
            print("  - Non-commercial use: CPML license (https://coqui.ai/cpml)")
            print("  - Commercial use: Requires commercial license from Coqui")
            accept = prompt_yes_no(
                "\nDo you accept the non-commercial CPML license?",
                default=non_interactive,
                non_interactive=non_interactive,
            )
            if not accept:
                warn("License not accepted. Skipping model download.")
                return 0
        rc = predownload_model(env_model)
        if rc != 0:
            return rc
        check_sample_file()
        success("\nInstallation complete!")
        return 0

    if non_interactive:
        success("\nInstallation complete (no COQUITTS_MODEL set — model will download on first use).")
        return 0

    options = [
        f"Multilingual model ({DEFAULT_MODEL}, ~1.8GB) — best quality, voice cloning",
        f"English model ({ENGLISH_MODEL}, ~200MB) — fast",
        "Skip (download on first use)",
    ]
    choice = choose_from("\nPre-download a model?", options, default=3)

    if choice == 1:
        warn("\nIMPORTANT: License Agreement")
        print("The xtts_v2 model requires accepting a license:")
        print("  - Non-commercial use: CPML license (https://coqui.ai/cpml)")
        print("  - Commercial use: Requires commercial license from Coqui")
        if not prompt_yes_no("\nDo you accept the non-commercial CPML license?", default=False):
            warn("License not accepted. Skipping model download.")
        else:
            rc = predownload_model(DEFAULT_MODEL)
            if rc != 0:
                return rc
            check_sample_file()
    elif choice == 2:
        rc = predownload_model(ENGLISH_MODEL)
        if rc != 0:
            return rc

    success("\nInstallation complete!")
    info("Usage:")
    print('  tts "Hello world" --engine coquitts')
    print('  tts "Привет мир" --engine coquitts --language ru')
    return 0


def main():
    pass


if __name__ == "__main__":
    main()
