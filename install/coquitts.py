#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""coqui-tts installer (Idiap community fork) — pip + optional model pre-download.

Original Coqui TTS (`TTS` on PyPI) was last released Dec 2023 and capped at Python 3.11.
We use the maintained fork `coqui-tts` (distribution name) which keeps the same `TTS`
import name for API compatibility but supports Python 3.12+.

PyTorch 2.6+ workaround for xtts_v2 checkpoints (add_safe_globals) still applies — see predownload_model().
"""

import io
import logging
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

from install.common import (
    choose_from,
    error,
    info,
    install_torch_choice,
    pip_install,
    project_root,
    prompt_yes_no,
    resolve_file_path,
    resolve_models_dir,
    success,
    warn,
    warn_no_venv,
)

DEFAULT_MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"
ENGLISH_MODEL = "tts_models/en/ljspeech/tacotron2-DDC"
DEFAULT_SAMPLE = "samples/1.wav"

logger = logging.getLogger(__name__)


def check_python_version() -> bool:
    """coqui-tts (Idiap fork) requires Python 3.9+."""
    major, minor = sys.version_info[:2]
    if major != 3 or minor < 9:
        error(f"coqui-tts requires Python 3.9+. You have {major}.{minor}.")
        return False
    return True


def model_dir_for(model_name: str) -> Path:
    """Path where Coqui caches a model: <TTS_HOME>/tts/<model_name with '/' -> '--'>."""
    base = Path(os.environ.get("TTS_HOME") or (Path.home() / ".local" / "share" / "tts"))
    return base / "tts" / model_name.replace("/", "--")


def model_already_present(model_name: str) -> bool:
    """True if the model directory exists and looks populated (has config.json)."""
    d = model_dir_for(model_name)
    return d.is_dir() and (d / "config.json").exists()


def prompt_redownload_or_skip(model_name: str, non_interactive: bool = False) -> bool:
    """If model already exists, ask whether to reuse or wipe+redownload.

    Returns True if caller should SKIP download (model already usable).
    Returns False if model is absent OR user opted to delete and redownload.
    """
    if not model_already_present(model_name):
        return False
    d = model_dir_for(model_name)
    info(f"\nModel already present at {d}")
    if non_interactive:
        info("Reusing existing files (non-interactive).")
        return True
    if not prompt_yes_no("Re-download (this will delete the existing files)?", default=False):
        info("Reusing existing files.")
        return True
    try:
        shutil.rmtree(d)
        info(f"Removed {d}.")
    except OSError as exc:
        error(f"Could not remove {d}: {type(exc).__name__}: {exc}")
        return True
    return False


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
            from TTS.config.shared_configs import BaseDatasetConfig
            from TTS.tts.configs.xtts_config import XttsConfig
            from TTS.tts.models.xtts import XttsArgs, XttsAudioConfig

            add_safe_globals([XttsConfig, XttsAudioConfig, BaseDatasetConfig, XttsArgs])
        except ImportError:
            pass

        from TTS.api import TTS

        info(f"\nDownloading {model_name}...")
        # Coqui's TTS() asks an in-process `input("y/n")` license confirmation for some
        # models (e.g. xtts_v2). Our installer already collected user consent before
        # calling this function, so feed "y" automatically.
        original_stdin = sys.stdin
        sys.stdin = io.StringIO("y\n" * 10)
        try:
            TTS(model_name, progress_bar=True, gpu=False)
        finally:
            sys.stdin = original_stdin
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

    # Where to store coqui models (Coqui reads TTS_HOME env var; we tunnel it through COQUITTS_PATH).
    target = resolve_models_dir(
        engine_label="Coqui TTS",
        env_key="COQUITTS_PATH",
        default_dir=Path.home() / ".local" / "share" / "tts",
        project_dir=project_root() / "cache" / "coquitts",
        non_interactive=non_interactive,
    )
    os.environ["TTS_HOME"] = str(target)

    # Where to store the voice sample WAV (xtts_v2 needs it at synthesis time).
    # Default matches ttsrec.DEFAULT_FALLBACK and engines/coquitts.DEFAULT_COQUITTS_SAMPLE.
    resolve_file_path(
        label="voice sample WAV (COQUITTS_SAMPLE, used by xtts_v2)",
        env_key="COQUITTS_SAMPLE",
        default_path=Path.home() / ".config" / "ttsgen.wav",
        project_path=Path.cwd() / "ttsgen.wav",
        non_interactive=non_interactive,
    )

    # Install torch from the official PyTorch index (cpu / cu121) — the default PyPI
    # index ships cu13 wheels which fail on NVIDIA drivers below ~580.
    install_torch_choice(non_interactive=non_interactive)

    info("\nInstalling coqui-tts (Idiap fork — actively maintained, supports Python 3.12+)...")
    # Original `coqpit` (0.x) conflicts with the fork's `coqpit-config` package.
    # If the original is present, remove it first so coqui-tts installs cleanly.
    subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y", "coqpit"],
        check=False,
        capture_output=True,
    )
    # `coqui-tts[codec]` pulls torchcodec — required by coqui-tts under PyTorch 2.9+.
    # transformers 5.x removed `isin_mps_friendly`; coqui-tts < 0.28 still imports it.
    pip_install(["coqui-tts[codec]", "transformers>=4.46,<5.0"])

    # Resolve model from env (COQUITTS_MODEL) — primary source of truth.
    env_model = os.environ.get("COQUITTS_MODEL", "").strip()

    if env_model:
        info(f"\nUsing model from COQUITTS_MODEL env: {env_model}")
        if prompt_redownload_or_skip(env_model, non_interactive=non_interactive):
            check_sample_file()
            success("\nInstallation complete (existing model reused).")
            return 0
        if "xtts" in env_model.lower():
            warn("\nIMPORTANT: License Agreement")
            logger.info("The xtts model requires accepting a license:")
            logger.info("  - Non-commercial use: CPML license (https://coqui.ai/cpml)")
            logger.info("  - Commercial use: Requires commercial license from Coqui")
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
        if prompt_redownload_or_skip(DEFAULT_MODEL, non_interactive=non_interactive):
            check_sample_file()
        else:
            warn("\nIMPORTANT: License Agreement")
            logger.info("The xtts_v2 model requires accepting a license:")
            logger.info("  - Non-commercial use: CPML license (https://coqui.ai/cpml)")
            logger.info("  - Commercial use: Requires commercial license from Coqui")
            if not prompt_yes_no("\nDo you accept the non-commercial CPML license?", default=False):
                warn("License not accepted. Skipping model download.")
            else:
                rc = predownload_model(DEFAULT_MODEL)
                if rc != 0:
                    return rc
                check_sample_file()
    elif choice == 2:
        if not prompt_redownload_or_skip(ENGLISH_MODEL, non_interactive=non_interactive):
            rc = predownload_model(ENGLISH_MODEL)
            if rc != 0:
                return rc

    success("\nInstallation complete!")
    info("Usage:")
    logger.info('  ttsgen "Hello world" --engine coquitts')
    logger.info('  ttsgen "Привет мир" --engine coquitts --language ru')
    return 0


def main():
    pass


if __name__ == "__main__":
    main()
