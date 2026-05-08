#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for engines/silerotts.py — Silero TTS via torch.hub.

Real `torch` is in the dev venv (CUDA initialisation may warn but import
succeeds), so the engine module loads. Tests stub torch.hub.load and
torchaudio.save so no model is fetched and no network is touched.
"""

import importlib
import sys
import types

import pytest

from libs.exceptions import EngineNotAvailableError, TTSException


def _make_fake_torch():
    """Minimal torch stand-in covering only what silerotts.py touches at runtime."""

    class _FakeHub:
        def load(self, **kw):  # overridden per-test
            raise NotImplementedError

        def set_dir(self, path):
            pass

    new_torch = types.ModuleType("torch")  # type: ignore[name-defined]
    new_torch.hub = _FakeHub()
    new_torch.device = lambda name: name  # 'cpu' string is fine for tests
    new_torch.__version__ = "2.6.0"
    return new_torch


def _make_fake_torchaudio():
    fake = types.ModuleType("torchaudio")  # type: ignore[name-defined]
    fake.save = lambda buf, tensor, sr, format: buf.write(b"")
    return fake


@pytest.fixture
def engine(monkeypatch):
    """Inject fake torch + torchaudio, then fresh-import engines.silerotts.

    Without this the real torchaudio fails dlopen on libcudart.so.11.
    """
    monkeypatch.setitem(sys.modules, "torch", _make_fake_torch())
    monkeypatch.setitem(sys.modules, "torchaudio", _make_fake_torchaudio())
    monkeypatch.delitem(sys.modules, "engines.silerotts", raising=False)
    return importlib.import_module("engines.silerotts")


# is_available


def test_is_available_reflects_module_flag(engine, monkeypatch):
    monkeypatch.setattr(engine, "AVAILABLE", True)
    assert engine.is_available() is True
    monkeypatch.setattr(engine, "AVAILABLE", False)
    assert engine.is_available() is False


# get_model_info — language → (model_id, speaker, sample_rate)


@pytest.mark.parametrize(
    "lang,expected_speaker",
    [
        ("ru", "aidar"),
        ("en", "en_0"),
        ("de", "bernd_ungerer"),
        ("es", "es_0"),
        ("fr", "fr_0"),
        ("ua", "mykyta"),
        ("uk", "mykyta"),  # alias for ua
    ],
)
def test_get_model_info_known_languages(engine, lang, expected_speaker):
    _model_id, speaker, sample_rate = engine.get_model_info(lang)
    assert speaker == expected_speaker
    assert sample_rate == 48000


def test_get_model_info_unknown_falls_back_to_english(engine):
    """Any unmapped language code must return the English model, not crash."""
    info = engine.get_model_info("xx_unknown")
    assert info == engine.get_model_info("en")


# get_models_directory


def test_models_dir_env_var_absolute(engine, monkeypatch, tmp_path):
    monkeypatch.setenv("SILEROTTS_MODELS", str(tmp_path / "abs"))
    assert engine.get_models_directory() == str(tmp_path / "abs")


def test_models_dir_env_var_relative_resolved_against_project(engine, monkeypatch):
    monkeypatch.setenv("SILEROTTS_MODELS", "models_subdir")
    result = engine.get_models_directory()
    assert result.endswith("models_subdir")


def test_models_dir_default_when_no_env_and_no_dotdir(engine, monkeypatch):
    """Without env var and without project-local .silerotts/ → torch hub default."""
    monkeypatch.delenv("SILEROTTS_MODELS", raising=False)
    monkeypatch.setattr(engine.os.path, "exists", lambda p: False)
    result = engine.get_models_directory()
    assert result.endswith(".cache/torch/hub")


# generate — error paths


def test_generate_raises_engine_not_available_when_flag_off(engine, monkeypatch):
    monkeypatch.setattr(engine, "AVAILABLE", False)
    with pytest.raises(EngineNotAvailableError, match="not available"):
        engine.generate("hi", {})


def test_generate_translates_no_module_error_to_engine_not_available(engine, monkeypatch):
    """A 'No module named X' inside generate must surface as EngineNotAvailableError,
    not TTSException — actionable diagnostic for the user."""
    monkeypatch.setattr(engine, "AVAILABLE", True)
    monkeypatch.setattr(
        engine.torch.hub, "load", lambda **kw: (_ for _ in ()).throw(ImportError("No module named 'silero_helpers'"))
    )

    with pytest.raises(EngineNotAvailableError, match="dependencies missing"):
        engine.generate("hi", {"language": "en"})


def test_generate_translates_model_not_found_to_tts_exception(engine, monkeypatch):
    monkeypatch.setattr(engine, "AVAILABLE", True)

    def boom(**kw):
        raise RuntimeError("model checkpoint not found in cache")

    monkeypatch.setattr(engine.torch.hub, "load", boom)
    with pytest.raises(TTSException, match="model not found"):
        engine.generate("hi", {"language": "en"})


def test_generate_unexpected_hub_result_shape_raises(engine, monkeypatch):
    """torch.hub.load that returns a non-tuple must raise TTSException
    instead of crashing on tuple-unpacking."""
    monkeypatch.setattr(engine, "AVAILABLE", True)
    monkeypatch.setattr(engine.torch.hub, "load", lambda **kw: "single_value_not_tuple")
    with pytest.raises(TTSException):
        engine.generate("hi", {"language": "en"})


def test_generate_model_without_apply_tts_raises(engine, monkeypatch):
    """Wrong model object (no apply_tts attr) → TTSException with hint."""

    class StubModel:
        def to(self, device):
            return None

    monkeypatch.setattr(engine, "AVAILABLE", True)
    monkeypatch.setattr(engine.torch.hub, "load", lambda **kw: (StubModel(), "example"))
    with pytest.raises(TTSException, match="apply_tts"):
        engine.generate("hi", {"language": "en"})


# generate — happy path


def test_generate_returns_bytes_from_torchaudio_save(engine, monkeypatch):
    """End-to-end stubbed pipeline: torch.hub.load → model.apply_tts →
    torchaudio.save into BytesIO → returned as bytes."""
    captured = {}

    class StubTensor:
        def dim(self):
            return 1

        def unsqueeze(self, dim):
            return self  # no-op

    class StubModel:
        def to(self, device):
            return None

        def apply_tts(self, text, speaker, sample_rate):
            captured.update(text=text, speaker=speaker, sample_rate=sample_rate)
            return StubTensor()

    monkeypatch.setattr(engine, "AVAILABLE", True)
    monkeypatch.setattr(engine.torch.hub, "load", lambda **kw: (StubModel(), "example"))

    def fake_save(buf, tensor, sr, format):
        buf.write(b"RIFFFAKEWAV")

    monkeypatch.setattr(engine.torchaudio, "save", fake_save)

    audio = engine.generate("hello", {"language": "ru"})
    assert audio == b"RIFFFAKEWAV"
    # Russian must use 'aidar' speaker at 48kHz (per the language map).
    assert captured["speaker"] == "aidar"
    assert captured["sample_rate"] == 48000
    assert captured["text"] == "hello"


def test_generate_unsqueezes_1d_tensor_into_2d(engine, monkeypatch):
    """If apply_tts returns a 1D tensor, generate must call unsqueeze(0)
    before handing it to torchaudio.save (which expects [channels, samples])."""
    unsqueezed = {"called": False}

    class Tensor1D:
        def dim(self):
            return 1

        def unsqueeze(self, dim):
            unsqueezed["called"] = True
            unsqueezed["dim_arg"] = dim
            return self

    class StubModel:
        def to(self, device):
            return None

        def apply_tts(self, **kw):
            return Tensor1D()

    monkeypatch.setattr(engine, "AVAILABLE", True)
    monkeypatch.setattr(engine.torch.hub, "load", lambda **kw: (StubModel(), "ex"))
    monkeypatch.setattr(engine.torchaudio, "save", lambda buf, t, sr, format: buf.write(b"x"))

    engine.generate("hi", {"language": "en"})
    assert unsqueezed["called"] is True
    assert unsqueezed["dim_arg"] == 0
