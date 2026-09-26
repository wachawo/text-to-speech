#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for libs/cli, the pipeline helpers shared by ttsgen and ttsapi.

Covers:
- chunk_text: empty, at or below max, above max, no punctuation, very long single token.
- concat_wav_files: empty list, single file, two-file concat, mismatched params.
- output resolution: directory targets, exact names, timestamped names from the header.
- write_audio / save_audio_file: WAV concat, MP3 byte concat, umask-driven file mode.
- rec_worker / play_worker: success path, partial failure (sentinel propagation),
  done-sentinel always emitted, failures list capture.
"""

import io
import os
import queue
import stat
import sys
import threading
import wave
from pathlib import Path

import pytest

# Local imports
from libs.cli import (
    ChunkResult,
    chunk_extension,
    chunk_text,
    concat_wav_files,
    is_directory_target,
    output_path_for,
    play_worker,
    rec_worker,
    resolve_output_target,
    save_audio_file,
    write_audio,
)

# chunk_text


def test_chunk_text_empty():
    """Empty input produces no chunks at all."""
    assert chunk_text("") == []


def test_chunk_text_short_returns_single_chunk():
    """Text shorter than the limit stays in one piece."""
    chunks = chunk_text("Hello, world!", max_len=200)
    assert len(chunks) == 1
    assert "Hello" in chunks[0]


def test_chunk_text_splits_on_sentence_boundaries():
    """Longer text is split into several chunks, each within the limit."""
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
    """Text without sentence boundaries still respects the length limit."""
    text = "word " * 50  # 250 chars, no sentence boundary
    chunks = chunk_text(text, max_len=50)
    for c in chunks:
        assert len(c) <= 50


# concat_wav_files


def silent_wav(path: Path, ms: int = 50, rate: int = 22050) -> None:
    """Write a silent 16-bit mono WAV of `ms` milliseconds to `path`."""
    nframes = int(rate * ms / 1000)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * nframes)


def test_concat_wav_files_empty(tmp_path):
    """Concatenating no files writes nothing to the output stream."""
    out = io.BytesIO()
    concat_wav_files([], out)
    assert out.getvalue() == b""


def test_concat_wav_files_single(tmp_path):
    """A single input file is copied through with its frame count intact."""
    f = tmp_path / "a.wav"
    silent_wav(f, ms=100, rate=22050)
    out_path = tmp_path / "out.wav"
    with open(out_path, "wb") as out:
        concat_wav_files([str(f)], out)
    with wave.open(str(out_path), "rb") as r:
        assert r.getnframes() == 22050 // 10  # 100 ms at 22050 Hz


def test_concat_wav_files_two_same_params(tmp_path):
    """Two files with identical parameters merge into their summed duration."""
    a, b = tmp_path / "a.wav", tmp_path / "b.wav"
    silent_wav(a, ms=100, rate=22050)
    silent_wav(b, ms=200, rate=22050)
    out_path = tmp_path / "out.wav"
    with open(out_path, "wb") as out:
        concat_wav_files([str(a), str(b)], out)
    with wave.open(str(out_path), "rb") as r:
        # 100 ms + 200 ms = 300 ms at 22050 Hz
        assert r.getnframes() == int(22050 * 0.3)


def test_concat_wav_files_param_mismatch_warns(tmp_path, caplog):
    """Mixing sample rates is allowed but logs a warning about the mismatch."""
    a, b = tmp_path / "a.wav", tmp_path / "b.wav"
    silent_wav(a, ms=50, rate=22050)
    silent_wav(b, ms=50, rate=16000)  # different rate
    out_path = tmp_path / "out.wav"
    with caplog.at_level("WARNING"):
        with open(out_path, "wb") as out:
            concat_wav_files([str(a), str(b)], out)
    assert any("WAV params mismatch" in r.message for r in caplog.records)


# output resolution


def test_is_directory_target_trailing_separator_or_existing_dir(tmp_path):
    """A trailing separator or an existing directory means "directory, auto-named file"."""
    assert is_directory_target("audio" + os.sep)
    assert is_directory_target(str(tmp_path))
    assert not is_directory_target(str(tmp_path / "out.wav"))
    assert not is_directory_target("out")


@pytest.mark.skipif(os.altsep is None, reason="no alternative separator on this platform")
def test_is_directory_target_accepts_altsep():
    """On Windows a forward slash also marks a directory target."""
    assert is_directory_target("audio" + os.altsep)


def test_resolve_output_target_empty_uses_audio_dir(tmp_path):
    """None (via --output file) and "" (bare --file) both mean the audio directory."""
    audio_dir = tmp_path / "audio"
    assert resolve_output_target(None, str(audio_dir)) == (str(audio_dir), True)
    assert resolve_output_target("", str(audio_dir)) == (str(audio_dir), True)
    assert audio_dir.is_dir()


def test_resolve_output_target_exact_name_creates_parent(tmp_path):
    """An exact file name is returned verbatim and its parent directory is created."""
    target = tmp_path / "nested" / "out.wav"
    assert resolve_output_target(str(target), str(tmp_path)) == (str(target), False)
    assert target.parent.is_dir()
    assert not target.exists()


def test_output_path_for_directory_uses_prefix_and_extension(tmp_path):
    """A directory target gets a [prefix_]timestamp.<extension> name inside it."""
    name = output_path_for(str(tmp_path), True, "voice", "mp3")
    assert Path(name).parent == tmp_path
    assert Path(name).name.startswith("voice_")
    assert name.endswith(".mp3")
    assert output_path_for(str(tmp_path / "exact.wav"), False, "voice", "mp3") == str(tmp_path / "exact.wav")


# write_audio / save_audio_file


def test_chunk_extension_sniffs_first_chunk(tmp_path):
    """The extension comes from the header of the first chunk, whatever the file is called."""
    wav = tmp_path / "a.part"
    silent_wav(wav)
    mp3 = tmp_path / "b.part"
    mp3.write_bytes(b"\xff\xf3\x64\xc4" + b"\x00" * 8)
    assert chunk_extension([str(wav)]) == "wav"
    assert chunk_extension([str(mp3)]) == "mp3"


def test_write_audio_concatenates_wav_chunks(tmp_path):
    """Several WAV chunks are merged through the wave module into one valid WAV."""
    a, b = tmp_path / "a.part", tmp_path / "b.part"
    silent_wav(a, ms=100)
    silent_wav(b, ms=200)
    out = io.BytesIO()
    write_audio([str(a), str(b)], out)
    with wave.open(io.BytesIO(out.getvalue()), "rb") as merged:
        assert merged.getnframes() == int(22050 * 0.3)


def test_write_audio_concatenates_wav_chunks_into_a_pipe(tmp_path):
    """A pipe cannot seek, yet `ttsgen --stdout | ttsplay` still gets one WAV with the right frame count."""
    a, b = tmp_path / "a.part", tmp_path / "b.part"
    silent_wav(a, ms=100)
    silent_wav(b, ms=200)
    read_fd, write_fd = os.pipe()
    with os.fdopen(read_fd, "rb") as reader:
        with os.fdopen(write_fd, "wb") as writer:
            assert writer.seekable() is False
            write_audio([str(a), str(b)], writer)
        data = reader.read()
    with wave.open(io.BytesIO(data), "rb") as merged:
        assert merged.getnframes() == int(22050 * 0.3)


def test_write_audio_concatenates_mp3_bytes(tmp_path):
    """MP3 chunks are written back to back, untouched."""
    frame = b"\xff\xfb\x90\x64" + b"\x01" * 8
    a, b = tmp_path / "a.part", tmp_path / "b.part"
    a.write_bytes(frame)
    b.write_bytes(frame)
    out = io.BytesIO()
    write_audio([str(a), str(b)], out)
    assert out.getvalue() == frame + frame


def test_write_audio_single_chunk_is_copied(tmp_path):
    """One chunk is copied byte for byte, no re-encoding."""
    a = tmp_path / "a.part"
    silent_wav(a, ms=50)
    out = io.BytesIO()
    write_audio([str(a)], out)
    assert out.getvalue() == a.read_bytes()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_save_audio_file_follows_umask(tmp_path):
    """The saved file is group and world readable under umask 022, unlike the 0600 temp chunks."""
    a = tmp_path / "a.part"
    silent_wav(a)
    destination = tmp_path / "out.wav"
    old_umask = os.umask(0o022)
    try:
        save_audio_file([str(a)], str(destination))
    finally:
        os.umask(old_umask)
    mode = stat.S_IMODE(destination.stat().st_mode)
    assert mode & 0o044 == 0o044


# rec_worker / play_worker


def silent_bytes() -> bytes:
    """Return a short silent 16-bit mono WAV as raw bytes."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"\x00\x00" * 100)
    return buf.getvalue()


def test_rec_play_worker_success_path(tmp_path):
    """Every chunk is synthesized, spooled to disk and collected without failures."""
    chunks = ["one", "two", "three"]
    audio = silent_bytes()
    q: queue.Queue = queue.Queue(maxsize=2)
    collected: list[str] = []
    failures: list = []

    def gen(text: str) -> bytes:
        """Return the same canned audio for every chunk."""
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
    """One failing chunk is recorded as a failure while the others still complete."""
    chunks = ["ok1", "boom", "ok2"]
    q: queue.Queue = queue.Queue(maxsize=2)
    collected: list[str] = []
    failures: list = []

    def gen(text: str) -> bytes:
        """Fail on the chunk literally named 'boom', succeed otherwise."""
        if text == "boom":
            raise RuntimeError("synthetic engine error")
        return silent_bytes()

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


def test_rec_worker_removes_the_chunk_file_it_could_not_write(tmp_path):
    """A chunk whose bytes cannot be written is reported as failed and leaves no file behind."""
    q: queue.Queue = queue.Queue()
    # A str where bytes belong makes the write itself fail, after mkstemp created the file.
    rec_worker(["only"], lambda text: "not bytes", q, ".wav", str(tmp_path))  # type: ignore[arg-type, return-value]
    item = q.get_nowait()
    assert item.error is not None and item.tmp_path is None
    assert q.get_nowait() is None
    assert list(tmp_path.iterdir()) == []


def test_rec_worker_emits_done_sentinel_even_on_total_failure(tmp_path):
    """Every chunk fails — play_worker must still see the None sentinel and exit."""
    chunks = ["a", "b"]
    q: queue.Queue = queue.Queue(maxsize=2)
    collected: list[str] = []
    failures: list = []

    def gen(text: str) -> bytes:
        """Fail on every chunk to exercise the total-failure path."""
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
    """In play mode each successful chunk's bytes are handed to the play callback."""
    played: list[bytes] = []
    q: queue.Queue = queue.Queue()
    q.put(ChunkResult(idx=1, tmp_path=str(tmp_path / "a.wav"), audio_bytes=b"abc", error=None))
    q.put(None)
    play_worker(q, ["play"], [], played.append)
    assert played == [b"abc"]


def test_play_worker_skips_play_for_failed_chunk(tmp_path):
    """A chunk carrying an error is counted as a failure and never played."""
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
        """Fail on the first playback attempt and succeed on later ones."""
        calls.append(b)
        if len(calls) == 1:
            raise OSError("audio device gone")

    with caplog.at_level("ERROR"):
        play_worker(q, ["play"], [], boom_then_ok)
    assert calls == [b"x", b"y"]
    assert any("Playback error" in r.message for r in caplog.records)
