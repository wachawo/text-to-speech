#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for engines/pipertts.py — offline TTS via Piper.

Fakes the `piper` package and the on-disk .onnx model layout. Pins the
contract for path resolution (PIPERTTS_MODELS env > .pipertts > default),
language→voice mapping, and the FileNotFoundError → instructions branch.
"""

import importlib
import io
import sys
import types
import wave

import pytest

from libs.exceptions import EngineNotAvailableError, TTSException


def _make_fake_piper(synthesise_bytes: bytes = b""):
    """Fake `piper` module with a PiperVoice that writes a valid WAV."""
    fake = types.ModuleType("piper")

    class FakePiperVoice:
        def __init__(self, path):
            self.path = path

        @classmethod
        def load(cls, path):
            return cls(path)

        def synthesize_wav(self, text, wav_file):
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(22050)
            wav_file.writeframes(synthesise_bytes if synthesise_bytes else b"\x00\x00" * 100)

    fake.PiperVoice = FakePiperVoice
    return fake


@pytest.fixture
def engine(monkeypatch):
    monkeypatch.setitem(sys.modules, "piper", _make_fake_piper())
    monkeypatch.delitem(sys.modules, "engines.pipertts", raising=False)
    return importlib.import_module("engines.pipertts")


# is_available

def test_is_available_true_with_fake_piper(engine):
    assert engine.is_available() is True


# get_models_directory — three-priority resolution

def test_models_dir_uses_env_var_absolute(engine, monkeypatch, tmp_path):
    monkeypatch.setenv("PIPERTTS_MODELS", str(tmp_path / "abs_models"))
    assert engine.get_models_directory() == str(tmp_path / "abs_models")


def test_models_dir_resolves_relative_env_against_project_root(engine, monkeypatch):
    monkeypatch.setenv("PIPERTTS_MODELS", "custom_voices")
    result = engine.get_models_directory()
    # Relative env var must resolve under project root, NOT cwd.
    assert result.endswith("custom_voices")
    assert "/text-to-speech/" in result or result.endswith("text-to-speech/custom_voices")


def test_models_dir_falls_back_to_dot_pipertts_in_project(engine, monkeypatch, tmp_path):
    """If env var is unset, .pipertts in project root wins over the default."""
    monkeypatch.delenv("PIPERTTS_MODELS", raising=False)
    # Stub the project-root path lookup by patching the module attribute.
    fake_project = tmp_path / "fake_project"
    pipertts_dir = fake_project / ".pipertts"
    pipertts_dir.mkdir(parents=True)

    import os as _os

    real_dirname = _os.path.dirname

    def stubbed_dirname(p):
        # First call returns engines/, second engines/.. — i.e. project root.
        if p.endswith("engines"):
            return str(fake_project)
        return real_dirname(p)

    monkeypatch.setattr(_os.path, "dirname", stubbed_dirname)
    assert engine.get_models_directory() == str(pipertts_dir)


def test_models_dir_default_when_nothing_configured(engine, monkeypatch, tmp_path):
    """Neither env var nor .pipertts/ → fallback to <project>/.piper/voices."""
    monkeypatch.delenv("PIPERTTS_MODELS", raising=False)
    # Move CWD somewhere that has no .pipertts so the project-root one wins —
    # but the project DOES contain it in real life. We only assert the path
    # ends with .piper/voices when we force-skip the .pipertts branch.
    monkeypatch.setattr(engine.os.path, "exists", lambda p: False)
    result = engine.get_models_directory()
    assert result.endswith(".piper/voices")


# get_voice_path — language → file mapping

def test_voice_path_known_language_uses_mapped_name(engine, monkeypatch, tmp_path):
    monkeypatch.setattr(engine, "get_models_directory", lambda: str(tmp_path))
    # Pre-create the file so the first existence check wins.
    (tmp_path / "ru_RU-ruslan-medium.onnx").write_bytes(b"x")
    assert engine.get_voice_path("ru") == str(tmp_path / "ru_RU-ruslan-medium.onnx")


def test_voice_path_unknown_language_defaults_to_english(engine, monkeypatch, tmp_path):
    monkeypatch.setattr(engine, "get_models_directory", lambda: str(tmp_path))
    (tmp_path / "en_US-lessac-medium.onnx").write_bytes(b"x")
    assert engine.get_voice_path("xx") == str(tmp_path / "en_US-lessac-medium.onnx")


def test_voice_path_returns_models_dir_path_when_file_missing(engine, monkeypatch, tmp_path):
    """When neither models_dir nor fallback dirs contain the .onnx, the
    function still returns the canonical models_dir candidate so generate()
    can produce a useful FileNotFoundError downstream."""
    monkeypatch.setattr(engine, "get_models_directory", lambda: str(tmp_path))
    monkeypatch.setattr(engine.os.path, "exists", lambda p: False)
    result = engine.get_voice_path("en")
    assert result == str(tmp_path / "en_US-lessac-medium.onnx")


# get_download_instructions

def test_download_instructions_mention_installer_and_url(engine):
    out = engine.get_download_instructions("ru")
    assert "ttsgen --install pipertts" in out
    assert "huggingface.co/rhasspy/piper-voices" in out
    assert "ru_RU-ruslan-medium.onnx" in out


def test_download_instructions_unknown_language_falls_back_to_en(engine):
    out = engine.get_download_instructions("xx")
    assert "en_US-lessac-medium.onnx" in out


# generate — error paths

def test_generate_raises_engine_not_available_when_flag_off(engine, monkeypatch):
    monkeypatch.setattr(engine, "AVAILABLE", False)
    with pytest.raises(EngineNotAvailableError, match="not available"):
        engine.generate("hi", {})


def test_generate_filenotfound_yields_download_instructions(engine, monkeypatch, tmp_path):
    """FileNotFoundError from PiperVoice.load → TTSException whose message
    contains the install command (so end users know what to do)."""
    monkeypatch.setattr(engine, "get_voice_path", lambda lang: str(tmp_path / "missing.onnx"))

    def boom_load(path):
        raise FileNotFoundError(path)

    monkeypatch.setattr(engine.PiperVoice, "load", staticmethod(boom_load))
    with pytest.raises(TTSException, match="ttsgen --install pipertts"):
        engine.generate("hi", {"language": "en"})


def test_generate_other_failure_wrapped_as_tts_exception(engine, monkeypatch, tmp_path):
    monkeypatch.setattr(engine, "get_voice_path", lambda lang: str(tmp_path / "v.onnx"))

    def boom(path):
        raise RuntimeError("inference crashed")

    monkeypatch.setattr(engine.PiperVoice, "load", staticmethod(boom))
    with pytest.raises(TTSException, match="generation failed"):
        engine.generate("hi", {})


# generate — happy path

def test_generate_returns_valid_wav_bytes(engine, monkeypatch, tmp_path):
    """generate writes WAV via wave.open into BytesIO; result must be parseable."""
    monkeypatch.setattr(engine, "get_voice_path", lambda lang: str(tmp_path / "v.onnx"))
    audio = engine.generate("hi", {"language": "en"})

    # Must be a real RIFF WAV that the wave module can open.
    with wave.open(io.BytesIO(audio), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 22050
