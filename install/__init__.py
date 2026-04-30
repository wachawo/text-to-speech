#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Engine installer dispatcher — entry point for `ttsgen --install <engine>`."""

import importlib
import sys

try:
    from libs.config import load_config
    load_config()
except ImportError:
    pass

INSTALLERS = ("pipertts", "silerotts", "coquitts", "barktts")
NO_INSTALLER_NEEDED = ("gtts", "pyttsx3")


def run(engine: str, non_interactive: bool = False) -> int:
    """Dispatch installation for the named engine. Returns process exit code."""
    if engine in NO_INSTALLER_NEEDED:
        print(f"Engine '{engine}' has no installer (covered by base requirements).")
        return 0
    if engine not in INSTALLERS:
        print(
            f"No installer for engine '{engine}'. Available: {', '.join(INSTALLERS)}",
            file=sys.stderr,
        )
        return 2
    module = importlib.import_module(f"install.{engine}")
    return int(module.install(non_interactive=non_interactive))


def main():
    pass


if __name__ == "__main__":
    main()
