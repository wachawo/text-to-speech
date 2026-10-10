#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared CLI helpers: chunking, output resolution, chunk concat, producer/consumer pipeline.

Used by both `ttsgen` (offline, calls `libs.api.text_to_speech_bytes`) and `ttsapi`
(remote, calls HTTP endpoint). The producer is injected as a callable so the same
pipeline supports both backends.
"""

import contextlib
import io
import logging
import os
import queue
import re
import shutil
import tempfile
import threading
import traceback
import wave
from collections.abc import Callable
from typing import IO, NamedTuple

# Local imports
from .audio import extension_for, is_wav
from .exceptions import ValidationError
from .tempfiles import safe_unlink
from .tools import claim_timestamp_path, ensure_audio_directory

logger = logging.getLogger(__name__)

# Scratch files hold one chunk each; the container is sniffed, never read off the name.
CHUNK_SUFFIX = ".part"

# Long input is split into chunks so playback can start before synthesis finishes.
DEFAULT_CHUNK_CHARS = 200

# Bounded queue between producer and consumer threads, provides backpressure.
PIPELINE_QUEUE_SIZE = 2

VALID_OUTPUT_FORMATS = ("play", "file", "stdout")

# Split at the whitespace after sentence-ish punctuation, or at a line break, so
# each fragment keeps its own terminator. Punctuation inside a token ("3.50",
# "1,000", "example.com") is not a boundary.
SPLIT_REGEX = re.compile(r"(?<=[.!?,])\s+|\s*\n\s*")

# Producer: (text) -> audio bytes. Engine/language are bound at call site.
GeneratorFn = Callable[[str], bytes]


class ChunkResult(NamedTuple):
    """One queue item produced by rec_worker.

    On success: tmp_path points to a temp file holding audio_bytes, error is None.
    On failure: tmp_path is None, audio_bytes is b"", error holds the exception.
    """

    idx: int
    tmp_path: str | None
    audio_bytes: bytes
    error: BaseException | None


# `None` is the sentinel pushed by rec_worker after the last chunk to signal
# play_worker to exit. Any non-None item is a ChunkResult.
QueueItem = ChunkResult | None

# The chunk that stopped the pipeline: (chunk index, exception).
ChunkFailure = tuple[int, BaseException]


def read_text_file(path: str) -> str:
    """Read and strip the text to synthesize from `path`.

    Raises:
        ValidationError: The path is missing, is not a file, cannot be read or
            decoded, or holds only whitespace.
    """
    path = os.path.normpath(path)
    if not os.path.exists(path):
        raise ValidationError(f"File not found: {path}")
    if not os.path.isfile(path):
        raise ValidationError(f"Path is not a file: {path}")
    try:
        with open(path, encoding="utf-8") as handle:
            content = handle.read().strip()
    except UnicodeDecodeError as exc:
        raise ValidationError(f"File encoding error in {path}: {exc}") from exc
    except OSError as exc:
        raise ValidationError(f"Could not read file {path}: {exc}") from exc
    if not content:
        raise ValidationError(f"File is empty: {path}")
    return content


def resolve_output_formats(output: str | None, file_arg: str | None, play: bool, stdout: bool) -> list[str]:
    """Combine --output, --file, --play and --stdout into ordered output modes.

    --stdout disables --file unless --output names both explicitly.

    Returns:
        Deduplicated output modes; defaults to ["play"] when nothing is requested.

    Raises:
        ValidationError: If --output names a mode other than play, file or stdout.
    """
    output_formats: list[str] = []
    if output:
        for fmt in [f.strip() for f in output.split(",")]:
            if fmt not in VALID_OUTPUT_FORMATS:
                raise ValidationError(f"Invalid output format: {fmt}. Valid: play, file, stdout")
            if fmt not in output_formats:
                output_formats.append(fmt)
    if file_arg is not None and "file" not in output_formats:
        output_formats.append("file")
    if play and "play" not in output_formats:
        output_formats.append("play")
    if stdout and "stdout" not in output_formats:
        output_formats.append("stdout")
    if stdout and file_arg is not None and not output:
        output_formats = [f for f in output_formats if f != "file"]
    return output_formats or ["play"]


def slice_long_fragment(fragment: str, max_len: int) -> list[str]:
    """Cut a single-spaced fragment into pieces of <= max_len chars at spaces; a word longer than max_len is cut."""
    pieces: list[str] = []
    rest = fragment
    while len(rest) > max_len:
        cut = rest.rfind(" ", 0, max_len + 1)
        if cut <= 0:
            cut = max_len
        pieces.append(rest[:cut].rstrip())
        rest = rest[cut:].lstrip()
    if rest:
        pieces.append(rest)
    return pieces


def chunk_text(text: str, max_len: int = 5000) -> list[str]:
    """Split text at sentence-ish boundaries and regroup it into chunks of <= max_len chars.

    Fragments are packed greedily so each chunk is as full as possible. A single
    fragment longer than max_len is cut at its last space that fits, and only a
    word longer than max_len is cut inside the word.

    Args:
        text: Source text of any length.
        max_len: Maximum characters per returned chunk.

    Returns:
        Non-empty chunks in source order; an empty list for blank input.
    """
    parts = [" ".join(p.split()) for p in SPLIT_REGEX.split(text) if p and p.strip()]
    chunks: list[str] = []
    buf: list[str] = []
    cur_len = 0
    for p in parts:
        if len(p) > max_len:
            if cur_len:
                chunks.append(" ".join(buf))
                buf, cur_len = [], 0
            chunks.extend(slice_long_fragment(p, max_len))
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


def is_directory_target(path: str) -> bool:
    """Report whether a --file value names a directory: a trailing separator or an existing directory."""
    separators = (os.sep, os.altsep) if os.altsep else (os.sep,)
    return path.endswith(separators) or os.path.isdir(path)


def resolve_output_target(file_arg: str | None, audio_dir: str) -> tuple[str, bool]:
    """Turn the --file value into (path, is_directory), creating the directory part.

    Args:
        file_arg: The --file value: None (file mode via --output), "" (bare --file),
            a directory (trailing separator or existing) or an exact file name.
        audio_dir: Directory for auto-named files when file_arg names none.

    Returns:
        (directory, True) when the file name is generated after synthesis from the
        audio header, (file name, False) when the caller asked for an exact name.
    """
    if not file_arg:
        return ensure_audio_directory(audio_dir), True
    if is_directory_target(file_arg):
        return ensure_audio_directory(file_arg), True
    parent_dir = os.path.dirname(file_arg)
    if parent_dir:
        ensure_audio_directory(parent_dir)
    return file_arg, False


def output_path_for(target: str, is_directory: bool, prefix: str, extension: str) -> str:
    """Return the exact file name: the target itself, or a new timestamped file inside it.

    An exact name is the caller's choice and is overwritten; an auto-generated
    name is claimed with an exclusive create and never replaces an existing file.
    """
    if not is_directory:
        return target
    return claim_timestamp_path(target, prefix, extension)


def scratch_dir(target: str | None, is_directory: bool) -> str | None:
    """Return the directory for the chunk temp files: next to the output, or None for the system temp dir."""
    if target is None:
        return None
    if is_directory:
        return target
    return os.path.dirname(target) or "."


def read_header(path: str, size: int = 12) -> bytes:
    """Return the first `size` bytes of a file, enough for the container sniffers."""
    with open(path, "rb") as handle:
        return handle.read(size)


def write_audio(chunk_paths: list[str], out_stream: IO[bytes]) -> None:
    """Write the chunks as one audio stream: WAV through the wave module, anything else byte-wise.

    MP3 frames concatenate as they are (the server's streaming path does the
    same and players accept it), so only WAV needs its headers merged.

    Args:
        chunk_paths: Chunk files in playback order; an empty list is a no-op.
        out_stream: Writable binary stream receiving the combined audio.
    """
    if not chunk_paths:
        return
    if len(chunk_paths) > 1 and is_wav(read_header(chunk_paths[0])):
        if out_stream.seekable():
            concat_wav_files(chunk_paths, out_stream)
            return
        # The wave module seeks back to patch the header sizes, which a pipe
        # (`ttsgen --stdout | ttsplay`) cannot do, so the WAV is built in memory.
        buffer = io.BytesIO()
        concat_wav_files(chunk_paths, buffer)
        out_stream.write(buffer.getvalue())
        return
    for path in chunk_paths:
        with open(path, "rb") as handle:
            shutil.copyfileobj(handle, out_stream)


def save_audio_file(chunk_paths: list[str], destination: str) -> None:
    """Write the chunks into `destination` as one file.

    The file is created with a plain open(), so its mode follows the umask
    instead of the 0600 the temp chunks were created with.
    """
    with open(destination, "wb") as out_stream:
        write_audio(chunk_paths, out_stream)


def chunk_extension(chunk_paths: list[str]) -> str:
    """Return the file extension matching the container of the first chunk."""
    return extension_for(read_header(chunk_paths[0]))


def concat_wav_files(in_paths: list[str], out_stream: IO[bytes]) -> None:
    """Append several WAV files into one WAV written to out_stream.

    Output format is taken from the first input. Inputs whose channel count,
    sample width or frame rate differ are appended anyway and logged as a
    warning: the result may be malformed, but no chunk is silently dropped.

    Args:
        in_paths: WAV file paths in playback order; an empty list is a no-op.
        out_stream: Writable binary stream receiving the combined WAV.
    """
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
                elif (
                    win.getnchannels() != wout.getnchannels()
                    or win.getsampwidth() != wout.getsampwidth()
                    or win.getframerate() != wout.getframerate()
                ):
                    logger.warning(f"WAV params mismatch in {p}; naive append (may be invalid).")
                frames = win.readframes(win.getnframes())
                wout.writeframes(frames)
            finally:
                win.close()
    except BaseException:
        # Closing a writer that never got its format raises "# channels not
        # specified", which would replace the error that actually happened.
        with contextlib.suppress(wave.Error):
            wout.close()
        raise
    wout.close()


def rec_worker(
    text_chunks: list[str],
    generator: GeneratorFn,
    q: "queue.Queue[QueueItem]",
    tmp_suffix: str,
    tmp_dir: str | None = None,
    stop: threading.Event | None = None,
    created_paths: list[str] | None = None,
    lock: "threading.Lock | None" = None,
) -> None:
    """Generate audio for each chunk and push a ChunkResult onto the queue.

    Runs as the producer thread of the CLI pipeline. The first chunk that fails
    is forwarded as a ChunkResult with `error` set and ends the run: an error
    such as a bad language or an unreachable server is the same for every chunk,
    so the remaining chunks are not attempted. A final `None` sentinel is always
    pushed.

    Args:
        text_chunks: Chunks to synthesize, in playback order.
        generator: Callable turning one chunk of text into audio bytes.
        q: Bounded queue shared with play_worker; provides backpressure.
        tmp_suffix: Extension for the per-chunk temp files.
        tmp_dir: Directory for temp files; None uses the system temp dir.
        stop: Set by the caller to end the run early; no chunk is synthesized
            or written after it is set.
        created_paths: Receives every temp file this worker creates, so the
            caller can remove them all, queued or not.
        lock: Held while a temp file is created and written; the caller sets
            `stop` under it, so no file appears after the caller's cleanup.
    """
    stop = stop or threading.Event()
    lock = lock or threading.Lock()
    try:
        for i, chunk in enumerate(text_chunks, start=1):
            if stop.is_set():
                break
            try:
                audio_bytes = generator(chunk)
            except Exception as exc:
                # The caller logs the failure once; the traceback is kept for -v.
                logger.debug(f"TTS error on chunk {i}: {type(exc).__name__}: {exc}\n{traceback.format_exc()}")
                q.put(ChunkResult(idx=i, tmp_path=None, audio_bytes=b"", error=exc))
                break

            with lock:
                if stop.is_set():
                    break
                fd, tmp_path = tempfile.mkstemp(suffix=tmp_suffix, dir=tmp_dir)
                if created_paths is not None:
                    created_paths.append(tmp_path)
                try:
                    # Written through the descriptor, never reopened by name, so a
                    # file removed by the caller's cleanup cannot be recreated.
                    with os.fdopen(fd, "wb") as handle:
                        handle.write(audio_bytes)
                except Exception as exc:
                    logger.debug(f"Failed to write temp audio for chunk {i}: {type(exc).__name__}: {exc}")
                    safe_unlink(tmp_path)
                    q.put(ChunkResult(idx=i, tmp_path=None, audio_bytes=audio_bytes, error=exc))
                    break

            q.put(ChunkResult(idx=i, tmp_path=tmp_path, audio_bytes=audio_bytes, error=None))
    finally:
        # Always emit the done sentinel so play_worker exits even on iterator/
        # exhaustion errors above.
        q.put(None)


def play_worker(
    q: "queue.Queue[QueueItem]",
    modes: list[str],
    collected_paths: list[str],
    play_func: Callable[[bytes], None],
    failures: list[ChunkFailure] | None = None,
    stop: threading.Event | None = None,
) -> None:
    """Consume queue items until the sentinel, playing and collecting each chunk.

    Runs as the consumer thread of the CLI pipeline. Failed chunks
    (ChunkResult.error not None) are appended to `failures` when provided,
    never to `collected_paths`, and are not played. A playback error on one
    chunk is logged and the remaining chunks still play. Once `stop` is set the
    queue is still drained, so the producer never blocks, but nothing is played.

    Args:
        q: Queue fed by rec_worker; a `None` item ends the loop.
        modes: Active output modes; audio is played only if "play" is present.
        collected_paths: Populated in order with the temp paths of good chunks.
        play_func: Callable that plays one chunk of audio bytes.
        failures: Optional sink for (chunk index, exception) pairs.
        stop: Optional event that ends playback early.
    """
    while True:
        item = q.get()
        if item is None:
            break
        if item.error is not None:
            if failures is not None:
                failures.append((item.idx, item.error))
            continue
        if item.tmp_path is not None:
            collected_paths.append(item.tmp_path)
        if "play" in modes and not (stop is not None and stop.is_set()):
            try:
                play_func(item.audio_bytes)
            except Exception as exc:
                logger.error(f"Playback error on chunk {item.idx}: {type(exc).__name__}: {exc}")


def run_pipeline(
    text_chunks: list[str],
    generator: GeneratorFn,
    modes: list[str],
    play_func: Callable[[bytes], None],
    tmp_dir: str | None,
    created_paths: list[str],
) -> tuple[list[str], ChunkFailure | None]:
    """Synthesize the chunks on a producer thread while a consumer plays them.

    The run stops at the first failed chunk. On any exit, Ctrl+C included, every
    temp file the run created is listed in `created_paths`, which the caller
    removes with safe_unlink() in its own `finally`, after saving the output.

    Args:
        text_chunks: Chunks to synthesize, in playback order.
        generator: Callable turning one chunk of text into audio bytes.
        modes: Active output modes; chunks are played only if "play" is present.
        play_func: Callable that plays one chunk of audio bytes.
        tmp_dir: Directory for the chunk temp files; None uses the system temp dir.
        created_paths: Receives every temp file the run creates.

    Returns:
        The temp paths of the good chunks in playback order, and the failed
        chunk, or None when every chunk succeeded.
    """
    audio_queue: queue.Queue[QueueItem] = queue.Queue(maxsize=PIPELINE_QUEUE_SIZE)
    stop = threading.Event()
    lock = threading.Lock()
    collected_paths: list[str] = []
    failures: list[ChunkFailure] = []
    rec_thread = threading.Thread(
        target=rec_worker,
        args=(text_chunks, generator, audio_queue, CHUNK_SUFFIX, tmp_dir, stop, created_paths, lock),
        daemon=True,
    )
    play_thread = threading.Thread(
        target=play_worker,
        args=(audio_queue, modes, collected_paths, play_func, failures, stop),
        daemon=True,
    )
    try:
        rec_thread.start()
        play_thread.start()
        rec_thread.join()
        play_thread.join()
    except BaseException:
        # Ctrl+C: stop the producer before the caller removes the files, so no
        # chunk file appears after that cleanup and nothing more is played.
        with lock:
            stop.set()
        raise
    return collected_paths, (failures[0] if failures else None)


def main():
    """Module entrypoint placeholder, this file is import-only."""
    pass


if __name__ == "__main__":
    main()
