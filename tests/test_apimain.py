#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integration tests for ttsapi.main() — full CLI orchestration with mocked HTTP.

Pins the contract for exit codes, output-format combinatorics, and the
chunked producer/consumer pipeline that calls fetch_audio under the hood.
"""

import io
import sys
import wave
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ttsapi  # noqa: E402


def _wav_bytes() -> bytes:
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
    monkeypatch.setattr(ttsapi, "fetch_audio", lambda text, engine, language: _wav_bytes())
    monkeypatch.setattr("libs.config.load_config", lambda: None)
    return tmp_path


def _run(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["ttsapi.py", *argv])
    return ttsapi.main()


def test_main_list_flag_returns_list_engines_exit_code(monkeypatch, quiet_main):
    monkeypatch.setattr(ttsapi, "fetch_engines", lambda: {"engines": ["gtts"], "default": "gtts"})
    rc = _run(monkeypatch, ["--list", "--quiet"])
    assert rc == 0


def test_main_missing_input_file_returns_2(monkeypatch, quiet_main, caplog):
    """A path that does not exist must surface as exit 2, not crash."""
    rc = _run(monkeypatch, ["-i", str(quiet_main / "missing.txt"), "--quiet"])
    assert rc == 2


def test_main_invalid_output_format_returns_2(monkeypatch, quiet_main):
    rc = _run(monkeypatch, ["hello", "--output", "play,wat", "--quiet"])
    assert rc == 2


def test_main_file_output_writes_audio(monkeypatch, quiet_main):
    """End-to-end: text → mocked fetch → file written to args path."""
    out = quiet_main / "out.wav"
    rc = _run(monkeypatch, ["hello", "-e", "coquitts", "-f", str(out), "--quiet"])
    assert rc == 0
    assert out.exists() and out.stat().st_size > 44


def test_main_file_output_auto_names_under_audio_dir(monkeypatch, quiet_main, capsys):
    """`--file` (no value) generates a timestamped name under AUDIO_DIRECTORY,
    and the path is printed to stdout for shell capture."""
    audio_dir = quiet_main / "audio_out"
    rc = _run(
        monkeypatch,
        ["hello", "-e", "coquitts", "-f", "--audio-dir", str(audio_dir), "--quiet"],
    )
    assert rc == 0
    files = list(audio_dir.glob("*.wav"))
    assert len(files) == 1
    captured = capsys.readouterr()
    assert str(files[0]) in captured.out


def test_main_chunks_long_input_into_separate_files(monkeypatch, quiet_main):
    """Text > 200 chars splits into multiple chunks → file per chunk
    (the per-chunk file naming uses _NNN suffix)."""
    long_text = ". ".join(f"sentence number {i}" for i in range(40)) + "."
    out = quiet_main / "many.wav"
    rc = _run(monkeypatch, [long_text, "-e", "coquitts", "-f", str(out), "--quiet"])
    assert rc == 0
    suffixed = sorted(quiet_main.glob("many_*.wav"))
    assert len(suffixed) >= 2  # at least 2 chunks given chunk size 200


def test_main_engine_failure_returns_exit_code_3(monkeypatch, quiet_main):
    """fetch_audio raising RuntimeError on every chunk → all failures → rc=3."""

    def boom(text, engine, language):
        raise RuntimeError("Server returned 500: boom")

    monkeypatch.setattr(ttsapi, "fetch_audio", boom)
    rc = _run(monkeypatch, ["hello", "-e", "coquitts", "-f", str(quiet_main / "x.wav"), "--quiet"])
    assert rc == 3


def test_main_input_file_synthesizes_text(monkeypatch, quiet_main):
    """`-i FILE` reads, strips, and runs synthesis just like positional text."""
    inp = quiet_main / "input.txt"
    inp.write_text("  text from file  \n")
    out = quiet_main / "from_file.wav"
    captured = []

    def capture(text, engine, language):
        captured.append(text)
        return _wav_bytes()

    monkeypatch.setattr(ttsapi, "fetch_audio", capture)
    rc = _run(monkeypatch, ["-i", str(inp), "-e", "coquitts", "-f", str(out), "--quiet"])
    assert rc == 0
    assert captured == ["text from file"]


def test_main_default_output_format_is_play(monkeypatch, quiet_main):
    """No --file, --stdout, --play, --output → defaults to play (no file written)."""
    libs_api = sys.modules["libs.api"]
    monkeypatch.setattr(libs_api, "play_audio", lambda data: None)
    rc = _run(monkeypatch, ["hi", "-e", "coquitts", "--quiet"])
    assert rc == 0
    # No .wav files produced anywhere because play-only mode.
    assert list(quiet_main.glob("*.wav")) == []
