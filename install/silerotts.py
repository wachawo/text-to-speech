#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Silero TTS installer — torch + torchaudio + omegaconf, optional model pre-download."""

import logging
from pathlib import Path

from install.common import (
    choose_from,
    info,
    install_torch_choice,
    pip_install,
    project_root,
    resolve_models_dir,
    success,
    warn,
    warn_no_venv,
)

logger = logging.getLogger(__name__)


def get_silero_dir(non_interactive: bool) -> Path:
    return resolve_models_dir(
        engine_label="Silero TTS",
        env_key="SILEROTTS_PATH",
        default_dir=Path.home() / ".cache" / "torch" / "hub",
        project_dir=project_root() / ".silerotts",
        non_interactive=non_interactive,
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

    models_dir = get_silero_dir(non_interactive)
    info(f"Models directory: {models_dir}")

    install_torch_choice(non_interactive=non_interactive)

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
    logger.info('  ttsgen "Hello world" --engine silerotts')
    logger.info('  ttsgen "Привет мир" --engine silerotts --language ru')
    return 0


def main():
    pass


if __name__ == "__main__":
    main()
