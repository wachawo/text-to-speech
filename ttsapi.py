#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TTS HTTP client, a mirror of `ttsgen` that forwards synthesis to a remote `ttssrv`.

Accepts the same core argparse surface as `ttsgen` (text input, --file/--play/--stdout/
--output, --engine, --language, --list, -i, -v/-q) but replaces local
`text_to_speech_bytes()` with `POST {TTS_URL}/api/tts`.

Reads `TTS_URL` and `TTS_TOKEN` from the same config chain as ttsgen
(shell env > ./ttsgen.conf > ~/.config/ttsgen.conf > .env.local > .env > defaults).
"""

import argparse
import logging
import os
import sys
import traceback
from typing import Any, cast

import requests

# Local imports
from libs.cli import (
    DEFAULT_CHUNK_CHARS,
    chunk_extension,
    chunk_text,
    output_path_for,
    read_text_file,
    resolve_output_formats,
    resolve_output_target,
    run_pipeline,
    save_audio_file,
    scratch_dir,
    write_audio,
)
from libs.exceptions import ValidationError
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

# Extension per response Content-Type; anything else falls back to sniffing the bytes.
CONTENT_TYPE_EXTENSIONS = {
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
}

# Content-Type of the last /api/tts response. The pipeline generator only returns
# bytes, so the type that names an auto-generated file is kept here instead.
LAST_RESPONSE: dict[str, str] = {"content_type": ""}


def get_url() -> str:
    """Return the remote ttssrv base URL without a trailing slash."""
    return os.getenv("TTS_URL", DEFAULT_URL).rstrip("/")


def get_headers() -> dict[str, str]:
    """Build request headers, adding bearer auth only when TTS_TOKEN is set."""
    token = os.getenv("TTS_TOKEN", "").strip()
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def fetch_audio(text: str, engine: str, language: str) -> bytes:
    """POST text to remote ttssrv → return audio bytes.

    Args:
        text: Text to synthesize (one chunk).
        engine: Remote engine name; empty string lets the server pick its default.
        language: Two-letter language code; empty string lets the server use its TTS_LANGUAGE.

    Returns:
        Raw audio bytes (MP3 or WAV, depending on the server-side engine).

    Raises:
        RuntimeError: The server answered with an HTTP status of 400 or above.
    """
    url = f"{get_url()}/api/tts"
    payload = {"text": text, "engine": engine}
    if language:
        payload["language"] = language
    resp = requests.post(url, json=payload, headers=get_headers(), timeout=DEFAULT_TIMEOUT)
    if resp.status_code >= 400:
        raise RuntimeError(f"Server returned {resp.status_code}: {resp.text[:500]}")
    headers = getattr(resp, "headers", None) or {}
    LAST_RESPONSE["content_type"] = str(headers.get("Content-Type", ""))
    return resp.content


def response_extension(content_type: str, chunk_paths: list[str]) -> str:
    """Return the extension named by the response Content-Type, or sniff the first chunk."""
    media_type = content_type.split(";", 1)[0].strip().lower()
    return CONTENT_TYPE_EXTENSIONS.get(media_type) or chunk_extension(chunk_paths)


def fetch_engines() -> dict[str, Any]:
    """Return the decoded JSON body of GET /api/engines."""
    url = f"{get_url()}/api/engines"
    resp = requests.get(url, headers=get_headers(), timeout=10)
    resp.raise_for_status()
    return cast(dict[str, Any], resp.json())


def list_remote_engines() -> int:
    """Print the engines reported by the server and return a shell exit code."""
    try:
        data = fetch_engines()
    except Exception as exc:
        logger.error(f"Failed to fetch engines from {get_url()}: {type(exc).__name__}: {exc}")
        return 1
    # Human-facing table: stdout, not logging, so the listing stays free of log decoration.
    print(f"Remote engines on {get_url()}:")
    # "available" is what the server can synthesize with: GET /api/engines has
    # not carried an "engines" key since 1.0.3.
    for name in data.get("available", []):
        marker = "*" if name == data.get("default") else " "
        print(f"  {marker} {name}")
    return 0


def parse_arguments() -> argparse.ArgumentParser:
    """Build the argparse parser mirroring the ttsgen command line."""
    parser = argparse.ArgumentParser(
        description="TTS HTTP client: synthesize via remote ttssrv (mirror of ttsgen).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "Hello world"                    # POST to the server, then play
  %(prog)s "Hello" --file out.mp3           # save server response
  %(prog)s -i input.txt -o play,file        # multi-output, chunked
  %(prog)s --list                           # list engines on server
  %(prog)s "Hi" --engine coquitts           # ask server to use coquitts

Configuration (read from process env, ./ttsgen.conf, ~/.config/ttsgen.conf, .env.local, .env):
  TTS_URL    = http://localhost:5000   (server URL, default localhost:5000)
  TTS_TOKEN  =                          (Bearer token; empty disables auth header)
        """,
    )
    text_group = parser.add_mutually_exclusive_group(required=True)
    text_group.add_argument("text", nargs="?", help="Text to synthesize")
    text_group.add_argument("-i", "--input", metavar="FILE", dest="text_file", help="Path to text file")
    text_group.add_argument("-L", "--list", action="store_true", help="List engines available on the remote server")

    parser.add_argument(
        "-f", "--file", nargs="?", const="", metavar="PATH", help="Save server response to file (auto-name if no PATH)"
    )
    parser.add_argument("-p", "--play", action="store_true", help="Play audio (default)")
    parser.add_argument("-s", "--stdout", action="store_true", help="Output audio bytes to stdout (disables --file)")
    parser.add_argument("-o", "--output", metavar="FORMATS", help="Comma-separated: play, file, stdout")
    parser.add_argument("-e", "--engine", help="Remote engine name (server's TTS_ENGINE if omitted)")
    parser.add_argument("-l", "--language", help="Language code (default: the server's TTS_LANGUAGE)")
    parser.add_argument("-d", "--audio-dir", metavar="DIR", help="Directory for saved files (default: audio/)")

    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-q", "--quiet", action="store_true")
    return parser


def setup_logging(verbose: bool, quiet: bool) -> None:
    """Set the root log level from the -v/-q flags (quiet wins over verbose)."""
    if quiet:
        logging.getLogger().setLevel(logging.ERROR)
    elif verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)


def run_cli() -> int:
    """Run the remote-synthesis CLI and return a shell exit code."""
    parser = parse_arguments()
    args = parser.parse_args()
    setup_logging(args.verbose, args.quiet)

    # Load config files (./ttsgen.conf > ~/.config/ttsgen.conf > .env.local > .env > defaults).
    # Imported lazily and tolerantly so the client still runs from a bare checkout.
    try:
        from libs.config import load_config

        load_config()
    except ImportError:
        pass

    if getattr(args, "list", False):
        return list_remote_engines()

    LAST_RESPONSE["content_type"] = ""

    # Resolve inputs; a bad -i file or -o value exits 1, as in ttsgen.
    try:
        text = read_text_file(args.text_file) if args.text_file else args.text
        output_formats = resolve_output_formats(args.output, args.file, args.play, args.stdout)
    except ValidationError as exc:
        logger.error(f"Validation error: {exc}")
        return 1

    engine = args.engine or os.getenv("TTS_ENGINE", "")  # empty: the server picks its default
    language = args.language or os.getenv("TTS_LANGUAGE", "")  # empty: the server picks its default
    audio_dir = args.audio_dir or os.getenv("AUDIO_DIRECTORY", "audio")

    out_is_stdout = "stdout" in output_formats
    out_is_file = "file" in output_formats

    # The output target is an exact file name, or a directory whose file name is
    # built after synthesis from the response Content-Type (or the audio header).
    output_target: str | None = None
    target_is_dir = False
    if out_is_file:
        output_target, target_is_dir = resolve_output_target(args.file, audio_dir)

    if not args.quiet and not out_is_stdout:
        logger.info(f"TTS API client: {get_url()}")
        logger.info(f"Engine: {engine or '(server default)'}  Language: {language or '(server default)'}")
        logger.info(f"Formats: {', '.join(output_formats)}")
        if output_target:
            logger.info(f"Output: {output_target}")

    # Chunking and pipeline, shared with ttsgen
    chunks = chunk_text(text, DEFAULT_CHUNK_CHARS)
    if not args.quiet and not out_is_stdout:
        logger.info(f"Chunks: {len(chunks)} (<= {DEFAULT_CHUNK_CHARS} chars each)")

    # Keep scratch files next to the destination in file mode, in the system temp dir otherwise.
    tmp_dir = scratch_dir(output_target, target_is_dir)

    def generator(text_chunk: str) -> bytes:
        """Synthesize one chunk remotely, binding the resolved engine and language."""
        return fetch_audio(text_chunk, engine or "", language)

    created_paths: list[str] = []

    # Imported lazily: playback pulls in pygame, which is useless for --file/--stdout runs.
    from libs.api import play_audio

    try:
        collected_paths, failure = run_pipeline(chunks, generator, output_formats, play_audio, tmp_dir, created_paths)

        if failure is not None:
            idx, err = failure
            logger.error(f"Chunk {idx} of {len(chunks)} failed, nothing saved: {type(err).__name__}: {err}")
            return 3
        if not collected_paths:
            logger.error("No audio was generated: the text holds nothing to synthesize.")
            return 1

        if out_is_file and output_target is not None:
            extension = response_extension(LAST_RESPONSE["content_type"], collected_paths)
            output_filename = output_path_for(output_target, target_is_dir, os.getenv("FILENAME_PREFIX", ""), extension)
            try:
                save_audio_file(collected_paths, output_filename)
            except OSError as exc:
                logger.error(f"Failed to save {output_filename}: {type(exc).__name__}: {exc}\n{traceback.format_exc()}")
                if target_is_dir:
                    # The auto-generated name was claimed empty for this run.
                    safe_unlink(output_filename)
                return 1
            if out_is_stdout:
                # stdout carries the audio stream, so the filename goes to the log instead.
                logger.info(output_filename)
            else:
                # Shell-pipeable output: FILE=$(ttsapi "Hi" --file) must capture the path alone.
                print(output_filename, file=sys.stdout)

        if out_is_stdout:
            write_audio(collected_paths, sys.stdout.buffer)
            sys.stdout.buffer.flush()

        return 0
    finally:
        # Every exit, a failed chunk, a failed save or Ctrl+C included, removes
        # every chunk file the run created, queued or not.
        for chunk_path in created_paths:
            safe_unlink(chunk_path)


def main() -> int:
    """Console-script entry point: run the CLI, turning Ctrl+C and stray errors into exit code 1."""
    try:
        return run_cli()
    except KeyboardInterrupt:
        logger.warning("Interrupted")
        return 1
    except Exception as exc:
        logger.error(f"{type(exc).__name__}: {str(exc)}\n{traceback.format_exc()}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
