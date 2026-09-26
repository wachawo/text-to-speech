#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for engines/pipertts.py, plus a schema check against the upstream `voices.json` manifest.

Unit tests fake the `piper` package and the on-disk .onnx model layout.
The manifest tests at the bottom of this file are network-dependent and
auto-skip when the manifest cannot be fetched.
"""

import importlib
import io
import json
import os
import sys
import types
import urllib.error
import urllib.request
import wave

import pytest

from install.pipertts import VOICES, VOICES_JSON_URL, expected_hash
from libs.exceptions import EngineNotAvailableError, TTSException, ValidationError


def make_fake_piper(synthesise_bytes: bytes = b""):
    """Fake `piper` module with a PiperVoice that writes a valid WAV."""
    fake = types.ModuleType("piper")

    class FakePiperVoice:
        """Stand-in for piper.PiperVoice that emits canned PCM instead of running inference."""

        def __init__(self, path):
            """Remember the model path the voice was loaded from."""
            self.path = path

        @classmethod
        def load(cls, path):
            """Return an instance bound to `path` without touching the filesystem."""
            return cls(path)

        def synthesize_wav(self, text, wav_file):
            """Configure the open wave file and write the canned frames into it."""
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(22050)
            wav_file.writeframes(synthesise_bytes if synthesise_bytes else b"\x00\x00" * 100)

    fake.PiperVoice = FakePiperVoice
    return fake


@pytest.fixture
def engine(monkeypatch):
    """Fresh-import engines.pipertts with the fake piper package in sys.modules."""
    monkeypatch.setitem(sys.modules, "piper", make_fake_piper())
    monkeypatch.delitem(sys.modules, "engines.pipertts", raising=False)
    return importlib.import_module("engines.pipertts")


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


def test_concurrent_first_load_loads_voice_once(engine, monkeypatch, tmp_path):
    """Four threads asking for the same voice at once construct exactly one PiperVoice."""
    import threading
    import time

    constructions = []

    class SlowVoice:
        """PiperVoice stand-in whose load is slow enough for the threads to overlap."""

        def __init__(self, path):
            """Record the construction and hold the lock long enough to overlap."""
            constructions.append(path)
            time.sleep(0.05)

        @classmethod
        def load(cls, path):
            """Mirror PiperVoice.load."""
            return cls(path)

    monkeypatch.setattr(engine, "PiperVoice", SlowVoice)
    engine.VOICE_CACHE.clear()
    voice_path = str(tmp_path / "en_US-lessac-medium.onnx")
    threads = [threading.Thread(target=engine.get_voice, args=(voice_path,)) for unused in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(constructions) == 1


# is_available


def test_is_available_true_with_fake_piper(engine):
    """The engine reports itself usable once the piper import succeeds."""
    assert engine.is_available() is True


# get_models_directory — three-priority resolution


def test_models_dir_uses_env_var_absolute(engine, monkeypatch, tmp_path):
    """An absolute PIPERTTS_MODELS value is used verbatim."""
    monkeypatch.setenv("PIPERTTS_MODELS", str(tmp_path / "abs_models"))
    assert engine.get_models_directory() == str(tmp_path / "abs_models")


def test_models_dir_resolves_relative_env_against_project_root(engine, monkeypatch):
    """A relative PIPERTTS_MODELS value resolves under the project root, not the cwd."""
    monkeypatch.setenv("PIPERTTS_MODELS", "custom_voices")
    result = engine.get_models_directory()
    # Relative env var must resolve under project root, NOT cwd.
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(engine.__file__)))
    assert result == os.path.join(project_root, "custom_voices")


def test_models_dir_falls_back_to_cache_pipertts_in_project(engine, monkeypatch, tmp_path):
    """With the env var unset, an existing cache/pipertts in the project root wins over the default."""
    monkeypatch.delenv("PIPERTTS_MODELS", raising=False)
    # Stub the project-root path lookup by patching the module attribute.
    fake_project = tmp_path / "fake_project"
    pipertts_dir = fake_project / "cache" / "pipertts"
    pipertts_dir.mkdir(parents=True)

    real_dirname = os.path.dirname

    def stubbed_dirname(p):
        """Redirect the engines/ parent lookup to the fake project root."""
        # First call returns engines/, second engines/.. — i.e. project root.
        if p.endswith("engines"):
            return str(fake_project)
        return real_dirname(p)

    monkeypatch.setattr(os.path, "dirname", stubbed_dirname)
    assert engine.get_models_directory() == str(pipertts_dir)


def test_models_dir_default_when_nothing_configured(engine, monkeypatch, tmp_path):
    """With neither the env var nor cache/pipertts present, the <project>/.piper/voices default applies."""
    monkeypatch.delenv("PIPERTTS_MODELS", raising=False)
    # Move CWD somewhere that has no cache/pipertts so the project-root one wins —
    # but the project DOES contain it in real life. We only assert the path
    # ends with .piper/voices when we force-skip the cache/pipertts branch.
    monkeypatch.setattr(engine.os.path, "exists", lambda p: False)
    result = engine.get_models_directory()
    assert result.endswith(".piper/voices")


# get_voice_path — language → file mapping


@pytest.fixture
def voices_dir(engine, monkeypatch, tmp_path):
    """Make an empty tmp directory the models directory and the only place voices are searched."""
    monkeypatch.setattr(engine, "get_models_directory", lambda: str(tmp_path))
    monkeypatch.setattr(engine, "voice_search_dirs", lambda: [str(tmp_path)])
    return tmp_path


def install_voices(directory, *stems):
    """Create an empty .onnx file for each voice stem."""
    for stem in stems:
        (directory / f"{stem}.onnx").write_bytes(b"x")


def test_voice_path_known_language_uses_mapped_name(engine, monkeypatch, tmp_path):
    """A mapped language resolves to its own .onnx file inside the models directory."""
    monkeypatch.setattr(engine, "get_models_directory", lambda: str(tmp_path))
    # Pre-create the file so the first existence check wins.
    (tmp_path / "ru_RU-ruslan-medium.onnx").write_bytes(b"x")
    assert engine.get_voice_path("ru") == str(tmp_path / "ru_RU-ruslan-medium.onnx")


def test_voice_path_unknown_language_defaults_to_english(engine, monkeypatch, tmp_path):
    """An unmapped language falls back to the English voice rather than failing."""
    monkeypatch.setattr(engine, "get_models_directory", lambda: str(tmp_path))
    (tmp_path / "en_US-lessac-medium.onnx").write_bytes(b"x")
    assert engine.get_voice_path("xx") == str(tmp_path / "en_US-lessac-medium.onnx")


@pytest.mark.parametrize("lang", ["ru-ru", "ru_RU", "ru-UA"])
def test_voice_path_tag_uses_primary_subtag(engine, monkeypatch, tmp_path, lang):
    """A tag resolves to the voice of its primary subtag, not to the English fallback."""
    monkeypatch.setattr(engine, "get_models_directory", lambda: str(tmp_path))
    (tmp_path / "ru_RU-ruslan-medium.onnx").write_bytes(b"x")
    assert engine.get_voice_path(lang) == str(tmp_path / "ru_RU-ruslan-medium.onnx")


def test_list_languages_are_the_languages_with_a_voice(engine, voices_dir):
    """list_languages() declares the languages of the installed voices."""
    install_voices(voices_dir, "ru_RU-ruslan-medium", "en_US-lessac-medium", "en_GB-alan-low", "pl_PL-gosia-medium")
    assert engine.list_languages() == ["en", "pl", "ru"]


def test_voice_path_returns_models_dir_path_when_file_missing(engine, monkeypatch, tmp_path):
    """When no directory holds the .onnx, the canonical models_dir candidate is returned for a useful error."""
    monkeypatch.setattr(engine, "get_models_directory", lambda: str(tmp_path))
    monkeypatch.setattr(engine.os.path, "exists", lambda p: False)
    result = engine.get_voice_path("en")
    assert result == str(tmp_path / "en_US-lessac-medium.onnx")


# get_download_instructions


def test_download_instructions_mention_installer_and_url(engine):
    """The instructions name the install command, the upstream repo and the exact voice file."""
    out = engine.get_download_instructions("ru")
    assert "ttsgen --install pipertts" in out
    assert "huggingface.co/rhasspy/piper-voices" in out
    assert "ru_RU-ruslan-medium.onnx" in out


def test_download_instructions_unknown_language_falls_back_to_en(engine):
    """Instructions for an unmapped language point at the English voice."""
    out = engine.get_download_instructions("xx")
    assert "en_US-lessac-medium.onnx" in out


def test_download_instructions_tag_uses_primary_subtag(engine):
    """Instructions for a tag point at the voice of its primary subtag."""
    assert "de_DE-thorsten-medium.onnx" in engine.get_download_instructions("de-at")


# generate — error paths


def test_generate_raises_engine_not_available_when_flag_off(engine, monkeypatch):
    """Synthesising with AVAILABLE cleared raises EngineNotAvailableError."""
    monkeypatch.setattr(engine, "AVAILABLE", False)
    with pytest.raises(EngineNotAvailableError, match="not available"):
        engine.generate("hi", {})


def test_generate_filenotfound_yields_download_instructions(engine, monkeypatch, tmp_path):
    """A missing model file produces a TTSException whose message carries the install command."""
    monkeypatch.setattr(engine, "get_voice_path", lambda lang: str(tmp_path / "missing.onnx"))

    def boom_load(path):
        """Fail the way PiperVoice.load does when the .onnx is absent."""
        raise FileNotFoundError(path)

    monkeypatch.setattr(engine.PiperVoice, "load", staticmethod(boom_load))
    with pytest.raises(TTSException, match="ttsgen --install pipertts"):
        engine.generate("hi", {"language": "en"})


def test_generate_other_failure_wrapped_as_tts_exception(engine, monkeypatch, tmp_path):
    """Any other backend failure is wrapped as TTSException instead of escaping raw."""
    monkeypatch.setattr(engine, "get_voice_path", lambda lang: str(tmp_path / "v.onnx"))

    def boom(path):
        """Fail the way a crashing inference session would."""
        raise RuntimeError("inference crashed")

    monkeypatch.setattr(engine.PiperVoice, "load", staticmethod(boom))
    with pytest.raises(TTSException, match="generation failed"):
        engine.generate("hi", {})


# generate — happy path


def test_generate_returns_valid_wav_bytes(engine, monkeypatch, tmp_path):
    """The returned bytes are a parseable mono 16-bit 22.05 kHz WAV."""
    monkeypatch.setattr(engine, "get_voice_path", lambda lang: str(tmp_path / "v.onnx"))
    audio = engine.generate("hi", {"language": "en"})

    # Must be a real RIFF WAV that the wave module can open.
    with wave.open(io.BytesIO(audio), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 22050


# get_voice — module-level cache (issue #11)


def test_generate_caches_voice_between_calls(engine, monkeypatch, tmp_path):
    """Repeated synthesis for the same voice loads the ONNX session only once."""
    engine.VOICE_CACHE.clear()
    monkeypatch.setattr(engine, "get_voice_path", lambda lang: str(tmp_path / "v.onnx"))

    calls = {"n": 0}
    fake_voice_cls = engine.PiperVoice
    original_load = fake_voice_cls.load

    def counting_load(path):
        """Count invocations before delegating to the fake loader."""
        calls["n"] += 1
        return original_load(path)

    monkeypatch.setattr(engine.PiperVoice, "load", staticmethod(counting_load))

    engine.generate("first", {"language": "en"})
    engine.generate("second", {"language": "en"})

    assert calls["n"] == 1


def test_generate_creates_separate_voice_per_path(engine, monkeypatch, tmp_path):
    """The cache is keyed by voice path, so two different paths each load once."""
    engine.VOICE_CACHE.clear()
    paths = iter([str(tmp_path / "a.onnx"), str(tmp_path / "b.onnx")])
    monkeypatch.setattr(engine, "get_voice_path", lambda lang: next(paths))

    calls = {"n": 0}
    original_load = engine.PiperVoice.load

    def counting_load(path):
        """Count invocations before delegating to the fake loader."""
        calls["n"] += 1
        return original_load(path)

    monkeypatch.setattr(engine.PiperVoice, "load", staticmethod(counting_load))

    engine.generate("a", {"language": "en"})
    engine.generate("b", {"language": "en"})

    assert calls["n"] == 2


# voices.json manifest — schema sanity check (network)

EXPECTED_HASH_KEYS = {"sha256", "md5_digest", "md5"}


def try_fetch_manifest() -> dict | None:
    """Download and parse the upstream voices.json, or return None if it is unreachable."""
    try:
        req = urllib.request.Request(VOICES_JSON_URL, headers={"User-Agent": "ttsgen-tests"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, OSError, ValueError):
        return None


@pytest.fixture(scope="module")
def manifest() -> dict:
    """Provide the upstream voices.json, skipping the module when the network is unavailable."""
    data = try_fetch_manifest()
    if data is None:
        pytest.skip(f"manifest not reachable: {VOICES_JSON_URL}")
    assert data is not None
    return data


def test_manifest_has_entry_for_every_voice_we_install(manifest: dict) -> None:
    """Every voice the installer ships still has a matching entry upstream."""
    missing = [code for code in VOICES if VOICES[code][1] not in manifest]
    assert not missing, f"voices.json missing entries for: {missing}"


def test_every_voice_file_has_a_known_hash_key(manifest: dict) -> None:
    """Both the .onnx and .onnx.json of every shipped voice expose a recognised checksum field."""
    bad: list[str] = []
    for code, voice_info in VOICES.items():
        path, basename = voice_info[0], voice_info[1]
        entry = manifest.get(basename)
        files = entry.get("files") if isinstance(entry, dict) else None
        if not isinstance(files, dict):
            bad.append(f"{code}: no `files` map in manifest entry")
            continue
        for ext in (".onnx", ".onnx.json"):
            rel_path = f"{path}/{basename}{ext}"
            file_entry = files.get(rel_path) or files.get(f"{basename}{ext}")
            if not isinstance(file_entry, dict):
                bad.append(f"{code} {ext}: no entry at {rel_path}")
                continue
            present = set(file_entry.keys()) & EXPECTED_HASH_KEYS
            if not present:
                bad.append(f"{code} {ext}: none of {sorted(EXPECTED_HASH_KEYS)} found " f"(keys={sorted(file_entry.keys())})")
    assert not bad, "manifest schema drift detected:\n  " + "\n  ".join(bad)


def test_expected_hash_extracts_a_value_for_every_voice(manifest: dict) -> None:
    """expected_hash yields a usable digest for every shipped voice, so install-time verification never silently skips."""
    skipped: list[str] = []
    for code, voice_info in VOICES.items():
        path, basename = voice_info[0], voice_info[1]
        for ext in (".onnx", ".onnx.json"):
            result = expected_hash(manifest, path, basename, ext)
            if result is None:
                skipped.append(f"{code}{ext}")
            else:
                digest, algo = result
                assert isinstance(digest, str) and digest
                assert algo in {"sha256", "md5"}
    assert not skipped, "expected_hash returned None for: " + ", ".join(skipped)


# Voice selection by language and by model


def test_voice_path_picks_an_installed_voice_outside_the_legacy_table(engine, voices_dir):
    """A language without a LEGACY_VOICES entry takes its installed voice instead of English."""
    install_voices(voices_dir, "en_US-lessac-medium", "pl_PL-gosia-medium")
    assert engine.get_voice_path("pl") == str(voices_dir / "pl_PL-gosia-medium.onnx")


def test_voice_path_keeps_the_legacy_voice_when_installed(engine, voices_dir):
    """'en' keeps en_US-lessac-medium even when another English voice is installed."""
    install_voices(voices_dir, "en_GB-alan-low", "en_US-amy-medium", "en_US-lessac-medium")
    assert engine.get_voice_path("en") == str(voices_dir / "en_US-lessac-medium.onnx")


def test_voice_path_region_tag_picks_that_region(engine, voices_dir):
    """'en-gb' takes the installed British voice; 'en-us' keeps the legacy American one."""
    install_voices(voices_dir, "en_GB-alan-low", "en_US-amy-medium", "en_US-lessac-medium")
    assert engine.get_voice_path("en-gb") == str(voices_dir / "en_GB-alan-low.onnx")
    assert engine.get_voice_path("en_GB") == str(voices_dir / "en_GB-alan-low.onnx")
    assert engine.get_voice_path("en-us") == str(voices_dir / "en_US-lessac-medium.onnx")


def test_voice_path_region_without_a_voice_uses_the_language(engine, voices_dir):
    """A region with no installed voice falls back to the language's voice."""
    install_voices(voices_dir, "en_US-lessac-medium")
    assert engine.get_voice_path("en-au") == str(voices_dir / "en_US-lessac-medium.onnx")


def test_voice_path_prefers_medium_quality(engine, voices_dir):
    """Among several voices of a language outside the legacy table, a medium one wins."""
    install_voices(voices_dir, "pl_PL-darkman-low", "pl_PL-gosia-medium", "pl_PL-mc_speech-x_low")
    assert engine.get_voice_path("pl") == str(voices_dir / "pl_PL-gosia-medium.onnx")


def test_voice_path_other_voice_when_legacy_voice_is_missing(engine, voices_dir):
    """A legacy language whose own voice is not installed takes another installed voice of that language."""
    install_voices(voices_dir, "en_US-lessac-medium", "ru_RU-denis-medium")
    assert engine.get_voice_path("ru") == str(voices_dir / "ru_RU-denis-medium.onnx")


def test_voice_path_language_without_voices_keeps_the_english_fallback(engine, voices_dir):
    """With no voice of the language installed, the English voice is used, as before."""
    install_voices(voices_dir, "en_US-lessac-medium", "pl_PL-gosia-medium")
    assert engine.get_voice_path("cs") == str(voices_dir / "en_US-lessac-medium.onnx")


def test_voice_path_model_wins_over_language(engine, voices_dir):
    """A model names an installed voice, whatever the language."""
    install_voices(voices_dir, "en_US-lessac-medium", "en_GB-alan-low")
    assert engine.get_voice_path("ru", "en_GB-alan-low") == str(voices_dir / "en_GB-alan-low.onnx")


@pytest.mark.parametrize("model", ["en_GB-missing-low", "../en_US-lessac-medium", "en_US-lessac-medium.onnx"])
def test_voice_path_unknown_model_is_refused(engine, voices_dir, model):
    """A model that is not an installed voice stem is a ValidationError; it is never joined into a path."""
    install_voices(voices_dir, "en_US-lessac-medium")
    with pytest.raises(ValidationError, match="Unknown pipertts model"):
        engine.get_voice_path("en", model)


def test_first_search_directory_wins(engine, monkeypatch, tmp_path):
    """A voice installed in two directories is loaded from the first one searched."""
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    install_voices(first, "en_US-lessac-medium")
    install_voices(second, "en_US-lessac-medium", "pl_PL-gosia-medium")
    monkeypatch.setattr(engine, "voice_search_dirs", lambda: [str(first), str(second)])
    assert engine.list_installed_voices() == {
        "en_US-lessac-medium": str(first / "en_US-lessac-medium.onnx"),
        "pl_PL-gosia-medium": str(second / "pl_PL-gosia-medium.onnx"),
    }


def test_unreadable_search_directory_is_skipped(engine, monkeypatch, tmp_path, caplog):
    """A search directory that exists but cannot be listed is logged and skipped; the voices elsewhere are found."""
    unreadable, models = tmp_path / "unreadable", tmp_path / "models"
    unreadable.mkdir()
    models.mkdir()
    install_voices(models, "en_US-lessac-medium")
    monkeypatch.setattr(engine, "voice_search_dirs", lambda: [str(unreadable), str(models)])
    real_listdir = os.listdir

    def listdir(path):
        """Refuse the unreadable directory like a chmod 000 ./voices would."""
        if str(path) == str(unreadable):
            raise PermissionError(13, "Permission denied", str(path))
        return real_listdir(path)

    monkeypatch.setattr(engine.os, "listdir", listdir)
    with caplog.at_level("WARNING", logger="engines.pipertts"):
        assert engine.get_voice_path("en") == str(models / "en_US-lessac-medium.onnx")
    assert engine.list_models()[0]["id"] == "en_US-lessac-medium"
    assert engine.list_languages() == ["en"]
    assert f"Skipping unreadable Piper voice directory {unreadable}: PermissionError" in caplog.text


def test_list_languages_none_when_no_voice_is_installed(engine, voices_dir):
    """With no voice installed the engine declares no languages, so the strict check lets the request reach generate()."""
    assert engine.list_models() == []
    assert engine.list_languages() is None


def test_list_models_describes_installed_voices(engine, voices_dir):
    """Every installed voice is a model with its family and family-region languages."""
    install_voices(voices_dir, "ru_RU-ruslan-medium", "en_GB-alan-low")
    (voices_dir / "en_GB-alan-low.onnx.json").write_text("{}")
    assert engine.list_models() == [
        {"id": "en_GB-alan-low", "languages": ["en", "en-gb"], "installed": True},
        {"id": "ru_RU-ruslan-medium", "languages": ["ru", "ru-ru"], "installed": True},
    ]


def test_voice_languages_read_the_config_when_the_name_does_not_parse(engine, voices_dir):
    """A voice named otherwise is described by language.family in its .onnx.json."""
    install_voices(voices_dir, "my-custom-voice", "broken")
    (voices_dir / "my-custom-voice.onnx.json").write_text(json.dumps({"language": {"code": "cs_CZ", "family": "cs"}}))
    (voices_dir / "broken.onnx.json").write_text("not json")
    models = {model["id"]: model for model in engine.list_models()}
    assert models["my-custom-voice"]["languages"] == ["cs"]
    assert models["broken"]["languages"] is None
    assert engine.list_languages() == ["cs"]
    assert engine.get_voice_path("cs") == str(voices_dir / "my-custom-voice.onnx")


def test_list_languages_of_a_model(engine, voices_dir):
    """list_languages(model) gives that voice's languages, None for a voice that is not installed."""
    install_voices(voices_dir, "en_GB-alan-low")
    assert engine.list_languages("en_GB-alan-low") == ["en", "en-gb"]
    assert engine.list_languages("de_DE-thorsten-medium") is None


def test_default_model_follows_the_language(engine, voices_dir):
    """default_model(language) is the voice a request without model loads; None without a language or a file."""
    install_voices(voices_dir, "en_US-lessac-medium", "en_GB-alan-low")
    assert engine.default_model() is None
    assert engine.default_model("en") == "en_US-lessac-medium"
    assert engine.default_model("en-gb") == "en_GB-alan-low"
    assert engine.default_model("pl") == "en_US-lessac-medium"  # spoken with the English voice


def test_default_model_none_when_nothing_is_installed(engine, voices_dir):
    """Without any voice on disk no model serves the language."""
    assert engine.default_model("en") is None


def test_hooks_never_load_a_voice(engine, voices_dir, monkeypatch):
    """The discovery hooks read file names only; PiperVoice.load is never called."""

    def fail_load(path):
        """Fail the test: a discovery hook must not load a voice."""
        raise AssertionError("PiperVoice.load must not be called")

    monkeypatch.setattr(engine.PiperVoice, "load", staticmethod(fail_load))
    install_voices(voices_dir, "en_US-lessac-medium")
    engine.list_models()
    engine.list_languages()
    engine.default_model("en")


@pytest.mark.parametrize(
    ("language", "model", "expected"),
    [
        ("it", None, "it/it_IT/riccardo/medium/it_IT-riccardo-medium.onnx"),
        ("uk", None, "uk/uk_UA/ukrainian_tts/medium/uk_UA-ukrainian_tts-medium.onnx"),
        ("en", "en_GB-alan-low", "en/en_GB/alan/low/en_GB-alan-low.onnx"),
        ("en", "my-custom-voice", "en/en_US/lessac/medium/en_US-lessac-medium.onnx"),
    ],
)
def test_download_instructions_follow_the_voice_stem(engine, language, model, expected):
    """The download URL is derived from the voice stem, for every legacy language and any named model."""
    assert f"resolve/v1.0.0/{expected}" in engine.get_download_instructions(language, model)


def test_generate_uses_the_model_from_config(engine, voices_dir):
    """config['model'] loads that voice instead of the language's."""
    install_voices(voices_dir, "en_US-lessac-medium", "en_GB-alan-low")
    engine.VOICE_CACHE.clear()
    engine.generate("hi", {"language": "en", "model": "en_GB-alan-low"})
    assert list(engine.VOICE_CACHE) == [str(voices_dir / "en_GB-alan-low.onnx")]


def test_voice_cache_is_bounded(engine, voices_dir, monkeypatch):
    """Walking every installed voice keeps at most VOICE_CACHE_SIZE of them loaded, the latest ones."""
    stems = ["en_US-lessac-medium", "en_GB-alan-low", "de_DE-thorsten-medium"]
    install_voices(voices_dir, *stems)
    monkeypatch.setattr(engine, "VOICE_CACHE_SIZE", 2)
    engine.VOICE_CACHE.clear()
    for stem in stems:
        engine.generate("hi", {"language": "en", "model": stem})
    assert list(engine.VOICE_CACHE) == [str(voices_dir / f"{stem}.onnx") for stem in stems[1:]]


def test_generate_unknown_model_is_a_validation_error(engine, voices_dir):
    """An unknown model stays a ValidationError (a 400), not a wrapped TTSException."""
    with pytest.raises(ValidationError, match="Unknown pipertts model 'en_GB-alan-low'"):
        engine.generate("hi", {"language": "en", "model": "en_GB-alan-low"})
