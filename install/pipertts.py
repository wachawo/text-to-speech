#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Piper TTS installer — pip + voice model download from HuggingFace."""

import logging
from pathlib import Path

from install.common import (
    download_file,
    fetch_json,
    info,
    pip_install,
    project_root,
    prompt_text,
    resolve_models_dir,
    success,
    verify_checksum,
    warn,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"
# Upstream-published manifest with size + hash for every voice file. Pinned to
# the same v1.0.0 tag as BASE_URL so the manifest matches what we download.
VOICES_JSON_URL = f"{BASE_URL}/voices.json"

# code → (huggingface_path, file_basename, label)
VOICES = {
    "en_US": ("en/en_US/lessac/medium", "en_US-lessac-medium", "English (lessac, female)"),
    "ru_RU": ("ru/ru_RU/ruslan/medium", "ru_RU-ruslan-medium", "Russian (ruslan, male)"),
    "es_ES": ("es/es_ES/davefx/medium", "es_ES-davefx-medium", "Spanish (davefx)"),
    "de_DE": ("de/de_DE/thorsten/medium", "de_DE-thorsten-medium", "German (thorsten)"),
    "fr_FR": ("fr/fr_FR/siwis/medium", "fr_FR-siwis-medium", "French (siwis)"),
}


def models_dir(non_interactive: bool = False) -> Path:
    return resolve_models_dir(
        engine_label="Piper TTS",
        env_key="PIPERTTS_MODELS",
        default_dir=Path.home() / ".local" / "share" / "ttsgen" / "pipertts",
        project_dir=project_root() / "cache" / "pipertts",
        non_interactive=non_interactive,
    )


def select_voices(non_interactive: bool) -> list[str]:
    """Return list of voice codes to install."""
    codes = list(VOICES.keys())
    if non_interactive:
        return codes
    menu = ["\nSelect languages to download (space-separated, e.g. '1 2', or 6 for all):"]
    for i, code in enumerate(codes, start=1):
        _, _, label = VOICES[code]
        menu.append(f"  {i}) {label}")
    menu.append(f"  {len(codes) + 1}) All languages")
    logger.info("\n".join(menu))
    raw = prompt_text("Your choice", default=str(len(codes) + 1)).strip()
    if not raw:
        return codes
    chosen: list[str] = []
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


def _expected_hash(manifest: dict | None, voice_path: str, basename: str, ext: str) -> tuple[str, str] | None:
    """Look up the upstream-declared hash for a voice file.

    rhasspy/piper-voices `voices.json` keys voices by basename (e.g.
    `en_US-lessac-medium`). Each voice has a `files` map keyed by relative
    path; the value carries `md5_digest` (and sometimes `size_bytes`). We
    return (hex_digest, algo) or None when the manifest doesn't cover it.
    """
    if not manifest:
        return None
    voice_entry = manifest.get(basename)
    if not isinstance(voice_entry, dict):
        return None
    files = voice_entry.get("files")
    if not isinstance(files, dict):
        return None
    rel_path = f"{voice_path}/{basename}{ext}"
    file_entry = files.get(rel_path) or files.get(f"{basename}{ext}")
    if not isinstance(file_entry, dict):
        return None
    for algo_key, algo in (("sha256", "sha256"), ("md5_digest", "md5"), ("md5", "md5")):
        digest = file_entry.get(algo_key)
        if isinstance(digest, str) and digest:
            return digest, algo
    return None


def download_voice(code: str, target_dir: Path, manifest: dict | None) -> bool:
    """Download both files for a voice and verify them when a hash is published.

    Returns True on success, False if any file failed verification.
    """
    path, basename, label = VOICES[code]
    info(f"\nProcessing: {label}")
    ok = True
    for ext in (".onnx", ".onnx.json"):
        url = f"{BASE_URL}/{path}/{basename}{ext}"
        dest = target_dir / f"{basename}{ext}"
        download_file(url, dest, label=f"{basename}{ext}")

        expected = _expected_hash(manifest, path, basename, ext)
        if expected is None:
            warn(f"  no upstream checksum for {basename}{ext} — skipping verification")
            continue
        digest, algo = expected
        if not verify_checksum(dest, digest, algo=algo):
            ok = False
    if ok:
        success(f"Done: {basename}")
    else:
        warn(f"Failed: {basename} — file(s) deleted, re-run installer to retry")
    return ok


def install(non_interactive: bool = False) -> int:
    info("Piper TTS Installer")
    pip_install(["piper-tts"])

    target = models_dir(non_interactive=non_interactive)
    info(f"Models directory: {target}")

    info(f"\nFetching voice manifest: {VOICES_JSON_URL}")
    manifest = fetch_json(VOICES_JSON_URL)
    if manifest is None:
        warn("Could not fetch voices.json — downloads will proceed without checksum verification")

    voices = select_voices(non_interactive)
    failed = [code for code in voices if not download_voice(code, target, manifest)]
    if failed:
        warn(f"\nSome voices failed checksum verification: {', '.join(failed)}")
        return 1

    success("\nInstallation complete!")
    info(f"Models in: {target}")
    info("Usage:")
    logger.info('  ttsgen "Hello world" --engine pipertts')
    logger.info('  ttsgen "Привет мир" --engine pipertts --language ru')
    return 0


def main():
    pass


if __name__ == "__main__":
    main()
