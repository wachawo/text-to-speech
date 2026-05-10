#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared helpers for engine installers — pip, downloads, prompts, colored output."""

import hashlib
import json
import logging
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

# ANSI colors
RESET = "\033[0m"
GREEN = "\033[0;32m"
BLUE = "\033[0;34m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"


def info(msg: str) -> None:
    logger.info(f"{BLUE}{msg}{RESET}")


def success(msg: str) -> None:
    logger.info(f"{GREEN}{msg}{RESET}")


def warn(msg: str) -> None:
    logger.warning(f"{YELLOW}{msg}{RESET}")


def error(msg: str) -> None:
    logger.error(f"{RED}{msg}{RESET}")


def project_root() -> Path:
    """Return repo root — directory that contains ttsgen.py."""
    return Path(__file__).resolve().parent.parent


def pip_install(packages: list[str], extra_args: list[str] | None = None) -> None:
    """Install packages with the current python's pip. Raises on failure."""
    cmd = [sys.executable, "-m", "pip", "install", *packages]
    if extra_args:
        cmd.extend(extra_args)
    info(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def prompt_yes_no(question: str, default: bool = False, non_interactive: bool = False) -> bool:
    """Ask y/n. Returns default in non-interactive mode."""
    if non_interactive:
        return default
    suffix = " (y/N): " if not default else " (Y/n): "
    answer = input(question + suffix).strip().lower()
    if not answer:
        return default
    return answer == "y" or answer == "yes"


def choose_from(question: str, options: list[str], default: int = 1, non_interactive: bool = False) -> int:
    """Display numbered menu, return 1-based index. Returns default in non-interactive mode."""
    menu_lines = [question]
    for i, opt in enumerate(options, start=1):
        marker = " *" if i == default else ""
        menu_lines.append(f"  {i}) {opt}{marker}")
    logger.info("\n".join(menu_lines))
    if non_interactive:
        return default
    while True:
        raw = input(f"Your choice (1-{len(options)}, default={default}): ").strip()
        if not raw:
            return default
        try:
            idx = int(raw)
            if 1 <= idx <= len(options):
                return idx
        except ValueError:
            pass
        warn(f"Invalid choice: {raw}")


def prompt_text(question: str, default: str = "", non_interactive: bool = False) -> str:
    if non_interactive:
        return default
    suffix = f" [{default}]: " if default else ": "
    answer = input(question + suffix).strip()
    return answer if answer else default


def download_file(url: str, dest: Path, *, label: str | None = None) -> None:
    """Download url → dest with simple progress reporting. Skips if dest exists."""
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        info(f"  exists: {dest.name} (skip)")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    label = label or dest.name
    info(f"  download: {label}")

    last_pct = [-1]

    def reporthook(block_num: int, block_size: int, total_size: int) -> None:
        if total_size <= 0:
            return
        downloaded = block_num * block_size
        pct = min(100, int(downloaded * 100 / total_size))
        if pct != last_pct[0] and pct % 5 == 0:
            mb = downloaded / 1024 / 1024
            tot = total_size / 1024 / 1024
            sys.stdout.write(f"\r    {pct:3d}%  {mb:6.1f} / {tot:6.1f} MB")
            sys.stdout.flush()
            last_pct[0] = pct

    urllib.request.urlretrieve(url, dest, reporthook=reporthook)
    sys.stdout.write("\n")
    sys.stdout.flush()


_HASH_CHUNK = 1024 * 1024  # 1 MiB read buffer for hashing


def hash_file(path: Path, algo: str = "sha256") -> str:
    """Return hex digest of the file at `path` using the named hashlib algorithm."""
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        while True:
            block = f.read(_HASH_CHUNK)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def verify_checksum(path: Path, expected: str, algo: str = "sha256") -> bool:
    """Compute file's hash and compare to `expected` (case-insensitive hex).

    On mismatch the corrupt file is removed and a warning is emitted; the
    caller decides how to recover (re-download, abort). Returns True on
    success, False on mismatch / IO error.
    """
    path = Path(path)
    if not path.exists():
        warn(f"verify_checksum: {path} does not exist")
        return False
    try:
        actual = hash_file(path, algo=algo)
    except Exception as exc:
        warn(f"verify_checksum: failed to hash {path}: {type(exc).__name__}: {exc}")
        return False
    if actual.lower() != expected.lower():
        warn(f"verify_checksum FAILED for {path.name}: " f"expected {algo}={expected[:16]}..., got {actual[:16]}...")
        try:
            path.unlink()
            info(f"  removed corrupt file: {path.name}")
        except OSError as exc:
            warn(f"  could not remove {path}: {type(exc).__name__}: {exc}")
        return False
    info(f"  verified {algo}: {path.name}")
    return True


def fetch_json(url: str, timeout: int = 30) -> dict | None:
    """GET `url` and parse JSON. Returns None on any failure (network, parse)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ttsgen-installer"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        return json.loads(data)
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        warn(f"fetch_json {url}: {type(exc).__name__}: {exc}")
        return None


PYTORCH_CPU_INDEX = "https://download.pytorch.org/whl/cpu"
PYTORCH_CUDA_INDEX = "https://download.pytorch.org/whl/cu121"


def install_torch_choice(non_interactive: bool = False, packages: list[str] | None = None) -> None:
    """Install torch + torchaudio with explicit CUDA or CPU index.

    Default index (https://download.pytorch.org/whl) ships cu13 which breaks
    against drivers older than ~580. cu121 wheels work with NVIDIA driver 525+,
    cpu wheels work everywhere.

    Skips entirely when the requested packages are already importable — covers
    the Docker case where torch is baked into the image via requirements-{gpu,cpu}.txt
    and we don't want to overwrite the GPU build with CPU wheels.
    """
    pkgs = packages if packages is not None else ["torch", "torchaudio"]

    try:
        import importlib.util
        if all(importlib.util.find_spec(p) is not None for p in pkgs):
            info(f"{', '.join(pkgs)} already importable — skipping torch install")
            return
    except Exception:
        pass

    if non_interactive:
        info("\nInstalling PyTorch (CPU)...")
        pip_install(pkgs, extra_args=["--index-url", PYTORCH_CPU_INDEX])
        return

    options = [
        "CPU only (works everywhere, no GPU required)",
        "GPU with CUDA 12.1 (works with NVIDIA driver 525+)",
    ]
    choice = choose_from("\nSelect PyTorch build:", options, default=1)
    if choice == 2:
        info(f"\nInstalling PyTorch with CUDA 12.1 from {PYTORCH_CUDA_INDEX}...")
        pip_install(pkgs, extra_args=["--index-url", PYTORCH_CUDA_INDEX])
    else:
        info(f"\nInstalling PyTorch (CPU) from {PYTORCH_CPU_INDEX}...")
        pip_install(pkgs, extra_args=["--index-url", PYTORCH_CPU_INDEX])


def in_virtualenv() -> bool:
    """Detect if running inside a venv."""
    return bool(os.environ.get("VIRTUAL_ENV")) or sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def resolve_file_path(
    label: str,
    env_key: str,
    default_path: Path,
    project_path: Path,
    non_interactive: bool = False,
) -> Path:
    """Like resolve_models_dir but for a single FILE path. Persists choice to ~/.config/ttsgen.conf."""
    existing = os.environ.get(env_key, "").strip()
    if existing:
        target = Path(os.path.expanduser(existing)).resolve()
        info(f"{label}: {target} (from {env_key})")
        return target

    if non_interactive:
        target = default_path
    else:
        options = [
            f"Default: {default_path}",
            f"Current directory: {project_path}",
            "Custom path (enter manually)",
        ]
        choice = choose_from(f"\nWhere should {label} be stored?", options, default=1)
        if choice == 1:
            target = default_path
        elif choice == 2:
            target = project_path
        else:
            raw = prompt_text("Enter file path", default=str(default_path))
            target = Path(os.path.expanduser(raw)).resolve()

    target.parent.mkdir(parents=True, exist_ok=True)
    os.environ[env_key] = str(target)

    try:
        from libs.config import persist_config_value

        persist_config_value(env_key, str(target))
        info(f"Saved {env_key}={target} to ~/.config/ttsgen.conf")
    except Exception as exc:
        warn(f"Could not persist {env_key} to config: {type(exc).__name__}: {exc}")

    return target


def resolve_models_dir(
    engine_label: str,
    env_key: str,
    default_dir: Path,
    project_dir: Path,
    non_interactive: bool = False,
) -> Path:
    """Ask user where to store model files. Persists choice to ~/.config/ttsgen.conf.

    Priority:
        1. If `env_key` already set in env (CLI flag, .env, ttsgen.conf) → use that, no prompt.
        2. Non-interactive mode → use `default_dir` silently.
        3. Interactive 3-way prompt (default / project-local / custom path).

    The chosen path is written back to os.environ AND persisted to ~/.config/ttsgen.conf
    so that synthesis-time engines find the same location later.
    """
    existing = os.environ.get(env_key, "").strip()
    if existing:
        target = Path(os.path.expanduser(existing)).resolve()
        target.mkdir(parents=True, exist_ok=True)
        info(f"{engine_label} models: {target} (from {env_key})")
        return target

    if non_interactive:
        target = default_dir
    else:
        options = [
            f"Default: {default_dir}",
            f"Project-local: {project_dir}",
            "Custom directory (enter path)",
        ]
        choice = choose_from(
            f"\nWhere do you want to store {engine_label} models?",
            options,
            default=1,
        )
        if choice == 1:
            target = default_dir
        elif choice == 2:
            target = project_dir
        else:
            raw = prompt_text("Enter directory path", default=str(default_dir))
            target = Path(os.path.expanduser(raw)).resolve()

    target.mkdir(parents=True, exist_ok=True)
    os.environ[env_key] = str(target)

    # Persist so synthesis time sees the same location.
    try:
        from libs.config import persist_config_value

        persist_config_value(env_key, str(target))
        info(f"Saved {env_key}={target} to ~/.config/ttsgen.conf")
    except Exception as exc:
        warn(f"Could not persist {env_key} to config: {type(exc).__name__}: {exc}")

    return target


def warn_no_venv(non_interactive: bool = False) -> bool:
    """If not in venv, warn and ask to continue. Returns True to continue.

    In non-interactive mode (CI, Docker entrypoint), skip the prompt entirely
    and proceed — the caller has explicitly opted in by passing the flag.
    """
    if in_virtualenv():
        return True
    if non_interactive:
        return True
    warn("Virtual environment not detected. It's recommended to activate venv first.")
    return prompt_yes_no("Continue anyway?", default=False, non_interactive=False)


def main():
    pass


if __name__ == "__main__":
    main()
