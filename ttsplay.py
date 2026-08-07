#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Play raw audio bytes read from stdin.

Companion to `ttsgen --stdout`, so audio can be piped between processes:

    ttsgen "Hello" --stdout | ttsplay
    cat audio.wav | ttsplay
"""

import logging
import os
import sys
import traceback

LOGGING = {
    "handlers": [
        logging.StreamHandler(),
        # RotatingFileHandler(filename=f'{LOGS_DIR}/app.log', maxBytes=1024*1024*10, backupCount=3),
        # logging.FileHandler(filename=f"{LOGS_DIR}/app.log"),
    ],
    "format": "%(asctime)s.%(msecs)03d [%(levelname)s]: (%(name)s.%(funcName)s) %(message)s",
    "level": logging.INFO,
    "datefmt": "%Y-%m-%d %H:%M:%S",
}
logging.basicConfig(**LOGGING)  # type: ignore
logger = logging.getLogger(__name__)

# Source-checkout fallback: put the bundled libs/ directory on sys.path before the
# libs.* import below, so the script also runs from a clone without installation.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "libs"))

# Local imports
try:
    from libs.api import play_audio
except ImportError as e:
    logger.error(f"Failed to import playback module: {e}")
    sys.exit(1)


def main():
    """Read audio bytes from stdin, play them, and return a shell exit code."""
    try:
        # Refuse to block on an interactive terminal: without a pipe there is nothing to play.
        if sys.stdin.isatty():
            logger.error("No input data")
            logger.error("Usage: ttsgen 'text' --stdout | ttsplay")
            logger.error("   or: cat audio.wav | ttsplay")
            return 1

        # Read binary data from stdin
        audio_data = sys.stdin.buffer.read()

        if not audio_data:
            logger.error("No audio data received")
            return 1

        # Format is reported for diagnostics only; play_audio sniffs the header itself.
        if audio_data.startswith(b"RIFF"):
            format_type = "WAV"
        elif audio_data.startswith(b"ID3") or audio_data[0:2] == b"\xff\xfb":
            format_type = "MP3"
        else:
            format_type = "Unknown"

        logger.info(f"Playing {len(audio_data)} bytes ({format_type})...")

        play_audio(audio_data)

        logger.info("Playback completed")
        return 0

    except KeyboardInterrupt:
        logger.warning("Playback interrupted")
        return 1
    except Exception as exc:
        logger.error(f"{type(exc).__name__}: {str(exc)}\n{traceback.format_exc()}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
