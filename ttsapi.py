#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TTS HTTP client — mirror of `ttsgen` that forwards synthesis to a remote `ttssrv`.

Same argparse surface as `ttsgen` (text input, --file/--play/--stdout/--output,
--engine, --language, --list, -i, -v/-q, --coqui-model, --coqui-sample, etc.).
Replaces local `text_to_speech_bytes()` with `POST {TTS_URL}/api/tts`.

Reads `TTS_URL` and `TTS_TOKEN` from the same config chain as ttsgen
(./ttsgen.conf > ~/.config/ttsgen.conf > .env > defaults).
"""

import argparse
import io
import logging
import os
import queue
import shutil
import sys
import threading
from typing import Any, cast

import requests

from libs.cli import (
    QueueItem as QUEUE_ITEM,
)
from libs.cli import (
    chunk_text,
    concat_wav_files,
    play_worker,
    rec_worker,
)
from libs.tempfiles import safe_unlink

LOGGING = {
    "handlers": [logging.StreamHandler()],
    "format": "%(asctime)s.%(msecs)03d [%(levelname)s]: (%(name)s.%(funcName)s) %(message)s",
    "level": logging.INFO,
    "datefmt": "%Y-%m-%d %H:%M:%S",
}
logging.basicConfig(**LOGGING)  # type: ignore[arg-type]
logger = logging.getLogger(__name__)

DEFAULT_URL = "http://localhost:5000"
DEFAULT_TIMEOUT = 120


def get_url() -> str:
    return os.getenv("TTS_URL", DEFAULT_URL).rstrip("/")


def get_headers() -> dict[str, str]:
    token = os.getenv("TTS_TOKEN", "").strip()
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def fetch_audio(text: str, engine: str, language: str) -> bytes:
    """POST text to remote ttssrv → return audio bytes."""
    url = f"{get_url()}/api/tts"
    payload = {"text": text, "engine": engine, "language": language}
    resp = requests.post(url, json=payload, headers=get_headers(), timeout=DEFAULT_TIMEOUT)
    if resp.status_code >= 400:
        raise RuntimeError(f"Server returned {resp.status_code}: {resp.text[:500]}")
    return resp.content


def fetch_engines() -> dict[str, Any]:
    """GET /api/engines → {engines: [...], default: ...}."""
    url = f"{get_url()}/api/engines"
    resp = requests.get(url, headers=get_headers(), timeout=10)
    resp.raise_for_status()
    return cast(dict[str, Any], resp.json())


def list_remote_engines() -> int:
    try:
        data = fetch_engines()
    except Exception as exc:
        logger.error(f"Failed to fetch engines from {get_url()}: {type(exc).__name__}: {exc}")
        return 1
    print(f"Remote engines on {get_url()}:")
    for name in data.get("engines", []):
        marker = "*" if name == data.get("default") else " "
        print(f"  {marker} {name}")
    return 0


def parse_arguments() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="TTS HTTP client — synthesize via remote ttssrv (mirror of ttsgen).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "Hello world"                    # POST → server → play
  %(prog)s "Hello" --file out.mp3           # save server response
  %(prog)s -i input.txt -o play,file        # multi-output, chunked
  %(prog)s --list                           # list engines on server
  %(prog)s "Hi" --engine coquitts           # ask server to use coquitts

Configuration (read from process env, ./ttsgen.conf, ~/.config/ttsgen.conf, .env):
  TTS_URL    = http://localhost:5000   (server URL, default localhost:5000)
  TTS_TOKEN  =                          (Bearer token; empty disables auth header)
        """,
    )
    text_group = parser.add_mutually_exclusive_group(required=True)
    text_group.add_argument("text", nargs="?", help="Text to synthesize")
    text_group.add_argument("-i", "--input", metavar="FILE", dest="text_file", help="Path to text file")
    text_group.add_argument(
        "-L", "--list", action="store_true", help="List engines available on the remote server"
    )

    parser.add_argument(
        "-f", "--file", nargs="?", const="", metavar="PATH", help="Save server response to file (auto-name if no PATH)"
    )
    parser.add_argument("-p", "--play", action="store_true", help="Play audio (default)")
    parser.add_argument("-s", "--stdout", action="store_true", help="Output audio bytes to stdout")
    parser.add_argument("-o", "--output", metavar="FORMATS", help="Comma-separated: play, file, stdout")
    parser.add_argument("-e", "--engine", help="Remote engine name (server's TTS_ENGINE if omitted)")
    parser.add_argument("-l", "--language", default="en", help="Language code (default: en)")
    parser.add_argument("-d", "--audio-dir", metavar="DIR", help="Directory for saved files (default: audio/)")

    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-q", "--quiet", action="store_true")
    return parser


def setup_logging(verbose: bool, quiet: bool) -> None:
    if quiet:
        logging.getLogger().setLevel(logging.ERROR)
    elif verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)


def read_text_file(path: str) -> str:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Not a file: {path}")
    with open(path, encoding="utf-8") as f:
        content = f.read().strip()
    if not content:
        raise ValueError(f"File is empty: {path}")
    return content


def main() -> int:
    parser = parse_arguments()
    args = parser.parse_args()
    setup_logging(args.verbose, args.quiet)

    # Load config files (./ttsgen.conf > ~/.config/ttsgen.conf > .env > defaults)
    try:
        from libs.config import load_config

        load_config()
    except ImportError:
        pass

    if getattr(args, "list", False):
        return list_remote_engines()

    # Resolve inputs
    if args.text_file:
        try:
            text = read_text_file(args.text_file)
        except (FileNotFoundError, ValueError) as exc:
            logger.error(str(exc))
            return 2
    else:
        text = args.text

    engine = args.engine or os.getenv("TTS_ENGINE", "")  # empty → server picks default
    language = args.language or os.getenv("TTS_LANGUAGE", "en")

    output_formats: list[str] = []
    if args.output:
        for fmt in [f.strip() for f in args.output.split(",")]:
            if fmt not in ("play", "file", "stdout"):
                logger.error(f"Invalid output format: {fmt}")
                return 2
            if fmt not in output_formats:
                output_formats.append(fmt)
    if args.file is not None and "file" not in output_formats:
        output_formats.append("file")
    if args.play and "play" not in output_formats:
        output_formats.append("play")
    if args.stdout and "stdout" not in output_formats:
        output_formats.append("stdout")
    if not output_formats:
        output_formats = ["play"]

    out_is_stdout = "stdout" in output_formats
    out_is_file = "file" in output_formats

    # Output filename resolution
    output_filename: str | None = None
    if out_is_file:
        ext = "mp3" if engine in ("", "gtts") else "wav"
        if args.file == "" or args.file is None:
            from datetime import datetime

            audio_dir = args.audio_dir or os.getenv("AUDIO_DIRECTORY", "audio")
            os.makedirs(audio_dir, exist_ok=True)
            output_filename = os.path.join(audio_dir, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}")
        else:
            output_filename = args.file

    if not args.quiet and not out_is_stdout:
        logger.info(f"TTS API client → {get_url()}")
        logger.info(f"Engine: {engine or '(server default)'}  Language: {language}")
        logger.info(f"Formats: {', '.join(output_formats)}")
        if output_filename:
            logger.info(f"Output file: {output_filename}")

    # Chunking and pipeline (matches ttsgen: 200-char chunks, producer/consumer threads)
    MAX_LEN = 200
    chunks = chunk_text(text, MAX_LEN)
    if not args.quiet and not out_is_stdout:
        logger.info(f"Chunks: {len(chunks)} (<= {MAX_LEN} chars each)")

    ext = "mp3" if engine in ("", "gtts") else "wav"
    tmp_suffix = f".{ext}"
    tmp_dir = (args.audio_dir or os.getenv("AUDIO_DIRECTORY", "audio")) if out_is_file else None
    if tmp_dir:
        os.makedirs(tmp_dir, exist_ok=True)

    def generator(text_chunk: str) -> bytes:
        return fetch_audio(text_chunk, engine or "", language)

    q: queue.Queue[QUEUE_ITEM] = queue.Queue(maxsize=2)
    collected_paths: list[str] = []
    failures: list[tuple[int, BaseException]] = []

    from libs.api import play_audio

    rec = threading.Thread(target=rec_worker, args=(chunks, generator, q, tmp_suffix, tmp_dir), daemon=True)
    play = threading.Thread(target=play_worker, args=(q, output_formats, collected_paths, play_audio, failures), daemon=True)
    rec.start()
    play.start()
    rec.join()
    play.join()

    if failures:
        for idx, err in failures:
            logger.error(f"Chunk {idx} failed: {type(err).__name__}: {err}")
        logger.error(f"{len(failures)}/{len(chunks)} chunk(s) failed; aborting with exit code 3.")
        return 3

    saved: list[str] = []
    if out_is_file and output_filename:
        if len(collected_paths) == 1:
            try:
                shutil.copy2(collected_paths[0], output_filename)
                safe_unlink(collected_paths[0])
                saved.append(output_filename)
            except Exception as exc:
                logger.error(f"Failed to save {output_filename}: {exc}")
        else:
            base, ext_dot = os.path.splitext(output_filename)
            for i, p in enumerate(collected_paths, start=1):
                dst = f"{base}_{i:03d}{ext_dot}"
                try:
                    shutil.copy2(p, dst)
                    safe_unlink(p)
                    saved.append(dst)
                except Exception as exc:
                    logger.error(f"Failed to save chunk {i}: {exc}")
        if not out_is_stdout:
            for f in saved:
                print(f, file=sys.stdout)

    if out_is_stdout:
        if ext == "mp3":
            for p in saved if saved else collected_paths:
                with open(p, "rb") as f:
                    sys.stdout.buffer.write(f.read())
            sys.stdout.buffer.flush()
        else:
            buf = io.BytesIO()
            concat_wav_files(saved if saved else collected_paths, buf)
            sys.stdout.buffer.write(buf.getvalue())
            sys.stdout.buffer.flush()

    if not out_is_file:
        for p in collected_paths:
            safe_unlink(p)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.warning("Interrupted")
        sys.exit(1)
    except Exception as exc:
        import traceback

        logger.error(f"{type(exc).__name__}: {str(exc)}\n{traceback.format_exc()}")
        sys.exit(1)
