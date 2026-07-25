#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Engine installer dispatcher — entry point for `ttsgen --install <engine>`."""

import importlib
import logging

logger = logging.getLogger(__name__)

# Load ttsgen.conf / .env at import time so installers see the user's stored
# choices. The libs package may be absent in a partially installed checkout.
try:
    from libs.config import load_config

    load_config()
except ImportError:
    pass

# Engines that ship a dedicated install/<name>.py module.
INSTALLERS = ("pipertts", "silerotts", "coquitts", "barktts", "kokorotts")
# Engines whose dependencies are already covered by the base requirements.
NO_INSTALLER_NEEDED = ("gtts", "pyttsx3")


def run(engine: str, non_interactive: bool = False) -> int:
    """Dispatch installation to the module for `engine`.

    Args:
        engine: Engine name as accepted by `ttsgen --install`.
        non_interactive: Forwarded to the installer so it picks defaults silently.

    Returns:
        Process exit code: 0 on success, 2 when no installer matches `engine`,
        otherwise whatever the engine installer returned.
    """
    if engine in NO_INSTALLER_NEEDED:
        logger.info(f"Engine '{engine}' has no installer (covered by base requirements).")
        return 0
    if engine not in INSTALLERS:
        logger.error(f"No installer for engine '{engine}'. Available: {', '.join(INSTALLERS)}")
        return 2
    module = importlib.import_module(f"install.{engine}")
    return int(module.install(non_interactive=non_interactive))


def main():
    """Module entrypoint placeholder — this file is import-only."""
    pass


if __name__ == "__main__":
    main()
