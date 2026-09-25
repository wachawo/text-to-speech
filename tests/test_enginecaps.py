#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the engine discovery helpers: models, default models, languages and capabilities."""

import logging
import types

import pytest

# Local imports
import engines as engines_pkg
from engines import (
    get_engine_capabilities,
    get_engine_default_model,
    get_engine_languages,
    get_engine_models,
    get_engine_voices,
    list_engine_models,
)


def use_fake_engine(monkeypatch, fake):
    """Make every engine name resolve to the fake module."""
    monkeypatch.setattr(engines_pkg, "get_engine_module", lambda name: fake)


def fake_engine_with_hooks():
    """A fake engine with two models: 'big' serves en and de, 'ru-model' serves ru."""
    models = [
        {"id": "big", "languages": ["en", "de"], "installed": True},
        {"id": "ru-model", "languages": ["ru"], "installed": False},
    ]
    defaults = {"en": "big", "de": "big", "ru": "ru-model"}
    return types.SimpleNamespace(
        list_models=lambda: models,
        default_model=lambda language=None: defaults.get(language) if language else None,
        list_languages=lambda model=None: ["de", "en", "ru"] if model is None else ["en", "de"],
        list_voices=lambda language, model=None: {"voices": [], "default": None},
        OUTPUT_FORMAT="mp3",
        MAX_TEXT_LENGTH=5000,
    )


def test_capabilities_of_an_engine_without_hooks(monkeypatch):
    """No hooks: no models, no default model, languages not declared, WAV output."""
    use_fake_engine(monkeypatch, types.SimpleNamespace())
    caps = get_engine_capabilities("fake")
    assert caps == {
        "models": [],
        "default_model": None,
        "model_selectable": False,
        "languages": None,
        "voice_selectable": False,
        "output_format": "wav",
        "max_text_length": None,
    }


def test_capabilities_of_an_engine_with_hooks(monkeypatch):
    """default_for lists the declared languages whose requests use each model without naming one."""
    use_fake_engine(monkeypatch, fake_engine_with_hooks())
    caps = get_engine_capabilities("fake")
    assert caps is not None
    assert caps["models"] == [
        {"id": "big", "languages": ["en", "de"], "installed": True, "default_for": ["de", "en"]},
        {"id": "ru-model", "languages": ["ru"], "installed": False, "default_for": ["ru"]},
    ]
    assert caps["default_model"] is None
    assert caps["model_selectable"] is True
    assert caps["languages"] == ["de", "en", "ru"]
    assert caps["voice_selectable"] is True
    assert caps["output_format"] == "mp3"
    assert caps["max_text_length"] == 5000


def test_capabilities_do_not_change_the_hook_result(monkeypatch):
    """default_for is added to copies, so a hook returning a module-level list is not modified."""
    fake = fake_engine_with_hooks()
    use_fake_engine(monkeypatch, fake)
    get_engine_capabilities("fake")
    assert "default_for" not in fake.list_models()[0]


def test_capabilities_none_for_unknown_engine():
    """No engines/<name>.py, a name that is not a module stem, or the package file itself: None."""
    assert get_engine_capabilities("definitely_not_a_real_engine_xyz") is None
    assert get_engine_capabilities("../libs") is None
    assert get_engine_capabilities("__init__") is None


def test_capabilities_of_a_broken_engine_raise(monkeypatch):
    """A shipped module that fails to import is broken, not unknown: the error propagates instead of None."""

    def broken_import(name):
        """Fail like an engine module with a syntax error."""
        raise ImportError("broken engine module")

    monkeypatch.setattr(engines_pkg, "get_engine_module", broken_import)
    with pytest.raises(ImportError, match="broken engine module"):
        get_engine_capabilities("kokorotts")


def test_list_engine_models_raises_where_get_engine_models_logs(monkeypatch, caplog):
    """list_engine_models lets a failing hook raise; get_engine_models logs it and answers []."""
    fake = fake_engine_with_hooks()

    def unreadable():
        """Fail like a models directory without read permission."""
        raise PermissionError(13, "Permission denied")

    fake.list_models = unreadable
    use_fake_engine(monkeypatch, fake)
    with pytest.raises(PermissionError):
        list_engine_models("fake")
    with caplog.at_level(logging.WARNING, logger="engines"):
        assert get_engine_models("fake") == []
    assert "list_models failed: PermissionError" in caplog.text


@pytest.mark.parametrize("hook", ["list_models", "default_model", "list_languages"])
def test_failing_hook_is_logged_and_left_out(monkeypatch, caplog, hook):
    """A hook that raises is logged as a warning with the exception type; its part is [] or None."""
    fake = fake_engine_with_hooks()

    def broken(*args, **kwargs):
        """Fail like a hook reading a corrupt directory."""
        raise RuntimeError("directory unreadable")

    setattr(fake, hook, broken)
    use_fake_engine(monkeypatch, fake)
    with caplog.at_level(logging.WARNING, logger="engines"):
        caps = get_engine_capabilities("fake")
    assert caps is not None
    assert f"{hook} failed: RuntimeError: directory unreadable" in caplog.text
    if hook == "list_models":
        assert caps["models"] == [] and caps["model_selectable"] is False
    elif hook == "default_model":
        assert caps["default_model"] is None
        assert all(model["default_for"] == [] for model in caps["models"])
    else:
        assert caps["languages"] is None


def test_get_engine_models_and_default_model(monkeypatch):
    """The helpers hand back the hook results."""
    use_fake_engine(monkeypatch, fake_engine_with_hooks())
    assert [model["id"] for model in get_engine_models("fake")] == ["big", "ru-model"]
    assert get_engine_default_model("fake", "ru") == "ru-model"
    assert get_engine_default_model("fake") is None


def test_get_engine_languages_passes_the_model(monkeypatch):
    """With a model the hook is asked about that model."""
    use_fake_engine(monkeypatch, fake_engine_with_hooks())
    assert get_engine_languages("fake", "big") == ["en", "de"]


def test_get_engine_voices_without_model_keeps_the_one_argument_call(monkeypatch):
    """A list_voices(language) hook without a model parameter still works when no model is asked for."""
    calls = []

    def list_voices(language):
        """Record the call; takes exactly one argument like the engines before models."""
        calls.append(language)
        return {"voices": ["a"], "default": "a"}

    use_fake_engine(monkeypatch, types.SimpleNamespace(list_voices=list_voices))
    assert get_engine_voices("fake", "ru") == {"voices": ["a"], "default": "a"}
    assert calls == ["ru"]


def test_get_engine_voices_passes_the_model(monkeypatch):
    """With a model, list_voices gets it as the second argument."""
    calls = []

    def list_voices(language, model=None):
        """Record the call."""
        calls.append((language, model))
        return {"voices": [], "default": None}

    use_fake_engine(monkeypatch, types.SimpleNamespace(list_voices=list_voices))
    get_engine_voices("fake", "en", "big")
    assert calls == [("en", "big")]


# Discovery on the shipped engines never loads a model


def refuse_to_load(*args, **kwargs):
    """Fail the test: discovery must not load a model."""
    raise AssertionError("a model loader was called during discovery")


@pytest.fixture
def model_dirs(monkeypatch, tmp_path):
    """Point every engine at a tmp models directory holding one model or voice each."""
    piper_dir = tmp_path / "piper"
    piper_dir.mkdir()
    (piper_dir / "en_US-lessac-medium.onnx").write_bytes(b"x")
    kokoro_dir = tmp_path / "kokoro"
    kokoro_dir.mkdir()
    (kokoro_dir / "kokoro-v1.0.onnx").write_bytes(b"x")
    coqui_dir = tmp_path / "coqui"
    (coqui_dir / "tts" / "tts_models--de--thorsten--vits").mkdir(parents=True)
    silero_dir = tmp_path / "silero"
    silero_dir.mkdir()
    (silero_dir / "v3_en.pt").write_bytes(b"x")
    monkeypatch.setenv("PIPERTTS_MODELS", str(piper_dir))
    monkeypatch.setenv("KOKOROTTS_MODELS", str(kokoro_dir))
    monkeypatch.setenv("COQUITTS_MODELS", str(coqui_dir))
    monkeypatch.setenv("SILEROTTS_MODELS", str(silero_dir))
    for name in ("KOKOROTTS_MODEL", "KOKOROTTS_VOICES", "COQUITTS_MODEL"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize(
    ("engine", "loaders", "expected_model"),
    [
        ("kokorotts", ["get_kokoro"], "kokoro-v1.0.onnx"),
        ("pipertts", ["get_voice"], "en_US-lessac-medium"),
        ("silerotts", ["load_model"], "v3_en"),
        ("coquitts", ["get_tts"], "tts_models/de/thorsten/vits"),
    ],
)
def test_discovery_of_shipped_engines_never_loads_a_model(monkeypatch, model_dirs, engine, loaders, expected_model):
    """get_engine_capabilities reads the real engines with every loader replaced by one that fails."""
    module = engines_pkg.get_engine_module(engine)
    assert module is not None
    for loader in loaders:
        monkeypatch.setattr(module, loader, refuse_to_load)
    torch = getattr(module, "torch", None)
    if torch is not None and hasattr(torch, "hub"):
        monkeypatch.setattr(torch.hub, "load", refuse_to_load)
    caps = get_engine_capabilities(engine)
    assert caps is not None
    assert caps["model_selectable"] is True
    assert expected_model in [model["id"] for model in caps["models"]]
    installed = {model["id"]: model["installed"] for model in caps["models"]}
    assert installed[expected_model] is True
