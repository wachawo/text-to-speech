#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for engines/barktts.py — Suno Bark TTS.

Fakes `bark`, `numpy`, `scipy.io.wavfile`, and `torch` so the engine
loads without the actual ML stack. The tests pin language-to-speaker
mapping, model-dir resolution, and the GPU/memory error translation.
"""

import importlib
import sys
import types

import pytest

# Local imports
from libs.exceptions import EngineNotAvailableError, TTSException


def make_fake_bark():
    """Build a `bark` stand-in exposing the sample rate and generation entrypoints."""
    fake = types.ModuleType("bark")
    fake.SAMPLE_RATE = 24000
    fake.preload_models = lambda: None
    fake.generate_audio = lambda text, history_prompt=None, text_temp=0.7, waveform_temp=0.7: object()
    return fake


def make_fake_torch():
    """Build a `torch` stand-in with the serialization hook barktts touches."""
    fake = types.ModuleType("torch")
    fake.__version__ = "2.6.0"

    class FakeSerialization:
        """Minimal `torch.serialization` replacement."""

        @staticmethod
        def add_safe_globals(items):
            """Accept and ignore the safe-globals registration."""
            pass

    fake.serialization = FakeSerialization()
    return fake


def make_fake_scipy_wavfile():
    """`scipy.io.wavfile` exposes only `write(file, rate, data)` to barktts."""
    scipy = types.ModuleType("scipy")
    io_pkg = types.ModuleType("scipy.io")
    wavfile = types.ModuleType("scipy.io.wavfile")

    def fake_write(filename, rate, data):
        """Write a recognisable marker payload instead of encoding real audio."""
        with open(filename, "wb") as f:
            f.write(b"RIFFFAKEBARK")

    wavfile.write = fake_write
    io_pkg.wavfile = wavfile
    scipy.io = io_pkg
    return scipy, io_pkg, wavfile


@pytest.fixture
def engine(monkeypatch):
    """Import `engines.barktts` freshly against the fake ML stack."""
    monkeypatch.setitem(sys.modules, "bark", make_fake_bark())
    monkeypatch.setitem(sys.modules, "torch", make_fake_torch())
    scipy, io_pkg, wavfile = make_fake_scipy_wavfile()
    monkeypatch.setitem(sys.modules, "scipy", scipy)
    monkeypatch.setitem(sys.modules, "scipy.io", io_pkg)
    monkeypatch.setitem(sys.modules, "scipy.io.wavfile", wavfile)
    monkeypatch.delitem(sys.modules, "engines.barktts", raising=False)
    return importlib.import_module("engines.barktts")


# is_available


def test_is_available_true_with_fake_bark(engine):
    """With the bark dependency importable the engine reports itself usable."""
    assert engine.is_available() is True


def test_is_available_reflects_module_flag(engine, monkeypatch):
    """is_available mirrors the module-level AVAILABLE flag rather than re-probing."""
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
    """Each supported language code maps to its documented Bark speaker preset."""
    assert engine.get_speaker_for_language(lang) == expected


def test_speaker_unknown_language_falls_back_to_english(engine):
    """An unmapped language code resolves to the English preset instead of failing."""
    assert engine.get_speaker_for_language("xx") == engine.get_speaker_for_language("en")


# get_models_directory


def test_models_dir_env_var_absolute(engine, monkeypatch, tmp_path):
    """An absolute BARKTTS_MODELS value is used verbatim."""
    monkeypatch.setenv("BARKTTS_MODELS", str(tmp_path / "models"))
    assert engine.get_models_directory() == str(tmp_path / "models")


def test_models_dir_env_var_relative_resolved_against_project(engine, monkeypatch):
    """A relative BARKTTS_MODELS value is resolved against the project root."""
    monkeypatch.setenv("BARKTTS_MODELS", "rel_models")
    result = engine.get_models_directory()
    assert result.endswith("rel_models")


def test_models_dir_default_when_no_env_and_no_dotdir(engine, monkeypatch):
    """With no env var and no project cache dir, the Suno default cache path is used."""
    monkeypatch.delenv("BARKTTS_MODELS", raising=False)
    monkeypatch.setattr(engine.os.path, "exists", lambda p: False)
    result = engine.get_models_directory()
    assert result.endswith(".cache/suno/bark_v0")


# generate — error paths


def test_generate_raises_engine_not_available_when_flag_off(engine, monkeypatch):
    """Synthesis refuses to run while the engine is marked unavailable."""
    monkeypatch.setattr(engine, "AVAILABLE", False)
    with pytest.raises(EngineNotAvailableError, match="not available"):
        engine.generate("hi", {})


def test_generate_translates_missing_module_to_engine_not_available(engine, monkeypatch):
    """`No module named` inside generate must surface as
    EngineNotAvailableError with install instructions."""

    def boom():
        """Simulate a transitive dependency missing at model-load time."""
        raise ImportError("No module named 'numba'")

    monkeypatch.setattr(engine, "preload_models", boom)
    with pytest.raises(EngineNotAvailableError, match="dependencies missing"):
        engine.generate("hi", {})


def test_generate_translates_cuda_memory_error_to_tts_exception(engine, monkeypatch):
    """CUDA OOM must surface as TTSException with the GPU/memory hint —
    actionable, not a generic 'generation failed'."""

    def boom():
        """Simulate the CUDA out-of-memory failure raised while loading models."""
        raise RuntimeError("CUDA out of memory")

    monkeypatch.setattr(engine, "preload_models", boom)
    with pytest.raises(TTSException, match="GPU/memory"):
        engine.generate("hi", {})


def test_generate_other_failure_wrapped_as_tts_exception(engine, monkeypatch):
    """Any unrecognised runtime failure is wrapped in a generic TTSException."""

    def boom():
        """Simulate an unclassified model-load failure."""
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


def test_generate_writes_int16_pcm(engine, monkeypatch):
    """A float32 waveform from Bark is written as int16 PCM, the format the stdlib wave reader accepts."""
    import numpy as np

    written = {}

    def fake_write(filename, rate, data):
        """Record the dtype scipy would write and leave a file behind like the real one."""
        written["dtype"] = data.dtype
        written["peak"] = int(data.max())
        with open(filename, "wb") as handle:
            handle.write(b"RIFFFAKEBARK")

    monkeypatch.setattr(engine.scipy.io.wavfile, "write", fake_write)
    monkeypatch.setattr(engine, "generate_audio", lambda *a, **k: np.array([0.0, 0.5, 1.0, -2.0], dtype=np.float32))
    engine.generate("hello", {"language": "en"})
    assert written["dtype"] == np.int16
    assert written["peak"] == 32767


def test_generate_passes_correct_speaker_for_language(engine, monkeypatch):
    """The configured language selects the matching speaker preset for generation."""
    captured = {}

    def fake_generate_audio(text, history_prompt, text_temp, waveform_temp):
        """Record the speaker preset Bark was asked to use."""
        captured["history_prompt"] = history_prompt
        return object()

    monkeypatch.setattr(engine, "generate_audio", fake_generate_audio)
    engine.generate("privet", {"language": "ru"})
    assert captured["history_prompt"] == "v2/ru_speaker_0"


# Availability probe, import-time side effects and concurrency


def test_is_available_false_without_scipy(monkeypatch):
    """generate() needs scipy to encode the WAV, so a missing scipy makes the engine unavailable."""
    monkeypatch.setitem(sys.modules, "bark", make_fake_bark())
    monkeypatch.setitem(sys.modules, "torch", make_fake_torch())
    monkeypatch.setitem(sys.modules, "scipy", None)  # forces ImportError on `import scipy.io.wavfile`
    monkeypatch.delitem(sys.modules, "scipy.io", raising=False)
    monkeypatch.delitem(sys.modules, "scipy.io.wavfile", raising=False)
    monkeypatch.delitem(sys.modules, "engines.barktts", raising=False)
    mod = importlib.import_module("engines.barktts")
    assert mod.is_available() is False


def raise_on_call(*args, **kwargs):
    """Fail the test: the patched config loader must never run at engine import."""
    raise AssertionError("config loading must not happen at engine import time")


def test_import_does_not_load_config(engine, monkeypatch):
    """Importing the engine neither calls libs.config.load_config nor dotenv.load_dotenv."""
    import dotenv

    import libs.config

    monkeypatch.setattr(libs.config, "load_config", raise_on_call)
    monkeypatch.setattr(dotenv, "load_dotenv", raise_on_call)
    monkeypatch.setattr(dotenv, "find_dotenv", raise_on_call)
    importlib.reload(engine)


def test_generate_does_not_touch_environment(engine, monkeypatch, tmp_path):
    """A custom BARKTTS_MODELS no longer rewrites XDG_CACHE_HOME (Bark read it at import anyway)."""
    import os

    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setenv("BARKTTS_MODELS", str(tmp_path / "weights"))
    engine.generate("hello", {"language": "en"})
    assert "XDG_CACHE_HOME" not in os.environ


def test_safe_globals_registered_without_numpy_core_warning(engine, monkeypatch):
    """The torch safe-globals fix reaches numpy's scalar without the deprecated numpy.core alias."""
    import warnings

    registered = []
    torch = sys.modules["torch"]
    monkeypatch.setattr(torch.serialization, "add_safe_globals", lambda items: registered.extend(items))
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        engine.generate("hello", {"language": "en"})
    assert engine.np.dtype in registered
    assert any(getattr(item, "__name__", "") == "scalar" for item in registered)


def run_threads(target, count=4):
    """Start `count` threads on `target` and wait for all of them."""
    import threading

    threads = [threading.Thread(target=target) for unused in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def test_concurrent_first_load_preloads_once(engine, monkeypatch):
    """Four threads generating at once call preload_models exactly once."""
    import time

    preloads = []

    def slow_preload():
        """Record the call and sleep so concurrent callers pile up."""
        preloads.append(1)
        time.sleep(0.05)

    monkeypatch.setattr(engine, "preload_models", slow_preload)
    run_threads(lambda: engine.generate("hi", {"language": "en"}))
    assert len(preloads) == 1
    assert engine.MODELS_PRELOADED is True


def test_inference_is_serialised(engine, monkeypatch):
    """generate_audio never overlaps: with four threads the fake sees at most one caller inside."""
    import threading
    import time

    state = {"inside": 0, "overlap": 0, "calls": 0}
    guard = threading.Lock()

    def overlapping_generate_audio(text, history_prompt=None, text_temp=0.7, waveform_temp=0.7):
        """Track concurrent entries, then return a placeholder waveform."""
        with guard:
            state["inside"] += 1
            state["calls"] += 1
            if state["inside"] > 1:
                state["overlap"] += 1
        time.sleep(0.02)
        with guard:
            state["inside"] -= 1
        return object()

    monkeypatch.setattr(engine, "generate_audio", overlapping_generate_audio)
    run_threads(lambda: engine.generate("hi", {"language": "en"}))
    assert state["calls"] == 4
    assert state["overlap"] == 0
