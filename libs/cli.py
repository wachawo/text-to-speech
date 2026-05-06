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
from typing import Callable, IO, List, Optional, Tuple

logger = logging.getLogger(__name__)

SPLIT_REGEX = re.compile(r"(?<=[.!?]|,|\n)")

# Producer: (text) -> audio bytes. Engine/language are bound at call site.
GeneratorFn = Callable[[str], bytes]
QueueItem = Optional[Tuple[int, str, bytes]]


def chunk_text(text: str, max_len: int = 5000) -> List[str]:
    """Split text by sentence-ish boundaries to chunks ≤ max_len chars."""
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
                chunks.append(p[i:i + max_len])
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
                    win.getnchannels()  != wout.getnchannels()
                    or win.getsampwidth() != wout.getsampwidth()
                    or win.getframerate() != wout.getframerate()
                ):
                    logger.warning(
                        f"WAV params mismatch in {p}; naive append (may be invalid)."
                    )
                frames = win.readframes(win.getnframes())
                wout.writeframes(frames)
            finally:
                win.close()
    finally:
        wout.close()


def rec_worker(
    text_chunks: List[str],
    generator: GeneratorFn,
    q: "queue.Queue[QueueItem]",
    tmp_suffix: str,
    tmp_dir: Optional[str] = None,
) -> None:
    """Generate audio for each chunk via `generator(text)` and push (idx, tmp_path, bytes) onto queue."""
    for i, chunk in enumerate(text_chunks, start=1):
        try:
            audio_bytes = generator(chunk)
        except Exception as exc:
            import traceback
            logger.error(f"TTS error on chunk {i}: {type(exc).__name__}: {exc}\n{traceback.format_exc()}")
            audio_bytes = b""
        fd, tmp_path = tempfile.mkstemp(suffix=tmp_suffix, dir=tmp_dir)
        os.close(fd)
        try:
            with open(tmp_path, "wb") as f:
                f.write(audio_bytes)
        except Exception as exc:
            logger.error(f"Failed to write temp audio for chunk {i}: {type(exc).__name__}: {exc}")
        q.put((i, tmp_path, audio_bytes))
    q.put(None)


def play_worker(
    q: "queue.Queue[QueueItem]",
    modes: List[str],
    collected_paths: List[str],
    play_func: Callable[[bytes], None],
) -> None:
    """Consume queue items; play audio if 'play' in modes; collect tmp paths in order."""
    while True:
        item = q.get()
        if item is None:
            break
        idx, tmp_path, audio_bytes = item
        collected_paths.append(tmp_path)
        if "play" in modes:
            try:
                play_func(audio_bytes)
            except Exception as exc:
                logger.error(f"Playback error on chunk {idx}: {type(exc).__name__}: {exc}")


def main():
    pass


if __name__ == "__main__":
    main()
