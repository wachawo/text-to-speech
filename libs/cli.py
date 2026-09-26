#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared CLI helpers: chunking, output resolution, chunk concat, producer/consumer pipeline.

Used by both `ttsgen` (offline, calls `libs.api.text_to_speech_bytes`) and `ttsapi`
(remote, calls HTTP endpoint). The producer is injected as a callable so the same
pipeline supports both backends.
"""

import io
import logging
import os
import queue
import re
import shutil
import tempfile
import traceback
import wave
from collections.abc import Callable
from typing import IO, NamedTuple

# Local imports
from .audio import extension_for, is_wav
from .tempfiles import safe_unlink
from .tools import ensure_audio_directory, generate_timestamp_filename

logger = logging.getLogger(__name__)

# Scratch files hold one chunk each; the container is sniffed, never read off the name.
CHUNK_SUFFIX = ".part"

# Zero-width split after sentence-ish punctuation, so each fragment keeps its own
# terminator and can be regrouped into chunks without re-parsing.
SPLIT_REGEX = re.compile(r"(?<=[.!?]|,|\n)")

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


def chunk_text(text: str, max_len: int = 5000) -> list[str]:
    """Split text at sentence-ish boundaries and regroup it into chunks of <= max_len chars.

    Fragments are packed greedily so each chunk is as full as possible. A single
    fragment longer than max_len is hard-sliced at max_len.

    Args:
        text: Source text of any length.
        max_len: Maximum characters per returned chunk.

    Returns:
        Non-empty chunks in source order; an empty list for blank input.
    """
    parts = [p.strip() for p in SPLIT_REGEX.split(text) if p and p.strip()]
    chunks: list[str] = []
    buf: list[str] = []
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
    """Return the exact file name: the target itself, or a timestamped name inside it."""
    if not is_directory:
        return target
    return os.path.join(target, generate_timestamp_filename(prefix, extension))


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
    finally:
        wout.close()


def rec_worker(
    text_chunks: list[str],
    generator: GeneratorFn,
    q: "queue.Queue[QueueItem]",
    tmp_suffix: str,
    tmp_dir: str | None = None,
) -> None:
    """Generate audio for each chunk and push a ChunkResult onto the queue.

    Runs as the producer thread of the CLI pipeline. On generator failure the
    chunk is forwarded as a ChunkResult with `error` set instead of being
    silently replaced by empty bytes; play_worker collects those failures so
    the CLI can exit non-zero. Exactly one ChunkResult per chunk plus a final
    `None` sentinel is pushed — including on partial failure.

    Args:
        text_chunks: Chunks to synthesize, in playback order.
        generator: Callable turning one chunk of text into audio bytes.
        q: Bounded queue shared with play_worker; provides backpressure.
        tmp_suffix: Extension for the per-chunk temp files (".wav" / ".mp3").
        tmp_dir: Directory for temp files; None uses the system temp dir.
    """
    try:
        for i, chunk in enumerate(text_chunks, start=1):
            try:
                audio_bytes = generator(chunk)
            except Exception as exc:
                logger.error(f"TTS error on chunk {i}: {type(exc).__name__}: {exc}\n{traceback.format_exc()}")
                q.put(ChunkResult(idx=i, tmp_path=None, audio_bytes=b"", error=exc))
                continue

            fd, tmp_path = tempfile.mkstemp(suffix=tmp_suffix, dir=tmp_dir)
            os.close(fd)
            try:
                with open(tmp_path, "wb") as f:
                    f.write(audio_bytes)
            except Exception as exc:
                logger.error(f"Failed to write temp audio for chunk {i}: {type(exc).__name__}: {exc}")
                safe_unlink(tmp_path)
                q.put(ChunkResult(idx=i, tmp_path=None, audio_bytes=audio_bytes, error=exc))
                continue

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
    failures: list[tuple[int, BaseException]] | None = None,
) -> None:
    """Consume queue items until the sentinel, playing and collecting each chunk.

    Runs as the consumer thread of the CLI pipeline. Failed chunks
    (ChunkResult.error not None) are appended to `failures` when provided,
    never to `collected_paths`, and are not played. A playback error on one
    chunk is logged and the remaining chunks still play.

    Args:
        q: Queue fed by rec_worker; a `None` item ends the loop.
        modes: Active output modes; audio is played only if "play" is present.
        collected_paths: Populated in order with the temp paths of good chunks.
        play_func: Callable that plays one chunk of audio bytes.
        failures: Optional sink for (chunk index, exception) pairs.
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
        if "play" in modes:
            try:
                play_func(item.audio_bytes)
            except Exception as exc:
                logger.error(f"Playback error on chunk {item.idx}: {type(exc).__name__}: {exc}")


def main():
    """Module entrypoint placeholder, this file is import-only."""
    pass


if __name__ == "__main__":
    main()
