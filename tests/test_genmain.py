#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integration tests for ttsgen.main(): output file resolution and language defaults, synthesis mocked.

Pins the contract that `--file NAME` writes exactly NAME (chunks concatenated),
that auto-named files take their extension from the audio header, that `-o file`
honours `--audio-dir`, and that `TTS_LANGUAGE` is used when `--language` is absent.
"""

import io
import os
import stat
import sys
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
