#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Command-line tool that synthesizes text locally and plays, saves or pipes the audio."""

import argparse
import io
import logging
import os
import queue
import shutil
import sys
import threading
import traceback
from pathlib import Path
from typing import Any, cast

from dotenv import find_dotenv, load_dotenv

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
    from libs.tempfiles import safe_unlink
    from libs.tools import ensure_audio_directory, generate_timestamp_filename
except ImportError as exc:
    logger.error(f"Failed to import TTS library: {exc}")
    sys.exit(1)

# Pipeline helpers (chunk_text, concat_wav_files, rec_worker, play_worker) live in libs.cli
# so they're shared between ttsgen (offline) and ttsapi (HTTP-based) without code duplication.
# This import sits below the logging setup and the guarded block above on purpose, so the
# E402 waiver is deliberate rather than an oversight.
from libs.cli import (  # noqa: E402
    QueueItem,
    chunk_text,
    concat_wav_files,
    play_worker,
    rec_worker,
)

# Long input is split into chunks so playback can start before synthesis finishes.
DEFAULT_CHUNK_CHARS = 200

# Bounded queue between producer and consumer threads — provides backpressure.
PIPELINE_QUEUE_SIZE = 2

VALID_OUTPUT_FORMATS = ("play", "file", "stdout")


def get_config() -> dict[str, Any]:
    """Load configuration from .env (base) → .env.local (override)."""
    found = find_dotenv(usecwd=True)
    if found:
        load_dotenv(found)
    if os.path.exists(".env.local"):
        load_dotenv(".env.local", override=True)
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
    parser.add_argument("-l", "--language", default="en", help="Language code (default: en)")

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


def to_file(args: argparse.Namespace, config: dict[str, Any], engine: str) -> str | None:
    """Determine output filename from arguments and configuration."""
    if args.file is None:
        return None
    extension = "mp3" if engine == "gtts" else "wav"
    if args.file == "":
        audio_dir = args.audio_dir or config["audio_directory"]
        ensure_audio_directory(audio_dir)
        timestamp_filename = cast(str, generate_timestamp_filename("", extension))
        return os.path.join(audio_dir, timestamp_filename)
    if args.file.endswith("/") or (os.path.exists(args.file) and os.path.isdir(args.file)):
        ensure_audio_directory(args.file)
        timestamp_filename = cast(str, generate_timestamp_filename("", extension))
        return os.path.join(args.file, timestamp_filename)
    parent_dir = os.path.dirname(args.file)
    if parent_dir and parent_dir != ".":
        ensure_audio_directory(parent_dir)
    filename: str = args.file
    return filename


ENGINE_MODEL_SOURCES = {
    "pipertts": (os.getenv("PIPERTTS_MODELS", "cache/pipertts"), ["*.onnx"]),
    "silerotts": (os.getenv("SILEROTTS_MODELS", "cache/silerotts"), ["**/*.pt", "**/*.jit"]),
    "coquitts": (os.getenv("COQUITTS_MODELS", "cache/coquitts"), ["tts/*"]),
    "barktts": (os.getenv("BARKTTS_MODELS", "cache/barktts"), ["**/*.pt"]),
    "kokorotts": (os.getenv("KOKOROTTS_MODELS", "cache/kokorotts"), ["*.onnx", "*.bin"]),
}

ENGINE_NOTES = {
    "gtts": "cloud — no local models",
    "pyttsx3": "uses system espeak voices",
}


def model_display_name(engine: str, rel: Path) -> str:
    """Render a glob match into a grep-friendly model identifier.

    coqui caches models as tts/tts_models--multilingual--multi-dataset--xtts_v2/.
    We strip the tts/ prefix and restore '/' so the displayed name matches the
    string users put in COQUITTS_MODEL.
    """
    display = str(rel)
    if engine == "coquitts":
        display = display.removeprefix("tts/").replace("--", "/")
    return display


def collect_engine_rows() -> list[tuple[str, str, str]]:
    """Build the (engine, status, model) rows shown by --list, one row per model."""
    # Imported lazily: loading the engine package probes every optional dependency,
    # which is wasted work for runs that never reach --list.
    from engines import is_engine_available

    engines_dir = Path(__file__).resolve().parent / "engines"
    engine_names = sorted(p.stem for p in engines_dir.glob("*.py") if p.name != "__init__.py")

    # Silence engine-loader probe warnings — status column already reports it.
    engines_logger = logging.getLogger("engines")
    prev_level = engines_logger.level
    engines_logger.setLevel(logging.ERROR)

    rows: list[tuple[str, str, str]] = []
    for name in engine_names:
        status = "installed" if is_engine_available(name) else "missing"

        # Cloud / system-voice engines have no on-disk model files.
        if name in ENGINE_NOTES:
            rows.append((name, status, ENGINE_NOTES[name]))
            continue

        # Engine deps not present → no point looking for models.
        if status == "missing" or name not in ENGINE_MODEL_SOURCES:
            rows.append((name, status, "-"))
            continue

        model_dir, patterns = ENGINE_MODEL_SOURCES[name]
        models_path = Path(model_dir)
        files: list[Path] = []
        if models_path.exists():
            for pattern in patterns:
                files.extend(sorted(models_path.glob(pattern)))
        if not files:
            rows.append((name, status, "-"))
        else:
            for model_file in files:
                rel = model_file.relative_to(models_path) if model_file.is_relative_to(models_path) else model_file
                rows.append((name, status, model_display_name(name, rel)))

    engines_logger.setLevel(prev_level)
    return rows


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
    output_filename: str | None,
) -> None:
    """Log the resolved run parameters before synthesis starts."""
    logger.info("TTS CLI Tool")
    logger.info("=" * 40)
    preview = text[:50] + ("..." if len(text) > 50 else "")
    logger.info(f"Text: {preview}")
    logger.info(f"Engine: {engine}")
    logger.info(f"Language: {language}")
    logger.info(f"Formats: {', '.join(output_formats)}")
    if output_filename:
        logger.info(f"Output file: {output_filename}")


def save_chunk_files(
    collected_paths: list[str],
    output_filename: str | None,
    extension: str,
    fallback_dir: str,
) -> list[str]:
    """Move the generated chunk temp files to their final destination.

    Args:
        collected_paths: Temp files produced by the pipeline, in playback order.
        output_filename: Requested output path, a directory, or None.
        extension: Audio extension used when the request carries none.
        fallback_dir: Directory used when output_filename is missing or is a directory.

    Returns:
        Destination paths of the chunks that were written successfully.
    """
    saved_files: list[str] = []

    if output_filename and not os.path.isdir(output_filename):
        base, requested_ext = os.path.splitext(output_filename)
        if not requested_ext:
            requested_ext = f".{extension}"
        for index, tmp_path in enumerate(collected_paths, start=1):
            destination = f"{base}_{index:03d}{requested_ext}"
            try:
                shutil.copy2(tmp_path, destination)  # copy temp file to destination
                safe_unlink(tmp_path)  # delete original temp file (Windows-safe)
                saved_files.append(destination)
            except Exception as exc:
                logger.error(f"Failed to save chunk {index} to {destination}: {exc}")
        return saved_files

    out_dir = output_filename if (output_filename and os.path.isdir(output_filename)) else fallback_dir
    ensure_audio_directory(out_dir)
    for index, tmp_path in enumerate(collected_paths, start=1):
        filename = generate_timestamp_filename(f"part_{index:03d}_", extension)
        destination = os.path.join(out_dir, filename)
        try:
            shutil.copy2(tmp_path, destination)
            safe_unlink(tmp_path)
            saved_files.append(destination)
        except Exception as exc:
            logger.error(f"Failed to save chunk {index} to {destination}: {exc}")
    return saved_files


def write_stdout_audio(engine: str, audio_paths: list[str]) -> None:
    """Write the generated audio to stdout, concatenating WAV chunks when possible."""
    if engine == "gtts":
        # MP3 - don't glue them together without recoding -
        # write them sequentially
        logger.warning("multiple MP3 chunks written sequentially to stdout; " "this is not a single valid MP3 file.")
        for path in audio_paths:
            with open(path, "rb") as f:
                sys.stdout.buffer.write(f.read())
        sys.stdout.buffer.flush()
        return

    stdout_buf = io.BytesIO()
    concat_wav_files(audio_paths, stdout_buf)
    sys.stdout.buffer.write(stdout_buf.getvalue())
    sys.stdout.buffer.flush()


def main() -> int:
    """Run the ttsgen command line and return the process exit code."""
    parser = parse_arguments()
    args = parser.parse_args()

    # Engine-specific CLI overrides → push into env so engine/installer pick them up.
    # CLI flags take top priority over config files.
    if getattr(args, "coqui_model", None):
        os.environ["COQUITTS_MODEL"] = args.coqui_model
    if getattr(args, "coqui_sample", None):
        os.environ["COQUITTS_SAMPLE"] = args.coqui_sample

    # Load config files (./ttsgen.conf > ~/.config/ttsgen.conf > .env). Existing env
    # (set by shell or by the CLI flags above) is preserved — files only fill gaps.
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
        config = get_config()
        text = get_text(args)
        engine = args.engine or config["engine"]
        language = args.language or config["language"]

        output_formats = resolve_output_formats(args)

        # Determine output filename if saving to file
        output_filename: str | None = None
        if "file" in output_formats:
            if args.file is not None:
                output_filename = to_file(args, config, engine)
            else:
                audio_dir = config["audio_directory"]
                ensure_audio_directory(audio_dir)
                prefix = config.get("filename_prefix", "")
                extension = "wav" if engine in ["pyttsx3", "pipertts"] else "mp3"
                timestamp_filename = generate_timestamp_filename(prefix, extension)
                output_filename = os.path.join(audio_dir, timestamp_filename)

        verbose_summary = not args.quiet and "stdout" not in output_formats
        if verbose_summary:
            log_run_summary(text, engine, language, output_formats, output_filename)

        # Chunked mode: synthesis and playback overlap through a bounded queue.
        chunks = chunk_text(text, DEFAULT_CHUNK_CHARS)
        if verbose_summary:
            logger.info(f"Chunks: {len(chunks)} (<= {DEFAULT_CHUNK_CHARS} chars each)")

        ext = "mp3" if engine == "gtts" else "wav"
        tmp_suffix = f".{ext}"

        out_is_stdout = "stdout" in output_formats
        out_is_file = "file" in output_formats

        # Co-locate temp chunks with the final file only when actually saving to disk
        # (avoids cross-drive moves). Otherwise use system /tmp.
        if out_is_file:
            tmp_dir = args.audio_dir or config["audio_directory"]
            ensure_audio_directory(tmp_dir)
        else:
            tmp_dir = None

        audio_queue: queue.Queue[QueueItem] = queue.Queue(maxsize=PIPELINE_QUEUE_SIZE)
        collected_paths: list[str] = []
        failures: list[tuple[int, BaseException]] = []

        def generator(chunk: str) -> bytes:
            """Synthesize one chunk with the engine and language chosen for this run."""
            return text_to_speech_bytes(text=chunk, engine=engine, language=language)

        rec_thread = threading.Thread(
            target=rec_worker,
            args=(chunks, generator, audio_queue, tmp_suffix, tmp_dir),
            daemon=True,
        )
        play_thread = threading.Thread(
            target=play_worker,
            args=(audio_queue, output_formats, collected_paths, play_audio, failures),
            daemon=True,
        )
        rec_thread.start()
        play_thread.start()
        rec_thread.join()
        play_thread.join()

        if failures:
            for idx, err in failures:
                logger.error(f"Chunk {idx} failed: {type(err).__name__}: {err}")
            logger.error(f"{len(failures)}/{len(chunks)} chunk(s) failed; aborting with exit code 3.")
            return 3

        saved_files: list[str] = []

        if out_is_file:
            fallback_dir = args.audio_dir or config["audio_directory"]
            saved_files = save_chunk_files(collected_paths, output_filename, ext, fallback_dir)
            if "stdout" not in output_formats:
                # Written to stdout so shells can capture it: FILE=$(ttsgen "Hi" --file).
                for fpath in saved_files:
                    print(fpath, file=sys.stdout)
            else:
                # stdout carries the audio stream, so the filenames go to the log instead.
                for fpath in saved_files:
                    logger.info(fpath)

        if out_is_stdout:
            write_stdout_audio(engine, saved_files if saved_files else collected_paths)

        if not out_is_file:
            for tmp_path in collected_paths:
                safe_unlink(tmp_path)

        return 0

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
