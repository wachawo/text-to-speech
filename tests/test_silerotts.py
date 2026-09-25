#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for engines/silerotts.py — Silero TTS via torch.hub.

Real `torch` is in the dev venv (CUDA initialisation may warn but import
succeeds), so the engine module loads. Tests stub torch.hub.load (and inject a
fake torchaudio) so no model is fetched and no network is touched.
"""

import importlib
import io
import sys
import types
import wave

import numpy as np
import pytest

from libs.exceptions import EngineNotAvailableError, TTSException, ValidationError


def make_fake_torch():
    """Minimal torch stand-in covering only what silerotts.py touches at runtime."""

    class FakeHub:
        """Replacement for torch.hub whose load() each test overrides."""

        def load(self, **kw):
            """Fail loudly unless a test has swapped in its own loader."""
            raise NotImplementedError

        def __init__(self):
            """Start with the torch default hub directory."""
            self.dir = "~/.cache/torch/hub"

        def set_dir(self, path):
            """Record the hub cache directory."""
            self.dir = path

        def get_dir(self):
            """Return the recorded hub cache directory."""
            return self.dir

    new_torch = types.ModuleType("torch")  # type: ignore[name-defined]
    new_torch.hub = FakeHub()
    new_torch.device = lambda name: name  # 'cpu' string is fine for tests
    new_torch.__version__ = "2.6.0"
    return new_torch


def make_fake_torchaudio():
    """Return a torchaudio stand-in whose save() writes nothing, avoiding a real dlopen."""
    fake = types.ModuleType("torchaudio")  # type: ignore[name-defined]
    fake.save = lambda buf, tensor, sr, format: buf.write(b"")
    return fake


@pytest.fixture
def engine(monkeypatch):
    """Inject fake torch + torchaudio, then fresh-import engines.silerotts.

    Without this the real torchaudio fails dlopen on libcudart.so.11.
    """
    monkeypatch.setitem(sys.modules, "torch", make_fake_torch())
    monkeypatch.setitem(sys.modules, "torchaudio", make_fake_torchaudio())
    monkeypatch.delitem(sys.modules, "engines.silerotts", raising=False)
    return importlib.import_module("engines.silerotts")


# is_available


def test_is_available_reflects_module_flag(engine, monkeypatch):
    """Availability tracks the module-level AVAILABLE flag in both directions."""
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
    """Each mapped language yields a model id, its default speaker and a 48 kHz rate."""
    model_id, speaker, sample_rate = engine.get_model_info(lang)
    assert isinstance(model_id, str) and model_id
    assert speaker == expected_speaker
    assert sample_rate == 48000


def test_get_model_info_unknown_falls_back_to_english(engine):
    """An unmapped language code returns the English model instead of raising."""
    info = engine.get_model_info("xx_unknown")
    assert info == engine.get_model_info("en")


@pytest.mark.parametrize("lang,expected", [("ru-ru", "ru"), ("de_AT", "de"), ("uk-ua", "uk")])
def test_get_model_info_tag_uses_primary_subtag(engine, lang, expected):
    """A tag such as 'ru-ru' picks the model of its primary subtag instead of falling back to English."""
    assert engine.get_model_info(lang) == engine.get_model_info(expected)


def test_list_languages_are_the_mapped_languages(engine, monkeypatch):
    """list_languages() declares the mapped languages without touching torch.hub."""

    def fail_hub_load(**kwargs):
        """Fail the test: declaring languages must not load a model."""
        raise AssertionError("list_languages must not load a model")

    monkeypatch.setattr(engine.torch.hub, "load", fail_hub_load)
    assert engine.list_languages() == ["de", "en", "es", "fr", "ru", "ua", "uk"]


def test_model_catalog_covers_every_language_default(engine):
    """Every language default names a catalogued model, so get_model_info never raises KeyError."""
    for model_id in engine.LANGUAGE_DEFAULT_MODELS.values():
        assert model_id in engine.MODEL_CATALOG


# load_model - torch.hub language key


@pytest.mark.parametrize(
    "lang,expected_hub_language,expected_model",
    [
        ("uk", "ua", "v3_ua"),  # the alias used to reach the hub as 'en'
        ("ua", "ua", "v3_ua"),
        ("ru", "ru", "v3_1_ru"),
        ("de", "de", "v3_de"),
        ("xx", "en", "v3_en"),  # unknown language keeps the English fallback
    ],
)
def test_load_model_passes_hub_language_of_the_model(engine, monkeypatch, lang, expected_hub_language, expected_model):
    """torch.hub.load gets the silero-models language key that holds the model, not the request language."""
    calls = []

    def recording_load(**kw):
        """Record the hub arguments and return a stub model."""
        calls.append(kw)
        return VoiceStubModel(["mykyta"]), "example"

    monkeypatch.setattr(engine, "AVAILABLE", True)
    monkeypatch.setattr(engine.torch.hub, "load", recording_load)
    engine.load_model(lang)
    assert len(calls) == 1
    assert calls[0]["language"] == expected_hub_language
    assert calls[0]["speaker"] == expected_model


def test_generate_uk_on_fresh_process_uses_ukrainian_model(engine, monkeypatch):
    """A first request in 'uk' loads v3_ua under the 'ua' key and speaks with its default speaker."""
    calls = []
    model = VoiceStubModel(["mykyta"])

    def recording_load(**kw):
        """Record the hub arguments and hand back the Ukrainian stub model."""
        calls.append(kw)
        return model, "example"

    monkeypatch.setattr(engine, "AVAILABLE", True)
    monkeypatch.setattr(engine.torch.hub, "load", recording_load)
    engine.TTS_CACHE.clear()
    audio = engine.generate("pryvit", {"language": "uk"})
    assert audio[:4] == b"RIFF"
    assert [(call["language"], call["speaker"]) for call in calls] == [("ua", "v3_ua")]
    assert model.captured["speaker"] == "mykyta"


# get_models_directory


def test_models_dir_env_var_absolute(engine, monkeypatch, tmp_path):
    """An absolute SILEROTTS_MODELS value is used verbatim."""
    monkeypatch.setenv("SILEROTTS_MODELS", str(tmp_path / "abs"))
    assert engine.get_models_directory() == str(tmp_path / "abs")


def test_models_dir_env_var_relative_resolved_against_project(engine, monkeypatch):
    """A relative SILEROTTS_MODELS value is resolved into an absolute project path."""
    monkeypatch.setenv("SILEROTTS_MODELS", "models_subdir")
    result = engine.get_models_directory()
    assert result.endswith("models_subdir")


def test_models_dir_default_when_no_env_and_no_dotdir(engine, monkeypatch):
    """With no env var and no project-local cache, the torch hub default directory is used."""
    monkeypatch.delenv("SILEROTTS_MODELS", raising=False)
    monkeypatch.setattr(engine.os.path, "exists", lambda p: False)
    result = engine.get_models_directory()
    assert result.endswith(".cache/torch/hub")


# generate — error paths


def test_generate_raises_engine_not_available_when_flag_off(engine, monkeypatch):
    """Synthesising with AVAILABLE cleared raises EngineNotAvailableError."""
    monkeypatch.setattr(engine, "AVAILABLE", False)
    with pytest.raises(EngineNotAvailableError, match="not available"):
        engine.generate("hi", {})


def test_generate_translates_no_module_error_to_engine_not_available(engine, monkeypatch):
    """A missing-module ImportError becomes EngineNotAvailableError, the actionable diagnostic."""
    monkeypatch.setattr(engine, "AVAILABLE", True)
    monkeypatch.setattr(
        engine.torch.hub,
        "load",
        lambda **kw: (unused for unused in ()).throw(ImportError("No module named 'silero_helpers'")),
    )

    with pytest.raises(EngineNotAvailableError, match="dependencies missing"):
        engine.generate("hi", {"language": "en"})


def test_generate_translates_model_not_found_to_tts_exception(engine, monkeypatch):
    """A missing model checkpoint is reported as TTSException, not a raw RuntimeError."""
    monkeypatch.setattr(engine, "AVAILABLE", True)

    def boom(**kw):
        """Fail the way torch.hub does when the checkpoint is absent."""
        raise RuntimeError("model checkpoint not found in cache")

    monkeypatch.setattr(engine.torch.hub, "load", boom)
    with pytest.raises(TTSException, match="model not found"):
        engine.generate("hi", {"language": "en"})


def test_generate_unexpected_hub_result_shape_raises(engine, monkeypatch):
    """A non-tuple return from torch.hub.load raises TTSException instead of an unpacking error."""
    monkeypatch.setattr(engine, "AVAILABLE", True)
    monkeypatch.setattr(engine.torch.hub, "load", lambda **kw: "single_value_not_tuple")
    with pytest.raises(TTSException):
        engine.generate("hi", {"language": "en"})


def test_generate_model_without_apply_tts_raises(engine, monkeypatch):
    """A model object lacking apply_tts raises TTSException naming the missing method."""

    class StubModel:
        """Model stand-in that deliberately omits apply_tts."""

        def to(self, device):
            """Accept the device move and return nothing, like the real API."""
            return None

    monkeypatch.setattr(engine, "AVAILABLE", True)
    monkeypatch.setattr(engine.torch.hub, "load", lambda **kw: (StubModel(), "example"))
    with pytest.raises(TTSException, match="apply_tts"):
        engine.generate("hi", {"language": "en"})


# generate — happy path


def test_generate_returns_wav_bytes(engine, monkeypatch):
    """The stubbed hub → apply_tts → wave pipeline yields a valid WAV at the language's rate."""
    captured = {}

    class StubTensor:
        """Stand-in for a Silero waveform; supports the chain generate() calls."""

        def __init__(self, arr):
            """Wrap the numpy array this stub waveform stands for."""
            self.arr = arr

        def squeeze(self):
            """Return a new stub holding the squeezed array."""
            return StubTensor(np.squeeze(self.arr))

        def detach(self):
            """Return self — there is no autograd graph to detach from."""
            return self

        def cpu(self):
            """Return self — the stub is always on the host already."""
            return self

        def numpy(self):
            """Return the wrapped numpy array."""
            return self.arr

    class StubModel:
        """Silero model stand-in that records the synthesis arguments it received."""

        def to(self, device):
            """Accept the device move and return nothing, like the real API."""
            return None

        def apply_tts(self, text, speaker, sample_rate):
            """Record the arguments and return a fixed 480-sample waveform."""
            captured.update(text=text, speaker=speaker, sample_rate=sample_rate)
            return StubTensor(np.linspace(-0.5, 0.5, 480, dtype="float32"))

    monkeypatch.setattr(engine, "AVAILABLE", True)
    monkeypatch.setattr(engine.torch.hub, "load", lambda **kw: (StubModel(), "example"))

    audio = engine.generate("hello", {"language": "ru"})

    # Result is a well-formed WAV at the language's sample rate (ru → 48 kHz).
    assert audio[:4] == b"RIFF"
    assert audio[8:12] == b"WAVE"
    with wave.open(io.BytesIO(audio), "rb") as w:
        assert w.getframerate() == 48000
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getnframes() == 480
    # Russian must use 'aidar' speaker at 48kHz (per the language map).
    assert captured["speaker"] == "aidar"
    assert captured["sample_rate"] == 48000
    assert captured["text"] == "hello"


# Voice selection — config['voice'] + list_voices


class VoiceStubTensor:
    """Minimal waveform stand-in supporting the chain generate() calls."""

    def __init__(self, arr):
        """Wrap the numpy array this stub waveform stands for."""
        self.arr = arr

    def squeeze(self):
        """Return a new stub holding the squeezed array."""
        return VoiceStubTensor(np.squeeze(self.arr))

    def detach(self):
        """Return self — there is no autograd graph to detach from."""
        return self

    def cpu(self):
        """Return self — the stub is always on the host already."""
        return self

    def numpy(self):
        """Return the wrapped numpy array."""
        return self.arr


class VoiceStubModel:
    """Silero model stand-in that exposes `speakers` and records the speaker used."""

    def __init__(self, speakers):
        """Store the advertised speaker list and an empty capture buffer."""
        self.speakers = list(speakers)
        self.captured = {}

    def to(self, device):
        """Accept the device move and return nothing, like the real API."""
        return None

    def apply_tts(self, text, speaker, sample_rate):
        """Record the synthesis arguments and return a fixed 480-sample waveform."""
        self.captured.update(text=text, speaker=speaker, sample_rate=sample_rate)
        return VoiceStubTensor(np.linspace(-0.5, 0.5, 480, dtype="float32"))


def install_voice_model(engine, monkeypatch, speakers):
    """Patch torch.hub.load to return a VoiceStubModel with `speakers` and hand it back."""
    model = VoiceStubModel(speakers)
    monkeypatch.setattr(engine, "AVAILABLE", True)
    monkeypatch.setattr(engine.torch.hub, "load", lambda **kw: (model, "example"))
    return model


def test_list_voices_returns_speakers_and_default(engine, monkeypatch):
    """list_voices reports the model's speakers plus the language's default speaker."""
    install_voice_model(engine, monkeypatch, ["aidar", "baya", "kseniya", "xenia"])
    info = engine.list_voices("ru")
    assert info["voices"] == ["aidar", "baya", "kseniya", "xenia"]
    assert info["default"] == "aidar"  # ru language default from get_model_info


def test_list_voices_engine_unavailable_raises(engine, monkeypatch):
    """Listing voices with AVAILABLE cleared raises EngineNotAvailableError."""
    monkeypatch.setattr(engine, "AVAILABLE", False)
    with pytest.raises(EngineNotAvailableError):
        engine.list_voices("ru")


def test_generate_uses_requested_voice(engine, monkeypatch):
    """An explicit config['voice'] overrides the language's default speaker."""
    model = install_voice_model(engine, monkeypatch, ["aidar", "baya", "kseniya"])
    audio = engine.generate("hello", {"language": "ru", "voice": "baya"})
    assert audio[:4] == b"RIFF"
    assert model.captured["speaker"] == "baya"  # requested voice, not the 'aidar' default


def test_generate_without_voice_uses_language_default(engine, monkeypatch):
    """Omitting config['voice'] falls back to the language's default speaker."""
    model = install_voice_model(engine, monkeypatch, ["aidar", "baya"])
    engine.generate("hello", {"language": "ru"})
    assert model.captured["speaker"] == "aidar"


def test_generate_unknown_voice_raises_validation_error(engine, monkeypatch):
    """A voice the model does not offer is rejected with ValidationError."""
    install_voice_model(engine, monkeypatch, ["aidar", "baya", "kseniya"])
    with pytest.raises(ValidationError, match="Unknown voice"):
        engine.generate("hello", {"language": "ru", "voice": "nonexistent"})


# Model selection


def fail_hub_load(**kwargs):
    """Fail the test: a discovery hook must not load a model."""
    raise AssertionError("torch.hub.load must not be called")


def test_list_models_describes_the_catalog_without_hub(engine, monkeypatch, tmp_path):
    """list_models() lists MODEL_CATALOG with the languages of each model and marks downloaded files."""
    monkeypatch.setattr(engine.torch.hub, "load", fail_hub_load)
    monkeypatch.setenv("SILEROTTS_MODELS", str(tmp_path))
    nested = tmp_path / "snakers4_silero-models_master" / "src" / "silero" / "model"
    nested.mkdir(parents=True)
    (nested / "v3_ua.pt").write_bytes(b"x")
    models = {model["id"]: model for model in engine.list_models()}
    assert list(models) == list(engine.MODEL_CATALOG)
    assert models["v3_ua"] == {"id": "v3_ua", "languages": ["ua", "uk"], "installed": True}
    assert models["v3_en"] == {"id": "v3_en", "languages": ["en"], "installed": False}


def test_list_languages_of_a_model(engine):
    """list_languages(model) gives that model's languages, None for a model outside the catalog."""
    assert engine.list_languages("v3_1_ru") == ["ru"]
    assert engine.list_languages("v3_ua") == ["ua", "uk"]
    assert engine.list_languages("v9_xx") is None


@pytest.mark.parametrize(
    "language,expected", [(None, None), ("ru", "v3_1_ru"), ("uk-ua", "v3_ua"), ("pt", "v3_en"), ("de_AT", "v3_de")]
)
def test_default_model_follows_the_language(engine, language, expected):
    """default_model() is the language's model (English for an unknown one), and None without a language."""
    assert engine.default_model(language) == expected


def test_load_model_named_model_beats_the_language(engine, monkeypatch):
    """load_model(language, model) loads the named model under its own hub language and speaker."""
    calls = []

    def recording_load(**kw):
        """Record the hub arguments and return a stub model."""
        calls.append(kw)
        return VoiceStubModel(["en_0"]), "example"

    monkeypatch.setattr(engine, "AVAILABLE", True)
    monkeypatch.setattr(engine.torch.hub, "load", recording_load)
    unused_model, speaker, sample_rate = engine.load_model("ru", "v3_en")
    assert [(call["language"], call["speaker"]) for call in calls] == [("en", "v3_en")]
    assert (speaker, sample_rate) == ("en_0", 48000)


def test_generate_uses_the_model_from_config(engine, monkeypatch):
    """config['model'] picks the model and its default speaker for a request in another language."""
    model = install_voice_model(engine, monkeypatch, ["en_0", "en_1"])
    engine.TTS_CACHE.clear()
    engine.generate("hello", {"language": "ru", "model": "v3_en"})
    assert model.captured["speaker"] == "en_0"
    assert list(engine.TTS_CACHE) == [("v3_en", "cpu")]


def test_generate_unknown_model_is_a_validation_error(engine, monkeypatch):
    """A model outside MODEL_CATALOG is refused before torch.hub is asked for it."""
    monkeypatch.setattr(engine, "AVAILABLE", True)
    monkeypatch.setattr(engine.torch.hub, "load", fail_hub_load)
    with pytest.raises(ValidationError, match="Unknown silerotts model 'v9_xx'"):
        engine.generate("hello", {"language": "ru", "model": "v9_xx"})


def test_list_voices_of_a_named_model(engine, monkeypatch):
    """list_voices(language, model) lists the speakers of the named model and its default speaker."""
    install_voice_model(engine, monkeypatch, ["en_0", "en_1"])
    assert engine.list_voices("ru", "v3_en") == {"voices": ["en_0", "en_1"], "default": "en_0"}


# Import-time side effects, hub dir handling and concurrency


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


def test_hub_dir_set_once_at_load(engine, monkeypatch, tmp_path):
    """torch.hub.set_dir runs at model load, only when the directory differs, never per call."""
    set_calls = []
    real_set_dir = engine.torch.hub.set_dir

    def counting_set_dir(path):
        """Record the call and forward it to the fake hub."""
        set_calls.append(path)
        real_set_dir(path)

    monkeypatch.setattr(engine.torch.hub, "set_dir", counting_set_dir)
    monkeypatch.setenv("SILEROTTS_MODELS", str(tmp_path / "hub"))
    install_voice_model(engine, monkeypatch, ["aidar"])

    engine.generate("a", {"language": "ru"})
    engine.generate("b", {"language": "ru"})
    assert set_calls == [str(tmp_path / "hub")]

    # Already pointing there: a new model load must not set it again.
    engine.TTS_CACHE.clear()
    engine.generate("c", {"language": "ru"})
    assert set_calls == [str(tmp_path / "hub")]


def run_threads(target, count=4):
    """Start `count` threads on `target` and wait for all of them."""
    import threading

    threads = [threading.Thread(target=target) for unused in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def test_concurrent_first_load_loads_model_once(engine, monkeypatch):
    """Four threads generating at once against an empty cache call torch.hub.load exactly once."""
    import time

    loads = []

    def slow_load(**kw):
        """Record the load and sleep so concurrent callers pile up."""
        loads.append(kw["speaker"])
        time.sleep(0.05)
        return VoiceStubModel(["aidar", "baya"]), "example"

    monkeypatch.setattr(engine, "AVAILABLE", True)
    monkeypatch.setattr(engine.torch.hub, "load", slow_load)
    run_threads(lambda: engine.generate("hi", {"language": "ru"}))
    assert len(loads) == 1
    assert len(engine.TTS_CACHE) == 1


def test_inference_is_serialised(engine, monkeypatch):
    """apply_tts never overlaps: with four threads the fake sees at most one caller inside."""
    import threading
    import time

    state = {"inside": 0, "overlap": 0, "calls": 0}
    guard = threading.Lock()

    class OverlapModel(VoiceStubModel):
        """Model stand-in that counts callers inside apply_tts at the same time."""

        def apply_tts(self, text, speaker, sample_rate):
            """Track concurrent entries, then return the canned waveform."""
            with guard:
                state["inside"] += 1
                state["calls"] += 1
                if state["inside"] > 1:
                    state["overlap"] += 1
            time.sleep(0.02)
            result = super().apply_tts(text, speaker, sample_rate)
            with guard:
                state["inside"] -= 1
            return result

    model = OverlapModel(["aidar"])
    monkeypatch.setattr(engine, "AVAILABLE", True)
    monkeypatch.setattr(engine.torch.hub, "load", lambda **kw: (model, "example"))
    run_threads(lambda: engine.generate("hi", {"language": "ru"}))
    assert state["calls"] == 4
    assert state["overlap"] == 0
