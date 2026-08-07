#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for engines/coquitts.py — Coqui xtts_v2 voice cloning.

Stubs the entire `TTS.*` package hierarchy that the engine imports at
module load time, so the engine module loads under any venv without the
real coqui-tts wheel. Real `torch` is used for the safe_globals context
manager (it's already in the dev venv).
"""

import importlib
import sys
import types

import pytest

# Local imports
from libs.exceptions import CustomError, EngineNotAvailableError, TTSException


def install_fake_torch(monkeypatch):
    """Stub `torch` and `torch.serialization` for engines/coquitts.py top-level imports.

    Only needed when the dev venv lacks real torch (CI without [coqui] extras).
    Covers `torch.cuda.is_available()`, `add_safe_globals`, and `safe_globals`
    (used as a context manager).
    """
    if "torch" in sys.modules and hasattr(sys.modules["torch"], "cuda"):
        return  # real torch already importable, leave it alone

    class SafeGlobalsCtx:
        """No-op stand-in for `torch.serialization.safe_globals`."""

        def __init__(self, *args, **kwargs):
            """Accept and ignore the allow-list of globals."""
            pass

        def __enter__(self):
            """Enter the context without changing any deserialization state."""
            return self

        def __exit__(self, *exc):
            """Leave the context and let any exception propagate."""
            return False

    fake_torch = types.ModuleType("torch")
    fake_torch.cuda = types.SimpleNamespace(is_available=lambda: False)
    fake_serialization = types.ModuleType("torch.serialization")
    fake_serialization.add_safe_globals = lambda items: None
    fake_serialization.safe_globals = SafeGlobalsCtx
    fake_torch.serialization = fake_serialization

    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "torch.serialization", fake_serialization)


def install_fake_tts(monkeypatch, tts_class):
    """Install the minimum TTS.* sub-package tree the engine imports."""

    def make_module(name, **attrs):
        """Create a named module object carrying the given attributes."""
        m = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(m, k, v)
        return m

    class XttsConfig:
        """Placeholder for the xtts config class registered as a safe global."""

    class XttsAudioConfig:
        """Placeholder for the xtts audio config class registered as a safe global."""

    class XttsArgs:
        """Placeholder for the xtts args class registered as a safe global."""

    class BaseDatasetConfig:
        """Placeholder for the shared dataset config registered as a safe global."""

    pkg = make_module("TTS")
    api = make_module("TTS.api", TTS=tts_class)
    tts_pkg = make_module("TTS.tts")
    cfgs_pkg = make_module("TTS.tts.configs")
    xtts_cfg = make_module("TTS.tts.configs.xtts_config", XttsConfig=XttsConfig)
    models_pkg = make_module("TTS.tts.models")
    xtts_models = make_module(
        "TTS.tts.models.xtts",
        XttsAudioConfig=XttsAudioConfig,
        XttsArgs=XttsArgs,
    )
    cfg_pkg = make_module("TTS.config")
    shared = make_module("TTS.config.shared_configs", BaseDatasetConfig=BaseDatasetConfig)

    for module in (pkg, api, tts_pkg, cfgs_pkg, xtts_cfg, models_pkg, xtts_models, cfg_pkg, shared):
        monkeypatch.setitem(sys.modules, module.__name__, module)


class FakeTTS:
    """Stand-in for the real coqui-tts TTS class."""

    instances: list = []  # capture constructor calls

    def __init__(self, model_name, progress_bar=False):
        """Record the requested model and register this instance for inspection."""
        self.model_name = model_name
        self.progress_bar = progress_bar
        self.calls: list = []
        FakeTTS.instances.append(self)

    def to(self, device):
        """Record the target device and return self, mirroring the real API."""
        self.device = device
        return self

    def tts_to_file(self, text, file_path, language=None, speaker_wav=None):
        """Record the synthesis arguments and write a recognisable marker payload."""
        self.calls.append({"text": text, "file": file_path, "language": language, "speaker": speaker_wav})
        with open(file_path, "wb") as f:
            f.write(b"RIFFFAKECOQUI")


@pytest.fixture
def engine(monkeypatch, tmp_path):
    """Import `engines.coquitts` freshly against the fake TTS stack and a dummy sample."""
    FakeTTS.instances = []
    install_fake_torch(monkeypatch)
    install_fake_tts(monkeypatch, FakeTTS)
    monkeypatch.delitem(sys.modules, "engines.coquitts", raising=False)
    eng = importlib.import_module("engines.coquitts")
    # Reset module-level cache so tests don't bleed.
    eng.TTS_CACHE.clear()
    # Provide a real sample WAV so the missing-file branch is opt-in only.
    sample = tmp_path / "voice.wav"
    sample.write_bytes(b"RIFF")
    monkeypatch.setenv("COQUITTS_SAMPLE", str(sample))
    monkeypatch.setenv("COQUITTS_MODELS", str(tmp_path / "cache" / "coquitts"))
    return eng


# is_available


def test_is_available_true_with_fake_TTS(engine):
    """With the TTS package importable the engine reports itself usable."""
    assert engine.is_available() is True


def test_is_available_reflects_module_flag(engine, monkeypatch):
    """is_available mirrors the module-level AVAILABLE flag rather than re-probing."""
    monkeypatch.setattr(engine, "AVAILABLE", False)
    assert engine.is_available() is False


# get_models_directory


def test_get_models_directory_uses_env_var(engine, monkeypatch, tmp_path):
    """COQUITTS_MODELS overrides the default model cache location."""
    monkeypatch.setenv("COQUITTS_MODELS", str(tmp_path / "models_here"))
    assert engine.get_models_directory() == str(tmp_path / "models_here")


def test_get_models_directory_expanduser(engine, monkeypatch, tmp_path):
    """Tilde in env var must be expanded to $HOME-relative absolute path."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("COQUITTS_MODELS", "~/coquitts_home")
    assert engine.get_models_directory() == str(tmp_path / "coquitts_home")


# generate — early returns


def test_generate_raises_engine_not_available_when_flag_off(engine, monkeypatch):
    """Synthesis refuses to run while the engine is marked unavailable."""
    monkeypatch.setattr(engine, "AVAILABLE", False)
    with pytest.raises(EngineNotAvailableError, match="not available"):
        engine.generate("hi", {})


def test_generate_raises_custom_error_when_sample_missing(engine, monkeypatch, tmp_path):
    """The whole point of CustomError exists for this case — the API turns
    it into 422 with structured payload."""
    monkeypatch.setenv("COQUITTS_SAMPLE", str(tmp_path / "no_such_sample.wav"))
    with pytest.raises(CustomError) as excinfo:
        engine.generate("hi", {})
    assert excinfo.value.payload["error"] == "voice_sample_missing"
    assert excinfo.value.status == 422


# generate — happy path & language wiring


def test_generate_returns_file_bytes_for_multilingual_model(engine, monkeypatch):
    """Default xtts_v2 is multilingual — generate must pass language and
    speaker_wav to the underlying tts_to_file call."""
    monkeypatch.setenv("COQUITTS_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2")
    audio = engine.generate("hello", {"language": "en"})
    assert audio == b"RIFFFAKECOQUI"
    inst = FakeTTS.instances[-1]
    last = inst.calls[-1]
    assert last["text"] == "hello"
    assert last["language"] == "en"
    assert last["speaker"]  # speaker_wav passed (the fake sample path)


def test_generate_omits_lang_and_speaker_for_single_speaker_model(engine, monkeypatch):
    """A non-multilingual model must call tts_to_file WITHOUT language/speaker_wav."""
    monkeypatch.setenv("COQUITTS_MODEL", "tts_models/en/ljspeech/tacotron2-DDC")
    engine.generate("hi", {"language": "en"})
    last = FakeTTS.instances[-1].calls[-1]
    assert last["language"] is None
    assert last["speaker"] is None


def test_generate_caches_TTS_instance_between_calls(engine, monkeypatch):
    """xtts_v2 takes ~15s to load on first call — repeated invocations
    MUST NOT instantiate a new TTS each time."""
    engine.generate("a", {"language": "en"})
    engine.generate("b", {"language": "en"})
    assert len(FakeTTS.instances) == 1


def test_generate_creates_separate_instance_per_model(engine, monkeypatch):
    """Cache key is (model, device) — different model → new instance."""
    monkeypatch.setenv("COQUITTS_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2")
    engine.generate("a", {"language": "en"})
    monkeypatch.setenv("COQUITTS_MODEL", "tts_models/en/ljspeech/tacotron2-DDC")
    engine.generate("b", {"language": "en"})
    assert len(FakeTTS.instances) == 2


# generate — error translation


def test_generate_translates_model_not_found_to_tts_exception(engine, monkeypatch):
    """When the underlying TTS raises a 'model not found' error, it must
    be wrapped with the actionable hint, not bubble up unchanged."""

    class BoomTTS:
        """TTS stand-in whose constructor reports an unknown model."""

        def __init__(self, *a, **kw):
            """Fail immediately with a registry lookup error."""
            raise RuntimeError("Requested model not found in registry")

        def to(self, device):
            """Return self so the engine's device call would still chain."""
            return self

    monkeypatch.setattr(engine, "TTS", BoomTTS)
    engine.TTS_CACHE.clear()
    with pytest.raises(TTSException, match="model not found"):
        engine.generate("hi", {"language": "en"})


def test_generate_other_failure_wrapped_as_tts_exception(engine, monkeypatch):
    """Any unrecognised load failure is wrapped in a generic TTSException."""

    class BoomTTS:
        """TTS stand-in whose constructor reports an unclassified crash."""

        def __init__(self, *a, **kw):
            """Fail immediately with a generic runtime error."""
            raise RuntimeError("inference crashed")

        def to(self, device):
            """Return self so the engine's device call would still chain."""
            return self

    monkeypatch.setattr(engine, "TTS", BoomTTS)
    engine.TTS_CACHE.clear()
    with pytest.raises(TTSException, match="generation failed"):
        engine.generate("hi", {"language": "en"})


def test_generate_raises_tts_exception_when_output_file_empty(engine, monkeypatch):
    """If tts_to_file silently produces a 0-byte file, the engine must
    raise TTSException — never return broken empty audio."""

    class EmptyTTS(FakeTTS):
        """FakeTTS variant that writes an empty output file."""

        def tts_to_file(self, text, file_path, language=None, speaker_wav=None):
            """Create an empty file so the engine sees zero-length audio."""
            open(file_path, "wb").close()

    monkeypatch.setattr(engine, "TTS", EmptyTTS)
    engine.TTS_CACHE.clear()
    with pytest.raises(TTSException, match="generation failed|failed to generate"):
        engine.generate("hi", {"language": "en"})
