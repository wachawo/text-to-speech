#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Config loader with priority chain.

Load order (later wins for overlapping keys):
    1. ./.env                       (versioned defaults, shared with Docker)
    2. ./.env.local                 (gitignored local overrides — override=True)
    3. ~/.config/ttsgen.conf        (user-wide fallback — override=False)
    4. ./ttsgen.conf                (project-local fallback — override=False)

Files use the same KEY=VALUE format as `.env`. Configs (3, 4) are loaded
last with override=False so they only fill keys not already set by the
.env pair above — they act as last-resort defaults.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from dotenv import find_dotenv, load_dotenv

    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False


USER_CONFIG_DIR = Path.home() / ".config"
USER_CONFIG_PATH = USER_CONFIG_DIR / "ttsgen.conf"

DEFAULT_USER_CONFIG = """\
# ttsgen configuration — KEY=VALUE format (same as .env).
# Load order (later wins for overlapping keys):
#   1. ./.env                       (versioned defaults)
#   2. ./.env.local                 (gitignored override, beats .env)
#   3. ~/.config/ttsgen.conf        (this file — fallback default)
#   4. ./ttsgen.conf                (project fallback)
#
# Uncomment and edit the lines below to set your defaults.

# Default engine and language for `ttsgen "..."` without flags
# TTS_ENGINE=gtts
# TTS_LANGUAGE=en

# Audio output directory (created if missing)
# AUDIO_DIRECTORY=audio

# coqui-tts configuration
# COQUITTS_MODELS=cache/coquitts
# COQUITTS_MODEL=tts_models/multilingual/multi-dataset/xtts_v2
# COQUITTS_SAMPLE=~/.config/ttsgen.wav

# Piper / Silero / Bark / Kokoro model directories (defaults: cache/<engine>/ in project root)
# PIPERTTS_MODELS=cache/pipertts
# SILEROTTS_MODELS=cache/silerotts
# BARKTTS_MODELS=cache/barktts
# KOKOROTTS_MODELS=cache/kokorotts

# HTTP client (used by `ttsapi` to reach a remote `ttssrv`)
# TTS_URL=http://localhost:5000
# TTS_TOKEN=

# HTTP server (used by `ttssrv` and docker-compose*.yml)
# TTS_HOST=0.0.0.0
# TTS_PORT=5000
# TTS_DEBUG=False
# TTS_TOKEN=SuP3rS3cr3tK3y!
# TTS_POOL_SIZE=1
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
    """Populate os.environ from config files.

    Order: .env (base) → .env.local (override=True) → user/project ttsgen.conf
    (override=False, last-resort fallback for keys neither .env nor .env.local set).
    """
    if not DOTENV_AVAILABLE:
        return

    ensure_user_config()

    # .env — found by walking up from cwd; .env.local — local override.
    found = find_dotenv(usecwd=True)
    if found:
        load_dotenv(found)
    local_env = Path(".env.local")
    if local_env.exists():
        load_dotenv(local_env, override=True)
    if USER_CONFIG_PATH.exists():
        load_dotenv(USER_CONFIG_PATH)
    local_config = Path("ttsgen.conf")
    if local_config.exists():
        load_dotenv(local_config)


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
