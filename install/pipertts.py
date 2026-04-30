#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Piper TTS installer — pip + voice model download from HuggingFace."""

import logging
import os
from pathlib import Path
from typing import List

from install.common import (
    download_file,
    info,
    pip_install,
    project_root,
    prompt_text,
    success,
    warn,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"

# code → (huggingface_path, file_basename, label)
VOICES = {
    "en_US": ("en/en_US/lessac/medium",     "en_US-lessac-medium",     "English (lessac, female)"),
    "ru_RU": ("ru/ru_RU/ruslan/medium",     "ru_RU-ruslan-medium",     "Russian (ruslan, male)"),
    "es_ES": ("es/es_ES/davefx/medium",     "es_ES-davefx-medium",     "Spanish (davefx)"),
    "de_DE": ("de/de_DE/thorsten/medium",   "de_DE-thorsten-medium",   "German (thorsten)"),
    "fr_FR": ("fr/fr_FR/siwis/medium",      "fr_FR-siwis-medium",      "French (siwis)"),
}


def models_dir() -> Path:
    return Path(os.getenv("PIPERTTS_PATH") or (project_root() / ".pipertts"))


def select_voices(non_interactive: bool) -> List[str]:
    """Return list of voice codes to install."""
    codes = list(VOICES.keys())
    if non_interactive:
        return codes
    print("\nSelect languages to download (space-separated, e.g. '1 2', or 6 for all):")
    for i, code in enumerate(codes, start=1):
        _, _, label = VOICES[code]
        print(f"  {i}) {label}")
    print(f"  {len(codes) + 1}) All languages")
    raw = prompt_text("Your choice", default=str(len(codes) + 1)).strip()
    if not raw:
        return codes
    chosen: List[str] = []
    for token in raw.split():
        try:
            idx = int(token)
        except ValueError:
            warn(f"Invalid choice: {token}")
            continue
        if idx == len(codes) + 1:
            return codes
        if 1 <= idx <= len(codes):
            code = codes[idx - 1]
            if code not in chosen:
                chosen.append(code)
        else:
            warn(f"Invalid choice: {idx}")
    return chosen or codes


def download_voice(code: str, target_dir: Path) -> None:
    path, basename, label = VOICES[code]
    info(f"\nProcessing: {label}")
    for ext in (".onnx", ".onnx.json"):
        url = f"{BASE_URL}/{path}/{basename}{ext}"
        dest = target_dir / f"{basename}{ext}"
        download_file(url, dest, label=f"{basename}{ext}")
    success(f"Done: {basename}")


def install(non_interactive: bool = False) -> int:
    info("Piper TTS Installer")
    pip_install(["piper-tts"])

    target = models_dir()
    target.mkdir(parents=True, exist_ok=True)
    info(f"Models directory: {target}")

    voices = select_voices(non_interactive)
    for code in voices:
        download_voice(code, target)

    success("\nInstallation complete!")
    info(f"Models in: {target}")
    info("Usage:")
    print('  ttsgen "Hello world" --engine pipertts')
    print('  ttsgen "Привет мир" --engine pipertts --language ru')
    return 0


def main():
    pass


if __name__ == "__main__":
    main()
