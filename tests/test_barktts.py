#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for engines/barktts.py — Suno Bark TTS.

Fakes `bark`, `numpy`, `scipy.io.wavfile`, and `torch` so the engine
loads without the actual ML stack. The tests pin language→speaker
mapping, model-dir resolution, and the GPU/memory error translation.
"""

import importlib
import sys
import types

import pytest

from libs.exceptions import EngineNotAvailableError, TTSException


def _make_fake_bark():
    fake = types.ModuleType("bark")
    fake.SAMPLE_RATE = 24000
    fake.preload_models = lambda: None
    fake.generate_audio = lambda text, history_prompt=None, text_temp=0.7, waveform_temp=0.7: object()
    return fake


def _make_fake_torch():
    fake = types.ModuleType("torch")
    fake.__version__ = "2.6.0"

    class _FakeSerialization:
        @staticmethod
        def add_safe_globals(items):
            pass

    fake.serialization = _FakeSerialization()
    return fake


def _make_fake_scipy_wavfile():
    """`scipy.io.wavfile` exposes only `write(file, rate, data)` to barktts."""
    scipy = types.ModuleType("scipy")
    io_pkg = types.ModuleType("scipy.io")
    wavfile = types.ModuleType("scipy.io.wavfile")

    def fake_write(filename, rate, data):
        with open(filename, "wb") as f:
            f.write(b"RIFFFAKEBARK")

    wavfile.write = fake_write
    io_pkg.wavfile = wavfile
    scipy.io = io_pkg
    return scipy, io_pkg, wavfile


@pytest.fixture
def engine(monkeypatch):
    monkeypatch.setitem(sys.modules, "bark", _make_fake_bark())
    monkeypatch.setitem(sys.modules, "torch", _make_fake_torch())
    scipy, io_pkg, wavfile = _make_fake_scipy_wavfile()
    monkeypatch.setitem(sys.modules, "scipy", scipy)
    monkeypatch.setitem(sys.modules, "scipy.io", io_pkg)
    monkeypatch.setitem(sys.modules, "scipy.io.wavfile", wavfile)
    monkeypatch.delitem(sys.modules, "engines.barktts", raising=False)
    return importlib.import_module("engines.barktts")


# is_available


def test_is_available_true_with_fake_bark(engine):
    assert engine.is_available() is True


def test_is_available_reflects_module_flag(engine, monkeypatch):
    monkeypatch.setattr(engine, "AVAILABLE", False)
    assert engine.is_available() is False


# get_speaker_for_language — preset map


@pytest.mark.parametrize(
    "lang,expected",
    [
        ("en", "v2/en_speaker_6"),
        ("ru", "v2/ru_speaker_0"),
        ("es", "v2/es_speaker_0"),
        ("zh", "v2/zh_speaker_0"),
        ("ja", "v2/ja_speaker_0"),
    ],
)
def test_speaker_for_known_language(engine, lang, expected):
    assert engine.get_speaker_for_language(lang) == expected


def test_speaker_unknown_language_falls_back_to_english(engine):
    assert engine.get_speaker_for_language("xx") == engine.get_speaker_for_language("en")


# get_models_directory


def test_models_dir_env_var_absolute(engine, monkeypatch, tmp_path):
    monkeypatch.setenv("BARKTTS_MODELS", str(tmp_path / "models"))
    assert engine.get_models_directory() == str(tmp_path / "models")


def test_models_dir_env_var_relative_resolved_against_project(engine, monkeypatch):
    monkeypatch.setenv("BARKTTS_MODELS", "rel_models")
    result = engine.get_models_directory()
    assert result.endswith("rel_models")


def test_models_dir_default_when_no_env_and_no_dotdir(engine, monkeypatch):
    monkeypatch.delenv("BARKTTS_MODELS", raising=False)
    monkeypatch.setattr(engine.os.path, "exists", lambda p: False)
    result = engine.get_models_directory()
    assert result.endswith(".cache/suno/bark_v0")


# generate — error paths


def test_generate_raises_engine_not_available_when_flag_off(engine, monkeypatch):
    monkeypatch.setattr(engine, "AVAILABLE", False)
    with pytest.raises(EngineNotAvailableError, match="not available"):
        engine.generate("hi", {})


def test_generate_translates_missing_module_to_engine_not_available(engine, monkeypatch):
    """`No module named` inside generate must surface as
    EngineNotAvailableError with install instructions."""

    def boom():
        raise ImportError("No module named 'numba'")

    monkeypatch.setattr(engine, "preload_models", boom)
    with pytest.raises(EngineNotAvailableError, match="dependencies missing"):
        engine.generate("hi", {})


def test_generate_translates_cuda_memory_error_to_tts_exception(engine, monkeypatch):
    """CUDA OOM must surface as TTSException with the GPU/memory hint —
    actionable, not a generic 'generation failed'."""

    def boom():
        raise RuntimeError("CUDA out of memory")

    monkeypatch.setattr(engine, "preload_models", boom)
    with pytest.raises(TTSException, match="GPU/memory"):
        engine.generate("hi", {})


def test_generate_other_failure_wrapped_as_tts_exception(engine, monkeypatch):
    def boom():
        raise RuntimeError("something else")

    monkeypatch.setattr(engine, "preload_models", boom)
    with pytest.raises(TTSException, match="generation failed"):
        engine.generate("hi", {})


# generate — happy path


def test_generate_writes_wav_file_and_returns_bytes(engine, monkeypatch):
    """Full stubbed pipeline: preload_models → generate_audio → scipy.write
    → file read → bytes returned. We just verify the bytes round-trip."""
    audio = engine.generate("hello", {"language": "en"})
    assert audio == b"RIFFFAKEBARK"


def test_generate_passes_correct_speaker_for_language(engine, monkeypatch):
    captured = {}

    def fake_generate_audio(text, history_prompt, text_temp, waveform_temp):
        captured["history_prompt"] = history_prompt
        return object()

    monkeypatch.setattr(engine, "generate_audio", fake_generate_audio)
    engine.generate("привет", {"language": "ru"})
    assert captured["history_prompt"] == "v2/ru_speaker_0"
