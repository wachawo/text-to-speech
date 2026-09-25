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
from libs.exceptions import CustomError, EngineNotAvailableError, TTSException, ValidationError


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


@pytest.mark.parametrize(
    "language,expected",
    [
        ("zh", "zh-cn"),  # xtts rejects a bare 'zh'
        ("ZH", "zh-cn"),
        ("zh-cn", "zh-cn"),
        ("zh_CN", "zh-cn"),
        ("zh-tw", "zh-cn"),  # xtts has one Chinese code
        ("ru", "ru"),
        ("en", "en"),
        ("pt-br", "pt"),  # other tags reduce to the primary subtag
    ],
)
def test_xtts_language_maps_request_codes(engine, language, expected):
    """xtts_language keeps listed codes, turns Chinese into 'zh-cn' and strips other regions."""
    assert engine.xtts_language(language) == expected


def test_xtts_language_results_are_listed_for_known_codes(engine):
    """Every code the UI and schema send for a supported xtts language maps into XTTS_LANGUAGES."""
    for language in ("ar", "cs", "de", "en", "es", "fr", "hi", "hu", "it", "ja", "ko", "nl", "pl", "pt", "ru", "tr", "zh"):
        assert engine.xtts_language(language) in engine.XTTS_LANGUAGES


def test_generate_sends_zh_cn_to_xtts_for_chinese(engine, monkeypatch):
    """A 'zh' request reaches xtts as 'zh-cn', the only Chinese code xtts accepts."""
    monkeypatch.setenv("COQUITTS_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2")
    engine.generate("ni hao", {"language": "zh"})
    assert FakeTTS.instances[-1].calls[-1]["language"] == "zh-cn"


def test_generate_keeps_language_for_other_multilingual_models(engine, monkeypatch):
    """The xtts mapping is not applied to non-xtts multilingual models, which use their own codes."""
    monkeypatch.setenv("COQUITTS_MODEL", "tts_models/multilingual/multi-dataset/your_tts")
    engine.generate("hi", {"language": "zh"})
    assert FakeTTS.instances[-1].calls[-1]["language"] == "zh"


@pytest.mark.parametrize(
    "model,expected",
    [
        ("tts_models/multilingual/multi-dataset/xtts_v2", "xtts"),
        ("tts_models/de/thorsten/vits", ["de"]),
        ("tts_models/zh-CN/baker/tacotron2-DDC-GST", ["zh", "zh-cn"]),
        ("tts_models/multilingual/multi-dataset/your_tts", None),
        ("tts_models/ewe/openbible/vits", None),
    ],
)
def test_list_languages_follows_the_configured_model(engine, monkeypatch, model, expected):
    """xtts declares its codes plus 'zh', a single-language model its language (and a tag's language part), others nothing."""
    monkeypatch.setenv("COQUITTS_MODEL", model)
    languages = engine.list_languages()
    if expected == "xtts":
        assert languages == sorted([*engine.XTTS_LANGUAGES, "zh"])
    else:
        assert languages == expected


def test_region_model_passes_the_strict_check_for_its_language_part(engine, monkeypatch):
    """A single-language `zh-CN` model serves `zh` (what the web UI sends) and `zh-cn` in strict mode."""
    from libs.languages import language_supported

    monkeypatch.setenv("COQUITTS_MODEL", "tts_models/zh-CN/baker/tacotron2-DDC-GST")
    languages = engine.list_languages()
    assert language_supported("zh", languages)
    assert language_supported("zh_CN", languages)
    assert not language_supported("en", languages)


def test_three_letter_model_language_passes_the_strict_check(engine, monkeypatch):
    """A `tts_models/ewe/...` model declares nothing, since no request can carry `ewe`, so strict mode refuses nothing."""
    from libs.tools import validate_engine_language

    monkeypatch.setenv("COQUITTS_MODEL", "tts_models/ewe/openbible/vits")
    validate_engine_language("coquitts", "en")


def test_list_languages_does_not_load_a_model(engine, monkeypatch):
    """Declaring languages reads COQUITTS_MODEL only; no TTS instance is built."""
    monkeypatch.delenv("COQUITTS_MODEL", raising=False)
    assert "zh-cn" in engine.list_languages()
    assert FakeTTS.instances == []


# Model selection hooks


def test_list_languages_of_a_named_model(engine, monkeypatch):
    """list_languages(model) describes that model, not COQUITTS_MODEL."""
    monkeypatch.setenv("COQUITTS_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2")
    assert engine.list_languages("tts_models/de/thorsten/vits") == ["de"]


def test_default_model_is_the_configured_model(engine, monkeypatch):
    """default_model() is COQUITTS_MODEL for every language, and the xtts default without it."""
    monkeypatch.delenv("COQUITTS_MODEL", raising=False)
    assert engine.default_model() == engine.DEFAULT_COQUITTS_MODEL
    monkeypatch.setenv("COQUITTS_MODEL", "tts_models/de/thorsten/vits")
    assert engine.default_model("ru") == "tts_models/de/thorsten/vits"


def test_list_models_reads_the_cache_directory(engine, monkeypatch, tmp_path):
    """Models on disk are listed by their COQUITTS_MODEL spelling; the default is listed even before its download."""
    cache = tmp_path / "cache" / "coquitts" / "tts"
    (cache / "tts_models--de--thorsten--vits").mkdir(parents=True)
    (cache / "vocoder_models--en--ljspeech--hifigan_v2").mkdir()
    (cache / "tts_models--stray-file").write_text("x")
    monkeypatch.delenv("COQUITTS_MODEL", raising=False)
    models = {model["id"]: model for model in engine.list_models()}
    assert set(models) == {"tts_models/de/thorsten/vits", engine.DEFAULT_COQUITTS_MODEL}
    assert models["tts_models/de/thorsten/vits"] == {
        "id": "tts_models/de/thorsten/vits",
        "languages": ["de"],
        "installed": True,
    }
    assert models[engine.DEFAULT_COQUITTS_MODEL]["installed"] is False
    assert "zh-cn" in models[engine.DEFAULT_COQUITTS_MODEL]["languages"]
    assert FakeTTS.instances == []


def test_list_models_marks_an_installed_default(engine, monkeypatch, tmp_path):
    """A default model already in the cache is listed once, as installed."""
    cache = tmp_path / "cache" / "coquitts" / "tts"
    (cache / "tts_models--multilingual--multi-dataset--xtts_v2").mkdir(parents=True)
    monkeypatch.delenv("COQUITTS_MODEL", raising=False)
    assert engine.list_models() == [
        {"id": engine.DEFAULT_COQUITTS_MODEL, "languages": engine.list_languages(), "installed": True}
    ]


def test_generate_uses_the_model_from_config(engine, monkeypatch):
    """config['model'] picks the checkpoint get_tts loads instead of COQUITTS_MODEL."""
    monkeypatch.setenv("COQUITTS_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2")
    engine.generate("hi", {"language": "de", "model": "tts_models/de/thorsten/vits"})
    assert FakeTTS.instances[-1].model_name == "tts_models/de/thorsten/vits"
    # A single-language model gets neither language nor speaker_wav.
    assert FakeTTS.instances[-1].calls[-1]["language"] is None


def test_generate_maps_zh_for_an_xtts_model_named_in_config(engine, monkeypatch):
    """The xtts language mapping follows the requested model, not COQUITTS_MODEL."""
    monkeypatch.setenv("COQUITTS_MODEL", "tts_models/de/thorsten/vits")
    engine.generate("ni hao", {"language": "zh", "model": "tts_models/multilingual/multi-dataset/xtts_v2"})
    assert FakeTTS.instances[-1].calls[-1]["language"] == "zh-cn"


def test_list_voices_ignores_the_model(engine):
    """Every Coqui model clones from the same samples, so `model` does not change the listing."""
    assert engine.list_voices("en", "tts_models/de/thorsten/vits") == engine.list_voices("en")


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


# generate - voice selection via config['voice']


def test_generate_with_voice_uses_samples_dir_file(engine, monkeypatch, tmp_path):
    """config['voice'] selects <COQUITTS_SAMPLES>/<voice>.wav as the cloned sample instead of COQUITTS_SAMPLE."""
    samples = tmp_path / "samples"
    samples.mkdir()
    maria = samples / "maria.wav"
    maria.write_bytes(b"RIFF")
    monkeypatch.setenv("COQUITTS_SAMPLES", str(samples))
    monkeypatch.setenv("COQUITTS_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2")

    audio = engine.generate("hello", {"language": "en", "voice": "maria"})
    assert audio == b"RIFFFAKECOQUI"
    last = FakeTTS.instances[-1].calls[-1]
    assert last["speaker"] == str(maria)


def test_generate_unknown_voice_raises_custom_error(engine, monkeypatch, tmp_path):
    """A voice with no sample file is reported as voice_sample_missing naming the voice and the expected path."""
    samples = tmp_path / "samples"
    samples.mkdir()
    monkeypatch.setenv("COQUITTS_SAMPLES", str(samples))

    with pytest.raises(CustomError) as excinfo:
        engine.generate("hi", {"language": "en", "voice": "ghost"})
    payload = excinfo.value.payload
    assert payload["error"] == "voice_sample_missing"
    assert payload["voice"] == "ghost"
    assert payload["path"] == str(samples / "ghost.wav")
    assert "ghost" in payload["message"]
    assert excinfo.value.status == 422
    assert FakeTTS.instances == []


def test_generate_invalid_voice_name_raises_validation_error(engine, monkeypatch, tmp_path):
    """A voice name with a path separator is refused by the traversal guard before any file access."""
    monkeypatch.setenv("COQUITTS_SAMPLES", str(tmp_path))
    with pytest.raises(ValidationError, match="Invalid voice name"):
        engine.generate("hi", {"language": "en", "voice": "../voice"})


# list_voices


def test_list_voices_returns_stems_and_default(engine, monkeypatch, tmp_path):
    """list_voices reports the sorted sample stems and the stem of COQUITTS_SAMPLE as default."""
    samples = tmp_path / "samples"
    samples.mkdir()
    for name in ("zoe.wav", "adam.wav"):
        (samples / name).write_bytes(b"RIFF")
    (samples / "readme.txt").write_text("skip")
    monkeypatch.setenv("COQUITTS_SAMPLES", str(samples))
    monkeypatch.setenv("COQUITTS_SAMPLE", str(tmp_path / "voice.wav"))

    assert engine.list_voices("en") == {"voices": ["adam", "zoe"], "default": "voice"}


def test_list_voices_default_none_when_sample_unset(engine, monkeypatch, tmp_path):
    """Without COQUITTS_SAMPLE the default is None and a missing samples dir lists nothing."""
    monkeypatch.delenv("COQUITTS_SAMPLE", raising=False)
    monkeypatch.setenv("COQUITTS_SAMPLES", str(tmp_path / "nowhere"))

    assert engine.list_voices() == {"voices": [], "default": None}


def test_list_voices_does_not_need_engine_available(engine, monkeypatch, tmp_path):
    """Listing voices is a directory scan: it works with AVAILABLE off and never constructs a TTS model."""
    samples = tmp_path / "samples"
    samples.mkdir()
    (samples / "maria.wav").write_bytes(b"RIFF")
    monkeypatch.setenv("COQUITTS_SAMPLES", str(samples))
    monkeypatch.setattr(engine, "AVAILABLE", False)

    assert engine.list_voices("en")["voices"] == ["maria"]
    assert FakeTTS.instances == []


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


# Import-time side effects, TTS_HOME handling and concurrency


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


def test_tts_home_set_once_at_load_and_left_alone_afterwards(engine, monkeypatch, tmp_path):
    """TTS_HOME is written at model load, only when it differs, and not on later calls."""
    import os

    monkeypatch.delenv("TTS_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    models_dir = str(tmp_path / "cache" / "coquitts")
    engine.generate("a", {"language": "en"})
    assert os.environ["TTS_HOME"] == models_dir
    assert "XDG_DATA_HOME" not in os.environ

    # A later change of COQUITTS_MODELS does not touch the environment while
    # the model is served from the cache.
    monkeypatch.setenv("COQUITTS_MODELS", str(tmp_path / "elsewhere"))
    engine.generate("b", {"language": "en"})
    assert os.environ["TTS_HOME"] == models_dir


def run_threads(target, count=4):
    """Start `count` threads on `target` and wait for all of them."""
    import threading

    threads = [threading.Thread(target=target) for unused in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def test_concurrent_first_load_constructs_tts_once(engine, monkeypatch):
    """Four threads generating at once against an empty cache build exactly one TTS."""
    import time

    class SlowTTS(FakeTTS):
        """FakeTTS whose constructor is slow enough for the threads to overlap."""

        def __init__(self, model_name, progress_bar=False):
            """Record the construction and sleep so concurrent callers pile up."""
            super().__init__(model_name, progress_bar)
            time.sleep(0.05)

    monkeypatch.setattr(engine, "TTS", SlowTTS)
    engine.TTS_CACHE.clear()
    run_threads(lambda: engine.generate("hi", {"language": "en"}))
    assert len(FakeTTS.instances) == 1
    assert len(engine.TTS_CACHE) == 1


def test_inference_is_serialised(engine, monkeypatch):
    """tts_to_file never overlaps: with four threads the fake sees at most one caller inside."""
    import threading
    import time

    state = {"inside": 0, "overlap": 0}
    guard = threading.Lock()

    class OverlapTTS(FakeTTS):
        """FakeTTS that counts callers inside tts_to_file at the same time."""

        def tts_to_file(self, text, file_path, language=None, speaker_wav=None):
            """Track concurrent entries, then write the marker payload."""
            with guard:
                state["inside"] += 1
                if state["inside"] > 1:
                    state["overlap"] += 1
            time.sleep(0.02)
            super().tts_to_file(text, file_path, language=language, speaker_wav=speaker_wav)
            with guard:
                state["inside"] -= 1

    monkeypatch.setattr(engine, "TTS", OverlapTTS)
    engine.TTS_CACHE.clear()
    run_threads(lambda: engine.generate("hi", {"language": "en"}))
    assert len(FakeTTS.instances[-1].calls) == 4
    assert state["overlap"] == 0
