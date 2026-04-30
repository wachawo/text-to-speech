#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared helpers for engine installers — pip, downloads, prompts, colored output."""

import logging
import os
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# ANSI colors
RESET  = "\033[0m"
GREEN  = "\033[0;32m"
BLUE   = "\033[0;34m"
YELLOW = "\033[1;33m"
RED    = "\033[0;31m"


def info(msg: str) -> None:
    print(f"{BLUE}{msg}{RESET}")


def success(msg: str) -> None:
    print(f"{GREEN}{msg}{RESET}")


def warn(msg: str) -> None:
    print(f"{YELLOW}{msg}{RESET}")


def error(msg: str) -> None:
    print(f"{RED}{msg}{RESET}", file=sys.stderr)


def project_root() -> Path:
    """Return repo root — directory that contains ttsgen.py."""
    return Path(__file__).resolve().parent.parent


def pip_install(packages: List[str], extra_args: Optional[List[str]] = None) -> None:
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


def choose_from(question: str, options: List[str], default: int = 1, non_interactive: bool = False) -> int:
    """Display numbered menu, return 1-based index. Returns default in non-interactive mode."""
    print(question)
    for i, opt in enumerate(options, start=1):
        marker = " *" if i == default else ""
        print(f"  {i}) {opt}{marker}")
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


def download_file(url: str, dest: Path, *, label: Optional[str] = None) -> None:
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


def in_virtualenv() -> bool:
    """Detect if running inside a venv."""
    return bool(os.environ.get("VIRTUAL_ENV")) or sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def warn_no_venv(non_interactive: bool = False) -> bool:
    """If not in venv, warn and ask to continue. Returns True to continue."""
    if in_virtualenv():
        return True
    warn("Virtual environment not detected. It's recommended to activate venv first.")
    return prompt_yes_no("Continue anyway?", default=False, non_interactive=non_interactive)


def main():
    pass


if __name__ == "__main__":
    main()
