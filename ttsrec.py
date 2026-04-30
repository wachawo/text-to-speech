#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Record a voice sample WAV from the default microphone.

Saves to one of:
  ttsrec                          → uses COQUITTS_SAMPLE from config / env
  ttsrec /path/to/file.wav        → explicit path

Usage:
  ttsrec                          # default location (config-driven)
  ttsrec ~/voice.wav              # explicit path
  ttsrec --duration 12            # 12 seconds (default 8)
  ttsrec --rate 22050             # sample rate (default 22050, matches xtts_v2)
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

LOGGING = {
    "handlers": [logging.StreamHandler()],
    "format":  "%(asctime)s.%(msecs)03d [%(levelname)s]: (%(name)s) %(message)s",
    "level":   logging.INFO,
    "datefmt": "%Y-%m-%d %H:%M:%S",
}

DEFAULT_DURATION = 8     # seconds
DEFAULT_RATE     = 22050  # Hz — matches xtts_v2 voice cloning expectations
DEFAULT_FALLBACK = Path.home() / ".local" / "share" / "ttsgen" / "ttsgen.wav"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record a voice sample WAV from the default microphone.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                        # save to COQUITTS_SAMPLE from config
  %(prog)s ~/voice.wav            # save to a specific path
  %(prog)s -d 12                  # record for 12 seconds
  %(prog)s --rate 16000           # record at 16 kHz
        """,
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Output WAV path (default: COQUITTS_SAMPLE from config)",
    )
    parser.add_argument(
        "-d", "--duration", type=int, default=DEFAULT_DURATION,
        help=f"Recording length in seconds (default: {DEFAULT_DURATION})",
    )
    parser.add_argument(
        "-r", "--rate", type=int, default=DEFAULT_RATE,
        help=f"Sample rate in Hz (default: {DEFAULT_RATE})",
    )
    parser.add_argument(
        "-y", "--yes", action="store_true",
        help="Skip the press-Enter-to-start prompt (start immediately)",
    )
    return parser.parse_args()


def resolve_output_path(arg_path: str | None) -> Path:
    """Pick output path: CLI arg → COQUITTS_SAMPLE env → fallback."""
    if arg_path:
        return Path(os.path.expanduser(arg_path)).resolve()

    try:
        from libs.config import load_config
        load_config()
    except ImportError:
        pass

    sample = os.environ.get("COQUITTS_SAMPLE", "").strip()
    if sample:
        return Path(os.path.expanduser(sample)).resolve()

    return DEFAULT_FALLBACK


def record_wav(output: Path, duration: int, rate: int) -> None:
    """Record `duration` seconds of mono audio at `rate` Hz to `output`."""
    try:
        import sounddevice as sd
        import numpy as np
    except ImportError as exc:
        print(
            f"Recording requires sounddevice + numpy. Install via:\n"
            f"  pip install \"text-to-speech[recorder]\" (or sounddevice numpy)\n"
            f"Original error: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        sys.exit(2)

    output.parent.mkdir(parents=True, exist_ok=True)
    print(f"Recording {duration}s at {rate} Hz → {output}")
    print("Speak after the beep...")
    for i in range(3, 0, -1):
        print(f"  {i}...", flush=True)
        time.sleep(1)
    print("  REC", flush=True)

    audio = sd.rec(int(duration * rate), samplerate=rate, channels=1, dtype="int16")
    sd.wait()
    print("  done")

    import wave
    with wave.open(str(output), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(rate)
        w.writeframes(audio.tobytes())


def main() -> int:
    logging.basicConfig(**LOGGING)  # type: ignore[arg-type]
    args = parse_args()

    output = resolve_output_path(args.path)

    if not args.yes and sys.stdin.isatty():
        try:
            input(f"Press Enter to start recording {args.duration}s into {output}, or Ctrl+C to abort. ")
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.", file=sys.stderr)
            return 1

    try:
        record_wav(output, args.duration, args.rate)
    except KeyboardInterrupt:
        print("\nRecording interrupted.", file=sys.stderr)
        return 1
    except Exception as exc:
        import traceback
        logger.error(f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")
        return 1

    if not output.exists() or output.stat().st_size == 0:
        print(f"Output file is empty or missing: {output}", file=sys.stderr)
        return 1

    print(f"\nSaved {output.stat().st_size // 1024} KB to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
