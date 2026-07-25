#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for engines/kokorotts.py, the offline kokoro-onnx engine.

`kokoro_onnx` and `soundfile` are faked so the engine loads without the
actual ONNX runtime or native libsndfile.
"""

import array
import importlib
import io
import os
import sys
import types
import wave

import pytest

from libs.exceptions import EngineNotAvailableError, TTSException, ValidationError


def make_fake_kokoro_onnx():
    """Fake `kokoro_onnx` module exposing a no-op `Kokoro` class."""
    fake = types.ModuleType("kokoro_onnx")

    class FakeKokoro:
        """Stand-in for kokoro_onnx.Kokoro that returns silence instead of running ONNX."""

        def __init__(self, model_path, voices_path):
            """Remember the model and voice bundle paths the engine resolved."""
            self.model_path = model_path
            self.voices_path = voices_path

        def create(self, text, voice, speed, lang):
            """Return a fixed block of silent samples and the sample rate."""
            # Return 2400 zero samples, about 0.1s at 24000 Hz mono.
            return array.array("h", [0] * 2400), 24000

    fake.Kokoro = FakeKokoro
    return fake


def make_fake_soundfile():
    """Fake `soundfile.write` that emits a valid minimal WAV blob."""
    fake = types.ModuleType("soundfile")

    def write(buf, samples, sample_rate, format="WAV", subtype="PCM_16"):
        """Write `samples` as a 16-bit mono WAV into a buffer or a path."""
        # Real soundfile writes to BytesIO when first arg is a buffer.
        # We emulate by writing a tiny but valid WAV via the stdlib.
        target = buf if hasattr(buf, "write") else open(buf, "wb")
        try:
            with wave.open(target, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sample_rate)
                w.writeframes(b"\x00\x00" * len(samples))
        finally:
            if not hasattr(buf, "write"):
                target.close()

    fake.write = write
    return fake


@pytest.fixture
def engine(monkeypatch):
    """Import engines.kokorotts against the fake dependencies with an empty model cache."""
    monkeypatch.setitem(sys.modules, "kokoro_onnx", make_fake_kokoro_onnx())
    monkeypatch.setitem(sys.modules, "soundfile", make_fake_soundfile())
    monkeypatch.delitem(sys.modules, "engines.kokorotts", raising=False)
    mod = importlib.import_module("engines.kokorotts")
    # Reset the per-process model cache between tests.
    mod.KOKORO_CACHE.clear()
    return mod


# is_available


def test_is_available_true_with_both_deps(engine):
    """The engine advertises itself when kokoro_onnx and soundfile both import."""
    assert engine.is_available() is True


def test_is_available_false_without_soundfile(monkeypatch):
    """AVAILABLE must be False if soundfile is missing — not just kokoro_onnx."""
    monkeypatch.setitem(sys.modules, "kokoro_onnx", make_fake_kokoro_onnx())
    monkeypatch.setitem(sys.modules, "soundfile", None)  # forces ImportError on `import soundfile`
    monkeypatch.delitem(sys.modules, "engines.kokorotts", raising=False)
    mod = importlib.import_module("engines.kokorotts")
    assert mod.is_available() is False


# get_models_directory — three-priority resolution


def test_models_dir_env_var_absolute(engine, monkeypatch, tmp_path):
    """An absolute KOKOROTTS_MODELS path is used exactly as given."""
    target = tmp_path / "abs_kokoro"
    monkeypatch.setenv("KOKOROTTS_MODELS", str(target))
    assert engine.get_models_directory() == str(target)


def test_models_dir_env_var_relative_resolved_against_project(engine, monkeypatch):
    """A relative KOKOROTTS_MODELS path is anchored on the project root, not cwd."""
    monkeypatch.setenv("KOKOROTTS_MODELS", "custom_kokoro")
    result = engine.get_models_directory()
    assert result.endswith("custom_kokoro")
    # Must be anchored on the project root, not cwd.
    assert os.path.isabs(result)


def test_models_dir_falls_back_to_default_when_unset(engine, monkeypatch):
    """With no env var and no local cache directory, the XDG default path is used."""
    monkeypatch.delenv("KOKOROTTS_MODELS", raising=False)
    # Force-skip the cache/kokorotts branch.
    monkeypatch.setattr(engine.os.path, "isdir", lambda p: False)
    result = engine.get_models_directory()
    assert result.endswith(".local/share/ttsgen/kokorotts")


# get_model_paths


def test_get_model_paths_uses_defaults(engine, monkeypatch, tmp_path):
    """Without overrides the v1.0 model and voice bundle filenames are assumed."""
    monkeypatch.setenv("KOKOROTTS_MODELS", str(tmp_path))
    monkeypatch.delenv("KOKOROTTS_MODEL", raising=False)
    monkeypatch.delenv("KOKOROTTS_VOICES", raising=False)
    model, voices = engine.get_model_paths()
    assert model.endswith("kokoro-v1.0.onnx")
    assert voices.endswith("voices-v1.0.bin")


def test_get_model_paths_respects_overrides(engine, monkeypatch, tmp_path):
    """KOKOROTTS_MODEL and KOKOROTTS_VOICES replace the default filenames."""
    monkeypatch.setenv("KOKOROTTS_MODELS", str(tmp_path))
    monkeypatch.setenv("KOKOROTTS_MODEL", "custom.onnx")
    monkeypatch.setenv("KOKOROTTS_VOICES", "custom-voices.bin")
    model, voices = engine.get_model_paths()
    assert model.endswith("custom.onnx")
    assert voices.endswith("custom-voices.bin")


# get_download_instructions


def test_download_instructions_mentions_installer_and_files(engine, monkeypatch, tmp_path):
    """The help text names the installer command, both model files and the target directory."""
    monkeypatch.setenv("KOKOROTTS_MODELS", str(tmp_path))
    text = engine.get_download_instructions()
    assert "ttsgen --install kokorotts" in text
    assert "kokoro-v1.0.onnx" in text
    assert "voices-v1.0.bin" in text
    assert str(tmp_path) in text


# generate — error paths


def test_generate_raises_when_unavailable(engine, monkeypatch):
    """Synthesis refuses to run while the engine reports itself unavailable."""
    monkeypatch.setattr(engine, "AVAILABLE", False)
    with pytest.raises(EngineNotAvailableError):
        engine.generate("hi", {"language": "en"})


def test_generate_validates_max_text_length(engine):
    """Text beyond MAX_TEXT_LENGTH is rejected before any model is loaded."""
    with pytest.raises(ValidationError):
        engine.generate("x" * (engine.MAX_TEXT_LENGTH + 1), {"language": "en"})


def test_generate_raises_when_model_missing(engine, monkeypatch, tmp_path):
    """Absent model files produce an explanatory TTSException, not an ONNX crash."""
    monkeypatch.setenv("KOKOROTTS_MODELS", str(tmp_path))  # empty dir, no .onnx
    with pytest.raises(TTSException) as exc:
        engine.generate("hello", {"language": "en"})
    assert "Kokoro TTS model files not found" in str(exc.value)


# generate — happy path


def test_generate_returns_wav_bytes(engine, monkeypatch, tmp_path):
    """Synthesis returns parseable 24 kHz mono WAV bytes."""
    # Plant the expected model files so the missing-files check passes.
    (tmp_path / "kokoro-v1.0.onnx").write_bytes(b"fake-onnx")
    (tmp_path / "voices-v1.0.bin").write_bytes(b"fake-voices")
    monkeypatch.setenv("KOKOROTTS_MODELS", str(tmp_path))

    result = engine.generate("hello world", {"language": "en"})
    assert isinstance(result, bytes)
    # Must be a parseable WAV — header check + framerate echoed by the fake.
    with wave.open(io.BytesIO(result), "rb") as w:
        assert w.getframerate() == 24000
        assert w.getnchannels() == 1


def test_generate_caches_kokoro_instance(engine, monkeypatch, tmp_path):
    """Second call with same paths must reuse the cached Kokoro instance."""
    (tmp_path / "kokoro-v1.0.onnx").write_bytes(b"x")
    (tmp_path / "voices-v1.0.bin").write_bytes(b"x")
    monkeypatch.setenv("KOKOROTTS_MODELS", str(tmp_path))

    engine.generate("first", {"language": "en"})
    assert len(engine.KOKORO_CACHE) == 1
    cached_before = next(iter(engine.KOKORO_CACHE.values()))

    engine.generate("second", {"language": "en"})
    cached_after = next(iter(engine.KOKORO_CACHE.values()))
    assert cached_before is cached_after  # same instance, not reloaded


# LANGUAGE_MAP coverage


def test_language_map_has_expected_entries(engine):
    """All advertised languages from docs/KOKOROTTS.md must be in LANGUAGE_MAP."""
    for code in ("en", "fr", "it", "ja", "zh", "es", "hi", "pt"):
        assert code in engine.LANGUAGE_MAP
        lang_code, default_voice = engine.LANGUAGE_MAP[code]
        assert isinstance(lang_code, str) and lang_code
        assert isinstance(default_voice, str) and default_voice


def test_generate_unknown_language_falls_back_to_en(engine, monkeypatch, tmp_path):
    """An unmapped language code silently falls back to the English entry."""
    (tmp_path / "kokoro-v1.0.onnx").write_bytes(b"x")
    (tmp_path / "voices-v1.0.bin").write_bytes(b"x")
    monkeypatch.setenv("KOKOROTTS_MODELS", str(tmp_path))

    # Should not raise — unknown language falls back to LANGUAGE_MAP["en"].
    out = engine.generate("hi", {"language": "xx"})
    assert isinstance(out, bytes)
