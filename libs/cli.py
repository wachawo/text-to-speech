#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared CLI helpers — chunking, WAV concat, producer/consumer pipeline.

Used by both `ttsgen` (offline, calls `libs.api.text_to_speech_bytes`) and `ttsapi`
(remote, calls HTTP endpoint). The producer is injected as a callable so the same
pipeline supports both backends.
"""

import logging
import os
import queue
import re
import tempfile
import wave
from collections.abc import Callable
from typing import IO, NamedTuple

logger = logging.getLogger(__name__)

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
    """Split text by sentence-ish boundaries to chunks ≤ max_len chars."""
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


def concat_wav_files(in_paths: list[str], out_stream: IO[bytes]) -> None:
    """Concat WAV files (same params expected) into one stream."""
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

    On generator failure, the chunk is forwarded as a ChunkResult with
    `error` set instead of being silently replaced by empty bytes. The caller
    (play_worker) is responsible for collecting failures so the CLI can exit
    non-zero. Each call is guaranteed to push exactly one ChunkResult per
    chunk plus a final `None` sentinel — including on partial failure.
    """
    try:
        for i, chunk in enumerate(text_chunks, start=1):
            try:
                audio_bytes = generator(chunk)
            except Exception as exc:
                import traceback

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
    """Consume queue items; play audio if 'play' in modes; collect tmp paths in order.

    Failed chunks (ChunkResult.error not None) are appended to `failures`
    when provided, never to `collected_paths`, and are not played.
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
    pass


if __name__ == "__main__":
    main()
