#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for libs/cli — pipeline helpers shared by ttsgen and ttsapi.

Covers:
- chunk_text: empty, ≤ max, > max, no punctuation, very long single token.
- concat_wav_files: empty list, single file, two-file concat, mismatched params.
- rec_worker / play_worker: success path, partial failure (sentinel propagation),
  done-sentinel always emitted, failures list capture.
"""

import io
import queue
import threading
import wave
from pathlib import Path

from libs.cli import ChunkResult, chunk_text, concat_wav_files, play_worker, rec_worker

# chunk_text


def test_chunk_text_empty():
    assert chunk_text("") == []


def test_chunk_text_short_returns_single_chunk():
    chunks = chunk_text("Hello, world!", max_len=200)
    assert len(chunks) == 1
    assert "Hello" in chunks[0]


def test_chunk_text_splits_on_sentence_boundaries():
    text = "First sentence. Second sentence. Third sentence."
    chunks = chunk_text(text, max_len=20)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c) <= 20


def test_chunk_text_handles_token_longer_than_max():
    """A single word longer than max_len is hard-split, not dropped."""
    long_word = "x" * 1000
    chunks = chunk_text(long_word, max_len=200)
    assert len(chunks) == 5
    assert "".join(chunks) == long_word


def test_chunk_text_no_punctuation():
    text = "word " * 50  # 250 chars, no sentence boundary
    chunks = chunk_text(text, max_len=50)
    for c in chunks:
        assert len(c) <= 50


# concat_wav_files


def _silent_wav(path: Path, ms: int = 50, rate: int = 22050) -> None:
    nframes = int(rate * ms / 1000)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * nframes)


def test_concat_wav_files_empty(tmp_path):
    out = io.BytesIO()
    concat_wav_files([], out)
    assert out.getvalue() == b""


def test_concat_wav_files_single(tmp_path):
    f = tmp_path / "a.wav"
    _silent_wav(f, ms=100, rate=22050)
    out_path = tmp_path / "out.wav"
    with open(out_path, "wb") as out:
        concat_wav_files([str(f)], out)
    with wave.open(str(out_path), "rb") as r:
        assert r.getnframes() == 22050 // 10  # 100 ms at 22050 Hz


def test_concat_wav_files_two_same_params(tmp_path):
    a, b = tmp_path / "a.wav", tmp_path / "b.wav"
    _silent_wav(a, ms=100, rate=22050)
    _silent_wav(b, ms=200, rate=22050)
    out_path = tmp_path / "out.wav"
    with open(out_path, "wb") as out:
        concat_wav_files([str(a), str(b)], out)
    with wave.open(str(out_path), "rb") as r:
        # 100 ms + 200 ms = 300 ms at 22050 Hz
        assert r.getnframes() == int(22050 * 0.3)


def test_concat_wav_files_param_mismatch_warns(tmp_path, caplog):
    a, b = tmp_path / "a.wav", tmp_path / "b.wav"
    _silent_wav(a, ms=50, rate=22050)
    _silent_wav(b, ms=50, rate=16000)  # different rate
    out_path = tmp_path / "out.wav"
    with caplog.at_level("WARNING"):
        with open(out_path, "wb") as out:
            concat_wav_files([str(a), str(b)], out)
    assert any("WAV params mismatch" in r.message for r in caplog.records)


# rec_worker / play_worker


def _silent_bytes() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"\x00\x00" * 100)
    return buf.getvalue()


def test_rec_play_worker_success_path(tmp_path):
    chunks = ["one", "two", "three"]
    audio = _silent_bytes()
    q: queue.Queue = queue.Queue(maxsize=2)
    collected: list[str] = []
    failures: list = []

    def gen(text: str) -> bytes:
        return audio

    rec = threading.Thread(target=rec_worker, args=(chunks, gen, q, ".wav", str(tmp_path)), daemon=True)
    play = threading.Thread(target=play_worker, args=(q, [], collected, lambda b: None, failures), daemon=True)
    rec.start()
    play.start()
    rec.join(timeout=5)
    play.join(timeout=5)

    assert len(collected) == 3
    assert failures == []
    for p in collected:
        assert Path(p).exists()
        assert Path(p).read_bytes() == audio


def test_rec_worker_pushes_sentinel_on_partial_failure(tmp_path):
    chunks = ["ok1", "boom", "ok2"]
    q: queue.Queue = queue.Queue(maxsize=2)
    collected: list[str] = []
    failures: list = []

    def gen(text: str) -> bytes:
        if text == "boom":
            raise RuntimeError("synthetic engine error")
        return _silent_bytes()

    rec = threading.Thread(target=rec_worker, args=(chunks, gen, q, ".wav", str(tmp_path)), daemon=True)
    play = threading.Thread(target=play_worker, args=(q, [], collected, lambda b: None, failures), daemon=True)
    rec.start()
    play.start()
    rec.join(timeout=5)
    play.join(timeout=5)

    assert len(collected) == 2  # ok1 and ok2
    assert len(failures) == 1
    idx, err = failures[0]
    assert idx == 2
    assert isinstance(err, RuntimeError)
    assert "synthetic engine error" in str(err)


def test_rec_worker_emits_done_sentinel_even_on_total_failure(tmp_path):
    """Every chunk fails — play_worker must still see the None sentinel and exit."""
    chunks = ["a", "b"]
    q: queue.Queue = queue.Queue(maxsize=2)
    collected: list[str] = []
    failures: list = []

    def gen(text: str) -> bytes:
        raise RuntimeError("always boom")

    rec = threading.Thread(target=rec_worker, args=(chunks, gen, q, ".wav", str(tmp_path)), daemon=True)
    play = threading.Thread(target=play_worker, args=(q, [], collected, lambda b: None, failures), daemon=True)
    rec.start()
    play.start()
    rec.join(timeout=5)
    play.join(timeout=5)

    assert play.is_alive() is False  # done sentinel reached
    assert collected == []
    assert len(failures) == 2


def test_play_worker_invokes_play_func_on_play_mode(tmp_path):
    played: list[bytes] = []
    q: queue.Queue = queue.Queue()
    q.put(ChunkResult(idx=1, tmp_path=str(tmp_path / "a.wav"), audio_bytes=b"abc", error=None))
    q.put(None)
    play_worker(q, ["play"], [], played.append)
    assert played == [b"abc"]


def test_play_worker_skips_play_for_failed_chunk(tmp_path):
    played: list[bytes] = []
    q: queue.Queue = queue.Queue()
    q.put(ChunkResult(idx=1, tmp_path=None, audio_bytes=b"", error=RuntimeError("x")))
    q.put(None)
    failures: list = []
    play_worker(q, ["play"], [], played.append, failures)
    assert played == []
    assert len(failures) == 1


def test_play_worker_swallows_play_errors(tmp_path, caplog):
    """Playback errors are logged but do not stop the queue drain."""
    q: queue.Queue = queue.Queue()
    q.put(ChunkResult(idx=1, tmp_path=str(tmp_path / "a.wav"), audio_bytes=b"x", error=None))
    q.put(ChunkResult(idx=2, tmp_path=str(tmp_path / "b.wav"), audio_bytes=b"y", error=None))
    q.put(None)

    calls: list = []

    def boom_then_ok(b: bytes) -> None:
        calls.append(b)
        if len(calls) == 1:
            raise OSError("audio device gone")

    with caplog.at_level("ERROR"):
        play_worker(q, ["play"], [], boom_then_ok)
    assert calls == [b"x", b"y"]
    assert any("Playback error" in r.message for r in caplog.records)
