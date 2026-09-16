#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Config loader that fills os.environ from KEY=VALUE files, strongest source first.

Priority, strongest first (a weaker source never overwrites a stronger one):
    1. CLI flags                    (pushed into the process environment by the entrypoint)
    2. shell environment            (variables already set when the process started)
    3. ./ttsgen.conf                (project-local settings)
    4. ~/.config/ttsgen.conf        (user-wide settings)
    5. ./.env.local                 (gitignored local overrides of ./.env)
    6. ./.env                       (versioned defaults, shared with Docker)

All files use the same KEY=VALUE format as `.env`. Every file is loaded with
override=False, strongest file first, so a file only fills keys nobody stronger
has set. `.env` and `.env.local` are read from the current directory only, never
from a parent directory.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv

    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False


USER_CONFIG_DIR = Path.home() / ".config"
USER_CONFIG_PATH = USER_CONFIG_DIR / "ttsgen.conf"

DEFAULT_USER_CONFIG = """\
# ttsgen configuration - KEY=VALUE format (same as .env).
# Load order, strongest first (a weaker source never overwrites a stronger one):
#   1. CLI flags                    (--engine, --coqui-model, ...)
#   2. shell environment
#   3. ./ttsgen.conf                (project-local)
#   4. ~/.config/ttsgen.conf        (this file)
#   5. ./.env.local                 (gitignored local overrides of ./.env)
#   6. ./.env
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
# COQUITTS_SAMPLES=samples

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
# TTS_TOKENS=SuP3rS3cr3tK3y!
# TTS_POOL_SIZE=1
# TTS_QUEUE_SIZE=8
# TTS_HISTORY_DIR=data/history
# TTS_HISTORY_MAX=200
# TTS_MAX_SAMPLE_BYTES=16777216
"""


def ensure_user_config() -> Path:
    """Create ~/.config/ttsgen.conf with commented defaults if it doesn't exist.

    Returns the path. Silent on errors (config is optional convenience).
    """
    try:
        if not USER_CONFIG_PATH.exists():
            USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            USER_CONFIG_PATH.write_text(DEFAULT_USER_CONFIG, encoding="utf-8")
            logger.info(f"Created default config at {USER_CONFIG_PATH}")
    except OSError as exc:
        logger.warning(f"Could not create {USER_CONFIG_PATH}: {type(exc).__name__}: {exc}")
    return USER_CONFIG_PATH


def load_config() -> None:
    """Populate os.environ from the config files, strongest file loaded first.

    Load sequence: ./ttsgen.conf -> ~/.config/ttsgen.conf -> ./.env.local -> ./.env,
    every file with override=False. A key already present in the process
    environment (shell variable or CLI flag) is never touched, and each file only
    fills the keys no stronger file has set. Does nothing when python-dotenv is
    not installed.
    """
    if not DOTENV_AVAILABLE:
        return

    ensure_user_config()

    config_files = [Path("ttsgen.conf"), USER_CONFIG_PATH, Path(".env.local"), Path(".env")]
    for config_file in config_files:
        if config_file.is_file():
            load_dotenv(config_file, override=False)


def quote_config_value(value: str) -> str:
    """Wrap `value` in double quotes when dotenv would otherwise cut or split it.

    A bare `#` starts an inline comment and a bare space ends the value, so a
    path such as `/home/me/my #1 voice.wav` has to be quoted. Backslashes and
    double quotes inside are escaped the way python-dotenv unescapes them.
    """
    if not any(ch in value for ch in "#'\" \t"):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def persist_config_value(key: str, value: str) -> None:
    """Set or update KEY=VALUE in ~/.config/ttsgen.conf, uncommenting if needed.

    Used by installers and `ttsrec` to remember a chosen path so the engine
    finds it at synthesis time. Only the first matching line is rewritten; if the
    key is absent entirely it is appended at the end of the file.

    Args:
        key: Config key to write, without the leading `#`.
        value: Value to store; quoted when it contains `#`, whitespace or quotes
            so dotenv reads it back intact.

    Raises:
        ValueError: If the value contains a line break.
    """
    if "\n" in value or "\r" in value:
        raise ValueError(f"Config value for {key} must not contain a line break")
    value = quote_config_value(value)
    ensure_user_config()
    lines = USER_CONFIG_PATH.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
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
    USER_CONFIG_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")


def main():
    """Module entrypoint placeholder — this file is import-only."""
    pass


if __name__ == "__main__":
    main()
