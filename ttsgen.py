#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Command-line tool that synthesizes text locally and plays, saves or pipes the audio."""

import argparse
import logging
import os
import queue
import sys
import threading
import traceback
from typing import Any, cast

# Configure logging
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

try:
    from libs.api import (  # type: ignore
        EngineNotAvailableError,
        TTSException,
        ValidationError,
        play_audio,
        text_to_speech_bytes,
    )
    from libs.config import load_config
    from libs.models import collect_engine_rows
    from libs.tempfiles import safe_unlink
except ImportError as exc:
    logger.error(f"Failed to import TTS library: {exc}")
    sys.exit(1)

# Pipeline helpers (chunk_text, output resolution, rec_worker, play_worker) live in libs.cli
# so they're shared between ttsgen (offline) and ttsapi (HTTP-based) without code duplication.
# This import sits below the logging setup and the guarded block above on purpose, so the
# E402 waiver is deliberate rather than an oversight.
from libs.cli import (  # noqa: E402
    CHUNK_SUFFIX,
    QueueItem,
    chunk_extension,
    chunk_text,
    output_path_for,
    play_worker,
    rec_worker,
    resolve_output_target,
    save_audio_file,
    scratch_dir,
    write_audio,
)

# Long input is split into chunks so playback can start before synthesis finishes.
DEFAULT_CHUNK_CHARS = 200

# Bounded queue between producer and consumer threads, provides backpressure.
PIPELINE_QUEUE_SIZE = 2

VALID_OUTPUT_FORMATS = ("play", "file", "stdout")


def read_env_config() -> dict[str, Any]:
    """Read the CLI defaults from the environment, after load_config() has filled it."""
    return {
        "engine": os.getenv("TTS_ENGINE", "gtts"),
        "language": os.getenv("TTS_LANGUAGE", "en"),
        "audio_directory": os.getenv("AUDIO_DIRECTORY", "audio"),
        "filename_prefix": os.getenv("FILENAME_PREFIX", ""),
    }


def read_file(file_path: str) -> str:
    """Read text content from a file."""
    try:
        file_path = os.path.normpath(file_path)
        if not os.path.exists(file_path):
            raise ValidationError(f"File not found: {file_path}")
        if not os.path.isfile(file_path):
            raise ValidationError(f"Path is not a file: {file_path}")
        with open(file_path, encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            raise ValidationError(f"File is empty: {file_path}")
        return content
    except UnicodeDecodeError as exc:
        raise ValidationError(f"File encoding error: {exc}") from exc
    except Exception as exc:
        raise ValidationError(f"Could not read file {file_path}: {exc}") from exc


def parse_arguments() -> argparse.ArgumentParser:
    """Create and configure argument parser.

    Returns the parser itself (not parsed arguments), so callers can decide when
    to call `parse_args()` or reuse the parser for help output.
    """
    parser = argparse.ArgumentParser(
        description="Professional TTS (Text-to-Speech) CLI tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "Hello world"                    # Play audio (default)
  %(prog)s "Hello world" --file             # Save with auto-generated name
  %(prog)s "Hello world" --file out.mp3     # Save to specific file
  %(prog)s "Hello world" --file audio/      # Save to directory with timestamp
  %(prog)s -i input.txt                     # Read text from file
  %(prog)s "Hello" --file --play            # Save and play
  %(prog)s "Hello" --stdout                 # Output audio bytes to stdout
  %(prog)s "Hello" -o play,file             # Play and save (via --output)
  %(prog)s "Hello" -o file,stdout           # Save and output to stdout
  %(prog)s "Hello" --engine pyttsx3         # Use offline engine (espeak)
  %(prog)s "Hello" --language es            # Use Spanish language
  %(prog)s --list                           # List engines and installed models
  %(prog)s --install coquitts               # Install an engine and download models

Environment Configuration:
  Create a .env file to set default values:
  TTS_ENGINE=gtts
  TTS_LANGUAGE=en
  DEFAULT_OUTPUT_FORMAT=file
  AUDIO_DIRECTORY=audio
  AUTO_PLAY=false
        """,
    )

    # Text input options
    text_group = parser.add_mutually_exclusive_group(required=True)
    text_group.add_argument("text", nargs="?", help="Text to convert to speech")
    text_group.add_argument(
        "-i",
        "--input",
        metavar="FILE",
        dest="text_file",
        help="Path to text file to read",
    )
    text_group.add_argument(
        "-L",
        "--list",
        action="store_true",
        help="List engines and installed model files, then exit",
    )
    text_group.add_argument(
        "-I",
        "--install",
        metavar="ENGINE",
        help="Install an engine (pipertts, silerotts, coquitts, barktts, kokorotts) and exit",
    )

    # Non-interactive flag — only meaningful with --install
    parser.add_argument(
        "-n",
        "--non-interactive",
        action="store_true",
        help="Skip prompts in --install (accept defaults)",
    )

    # Output options
    parser.add_argument(
        "-f",
        "--file",
        nargs="?",
        const="",  # If --file is specified without value, use empty string
        metavar="PATH",
        help="""Save to file. Can be: filename (e.g. output.mp3), directory
        (e.g. audio/),
        or just --file for auto-generated name. Returns filename to stdout.""",
    )
    parser.add_argument(
        "-p",
        "--play",
        action="store_true",
        help="Play audio (default if no other output specified)",
    )
    parser.add_argument(
        "-s",
        "--stdout",
        action="store_true",
        help="Output audio bytes to stdout (disables --file)",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="FORMATS",
        help='Comma-separated output formats: play, file, stdout (e.g. "play,file" or "file,stdout")',
    )

    # TTS engine options
    parser.add_argument(
        "-e",
        "--engine",
        help="TTS engine to use (gtts, pyttsx3, or any custom engine in engines/)",
    )
    parser.add_argument("-l", "--language", help="Language code (default: en)")

    # Audio directory option
    parser.add_argument(
        "-d",
        "--audio-dir",
        metavar="DIR",
        help="Directory to save audio files (default: audio/)",
    )

    # Engine-specific options (override .env values for one run)
    parser.add_argument(
        "-m",
        "--coqui-model",
        metavar="MODEL",
        help='coqui-tts model identifier (e.g. "tts_models/multilingual/multi-dataset/xtts_v2"). '
        "Sets COQUITTS_MODEL for this run.",
    )
    parser.add_argument(
        "-w",
        "--coqui-sample",
        metavar="PATH",
        help="Path to voice sample WAV used by xtts_v2 voice cloning. Sets COQUITTS_SAMPLE for this run.",
    )

    # Verbosity options
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress non-error output")

    return parser


def setup_logging(verbose: bool, quiet: bool) -> None:
    """Setup logging based on verbosity options."""
    if quiet:
        logging.getLogger().setLevel(logging.ERROR)
    elif verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)


def get_text(args: argparse.Namespace) -> str:
    """Determine text input from arguments."""
    if args.text_file:
        return read_file(args.text_file)
    elif args.text:
        return cast(str, args.text)
    else:
        raise ValidationError("No text provided")


def list_engines_and_models() -> None:
    """Print engines and installed model files as a fixed-width table.

    Format:  ENGINE  STATUS  MODEL    one row per (engine, model). Designed for
    grep: `ttsgen --list | grep installed`, `... | grep xtts_v2`, etc.
    """
    rows = collect_engine_rows()

    name_w = max(len("ENGINE"), max(len(r[0]) for r in rows)) + 2
    stat_w = max(len("STATUS"), max(len(r[1]) for r in rows)) + 2
    # Human-facing table goes to stdout, not logging: it is the command's payload
    # and must stay greppable and free of log prefixes.
    print(f"{'ENGINE':<{name_w}}{'STATUS':<{stat_w}}MODEL")
    for engine, status, model in rows:
        print(f"{engine:<{name_w}}{status:<{stat_w}}{model}")


def resolve_output_formats(args: argparse.Namespace) -> list[str]:
    """Combine --output, --file, --play and --stdout into ordered output modes.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Deduplicated output modes; defaults to ["play"] when nothing is requested.

    Raises:
        ValidationError: If --output names a mode other than play, file or stdout.
    """
    output_formats: list[str] = []
    if args.output:
        for fmt in [f.strip() for f in args.output.split(",")]:
            if fmt not in VALID_OUTPUT_FORMATS:
                raise ValidationError(f"Invalid output format: {fmt}. Valid: play, file, stdout")
            if fmt not in output_formats:
                output_formats.append(fmt)
    if args.file is not None and "file" not in output_formats:
        output_formats.append("file")
    if args.play and "play" not in output_formats:
        output_formats.append("play")
    if args.stdout and "stdout" not in output_formats:
        output_formats.append("stdout")
    if args.stdout and args.file is not None and not args.output:
        output_formats = [f for f in output_formats if f != "file"]
    return output_formats or ["play"]


def log_run_summary(
    text: str,
    engine: str,
    language: str,
    output_formats: list[str],
    output_target: str | None,
) -> None:
    """Log the resolved run parameters before synthesis starts."""
    logger.info("TTS CLI Tool")
    logger.info("=" * 40)
    preview = text[:50] + ("..." if len(text) > 50 else "")
    logger.info(f"Text: {preview}")
    logger.info(f"Engine: {engine}")
    logger.info(f"Language: {language}")
    logger.info(f"Formats: {', '.join(output_formats)}")
    if output_target:
        logger.info(f"Output: {output_target}")


def main() -> int:
    """Run the ttsgen command line and return the process exit code."""
    parser = parse_arguments()
    args = parser.parse_args()

    # Engine-specific CLI overrides are pushed into the env so engine/installer pick them up.
    # CLI flags take top priority over config files.
    if getattr(args, "coqui_model", None):
        os.environ["COQUITTS_MODEL"] = args.coqui_model
    if getattr(args, "coqui_sample", None):
        os.environ["COQUITTS_SAMPLE"] = args.coqui_sample

    # Load config files (./ttsgen.conf > ~/.config/ttsgen.conf > .env.local > .env). Existing
    # env (set by the shell or by the CLI flags above) is preserved: files only fill gaps.
    load_config()

    if getattr(args, "list", False):
        list_engines_and_models()
        return 0

    if getattr(args, "install", None):
        # Imported lazily so a plain synthesis run never pulls in the installer stack.
        from install import run as run_installer

        return run_installer(args.install, non_interactive=args.non_interactive)

    try:
        setup_logging(args.verbose, args.quiet)
        config = read_env_config()
        text = get_text(args)
        engine = args.engine or config["engine"]
        language = args.language or config["language"]

        output_formats = resolve_output_formats(args)
        out_is_stdout = "stdout" in output_formats
        out_is_file = "file" in output_formats

        # The output target is an exact file name, or a directory whose file name is
        # built after synthesis, once the audio header says whether it is WAV or MP3.
        output_target: str | None = None
        target_is_dir = False
        if out_is_file:
            audio_dir = args.audio_dir or config["audio_directory"]
            output_target, target_is_dir = resolve_output_target(args.file, audio_dir)

        verbose_summary = not args.quiet and not out_is_stdout
        if verbose_summary:
            log_run_summary(text, engine, language, output_formats, output_target)

        # Chunked mode: synthesis and playback overlap through a bounded queue.
        chunks = chunk_text(text, DEFAULT_CHUNK_CHARS)
        if verbose_summary:
            logger.info(f"Chunks: {len(chunks)} (<= {DEFAULT_CHUNK_CHARS} chars each)")

        # Co-locate temp chunks with the final file only when actually saving to disk.
        # Otherwise use the system temp dir.
        tmp_dir = scratch_dir(output_target, target_is_dir)

        audio_queue: queue.Queue[QueueItem] = queue.Queue(maxsize=PIPELINE_QUEUE_SIZE)
        collected_paths: list[str] = []
        failures: list[tuple[int, BaseException]] = []

        def generator(chunk: str) -> bytes:
            """Synthesize one chunk with the engine and language chosen for this run."""
            return text_to_speech_bytes(text=chunk, engine=engine, language=language)

        rec_thread = threading.Thread(
            target=rec_worker,
            args=(chunks, generator, audio_queue, CHUNK_SUFFIX, tmp_dir),
            daemon=True,
        )
        play_thread = threading.Thread(
            target=play_worker,
            args=(audio_queue, output_formats, collected_paths, play_audio, failures),
            daemon=True,
        )
        try:
            rec_thread.start()
            play_thread.start()
            rec_thread.join()
            play_thread.join()

            if failures:
                for idx, err in failures:
                    logger.error(f"Chunk {idx} failed: {type(err).__name__}: {err}")
                logger.error(f"{len(failures)}/{len(chunks)} chunk(s) failed; aborting with exit code 3.")
                return 3
            if not collected_paths:
                logger.error("No audio was generated: the text holds nothing to synthesize.")
                return 1

            if out_is_file and output_target is not None:
                extension = chunk_extension(collected_paths)
                output_filename = output_path_for(output_target, target_is_dir, config["filename_prefix"], extension)
                try:
                    save_audio_file(collected_paths, output_filename)
                except OSError as exc:
                    logger.error(f"Failed to save {output_filename}: {type(exc).__name__}: {exc}\n{traceback.format_exc()}")
                    return 1
                if out_is_stdout:
                    # stdout carries the audio stream, so the filename goes to the log instead.
                    logger.info(output_filename)
                else:
                    # Written to stdout so shells can capture it: FILE=$(ttsgen "Hi" --file).
                    print(output_filename, file=sys.stdout)

            if out_is_stdout:
                write_audio(collected_paths, sys.stdout.buffer)
                sys.stdout.buffer.flush()

            return 0
        finally:
            # Every exit, a failed chunk or a failed save included, removes the chunk files.
            for tmp_path in collected_paths:
                safe_unlink(tmp_path)

    except ValidationError as exc:
        logger.error(f"Validation error: {exc}")
        return 1
    except EngineNotAvailableError as exc:
        logger.error(f"Engine not available: {exc}")
        return 1
    except TTSException as exc:
        logger.error(f"TTS error: {exc}")
        return 1
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 1
    except Exception as exc:
        logger.error(f"Unexpected error: {exc}")
        if args.verbose:
            logger.error(f"{type(exc).__name__}: {str(exc)}\n{traceback.format_exc()}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
