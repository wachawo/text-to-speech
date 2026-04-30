#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio Player from STDIN

Reads audio data from stdin and plays it.
Useful for piping audio from other commands.

Usage:
    python tts.py "Hello" --format bytesio | python play.py
    cat audio.wav | python play.py
"""

import sys
import os
import logging

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

# Add libs to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "libs"))

try:
    from libs.api import play_audio
except ImportError as e:
    logger.error(f"Failed to import playback module: {e}")
    sys.exit(1)


def main():
    """Read audio from stdin and play it."""
    try:
        # Check if stdin has data
        if sys.stdin.isatty():
            print("Error: No input data", file=sys.stderr)
            print(
                "Usage: python tts.py 'text' --format bytesio | python play.py",
                file=sys.stderr,
            )
            print("   or: cat audio.wav | python play.py", file=sys.stderr)
            return 1

        # Read binary data from stdin
        audio_data = sys.stdin.buffer.read()

        if not audio_data:
            print("Error: No audio data received", file=sys.stderr)
            return 1

        # Detect format
        if audio_data.startswith(b"RIFF"):
            format_type = "WAV"
        elif audio_data.startswith(b"ID3") or audio_data[0:2] == b"\xff\xfb":
            format_type = "MP3"
        else:
            format_type = "Unknown"

        print(f"Playing {len(audio_data)} bytes ({format_type})...", file=sys.stderr)

        # Play audio
        play_audio(audio_data)

        print("Playback completed", file=sys.stderr)
        return 0

    except KeyboardInterrupt:
        print("\nPlayback interrupted", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
