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
    "format": "%(asctime)s.%(msecs)03d [%(levelname)s]: (%(name)s) %(message)s",
    "level": logging.INFO,
    "datefmt": "%Y-%m-%d %H:%M:%S",
}

DEFAULT_DURATION = 8  # seconds
DEFAULT_RATE = 22050  # Hz — matches xtts_v2 voice cloning expectations
# Single source of truth shared with engines/coquitts.py:DEFAULT_COQUITTS_SAMPLE.
DEFAULT_FALLBACK = Path.home() / ".config" / "ttsgen.wav"


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
        "-d",
        "--duration",
        type=int,
        default=DEFAULT_DURATION,
        help=f"Recording length in seconds (default: {DEFAULT_DURATION})",
    )
    parser.add_argument(
        "-r",
        "--rate",
        type=int,
        default=DEFAULT_RATE,
        help=f"Sample rate in Hz (default: {DEFAULT_RATE})",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
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
    import sounddevice as sd

    output.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Recording {duration}s at {rate} Hz → {output}")
    logger.info("Speak after the beep...")
    for i in range(3, 0, -1):
        logger.info(f"  {i}...")
        time.sleep(1)
    logger.info("  REC")

    audio = sd.rec(int(duration * rate), samplerate=rate, channels=1, dtype="int16")
    sd.wait()
    logger.info("  done")

    # Quick silence check — int16 max is 32767. Anything below ~5% peak is "silent".
    peak = int(abs(audio).max())
    if peak < 1000:
        logger.warning(
            f"Recording is nearly silent (peak amplitude: {peak}/32767). "
            f"Check that your microphone is selected and not muted. "
            f"List devices with: python -c 'import sounddevice; print(sounddevice.query_devices())'"
        )
    else:
        logger.info(f"  peak amplitude: {peak}/32767 ({peak * 100 // 32767}%)")

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
            logger.warning("Aborted.")
            return 1

    try:
        record_wav(output, args.duration, args.rate)
    except KeyboardInterrupt:
        logger.warning("Recording interrupted.")
        return 1
    except Exception as exc:
        import traceback

        logger.error(f"{type(exc).__name__}: {str(exc)}\n{traceback.format_exc()}")
        return 1

    if not output.exists() or output.stat().st_size == 0:
        logger.error(f"Output file is empty or missing: {output}")
        return 1

    logger.info(f"Saved {output.stat().st_size // 1024} KB to {output}")

    # Persist this path as COQUITTS_SAMPLE so `ttsgen --engine coquitts` finds it.
    try:
        from libs.config import persist_config_value

        persist_config_value("COQUITTS_SAMPLE", str(output))
        logger.info(f"COQUITTS_SAMPLE={output} written to ~/.config/ttsgen.conf")
    except Exception as exc:
        logger.warning(f"Could not persist COQUITTS_SAMPLE: {type(exc).__name__}: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
