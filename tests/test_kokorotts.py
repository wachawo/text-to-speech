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
import time
import types
import wave

import numpy as np
import pytest

from libs.exceptions import EngineNotAvailableError, TTSException, ValidationError

# Voices of the fake voices file, each a tiny style array with its own values.
FAKE_VOICE_NAMES = ("af_bella", "af_sky", "am_adam", "bf_emma", "jf_alpha")
FAKE_STYLES = {
    name: np.arange(8, dtype=np.float32).reshape(2, 1, 4) + 10 * index for index, name in enumerate(FAKE_VOICE_NAMES)
}


def write_fake_voices(directory):
    """Write an .npz voices file holding FAKE_STYLES as the real voices-v1.0.bin would."""
    # Written through a handle: np.savez appends .npz to a bare filename.
    with open(directory / "voices-v1.0.bin", "wb") as voices_file:
        np.savez(voices_file, **FAKE_STYLES)


def make_fake_kokoro_onnx():
    """Fake `kokoro_onnx` module exposing a no-op `Kokoro` class."""
    fake = types.ModuleType("kokoro_onnx")

    class FakeKokoro:
        """Stand-in for kokoro_onnx.Kokoro that returns silence instead of running ONNX."""

        instances: list = []
        created: list = []

        def __init__(self, model_path, voices_path):
            """Remember the model and voice bundle paths the engine resolved."""
            self.model_path = model_path
            self.voices_path = voices_path
            FakeKokoro.instances.append(self)

        def get_voice_style(self, name):
            """Return the style array stored under `name` in the voices file."""
            with np.load(self.voices_path) as archive:
                return archive[name]

        def create(self, text, voice, speed, lang):
            """Record the call and return a fixed block of silent samples and the sample rate."""
            FakeKokoro.created.append({"text": text, "voice": voice, "speed": speed, "lang": lang})
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
    write_fake_voices(tmp_path)
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
    write_fake_voices(tmp_path)
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
    write_fake_voices(tmp_path)
    monkeypatch.setenv("KOKOROTTS_MODELS", str(tmp_path))

    # Should not raise — unknown language falls back to LANGUAGE_MAP["en"].
    out = engine.generate("hi", {"language": "xx"})
    assert isinstance(out, bytes)


# Import-time side effects and concurrency


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


def test_concurrent_first_load_constructs_kokoro_once(engine, monkeypatch, tmp_path):
    """Four threads generating at once against an empty cache build exactly one Kokoro."""
    import threading
    import time

    constructions = []

    class SlowKokoro:
        """Kokoro stand-in whose constructor is slow enough for the threads to overlap."""

        def __init__(self, model_path, voices_path):
            """Record the construction and sleep so concurrent callers pile up."""
            constructions.append(model_path)
            time.sleep(0.05)

        def create(self, text, voice, speed, lang):
            """Return a fixed block of silent samples and the sample rate."""
            return array.array("h", [0] * 240), 24000

    (tmp_path / "kokoro-v1.0.onnx").write_bytes(b"x")
    write_fake_voices(tmp_path)
    monkeypatch.setenv("KOKOROTTS_MODELS", str(tmp_path))
    monkeypatch.setattr(engine, "Kokoro", SlowKokoro)

    threads = [threading.Thread(target=engine.generate, args=("hi", {"language": "en"})) for unused in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(constructions) == 1
    assert len(engine.KOKORO_CACHE) == 1


# Voice listing, voice specs and voice mixing


@pytest.fixture
def kokoro_dir(monkeypatch, tmp_path):
    """Model directory holding a placeholder model and the fake voices file, with no voice overrides."""
    (tmp_path / "kokoro-v1.0.onnx").write_bytes(b"x")
    write_fake_voices(tmp_path)
    monkeypatch.setenv("KOKOROTTS_MODELS", str(tmp_path))
    for name in ("KOKOROTTS_MODEL", "KOKOROTTS_VOICES", "KOKOROTTS_VOICE", "KOKOROTTS_SPEED"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path


def test_list_voices_english_has_american_and_british(engine, kokoro_dir):
    """English lists the a* and b* voices, sorted, and allows mixing."""
    info = engine.list_voices("en")
    assert info["voices"] == ["af_bella", "af_sky", "am_adam", "bf_emma"]
    assert info["mix"] is True


def test_list_voices_japanese_only_japanese(engine, kokoro_dir):
    """Japanese lists only the j* voices."""
    assert engine.list_voices("ja")["voices"] == ["jf_alpha"]


def test_list_voices_unknown_language_lists_english(engine, kokoro_dir):
    """An unmapped language code lists the English voices, as generate() falls back to English."""
    assert engine.list_voices("xx") == engine.list_voices("en")


def test_list_voices_tag_uses_primary_subtag(engine, kokoro_dir):
    """A tag such as 'ja-jp' lists the voices of its primary subtag."""
    assert engine.list_voices("ja-jp")["voices"] == ["jf_alpha"]


@pytest.mark.parametrize(
    "language,voice,expected",
    [
        ("en-gb", "af_bella", "en-gb"),
        ("en_GB", "af_bella", "en-gb"),
        ("en-us", "af_bella", "en-us"),
        ("ja-jp", "jf_alpha", "ja"),
    ],
)
def test_generate_tag_picks_the_kokoro_lang(engine, kokoro_dir, language, voice, expected):
    """'en-gb' asks for the British phonemizer; other tags use the lang code of their primary subtag."""
    engine.generate("hi", {"language": language, "voice": voice})
    assert sys.modules["kokoro_onnx"].Kokoro.created[-1]["lang"] == expected


def test_list_languages_are_the_mapped_languages(engine):
    """list_languages() declares the languages of LANGUAGE_MAP without opening the model."""
    assert engine.list_languages() == sorted(engine.LANGUAGE_MAP)
    assert engine.list_languages("kokoro-v1.0.int8.onnx") == sorted(engine.LANGUAGE_MAP)
    assert engine.KOKORO_CACHE == {}


# Model selection


def test_get_model_paths_pairs_a_named_model_with_its_release_voices(engine, kokoro_dir, monkeypatch):
    """A named model gets voices-<release>.bin from the same directory, not KOKOROTTS_VOICES."""
    monkeypatch.setenv("KOKOROTTS_VOICES", "custom-voices.bin")
    model, voices = engine.get_model_paths("kokoro-v1.0.int8.onnx")
    assert model == str(kokoro_dir / "kokoro-v1.0.int8.onnx")
    assert voices == str(kokoro_dir / "voices-v1.0.bin")


def test_get_model_paths_named_model_without_release_voices_uses_env(engine, kokoro_dir, monkeypatch):
    """Without a voices file for the model's release, KOKOROTTS_VOICES is used."""
    monkeypatch.setenv("KOKOROTTS_VOICES", "custom-voices.bin")
    unused_model, voices = engine.get_model_paths("kokoro-v2.0.onnx")
    assert voices == str(kokoro_dir / "custom-voices.bin")
    unused_model, voices = engine.get_model_paths("my-model.onnx")
    assert voices == str(kokoro_dir / "custom-voices.bin")


def test_get_model_paths_without_model_is_unchanged(engine, kokoro_dir, monkeypatch):
    """No model keeps KOKOROTTS_MODEL with KOKOROTTS_VOICES, as before models were selectable."""
    monkeypatch.setenv("KOKOROTTS_MODEL", "custom.onnx")
    monkeypatch.setenv("KOKOROTTS_VOICES", "custom-voices.bin")
    assert engine.get_model_paths(None) == (str(kokoro_dir / "custom.onnx"), str(kokoro_dir / "custom-voices.bin"))


@pytest.mark.parametrize("model", ["../kokoro-v1.0.onnx", "sub/kokoro-v1.0.onnx", "..", "/etc/passwd"])
def test_get_model_paths_rejects_a_path(engine, kokoro_dir, model):
    """A model is a file name in the models directory; anything with a separator is refused."""
    with pytest.raises(ValidationError, match="Unknown kokorotts model"):
        engine.get_model_paths(model)


def test_get_model_paths_serves_a_default_with_a_directory(engine, kokoro_dir, monkeypatch):
    """KOKOROTTS_MODEL with a directory part is listed, so naming it back resolves to the file it names."""
    (kokoro_dir / "v1").mkdir()
    (kokoro_dir / "v1" / "kokoro-v1.0.onnx").write_bytes(b"x")
    write_fake_voices(kokoro_dir / "v1")
    monkeypatch.setenv("KOKOROTTS_MODEL", "v1/kokoro-v1.0.onnx")
    assert "v1/kokoro-v1.0.onnx" in [model["id"] for model in engine.list_models()]
    assert engine.get_model_paths("v1/kokoro-v1.0.onnx") == (
        str(kokoro_dir / "v1" / "kokoro-v1.0.onnx"),
        str(kokoro_dir / "v1" / "voices-v1.0.bin"),
    )
    with pytest.raises(ValidationError, match="Unknown kokorotts model"):
        engine.get_model_paths("v1/kokoro-v1.0.int8.onnx")


def test_generate_keeps_at_most_the_cache_size_models(engine, kokoro_dir, monkeypatch):
    """With TTS_MODEL_CACHE_SIZE=1 a request for another model drops the loaded one first."""
    (kokoro_dir / "kokoro-v1.0.int8.onnx").write_bytes(b"x")
    monkeypatch.setenv("TTS_MODEL_CACHE_SIZE", "1")
    engine.generate("hi", {"language": "en"})
    engine.generate("hi", {"language": "en", "model": "kokoro-v1.0.int8.onnx"})
    assert set(engine.KOKORO_CACHE) == {(str(kokoro_dir / "kokoro-v1.0.int8.onnx"), str(kokoro_dir / "voices-v1.0.bin"))}


def test_list_models_lists_onnx_files_and_the_default(engine, kokoro_dir, monkeypatch):
    """Every *.onnx in the directory is a model; KOKOROTTS_MODEL is listed even when its file is missing."""
    (kokoro_dir / "kokoro-v1.0.int8.onnx").write_bytes(b"x")
    monkeypatch.setenv("KOKOROTTS_MODEL", "kokoro-v2.onnx")
    models = engine.list_models()
    assert [model["id"] for model in models] == ["kokoro-v1.0.int8.onnx", "kokoro-v1.0.onnx", "kokoro-v2.onnx"]
    assert [model["installed"] for model in models] == [True, True, False]
    assert models[0]["languages"] == sorted(engine.LANGUAGE_MAP)
    assert engine.KOKORO_CACHE == {}


def test_default_model_is_the_configured_model(engine, kokoro_dir, monkeypatch):
    """default_model() is KOKOROTTS_MODEL for any language, the v1.0 file without it."""
    assert engine.default_model() == "kokoro-v1.0.onnx"
    monkeypatch.setenv("KOKOROTTS_MODEL", "kokoro-v1.0.int8.onnx")
    assert engine.default_model("ja") == "kokoro-v1.0.int8.onnx"


def test_generate_loads_the_model_named_in_config(engine, kokoro_dir):
    """config['model'] loads that file with its release voices, cached apart from the default pair."""
    (kokoro_dir / "kokoro-v1.0.int8.onnx").write_bytes(b"x")
    engine.generate("hi", {"language": "en"})
    engine.generate("hi", {"language": "en", "model": "kokoro-v1.0.int8.onnx"})
    assert set(engine.KOKORO_CACHE) == {
        (str(kokoro_dir / "kokoro-v1.0.onnx"), str(kokoro_dir / "voices-v1.0.bin")),
        (str(kokoro_dir / "kokoro-v1.0.int8.onnx"), str(kokoro_dir / "voices-v1.0.bin")),
    }


def test_list_voices_reads_the_voices_file_of_the_model(engine, kokoro_dir, monkeypatch):
    """list_voices(language, model) reads the voices file paired with the model."""
    monkeypatch.setenv("KOKOROTTS_VOICES", "missing.bin")
    assert engine.list_voices("en")["voices"] == []
    assert engine.list_voices("en", "kokoro-v1.0.onnx")["voices"] == ["af_bella", "af_sky", "am_adam", "bf_emma"]


def test_list_voices_default_is_language_map_voice_when_present(engine, kokoro_dir):
    """The LANGUAGE_MAP default is reported when the voices file has it."""
    assert engine.list_voices("ja")["default"] == "jf_alpha"


def test_list_voices_default_falls_back_to_first_voice(engine, kokoro_dir):
    """Without the LANGUAGE_MAP default (af_sarah) in the file, the first listed voice is the default."""
    assert engine.list_voices("en")["default"] == "af_bella"


def test_default_voice_prefers_language_map_voice_over_first(engine):
    """The LANGUAGE_MAP voice wins even when another voice sorts before it."""
    assert engine.default_voice("en", ["af_alloy", "af_sarah"]) == "af_sarah"


@pytest.mark.parametrize("language", ["en", "ja", "fr"])
def test_list_voices_default_is_the_env_voice_generate_uses(engine, monkeypatch, kokoro_dir, language):
    """With KOKOROTTS_VOICE set, the reported default is the voice a request without one is spoken in."""
    monkeypatch.setenv("KOKOROTTS_VOICE", " af_sky ")
    engine.generate("hi", {"language": language})
    assert engine.list_voices(language)["default"] == engine.Kokoro.created[-1]["voice"] == "af_sky"


def test_list_voices_default_may_be_an_env_mix(engine, monkeypatch, kokoro_dir):
    """A mix in KOKOROTTS_VOICE is reported as the default, the spec generate() blends."""
    monkeypatch.setenv("KOKOROTTS_VOICE", "af_sky+bf_emma")
    assert engine.list_voices("en")["default"] == "af_sky+bf_emma"


def test_list_voices_language_without_voices(engine, kokoro_dir):
    """A language with no voices in the file lists nothing, no default and no mix."""
    assert engine.list_voices("fr") == {"voices": [], "default": None, "mix": False}


def test_list_voices_missing_file_is_empty(engine, monkeypatch, tmp_path):
    """A missing voices file lists nothing instead of raising."""
    monkeypatch.setenv("KOKOROTTS_MODELS", str(tmp_path))
    monkeypatch.delenv("KOKOROTTS_VOICES", raising=False)
    assert engine.list_voices("en") == {"voices": [], "default": None, "mix": False}


def test_list_voices_missing_file_is_not_cached(engine, monkeypatch, tmp_path):
    """A voices file downloaded after an empty listing shows up on the next listing."""
    monkeypatch.setenv("KOKOROTTS_MODELS", str(tmp_path))
    monkeypatch.delenv("KOKOROTTS_VOICES", raising=False)
    assert engine.list_voices("ja")["voices"] == []
    write_fake_voices(tmp_path)
    assert engine.list_voices("ja")["voices"] == ["jf_alpha"]


def test_list_voices_works_without_kokoro_onnx(monkeypatch, kokoro_dir):
    """Listing reads only the voices file, so it works while the engine itself is unavailable."""
    monkeypatch.setitem(sys.modules, "kokoro_onnx", None)
    monkeypatch.setitem(sys.modules, "soundfile", make_fake_soundfile())
    monkeypatch.delitem(sys.modules, "engines.kokorotts", raising=False)
    mod = importlib.import_module("engines.kokorotts")
    assert mod.is_available() is False
    assert mod.list_voices("ja") == {"voices": ["jf_alpha"], "default": "jf_alpha", "mix": True}


def test_voice_names_reads_the_archive_once(engine, monkeypatch, kokoro_dir):
    """Repeated listings and lookups for one voices file open the archive once."""
    loads = []
    real_load = np.load

    def counting_load(*args, **kwargs):
        """Count the call and delegate to the real np.load."""
        loads.append(args[0])
        return real_load(*args, **kwargs)

    monkeypatch.setattr(np, "load", counting_load)
    voices_path = str(kokoro_dir / "voices-v1.0.bin")
    assert engine.voice_names(voices_path) == FAKE_VOICE_NAMES
    assert engine.voice_names(voices_path) == FAKE_VOICE_NAMES
    engine.list_voices("en")
    engine.list_voices("ja")
    assert loads == [voices_path]


def test_parse_voice_spec_single_voice(engine):
    """One name is one component with weight 1."""
    assert engine.parse_voice_spec("af_bella") == [("af_bella", 1.0)]


def test_parse_voice_spec_weights_are_normalized(engine):
    """Weights are scaled to sum to 1, keeping their order."""
    components = engine.parse_voice_spec("af_bella(2)+af_sky(1)")
    assert [name for name, unused_weight in components] == ["af_bella", "af_sky"]
    assert [weight for unused_name, weight in components] == pytest.approx([2 / 3, 1 / 3])


def test_parse_voice_spec_missing_weight_defaults_to_one(engine):
    """A component without a weight counts as weight 1 beside weighted ones."""
    components = engine.parse_voice_spec("af_bella(3)+af_sky")
    assert [weight for unused_name, weight in components] == pytest.approx([0.75, 0.25])


def test_parse_voice_spec_ignores_whitespace(engine):
    """Whitespace around names, weights, parentheses and plus signs is ignored."""
    components = engine.parse_voice_spec("  af_bella ( 0.5 )  +  af_sky(1.5)  ")
    assert [name for name, unused_weight in components] == ["af_bella", "af_sky"]
    assert [weight for unused_name, weight in components] == pytest.approx([0.25, 0.75])


def test_parse_voice_spec_huge_weights_do_not_overflow(engine):
    """Weights near the float limit still normalize instead of summing to infinity."""
    components = engine.parse_voice_spec("af_bella(1e308)+af_sky(1e308)")
    assert [weight for unused_name, weight in components] == pytest.approx([0.5, 0.5])


def test_parse_voice_spec_accepts_max_mix_voices(engine):
    """Exactly MAX_MIX_VOICES components is still a valid mix."""
    assert len(engine.parse_voice_spec("af_bella+af_sky+am_adam+bf_emma")) == engine.MAX_MIX_VOICES


@pytest.mark.parametrize(
    "spec, token",
    [
        ("", "empty"),
        ("   ", "empty"),
        ("af_bella+", "Empty"),
        ("+af_sky", "Empty"),
        ("af_bella++af_sky", "Empty"),
        ("AF_BELLA", "AF_BELLA"),
        ("af-bella", "af-bella"),
        ("bella", "bella"),
        ("af_bella(2", "af_bella(2"),
        ("af_bella)2(", "af_bella)2("),
        ("af_bella(x)", "'x'"),
        ("af_bella()", "af_bella"),
        ("af_bella(inf)", "'inf'"),
        ("af_bella(nan)", "'nan'"),
        ("af_bella(1e999)", "'1e999'"),
        ("af_bella(0)", "'0'"),
        ("af_bella(0)+af_sky", "'0'"),
        ("af_sky+af_bella(0.0)", "'0.0'"),
        ("af_bella(-1)", "'-1'"),
        ("af_bella+af_sky+am_adam+bf_emma+jf_alpha", "5 > 4"),
        ("af_bella+af_bella", "'af_bella'"),
        ("af_bella(1)+af_sky+af_bella(2)", "'af_bella'"),
    ],
)
def test_parse_voice_spec_rejects_malformed(engine, spec, token):
    """Every malformed spec raises ValidationError whose message names the bad token."""
    with pytest.raises(ValidationError) as exc:
        engine.parse_voice_spec(spec)
    assert token in str(exc.value)


def test_resolve_voice_unknown_name_is_named_without_a_path(engine, kokoro_dir):
    """An unknown name is reported by name, and the message carries no filesystem path."""
    with pytest.raises(ValidationError) as exc:
        engine.resolve_voice("af_bella+zz_nobody", FAKE_VOICE_NAMES)
    assert "zz_nobody" in str(exc.value)
    assert str(kokoro_dir) not in str(exc.value)
    assert "/" not in str(exc.value)


def test_generate_passes_requested_voice_as_name(engine, kokoro_dir):
    """A single requested voice reaches Kokoro.create() as its name."""
    engine.generate("hi", {"language": "en", "voice": "am_adam"})
    assert engine.Kokoro.created[-1]["voice"] == "am_adam"


def test_generate_uses_env_voice_without_request(engine, monkeypatch, kokoro_dir):
    """KOKOROTTS_VOICE is used when the request names no voice."""
    monkeypatch.setenv("KOKOROTTS_VOICE", "af_sky")
    engine.generate("hi", {"language": "en"})
    assert engine.Kokoro.created[-1]["voice"] == "af_sky"


def test_generate_request_voice_beats_env(engine, monkeypatch, kokoro_dir):
    """The request's voice wins over KOKOROTTS_VOICE."""
    monkeypatch.setenv("KOKOROTTS_VOICE", "af_sky")
    engine.generate("hi", {"language": "en", "voice": "am_adam"})
    assert engine.Kokoro.created[-1]["voice"] == "am_adam"


@pytest.mark.parametrize("language, expected", [("en", "af_bella"), ("ja", "jf_alpha")])
def test_generate_uses_language_default_voice(engine, kokoro_dir, language, expected):
    """Without request or env voice, the voice list_voices() reports as default is used."""
    engine.generate("hi", {"language": language})
    assert engine.Kokoro.created[-1]["voice"] == expected


def test_generate_blends_a_mix_into_one_style(engine, kokoro_dir):
    """A two-voice mix reaches create() as the float32 weighted sum of the normalized styles."""
    engine.generate("hi", {"language": "en", "voice": "af_bella(3)+am_adam(1)"})
    voice = engine.Kokoro.created[-1]["voice"]
    expected = 0.75 * FAKE_STYLES["af_bella"] + 0.25 * FAKE_STYLES["am_adam"]
    assert isinstance(voice, np.ndarray)
    assert voice.dtype == np.float32
    np.testing.assert_allclose(voice, expected, rtol=1e-6)


def test_generate_env_voice_may_be_a_mix(engine, monkeypatch, kokoro_dir):
    """KOKOROTTS_VOICE accepts the same mix syntax as the request."""
    monkeypatch.setenv("KOKOROTTS_VOICE", "af_sky+bf_emma")
    engine.generate("hi", {"language": "en"})
    voice = engine.Kokoro.created[-1]["voice"]
    np.testing.assert_allclose(voice, 0.5 * FAKE_STYLES["af_sky"] + 0.5 * FAKE_STYLES["bf_emma"], rtol=1e-6)


@pytest.mark.parametrize(
    "request_voice, env_voice, error",
    [
        ("zz_nobody", "", ValidationError),
        ("", "zz_nobody", TTSException),
        ("af_bella+zz_nobody", "", ValidationError),
    ],
)
def test_generate_unknown_voice_never_loads_the_model(engine, monkeypatch, kokoro_dir, request_voice, env_voice, error):
    """An unknown voice fails before any Kokoro instance is built (a TTSException when it came from KOKOROTTS_VOICE)."""
    monkeypatch.setenv("KOKOROTTS_VOICE", env_voice)
    with pytest.raises(error) as exc:
        engine.generate("hi", {"language": "en", "voice": request_voice})
    assert "zz_nobody" in str(exc.value)
    assert engine.Kokoro.instances == []
    assert engine.KOKORO_CACHE == {}


@pytest.mark.parametrize(
    "language, voice, expected_lang",
    [
        ("en", "bf_emma", "en-gb"),
        ("en", "af_bella", "en-us"),
        ("en", "bf_emma(2)+af_bella", "en-gb"),
        ("en", "af_bella+bf_emma", "en-us"),
        ("xx", "bf_emma", "en-gb"),
        ("ja", "jf_alpha", "ja"),
        ("ja", "bf_emma", "ja"),
    ],
)
def test_generate_lang_code_follows_language_and_first_voice(engine, kokoro_dir, language, voice, expected_lang):
    """English led by a b* voice is spoken as en-gb; every other language keeps its own code."""
    engine.generate("hi", {"language": language, "voice": voice})
    assert engine.Kokoro.created[-1]["lang"] == expected_lang


def test_voice_names_are_sorted(engine, tmp_path):
    """The names come back sorted whatever order the archive stores them in."""
    with open(tmp_path / "voices-v1.0.bin", "wb") as voices_file:
        np.savez(voices_file, zf_b=np.zeros(1, np.float32), af_a=np.zeros(1, np.float32), bm_c=np.zeros(1, np.float32))
    assert engine.voice_names(str(tmp_path / "voices-v1.0.bin")) == ("af_a", "bm_c", "zf_b")


@pytest.mark.parametrize("weight", ["\u0662", "\uff12", "1_0", "nan", "0x10", "1,5"])
def test_parse_voice_spec_rejects_non_ascii_or_odd_weights(engine, weight):
    """Only plain ASCII decimals are weights; float() alone would accept some of these."""
    with pytest.raises(ValidationError):
        engine.parse_voice_spec(f"af_bella({weight})+af_sky")


def test_parse_voice_spec_unclosed_parenthesis_is_fast(engine):
    """An unclosed parenthesis with a long run of spaces is rejected without backtracking blowup."""
    started = time.monotonic()
    with pytest.raises(ValidationError):
        engine.parse_voice_spec("af_bella(" + " " * 5000)
    assert time.monotonic() - started < 0.5


def test_whitespace_request_voice_falls_back_to_env(engine, kokoro_dir, monkeypatch):
    """A voice of only spaces counts as no voice, so KOKOROTTS_VOICE applies."""
    monkeypatch.setenv("KOKOROTTS_VOICE", "am_adam")
    names = engine.voice_names(str(kokoro_dir / "voices-v1.0.bin"))
    assert engine.requested_voice_spec({"voice": "   "}, "en", names) == "am_adam"


def test_language_without_voices_falls_back_to_language_map_voice(engine):
    """With no voice of the language in the file, the LANGUAGE_MAP voice is named (and then refused as unknown)."""
    assert engine.requested_voice_spec({}, "fr", ("af_bella",)) == "ff_siwis"


def test_invalid_env_voice_blames_the_variable(engine, kokoro_dir, monkeypatch):
    """A bad KOKOROTTS_VOICE for a request without a voice is a server error naming the variable."""
    monkeypatch.setenv("KOKOROTTS_VOICE", "af_nobody")
    with pytest.raises(TTSException, match="KOKOROTTS_VOICE"):
        engine.generate("hi", {"language": "en"})


def test_invalid_request_voice_is_still_a_validation_error_with_env_set(engine, kokoro_dir, monkeypatch):
    """With KOKOROTTS_VOICE set, a bad voice sent by the client stays the client's error."""
    monkeypatch.setenv("KOKOROTTS_VOICE", "am_adam")
    with pytest.raises(ValidationError, match="af_nobody"):
        engine.generate("hi", {"language": "en", "voice": "af_nobody"})
