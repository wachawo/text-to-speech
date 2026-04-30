#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Config loader with priority chain.

Priority (highest wins):
    1. Process env (set by shell or CLI flag)
    2. ./ttsgen.conf (project-local override)
    3. ~/.config/ttsgen.conf (user-wide defaults)
    4. .env (legacy, current directory)
    5. Built-in defaults baked into engine modules.

Files use the same KEY=VALUE format as `.env`.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False


USER_CONFIG_DIR  = Path.home() / ".config"
USER_CONFIG_PATH = USER_CONFIG_DIR / "ttsgen.conf"

DEFAULT_USER_CONFIG = """\
# ttsgen configuration — KEY=VALUE format (same as .env).
# Priority (highest wins):
#   1. Process env (shell, --coqui-model flag, etc.)
#   2. ./ttsgen.conf (project-local override)
#   3. ~/.config/ttsgen.conf (this file — user defaults)
#   4. .env (legacy, current directory)
#   5. Built-in defaults
#
# Uncomment and edit the lines below to set your defaults.

# Default engine and language for `ttsgen "..."` without flags
# TTS_ENGINE=gtts
# TTS_LANGUAGE=en

# Audio output directory (created if missing)
# AUDIO_DIRECTORY=audio

# coqui-tts configuration
# COQUITTS_PATH=.coquitts
# COQUITTS_MODEL=tts_models/multilingual/multi-dataset/xtts_v2
# COQUITTS_SAMPLE=samples/1.wav

# Piper / Silero / Bark model directories (defaults are project-local dotfolders)
# PIPERTTS_PATH=.pipertts
# SILEROTTS_PATH=.silerotts
# BARKTTS_PATH=.barktts
"""


def ensure_user_config() -> Path:
    """Create ~/.config/ttsgen.conf with commented defaults if it doesn't exist.

    Returns the path. Silent on errors (config is optional convenience).
    """
    try:
        if not USER_CONFIG_PATH.exists():
            USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            USER_CONFIG_PATH.write_text(DEFAULT_USER_CONFIG)
            logger.info(f"Created default config at {USER_CONFIG_PATH}")
    except OSError as exc:
        logger.warning(f"Could not create {USER_CONFIG_PATH}: {type(exc).__name__}: {exc}")
    return USER_CONFIG_PATH


def load_config() -> None:
    """Populate os.environ from config files in priority order.

    Process env always wins (override=False everywhere). Files load from highest
    priority to lowest, each only filling values not already set by previous loads.
    """
    if not DOTENV_AVAILABLE:
        return

    ensure_user_config()

    local_config = Path("ttsgen.conf")
    legacy_env = Path(".env")

    # Highest-priority file first; subsequent ones don't override what's already set.
    if local_config.exists():
        load_dotenv(local_config, override=False)
    if USER_CONFIG_PATH.exists():
        load_dotenv(USER_CONFIG_PATH, override=False)
    if legacy_env.exists():
        load_dotenv(legacy_env, override=False)


def persist_config_value(key: str, value: str) -> None:
    """Set or update KEY=VALUE in ~/.config/ttsgen.conf, uncommenting if needed.

    Used by installers to remember the chosen model directory so the engine
    finds it at synthesis time.
    """
    ensure_user_config()
    lines = USER_CONFIG_PATH.read_text().splitlines()
    out: list = []
    replaced = False
    for line in lines:
        bare = line.lstrip().lstrip("#").strip()
        if bare.startswith(f"{key}=") and not replaced:
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        if out and out[-1].strip() != "":
            out.append("")
        out.append(f"{key}={value}")
    USER_CONFIG_PATH.write_text("\n".join(out) + "\n")


def main():
    pass


if __name__ == "__main__":
    main()
