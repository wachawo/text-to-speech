#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integration tests for ttsgen.main(): output file resolution and language defaults, synthesis mocked.

Pins the contract that `--file NAME` writes exactly NAME (chunks concatenated),
that auto-named files take their extension from the audio header, that `-o file`
honours `--audio-dir`, and that `TTS_LANGUAGE` is used when `--language` is absent.
"""

import io
import logging
import os
import signal
import stat
import sys
import threading
import time
import wave
from pathlib import Path

import pytest

# The repository root must be on sys.path before `ttsgen` is imported,
# so that import deliberately stays below this insert (E402 is expected).
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Local imports
import ttsgen  # noqa: E402
from libs import tools  # noqa: E402
from libs.exceptions import TTSException, ValidationError  # noqa: E402

MPEG2_FRAME = b"\xff\xf3\x64\xc4" + b"\x00" * 8
LONG_TEXT = ". ".join(f"sentence number {i}" for i in range(40)) + "."


@pytest.fixture
def quiet_main(monkeypatch, tmp_path, make_wav):
    """Common setup: cwd is tmp_path, no config files, synthesis returns canned WAV."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ttsgen, "load_config", lambda: None)
    monkeypatch.setattr(ttsgen, "text_to_speech_bytes", lambda text, engine, language: make_wav())
    monkeypatch.setattr(ttsgen, "play_audio", lambda data: None)
    monkeypatch.setenv("TTS_ENGINE", "gtts")
    monkeypatch.delenv("TTS_LANGUAGE", raising=False)
    monkeypatch.delenv("AUDIO_DIRECTORY", raising=False)
    monkeypatch.delenv("FILENAME_PREFIX", raising=False)
    return tmp_path


def run_main(monkeypatch, argv):
    """Run `ttsgen.main()` with the given argv tail and return its exit code."""
    monkeypatch.setattr(sys, "argv", ["ttsgen.py", *argv])
    return ttsgen.main()


def wav_frames(path: Path) -> int:
    """Return the frame count of a WAV file."""
    with wave.open(str(path), "rb") as handle:
        return handle.getnframes()


def wav_frames_of(data: bytes) -> int:
    """Return the frame count of in-memory WAV bytes."""
    with wave.open(io.BytesIO(data), "rb") as handle:
        return handle.getnframes()


def test_file_flag_writes_exactly_the_requested_name(monkeypatch, quiet_main, capsys, make_wav):
    """`--file out.wav` produces out.wav, not out_001.wav, and prints that path."""
    out = quiet_main / "out.wav"
    rc = run_main(monkeypatch, ["hello", "--file", str(out), "--quiet"])
    assert rc == 0
    assert sorted(quiet_main.iterdir()) == [out]
    assert wav_frames(out) == wav_frames_of(make_wav())
    assert capsys.readouterr().out.strip() == str(out)


def test_long_text_chunks_are_concatenated_into_one_wav(monkeypatch, quiet_main, make_wav):
    """Several WAV chunks are merged into the one requested file with their durations summed."""
    out = quiet_main / "many.wav"
    rc = run_main(monkeypatch, [LONG_TEXT, "--file", str(out), "--quiet"])
    assert rc == 0
    assert sorted(quiet_main.iterdir()) == [out]
    chunk_frames = wav_frames_of(make_wav())
    chunks = len(ttsgen.chunk_text(LONG_TEXT, ttsgen.DEFAULT_CHUNK_CHARS))
    assert chunks >= 2
    assert wav_frames(out) == chunk_frames * chunks


def test_output_file_without_file_flag_honours_audio_dir(monkeypatch, quiet_main):
    """`-o file` alone saves under `--audio-dir`, with an auto-generated name."""
    audio_dir = quiet_main / "elsewhere"
    rc = run_main(monkeypatch, ["hello", "-o", "file", "-d", str(audio_dir), "--quiet"])
    assert rc == 0
    files = list(audio_dir.iterdir())
    assert len(files) == 1
    assert files[0].suffix == ".wav"
    assert not (quiet_main / "audio").exists()


def test_directory_target_with_trailing_separator(monkeypatch, quiet_main, capsys):
    """`--file dir/` means "directory, auto-named file" and the printed path is inside it."""
    target = quiet_main / "outdir"
    rc = run_main(monkeypatch, ["hello", "--file", str(target) + os.sep, "--quiet"])
    assert rc == 0
    files = list(target.iterdir())
    assert len(files) == 1
    assert capsys.readouterr().out.strip() == str(files[0])


def test_auto_name_extension_comes_from_the_bytes(monkeypatch, quiet_main):
    """MP3 bytes get a .mp3 name even though nothing in the flags says so."""
    monkeypatch.setattr(ttsgen, "text_to_speech_bytes", lambda text, engine, language: MPEG2_FRAME)
    monkeypatch.setenv("FILENAME_PREFIX", "voice")
    rc = run_main(monkeypatch, ["hello", "--file", "--quiet"])
    assert rc == 0
    files = list((quiet_main / "audio").iterdir())
    assert len(files) == 1
    assert files[0].suffix == ".mp3"
    assert files[0].name.startswith("voice_")
    assert files[0].read_bytes() == MPEG2_FRAME


def test_language_falls_back_to_tts_language_env(monkeypatch, quiet_main, make_wav):
    """Without `--language`, TTS_LANGUAGE from the environment is what reaches the engine."""
    seen: list[str] = []

    def capture(text, engine, language):
        """Record the language handed to synthesis and return canned audio."""
        seen.append(language)
        return make_wav()

    monkeypatch.setattr(ttsgen, "text_to_speech_bytes", capture)
    monkeypatch.setenv("TTS_LANGUAGE", "de")
    rc = run_main(monkeypatch, ["hello", "--file", str(quiet_main / "de.wav"), "--quiet"])
    assert rc == 0
    assert seen == ["de"]


def test_language_defaults_to_en_without_flag_or_env(monkeypatch, quiet_main, make_wav):
    """With neither `--language` nor TTS_LANGUAGE the language is en."""
    seen: list[str] = []

    def capture(text, engine, language):
        """Record the language handed to synthesis and return canned audio."""
        seen.append(language)
        return make_wav()

    monkeypatch.setattr(ttsgen, "text_to_speech_bytes", capture)
    rc = run_main(monkeypatch, ["hello", "--file", str(quiet_main / "en.wav"), "--quiet"])
    assert rc == 0
    assert seen == ["en"]


def test_blank_text_produces_no_file_and_fails(monkeypatch, quiet_main, caplog):
    """Whitespace-only text yields no chunks; the run fails instead of writing an empty file."""
    out = quiet_main / "blank.wav"
    with caplog.at_level("ERROR"):
        rc = run_main(monkeypatch, ["   ", "--file", str(out), "--quiet"])
    assert rc == 1
    assert not out.exists()
    assert any("No audio was generated" in r.message for r in caplog.records)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_saved_file_follows_umask(monkeypatch, quiet_main):
    """The saved file is readable by group and others under umask 022."""
    out = quiet_main / "mode.wav"
    old_umask = os.umask(0o022)
    try:
        rc = run_main(monkeypatch, ["hello", "--file", str(out), "--quiet"])
    finally:
        os.umask(old_umask)
    assert rc == 0
    assert stat.S_IMODE(out.stat().st_mode) & 0o044 == 0o044


# One error stops the run (the same mistake would fail every chunk)

MANY_CHUNKS_TEXT = ". ".join(f"sentence number {i}" for i in range(200)) + "."


def error_messages(caplog) -> list[str]:
    """Return the messages of the ERROR records captured so far."""
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]


def test_bad_language_stops_at_the_first_chunk_and_exits_1(monkeypatch, quiet_main, caplog):
    """`-l english` is a validation error: one attempt, one log line, the exit code of a validation error."""
    asked: list[str] = []

    def refuse(text, engine, language):
        """Reject the language the way libs.tools.validate_language does."""
        asked.append(text)
        raise ValidationError("Language must be a 2-character code")

    monkeypatch.setattr(ttsgen, "text_to_speech_bytes", refuse)
    with caplog.at_level("ERROR"):
        rc = run_main(monkeypatch, [MANY_CHUNKS_TEXT, "-l", "english", "--file", str(quiet_main / "x.wav"), "--quiet"])
    assert rc == 1
    assert len(asked) == 1
    assert error_messages(caplog) == ["Validation error: Language must be a 2-character code"]


def test_engine_failure_stops_at_the_first_chunk(monkeypatch, quiet_main, caplog):
    """A runtime failure is logged once, without a traceback, and no later chunk is synthesized."""
    asked: list[str] = []

    def fail(text, engine, language):
        """Fail like an engine whose network is down."""
        asked.append(text)
        raise TTSException("network down")

    monkeypatch.setattr(ttsgen, "text_to_speech_bytes", fail)
    out_dir = quiet_main / "out"
    out_dir.mkdir()
    with caplog.at_level("ERROR"):
        rc = run_main(monkeypatch, [MANY_CHUNKS_TEXT, "--file", str(out_dir / "x.wav"), "--quiet"])
    assert rc == 3
    assert len(asked) == 1
    messages = error_messages(caplog)
    assert len(messages) == 1
    assert "network down" in messages[0] and "Traceback" not in messages[0]
    assert list(out_dir.iterdir()) == []


# Ctrl+C removes every chunk file the run created


def join_pipeline_threads() -> None:
    """Wait for the producer and consumer threads a run may have left behind."""
    for thread in threading.enumerate():
        if "rec_worker" in thread.name or "play_worker" in thread.name:
            thread.join(timeout=10)


def test_ctrl_c_removes_every_chunk_file_and_stops_the_pipeline(monkeypatch, quiet_main, make_wav):
    """Ctrl+C during playback leaves no .part file, plays nothing more and synthesizes no further chunk."""
    asked: list[str] = []
    played: list[bytes] = []

    def synth(text, engine, language):
        """Return canned audio and count the chunks synthesized."""
        asked.append(text)
        return make_wav()

    def play(data):
        """Deliver Ctrl+C to the main thread while the first chunk plays."""
        played.append(data)
        if len(played) == 1:
            signal.pthread_kill(threading.main_thread().ident, signal.SIGINT)
        time.sleep(0.05)

    monkeypatch.setattr(ttsgen, "text_to_speech_bytes", synth)
    monkeypatch.setattr(ttsgen, "play_audio", play)
    out_dir = quiet_main / "out"
    out_dir.mkdir()
    chunks = len(ttsgen.chunk_text(MANY_CHUNKS_TEXT, ttsgen.DEFAULT_CHUNK_CHARS))
    rc = run_main(monkeypatch, [MANY_CHUNKS_TEXT, "-o", "play,file", "--file", str(out_dir / "x.wav"), "--quiet"])
    join_pipeline_threads()
    assert rc == 1
    assert list(out_dir.iterdir()) == []
    assert len(played) == 1
    assert len(asked) < chunks


# Auto-generated names, error messages, entry point, help


def test_two_auto_named_runs_in_one_second_keep_both_files(monkeypatch, quiet_main):
    """`--file` twice within one second writes two files instead of overwriting the first."""

    class FrozenClock:
        """Stand-in for datetime whose now() never moves."""

        @staticmethod
        def now():
            """Return one fixed moment."""
            from datetime import datetime

            return datetime(2026, 10, 10, 12, 0, 0)

    monkeypatch.setattr(tools, "datetime", FrozenClock)
    assert run_main(monkeypatch, ["one", "--file", "--quiet"]) == 0
    assert run_main(monkeypatch, ["two", "--file", "--quiet"]) == 0
    assert len(list((quiet_main / "audio").iterdir())) == 2


def test_failed_save_leaves_no_empty_auto_named_file(monkeypatch, quiet_main):
    """A save that fails removes the auto-generated name it claimed, instead of leaving an empty file."""

    def disk_full(paths, filename):
        """Fail the way a full disk does."""
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(ttsgen, "save_audio_file", disk_full)
    assert run_main(monkeypatch, ["one", "--file", "--quiet"]) == 1
    assert list((quiet_main / "audio").iterdir()) == []


def test_failed_save_keeps_an_explicit_target(monkeypatch, quiet_main):
    """An explicit --file path is the caller's own file and is not removed on a failed save."""
    target = quiet_main / "mine.wav"
    target.write_bytes(b"old")

    def disk_full(paths, filename):
        """Fail the way a full disk does."""
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(ttsgen, "save_audio_file", disk_full)
    assert run_main(monkeypatch, ["one", "--file", str(target), "--quiet"]) == 1
    assert target.read_bytes() == b"old"


def test_missing_input_file_is_reported_once(monkeypatch, quiet_main, caplog):
    """A missing -i file reads "File not found", not "Could not read file ...: File not found"."""
    with caplog.at_level("ERROR"):
        rc = run_main(monkeypatch, ["-i", "nope.txt", "--quiet"])
    assert rc == 1
    assert error_messages(caplog) == ["Validation error: File not found: nope.txt"]


@pytest.mark.parametrize("raised", [KeyboardInterrupt, RuntimeError("listing broke")])
def test_entry_point_turns_ctrl_c_and_stray_errors_into_exit_1(monkeypatch, quiet_main, raised):
    """The console script returns 1 instead of a raw traceback, also outside the synthesis path."""

    def broken_listing():
        """Fail while --list collects its rows."""
        raise raised

    monkeypatch.setattr(ttsgen, "collect_engine_rows", broken_listing)
    try:
        rc = run_main(monkeypatch, ["--list"])
    except BaseException as exc:
        pytest.fail(f"{type(exc).__name__} escaped main()")
    assert rc == 1


def test_help_and_examples_drop_the_settings_nothing_reads():
    """DEFAULT_OUTPUT_FORMAT and AUTO_PLAY never had an effect, so nothing advertises them."""
    assert "DEFAULT_OUTPUT_FORMAT" not in ttsgen.parse_arguments().format_help()
    assert "AUTO_PLAY" not in ttsgen.parse_arguments().format_help()
    for name in ("env.example", "ttsgen.conf.example", "docs/BARKTTS.md", "docs/COQUITTS.md", "docs/SILEROTTS.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "DEFAULT_OUTPUT_FORMAT" not in text and "AUTO_PLAY" not in text, name
