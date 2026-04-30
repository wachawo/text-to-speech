#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Silero TTS installer — torch + torchaudio + omegaconf, optional model pre-download."""

import logging
import os
from pathlib import Path

from install.common import (
    choose_from,
    info,
    pip_install,
    project_root,
    prompt_text,
    success,
    warn,
    warn_no_venv,
)

logger = logging.getLogger(__name__)


def resolve_models_dir(non_interactive: bool) -> Path:
    """Ask user where to keep models (or use PROJECT/.silerotts in non-interactive)."""
    default_dir = project_root() / ".silerotts"
    if non_interactive:
        default_dir.mkdir(parents=True, exist_ok=True)
        return default_dir

    options = [
        f"Default: .silerotts/ (in project directory)",
        "Standard: ~/.cache/torch/hub/ (default Silero location)",
        "Custom directory",
    ]
    choice = choose_from("\nWhere do you want to store Silero models?", options, default=1)
    if choice == 1:
        default_dir.mkdir(parents=True, exist_ok=True)
        os.environ["SILEROTTS_MODELS"] = str(default_dir)
        return default_dir
    if choice == 2:
        target = Path.home() / ".cache" / "torch" / "hub"
        target.mkdir(parents=True, exist_ok=True)
        return target
    custom = prompt_text("Enter custom directory path", default=str(default_dir))
    target = Path(os.path.expanduser(custom)).resolve()
    target.mkdir(parents=True, exist_ok=True)
    os.environ["SILEROTTS_MODELS"] = str(target)
    return target


def install_torch(non_interactive: bool) -> None:
    if non_interactive:
        info("\nInstalling PyTorch (CPU)...")
        pip_install(
            ["torch", "torchaudio"],
            extra_args=["--index-url", "https://download.pytorch.org/whl/cpu"],
        )
        return

    options = [
        "CPU only (recommended, works on all systems)",
        "GPU with CUDA (faster, requires NVIDIA GPU)",
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


def predownload(models_dir: Path, languages: list) -> None:
    """Trigger torch.hub download for each language."""
    import torch  # noqa: WPS433 — late import; package may have just been installed

    torch.hub.set_dir(str(models_dir))

    for lang, speaker in languages:
        info(f"\nDownloading {lang} model (speaker={speaker})...")
        torch.hub.load(
            repo_or_dir="snakers4/silero-models",
            model="silero_tts",
            language=lang,
            speaker=speaker,
            verbose=True,
            trust_repo=True,
        )
        success(f"  {lang} model cached")


def install(non_interactive: bool = False) -> int:
    info("Silero TTS Installer")

    if not warn_no_venv(non_interactive):
        warn("Installation cancelled.")
        return 0

    models_dir = resolve_models_dir(non_interactive)
    info(f"Models directory: {models_dir}")

    install_torch(non_interactive)

    info("\nInstalling additional dependencies...")
    pip_install(["omegaconf"])

    if non_interactive:
        languages = [("ru", "v3_1_ru"), ("en", "v3_en")]
    else:
        options = [
            "Russian (~80MB)",
            "English (~80MB)",
            "Both Russian and English",
            "Skip (download on first use)",
        ]
        choice = choose_from("\nPre-download voice models?", options, default=4)
        if choice == 1:
            languages = [("ru", "v3_1_ru")]
        elif choice == 2:
            languages = [("en", "v3_en")]
        elif choice == 3:
            languages = [("ru", "v3_1_ru"), ("en", "v3_en")]
        else:
            languages = []

    if languages:
        try:
            predownload(models_dir, languages)
        except Exception as exc:
            import traceback
            warn(f"Pre-download failed: {type(exc).__name__}: {exc}")
            traceback.print_exc()
            warn("Models will be downloaded on first use.")

    success("\nInstallation complete!")
    info("Usage:")
    print('  tts "Hello world" --engine silerotts')
    print('  tts "Привет мир" --engine silerotts --language ru')
    return 0


def main():
    pass


if __name__ == "__main__":
    main()
