#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TTS CLI Tool - Professional Command Line Interface

A professional command-line interface for the TTS library with comprehensive
error handling, validation, and user-friendly output.

Features:
- Multiple input methods (text, file)
- Flexible output options (file, bytesio)
- Multiple TTS engines (pyttsx3, gTTS)
- Environment configuration support
- Audio playback capabilities
- Comprehensive error handling

Usage:
    python tts.py "Hello world"                    # Play audio (default)
    python tts.py "Hello world" --file             # Save to auto-generated file
    python tts.py "Hello world" --file output.mp3  # Save to specific file
    python tts.py -i input.txt                     # Read text from file
    python tts.py "Hello" --file --play            # Save and play
    python tts.py "Hello" --engine pyttsx3         # Use offline engine
    python tts.py "Hello" --format bytesio         # Output as BytesIO (advanced)
    python tts.py --list                           # List engines and installed models
    python tts.py --install coquitts               # Install an engine and download models

Author: TTS Library Team
Version: 1.0.0
License: MIT
"""

import argparse
import os
import shutil
import sys
import logging
import re
import threading
import queue
import tempfile
import io
import wave
from pathlib import Path
from typing import Optional, Dict, Any, cast, List, Tuple, IO
from dotenv import load_dotenv

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
        play_audio,
        TTSException,
        ValidationError,
        EngineNotAvailableError,
    )

    """ By Silletr -
     This functions is unavailable,
     write it and u can remove Except block
     Cause it local modules that not need installigng
    """
    from libs.tools import generate_timestamp_filename, ensure_audio_directory
    from libs.tempfiles import safe_unlink
except ImportError as e:
    logger.error(f"Failed to import TTS library: {e}")
    sys.exit(1)

SPLIT_REGEX = re.compile(r"(?<=[.!?]|,|\n)")


def chunk_text(text: str, max_len: int = 5000) -> List[str]:
    """Split text by sentence-ish boundaries to chunks <= max_len."""
    parts = [p.strip() for p in SPLIT_REGEX.split(text) if p and p.strip()]
    chunks: List[str] = []
    buf: List[str] = []
    cur_len = 0
    for p in parts:
        if len(p) > max_len:
            if cur_len:
                chunks.append(" ".join(buf))
                buf, cur_len = [], 0
            for i in range(0, len(p), max_len):
                chunks.append(p[i : i + max_len])
            continue
        add_len = (1 if buf else 0) + len(p)
        if cur_len + add_len <= max_len:
            buf.append(p)
            cur_len += add_len
        else:
            if buf:
                chunks.append(" ".join(buf))
            buf, cur_len = [p], len(p)
    if buf:
        chunks.append(" ".join(buf))
    return chunks


def concat_wav_files(in_paths: List[str], out_stream: IO[bytes]) -> None:
    """Concat WAV files (with same parametrs) to one WAV file,
    recordings to out_stream."""
    if not in_paths:
        return
    wout = wave.open(out_stream, "wb")
    first = True
    try:
        for p in in_paths:
            win = wave.open(p, "rb")
            try:
                if first:
                    wout.setnchannels(win.getnchannels())
                    wout.setsampwidth(win.getsampwidth())
                    wout.setframerate(win.getframerate())
                    first = False
                else:
                    if (
                        win.getnchannels() != wout.getnchannels()
                        or win.getsampwidth() != wout.getsampwidth()
                        or win.getframerate() != wout.getframerate()
                    ):
                        logger.warning(
                            f"WAV params mismatch in {p}; attempting naive append (may be invalid)."
                        )
                frames = win.readframes(win.getnframes())
                wout.writeframes(frames)
            finally:
                win.close()
    finally:
        wout.close()


# item in queue: Optional[Tuple[int, str, bytes]] -> (idx, tmp_path, audio_bytes)
QUEUE_ITEM = Optional[Tuple[int, str, bytes]]


def rec_worker(
    text_chunks: List[str],
    eng: str,
    lang: str,
    q: "queue.Queue[QUEUE_ITEM]",
    tmp_suffix: str,
    tmp_dir: Optional[str] = None,
) -> None:
    """Generating audio`s and packing its in row (idx, tmp_path, bytes)."""
    from libs.api import text_to_speech_bytes

    for i, chunk in enumerate(text_chunks, start=1):
        try:
            audio_bytes = text_to_speech_bytes(text=chunk, engine=eng, language=lang)
        except Exception as e:
            logger.error(f"TTS error on chunk {i}: {e}")
            audio_bytes = b""
        fd, tmp_path = tempfile.mkstemp(suffix=tmp_suffix, dir=tmp_dir)
        os.close(fd)
        try:
            with open(tmp_path, "wb") as f:
                f.write(audio_bytes)
        except Exception as e:
            logger.error(f"Failed to write temp audio for chunk {i}: {e}")
        q.put((i, tmp_path, audio_bytes))
    q.put(None)  # Signal of end


def play_worker(
    q: "queue.Queue[QUEUE_ITEM]",
    modes: List[str],
    collected_paths: List[str],
    play_func,
) -> None:
    """
    modes: subset ['file','play','stdout']
    collected_paths: filled with temporary file paths (in order of receipt)
    """
    while True:
        item = q.get()
        if item is None:
            break
        idx, tmp_path, audio_bytes = item
        collected_paths.append(tmp_path)
        if "play" in modes:
            try:
                play_func(audio_bytes)
            except Exception as e:
                logger.error(f"Playback error on chunk {idx}: {e}")


def get_config() -> Dict[str, Any]:
    """Load configuration from .env file if it exists."""
    load_dotenv(".env")
    engine = os.getenv("TTS_ENGINE", "gtts")
    language = os.getenv("TTS_LANGUAGE", "en")
    audio_directory = os.getenv("AUDIO_DIRECTORY", "audio")
    filename_prefix = os.getenv("FILENAME_PREFIX", "")
    default_output_format = os.getenv("DEFAULT_OUTPUT_FORMAT", "play")
    output_formats = [f.strip() for f in default_output_format.split(",") if f.strip()]
    audio_rate = int(os.getenv("AUDIO_RATE", "150"))
    audio_volume = float(os.getenv("AUDIO_VOLUME", "0.9"))
    return {
        "engine": engine,
        "language": language,
        "output_formats": output_formats,
        "audio_directory": audio_directory,
        "filename_prefix": filename_prefix,
        "audio_rate": audio_rate,
        "audio_volume": audio_volume,
    }


def read_file(file_path: str) -> str:
    """Read text content from a file."""
    try:
        file_path = os.path.normpath(file_path)
        if not os.path.exists(file_path):
            raise ValidationError(f"File not found: {file_path}")
        if not os.path.isfile(file_path):
            raise ValidationError(f"Path is not a file: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            raise ValidationError(f"File is empty: {file_path}")
        return content
    except UnicodeDecodeError as e:
        raise ValidationError(f"File encoding error: {e}")
    except Exception as e:
        raise ValidationError(f"Could not read file {file_path}: {e}")


def parse_arguments() -> argparse.ArgumentParser:
    """Create and configure argument parser."""
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
        "--list",
        action="store_true",
        help="List engines and installed model files, then exit",
    )
    text_group.add_argument(
        "--install",
        metavar="ENGINE",
        help="Install an engine (pipertts, silerotts, coquitts, barktts) and exit",
    )

    # Non-interactive flag — only meaningful with --install
    parser.add_argument(
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
    parser.add_argument(
        "-l", "--language", default="en", help="Language code (default: en)"
    )

    # Audio directory option
    parser.add_argument(
        "--audio-dir",
        metavar="DIR",
        help="Directory to save audio files (default: audio/)",
    )

    # Verbosity options
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress non-error output"
    )

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


def to_file(
    args: argparse.Namespace, config: Dict[str, Any], engine: str
) -> Optional[str]:
    """Determine output filename from arguments and configuration."""
    if args.file is None:
        return None
    extension = "mp3" if engine == "gtts" else "wav"
    if args.file == "":
        audio_dir = args.audio_dir or config["audio_directory"]
        ensure_audio_directory(audio_dir)
        timestamp_filename = cast(str, generate_timestamp_filename("", extension))
        return os.path.join(audio_dir, timestamp_filename)
    if args.file.endswith("/") or (
        os.path.exists(args.file) and os.path.isdir(args.file)
    ):
        ensure_audio_directory(args.file)
        timestamp_filename = cast(str, generate_timestamp_filename("", extension))
        return os.path.join(args.file, timestamp_filename)
    parent_dir = os.path.dirname(args.file)
    if parent_dir and parent_dir != ".":
        ensure_audio_directory(parent_dir)
    filename: str = args.file
    return filename


ENGINE_MODEL_SOURCES = {
    "pipertts":  (os.getenv("PIPERTTS_PATH",  ".pipertts"),  ["*.onnx"]),
    "silerotts": (os.getenv("SILEROTTS_PATH", ".silerotts"), ["**/*.pt", "**/*.jit"]),
    "coquitts":  (os.getenv("COQUITTS_PATH",  ".coquitts"),  ["tts/*"]),
    "barktts":   (os.getenv("BARKTTS_PATH",   ".barktts"),   ["**/*.pt"]),
}

ENGINE_NOTES = {
    "gtts":    "cloud — no local models",
    "pyttsx3": "uses system espeak voices",
}


def list_engines_and_models() -> None:
    """Print all engines, their availability, and installed model files."""
    from engines import is_engine_available
    engines_dir = Path(__file__).resolve().parent / "engines"
    engine_names = sorted(p.stem for p in engines_dir.glob("*.py") if p.name != "__init__.py")

    # Silence engine-loader probe warnings — we already report unavailable status below.
    engines_logger = logging.getLogger("engines")
    prev_level = engines_logger.level
    engines_logger.setLevel(logging.ERROR)

    print("Engines:")
    for name in engine_names:
        available = is_engine_available(name)
        marker = "✓" if available else "✗"
        status = "available" if available else "unavailable (deps missing)"
        print(f"  {marker} {name:<10} {status}")

        if name in ENGINE_NOTES:
            print(f"      ({ENGINE_NOTES[name]})")
            continue

        if name in ENGINE_MODEL_SOURCES:
            model_dir, patterns = ENGINE_MODEL_SOURCES[name]
            d = Path(model_dir)
            if not d.exists():
                print(f"      (model dir {d}/ not found — run `tts --install {name}`)")
                continue
            files: list[Path] = []
            for pat in patterns:
                files.extend(sorted(d.glob(pat)))
            if not files:
                print(f"      (no models in {d}/)")
            else:
                for f in files:
                    rel = f.relative_to(d) if f.is_relative_to(d) else f
                    print(f"      {d}/{rel}")

    engines_logger.setLevel(prev_level)


def main() -> int:
    parser = parse_arguments()
    args = parser.parse_args()

    if getattr(args, "list", False):
        list_engines_and_models()
        return 0

    if getattr(args, "install", None):
        from install import run as run_installer
        return run_installer(args.install, non_interactive=args.non_interactive)

    try:
        setup_logging(args.verbose, args.quiet)
        config = get_config()
        text = get_text(args)
        engine = args.engine or config["engine"]
        language = args.language or config["language"]

        # Determine output formats
        output_formats: List[str] = []
        if args.output:
            for fmt in [f.strip() for f in args.output.split(",")]:
                if fmt not in ["play", "file", "stdout"]:
                    raise ValidationError(
                        f"Invalid output format: {fmt}. Valid: play, file, stdout"
                    )
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
        if not output_formats:
            output_formats = ["play"]

        # Determine output filename if saving to file
        output_filename: Optional[str] = None
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

        # Print summary
        if not args.quiet and "stdout" not in output_formats:
            print("TTS CLI Tool", file=sys.stderr)
            print("=" * 40, file=sys.stderr)
            preview = text[:50] + ("..." if len(text) > 50 else "")
            print(f"Text: {preview}", file=sys.stderr)
            print(f"Engine: {engine}", file=sys.stderr)
            print(f"Language: {language}", file=sys.stderr)
            print(f"Formats: {', '.join(output_formats)}", file=sys.stderr)
            if output_filename:
                print(f"Output file: {output_filename}", file=sys.stderr)
            print(file=sys.stderr)

        """
         SINGLE-CHUNK MODE
         Generate TTS audio (engines return bytes)
        from libs.api import text_to_speech_bytes
        audio_bytes = text_to_speech_bytes(text=text, engine=engine, language=language)

        # Process based on output formats (file first, then play, then stdout)
        for output_format in [f for f in ['file', 'play', 'stdout'] if f in output_formats]:
            if output_format == 'file' and output_filename:
                with open(output_filename, 'wb') as f:
                    f.write(audio_bytes)
                if 'stdout' not in output_formats:
                    print(output_filename, file=sys.stdout)
                else:
                    print(output_filename, file=sys.stderr)
            elif output_format == 'play':
                if not args.quiet and 'stdout' not in output_formats:
                    logger.info("Playing audio...")
                play_audio(audio_bytes)
                if not args.quiet and 'stdout' not in output_formats:
                    logger.info("Playback completed")
            elif output_format == 'stdout':
                sys.stdout.buffer.write(audio_bytes)
                sys.stdout.buffer.flush()
        return 0
        """

        # CHUNKED MODE
        MAX_LEN = 200
        chunks = chunk_text(text, MAX_LEN)
        if not args.quiet and "stdout" not in output_formats:
            print(f"Chunks: {len(chunks)} (<= {MAX_LEN} chars each)", file=sys.stderr)

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

        q: "queue.Queue[QUEUE_ITEM]" = queue.Queue(maxsize=2)
        collected_paths: List[str] = []

        rec = threading.Thread(
            target=rec_worker,
            args=(chunks, engine, language, q, tmp_suffix, tmp_dir),
            daemon=True,
        )
        play = threading.Thread(
            target=play_worker,
            args=(q, output_formats, collected_paths, play_audio),
            daemon=True,
        )
        rec.start()
        play.start()
        rec.join()
        play.join()

        saved_files: List[str] = []

        if out_is_file:
            if output_filename and not os.path.isdir(output_filename):
                base, ext2 = os.path.splitext(output_filename)
                if not ext2:
                    ext2 = f".{ext}"
                for i, p in enumerate(collected_paths, start=1):
                    dst = f"{base}_{i:03d}{ext2}"
                    try:
                        shutil.copy2(p, dst)  # copy temp file to destination
                        safe_unlink(p)         # delete original temp file (Windows-safe)
                        saved_files.append(dst)
                    except Exception as e:
                        logger.error(f"Failed to save chunk {i} to {dst}: {e}")

            else:
                out_dir = (
                    output_filename
                    if (output_filename and os.path.isdir(output_filename))
                    else (args.audio_dir or config["audio_directory"])
                )
                ensure_audio_directory(out_dir)
                for i, p in enumerate(collected_paths, start=1):
                    fname = generate_timestamp_filename(f"part_{i:03d}_", ext)
                    dst = os.path.join(out_dir, fname)
                    try:
                        shutil.copy2(p, dst)
                        safe_unlink(p)
                        saved_files.append(dst)
                    except Exception as e:
                        logger.error(f"Failed to save chunk {i} to {dst}: {e}")


            if "stdout" not in output_formats:
                for fpath in saved_files:
                    print(fpath, file=sys.stdout)
            else:
                for fpath in saved_files:
                    print(fpath, file=sys.stderr)
        else:
            pass

        # STDOUT
        if out_is_stdout:
            if engine == "gtts":
                # MP3 - don't glue them together without recoding -
                # write them sequentially
                print(
                    """WARNING: multiple MP3 chunks written sequentially
                    to stdout; this is not a single valid MP3 file.""",
                    file=sys.stderr,
                )
                src_list = saved_files if saved_files else collected_paths
                for p in src_list:
                    with open(p, "rb") as f:
                        sys.stdout.buffer.write(f.read())
                sys.stdout.buffer.flush()
            else:
                src_list = saved_files if saved_files else collected_paths
                stdout_buf = io.BytesIO()
                concat_wav_files(src_list, stdout_buf)
                sys.stdout.buffer.write(stdout_buf.getvalue())
                sys.stdout.buffer.flush()

        if not out_is_file:
            for p in collected_paths:
                safe_unlink(p)

        return 0

    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        return 1
    except EngineNotAvailableError as e:
        logger.error(f"Engine not available: {e}")
        return 1
    except TTSException as e:
        logger.error(f"TTS error: {e}")
        return 1
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
