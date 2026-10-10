#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integration tests for ttsapi.main() — full CLI orchestration with mocked HTTP.

Pins the contract for exit codes, output-format combinatorics, and the
chunked producer/consumer pipeline that calls fetch_audio under the hood.
"""

import io
import logging
import signal
import sys
import threading
import time
import wave
from pathlib import Path

import pytest
import requests

# The repository root must be on sys.path before `ttsapi` is imported,
# so that import deliberately stays below this insert (E402 is expected).
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Local imports
import ttsapi  # noqa: E402


def make_wav_bytes() -> bytes:
    """Build a short silent 16-bit mono WAV to stand in for synthesized audio."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"\x00\x00" * 100)
    return buf.getvalue()


@pytest.fixture
def quiet_main(monkeypatch, tmp_path):
    """Common setup: cwd is tmp_path, no real network, no real config files."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ttsapi, "fetch_audio", lambda text, engine, language: make_wav_bytes())
    monkeypatch.setattr("libs.config.load_config", lambda: None)
    return tmp_path


def run_main(monkeypatch, argv):
    """Run `ttsapi.main()` with the given argv tail and return its exit code."""
    monkeypatch.setattr(sys, "argv", ["ttsapi.py", *argv])
    return ttsapi.main()


def test_main_list_flag_returns_list_engines_exit_code(monkeypatch, quiet_main):
    """`--list` short-circuits synthesis and exits with the listing status."""
    monkeypatch.setattr(ttsapi, "fetch_engines", lambda: {"available": ["gtts"], "default": "gtts"})
    rc = run_main(monkeypatch, ["--list", "--quiet"])
    assert rc == 0


def test_main_missing_input_file_returns_1_like_ttsgen(monkeypatch, quiet_main, caplog):
    """A path that does not exist exits 1, the code ttsgen uses for the same mistake."""
    missing = quiet_main / "missing.txt"
    with caplog.at_level("ERROR"):
        rc = run_main(monkeypatch, ["-i", str(missing), "--quiet"])
    assert rc == 1
    assert [r.message for r in caplog.records if r.levelname == "ERROR"] == [f"Validation error: File not found: {missing}"]


def test_main_invalid_output_format_returns_1_like_ttsgen(monkeypatch, quiet_main):
    """An unknown token in `--output` is rejected with exit 1, as in ttsgen."""
    rc = run_main(monkeypatch, ["hello", "--output", "play,wat", "--quiet"])
    assert rc == 1


def test_main_stdout_disables_file_like_ttsgen(monkeypatch, quiet_main, capsysbinary):
    """`--stdout --file X` without -o writes only to stdout, as `ttsgen --help` documents."""
    out = quiet_main / "both.wav"
    rc = run_main(monkeypatch, ["hello", "-e", "coquitts", "--stdout", "--file", str(out), "--quiet"])
    assert rc == 0
    assert not out.exists()
    assert capsysbinary.readouterr().out.startswith(b"RIFF")


def test_main_file_output_writes_audio(monkeypatch, quiet_main):
    """End-to-end: text → mocked fetch → file written to args path."""
    out = quiet_main / "out.wav"
    rc = run_main(monkeypatch, ["hello", "-e", "coquitts", "-f", str(out), "--quiet"])
    assert rc == 0
    assert out.exists() and out.stat().st_size > 44


def test_main_file_output_auto_names_under_audio_dir(monkeypatch, quiet_main, capsys):
    """`--file` (no value) generates a timestamped name under AUDIO_DIRECTORY,
    and the path is printed to stdout for shell capture."""
    audio_dir = quiet_main / "audio_out"
    rc = run_main(
        monkeypatch,
        ["hello", "-e", "coquitts", "-f", "--audio-dir", str(audio_dir), "--quiet"],
    )
    assert rc == 0
    files = list(audio_dir.glob("*.wav"))
    assert len(files) == 1
    captured = capsys.readouterr()
    assert str(files[0]) in captured.out


def test_main_chunks_long_input_into_one_file(monkeypatch, quiet_main):
    """Text > 200 chars splits into multiple chunks that are concatenated into the requested file."""
    long_text = ". ".join(f"sentence number {i}" for i in range(40)) + "."
    out = quiet_main / "many.wav"
    rc = run_main(monkeypatch, [long_text, "-e", "coquitts", "-f", str(out), "--quiet"])
    assert rc == 0
    assert sorted(quiet_main.glob("many*.wav")) == [out]
    with wave.open(str(out), "rb") as merged:
        # Every mocked chunk is 100 frames; at least 2 chunks given chunk size 200.
        assert merged.getnframes() >= 200
        assert merged.getnframes() % 100 == 0


def test_main_engine_failure_returns_exit_code_3(monkeypatch, quiet_main):
    """fetch_audio raising RuntimeError on every chunk → all failures → rc=3."""

    def boom(text, engine, language):
        """Fail every synthesis request so the run has no successful chunk."""
        raise RuntimeError("Server returned 500: boom")

    monkeypatch.setattr(ttsapi, "fetch_audio", boom)
    rc = run_main(monkeypatch, ["hello", "-e", "coquitts", "-f", str(quiet_main / "x.wav"), "--quiet"])
    assert rc == 3


def test_main_partial_failure_leaves_no_chunk_files(monkeypatch, quiet_main):
    """Exit 3 still removes the chunks that did succeed; they sit next to the requested file."""

    def second_fails(text, engine, language):
        """Answer the first chunk and fail the one that mentions the last sentence."""
        if "last" in text:
            raise RuntimeError("Server returned 500: boom")
        return make_wav_bytes()

    monkeypatch.setattr(ttsapi, "fetch_audio", second_fails)
    out_dir = quiet_main / "out"
    out_dir.mkdir()
    text = "first " * 40 + ". This is the last sentence."
    rc = run_main(monkeypatch, [text, "-e", "coquitts", "-f", str(out_dir / "x.wav"), "--quiet"])
    assert rc == 3
    assert list(out_dir.iterdir()) == []


def test_main_input_file_synthesizes_text(monkeypatch, quiet_main):
    """`-i FILE` reads, strips, and runs synthesis just like positional text."""
    inp = quiet_main / "input.txt"
    inp.write_text("  text from file  \n")
    out = quiet_main / "from_file.wav"
    captured = []

    def capture(text, engine, language):
        """Record the text handed to the client and return canned audio."""
        captured.append(text)
        return make_wav_bytes()

    monkeypatch.setattr(ttsapi, "fetch_audio", capture)
    rc = run_main(monkeypatch, ["-i", str(inp), "-e", "coquitts", "-f", str(out), "--quiet"])
    assert rc == 0
    assert captured == ["text from file"]


def test_main_leaves_language_to_the_server(monkeypatch, quiet_main):
    """Without -l and TTS_LANGUAGE the request names no language, rather than forcing English."""
    monkeypatch.delenv("TTS_LANGUAGE", raising=False)
    languages = []

    def capture(text, engine, language):
        """Record the language handed to the client and return canned audio."""
        languages.append(language)
        return make_wav_bytes()

    monkeypatch.setattr(ttsapi, "fetch_audio", capture)
    rc = run_main(monkeypatch, ["hi", "-f", str(quiet_main / "out.wav"), "--quiet"])
    assert rc == 0
    assert languages == [""]


def test_main_default_output_format_is_play(monkeypatch, quiet_main):
    """No --file, --stdout, --play, --output → defaults to play (no file written)."""
    libs_api = sys.modules["libs.api"]
    monkeypatch.setattr(libs_api, "play_audio", lambda data: None)
    rc = run_main(monkeypatch, ["hi", "-e", "coquitts", "--quiet"])
    assert rc == 0
    # No .wav files produced anywhere because play-only mode.
    assert list(quiet_main.glob("*.wav")) == []


MANY_CHUNKS_TEXT = ". ".join(f"sentence number {i}" for i in range(200)) + "."


def test_main_down_server_stops_at_the_first_chunk(monkeypatch, quiet_main, caplog):
    """An unreachable server is tried once and reported in one line, not once per chunk with tracebacks."""
    asked: list[str] = []

    def refuse(text, engine, language):
        """Fail like a server that is not listening."""
        asked.append(text)
        raise requests.ConnectionError("Connection refused")

    monkeypatch.setattr(ttsapi, "fetch_audio", refuse)
    with caplog.at_level("ERROR"):
        rc = run_main(monkeypatch, [MANY_CHUNKS_TEXT, "-f", str(quiet_main / "x.wav"), "--quiet"])
    assert rc == 3
    assert len(asked) == 1
    errors = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert "Connection refused" in errors[0] and "Traceback" not in errors[0]


def test_main_ctrl_c_removes_every_chunk_file(monkeypatch, quiet_main):
    """Ctrl+C during playback exits 1, leaves no .part file and plays nothing more."""
    played: list[bytes] = []

    def play(data):
        """Deliver Ctrl+C to the main thread while the first chunk plays."""
        played.append(data)
        if len(played) == 1:
            signal.pthread_kill(threading.main_thread().ident, signal.SIGINT)
        time.sleep(0.05)

    monkeypatch.setattr(sys.modules["libs.api"], "play_audio", play)
    out_dir = quiet_main / "out"
    out_dir.mkdir()
    try:
        rc = run_main(monkeypatch, [MANY_CHUNKS_TEXT, "-o", "play,file", "-f", str(out_dir / "x.wav"), "--quiet"])
    except KeyboardInterrupt:
        pytest.fail("KeyboardInterrupt escaped main()")
    finally:
        for thread in threading.enumerate():
            if "rec_worker" in thread.name or "play_worker" in thread.name:
                thread.join(timeout=10)
    assert rc == 1
    assert list(out_dir.iterdir()) == []
    assert len(played) == 1


@pytest.mark.parametrize("raised", [KeyboardInterrupt, RuntimeError("listing broke")])
def test_main_entry_point_turns_ctrl_c_and_stray_errors_into_exit_1(monkeypatch, quiet_main, raised):
    """The installed `ttsapi` script calls main(), so main() itself must catch, not the __main__ block."""

    def broken_listing():
        """Fail while --list talks to the server."""
        raise raised

    monkeypatch.setattr(ttsapi, "list_remote_engines", broken_listing)
    try:
        rc = run_main(monkeypatch, ["--list"])
    except BaseException as exc:
        pytest.fail(f"{type(exc).__name__} escaped main()")
    assert rc == 1
