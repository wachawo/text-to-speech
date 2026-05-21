#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for engines/pipertts.py — offline TTS via Piper, plus an
integration check against the upstream `voices.json` manifest schema.

Unit tests fake the `piper` package and the on-disk .onnx model layout.
The manifest tests at the bottom of this file are network-dependent and
auto-skip when the manifest cannot be fetched.
"""

import importlib
import io
import json
import sys
import types
import urllib.error
import urllib.request
import wave

import pytest

from install.pipertts import VOICES, VOICES_JSON_URL, expected_hash
from libs.exceptions import EngineNotAvailableError, TTSException


def make_fake_piper(synthesise_bytes: bytes = b""):
    """Fake `piper` module with a PiperVoice that writes a valid WAV."""
    fake = types.ModuleType("piper")

    class FakePiperVoice:
        def __init__(self, path):
            self.path = path

        @classmethod
        def load(cls, path):
            return cls(path)

        def synthesize_wav(self, text, wav_file):
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(22050)
            wav_file.writeframes(synthesise_bytes if synthesise_bytes else b"\x00\x00" * 100)

    fake.PiperVoice = FakePiperVoice
    return fake


@pytest.fixture
def engine(monkeypatch):
    monkeypatch.setitem(sys.modules, "piper", make_fake_piper())
    monkeypatch.delitem(sys.modules, "engines.pipertts", raising=False)
    return importlib.import_module("engines.pipertts")


# is_available


def test_is_available_true_with_fake_piper(engine):
    assert engine.is_available() is True


# get_models_directory — three-priority resolution


def test_models_dir_uses_env_var_absolute(engine, monkeypatch, tmp_path):
    monkeypatch.setenv("PIPERTTS_MODELS", str(tmp_path / "abs_models"))
    assert engine.get_models_directory() == str(tmp_path / "abs_models")


def test_models_dir_resolves_relative_env_against_project_root(engine, monkeypatch):
    monkeypatch.setenv("PIPERTTS_MODELS", "custom_voices")
    result = engine.get_models_directory()
    # Relative env var must resolve under project root, NOT cwd.
    assert result.endswith("custom_voices")
    assert "/text-to-speech/" in result or result.endswith("text-to-speech/custom_voices")


def test_models_dir_falls_back_to_cache_pipertts_in_project(engine, monkeypatch, tmp_path):
    """If env var is unset, cache/pipertts in project root wins over the default."""
    monkeypatch.delenv("PIPERTTS_MODELS", raising=False)
    # Stub the project-root path lookup by patching the module attribute.
    fake_project = tmp_path / "fake_project"
    pipertts_dir = fake_project / "cache" / "pipertts"
    pipertts_dir.mkdir(parents=True)

    import os as os_mod

    real_dirname = os_mod.path.dirname

    def stubbed_dirname(p):
        # First call returns engines/, second engines/.. — i.e. project root.
        if p.endswith("engines"):
            return str(fake_project)
        return real_dirname(p)

    monkeypatch.setattr(os_mod.path, "dirname", stubbed_dirname)
    assert engine.get_models_directory() == str(pipertts_dir)


def test_models_dir_default_when_nothing_configured(engine, monkeypatch, tmp_path):
    """Neither env var nor cache/pipertts/ → fallback to <project>/.piper/voices."""
    monkeypatch.delenv("PIPERTTS_MODELS", raising=False)
    # Move CWD somewhere that has no cache/pipertts so the project-root one wins —
    # but the project DOES contain it in real life. We only assert the path
    # ends with .piper/voices when we force-skip the cache/pipertts branch.
    monkeypatch.setattr(engine.os.path, "exists", lambda p: False)
    result = engine.get_models_directory()
    assert result.endswith(".piper/voices")


# get_voice_path — language → file mapping


def test_voice_path_known_language_uses_mapped_name(engine, monkeypatch, tmp_path):
    monkeypatch.setattr(engine, "get_models_directory", lambda: str(tmp_path))
    # Pre-create the file so the first existence check wins.
    (tmp_path / "ru_RU-ruslan-medium.onnx").write_bytes(b"x")
    assert engine.get_voice_path("ru") == str(tmp_path / "ru_RU-ruslan-medium.onnx")


def test_voice_path_unknown_language_defaults_to_english(engine, monkeypatch, tmp_path):
    monkeypatch.setattr(engine, "get_models_directory", lambda: str(tmp_path))
    (tmp_path / "en_US-lessac-medium.onnx").write_bytes(b"x")
    assert engine.get_voice_path("xx") == str(tmp_path / "en_US-lessac-medium.onnx")


def test_voice_path_returns_models_dir_path_when_file_missing(engine, monkeypatch, tmp_path):
    """When neither models_dir nor fallback dirs contain the .onnx, the
    function still returns the canonical models_dir candidate so generate()
    can produce a useful FileNotFoundError downstream."""
    monkeypatch.setattr(engine, "get_models_directory", lambda: str(tmp_path))
    monkeypatch.setattr(engine.os.path, "exists", lambda p: False)
    result = engine.get_voice_path("en")
    assert result == str(tmp_path / "en_US-lessac-medium.onnx")


# get_download_instructions


def test_download_instructions_mention_installer_and_url(engine):
    out = engine.get_download_instructions("ru")
    assert "ttsgen --install pipertts" in out
    assert "huggingface.co/rhasspy/piper-voices" in out
    assert "ru_RU-ruslan-medium.onnx" in out


def test_download_instructions_unknown_language_falls_back_to_en(engine):
    out = engine.get_download_instructions("xx")
    assert "en_US-lessac-medium.onnx" in out


# generate — error paths


def test_generate_raises_engine_not_available_when_flag_off(engine, monkeypatch):
    monkeypatch.setattr(engine, "AVAILABLE", False)
    with pytest.raises(EngineNotAvailableError, match="not available"):
        engine.generate("hi", {})


def test_generate_filenotfound_yields_download_instructions(engine, monkeypatch, tmp_path):
    """FileNotFoundError from PiperVoice.load → TTSException whose message
    contains the install command (so end users know what to do)."""
    monkeypatch.setattr(engine, "get_voice_path", lambda lang: str(tmp_path / "missing.onnx"))

    def boom_load(path):
        raise FileNotFoundError(path)

    monkeypatch.setattr(engine.PiperVoice, "load", staticmethod(boom_load))
    with pytest.raises(TTSException, match="ttsgen --install pipertts"):
        engine.generate("hi", {"language": "en"})


def test_generate_other_failure_wrapped_as_tts_exception(engine, monkeypatch, tmp_path):
    monkeypatch.setattr(engine, "get_voice_path", lambda lang: str(tmp_path / "v.onnx"))

    def boom(path):
        raise RuntimeError("inference crashed")

    monkeypatch.setattr(engine.PiperVoice, "load", staticmethod(boom))
    with pytest.raises(TTSException, match="generation failed"):
        engine.generate("hi", {})


# generate — happy path


def test_generate_returns_valid_wav_bytes(engine, monkeypatch, tmp_path):
    """generate writes WAV via wave.open into BytesIO; result must be parseable."""
    monkeypatch.setattr(engine, "get_voice_path", lambda lang: str(tmp_path / "v.onnx"))
    audio = engine.generate("hi", {"language": "en"})

    # Must be a real RIFF WAV that the wave module can open.
    with wave.open(io.BytesIO(audio), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 22050


# get_voice — module-level cache (issue #11)


def test_generate_caches_voice_between_calls(engine, monkeypatch, tmp_path):
    """PiperVoice.load is the dominant cost (~1.5s) — repeated calls for the
    same voice MUST hit the cache instead of re-loading the ONNX session."""
    engine.VOICE_CACHE.clear()
    monkeypatch.setattr(engine, "get_voice_path", lambda lang: str(tmp_path / "v.onnx"))

    calls = {"n": 0}
    fake_voice_cls = engine.PiperVoice
    original_load = fake_voice_cls.load

    def counting_load(path):
        calls["n"] += 1
        return original_load(path)

    monkeypatch.setattr(engine.PiperVoice, "load", staticmethod(counting_load))

    engine.generate("first", {"language": "en"})
    engine.generate("second", {"language": "en"})

    assert calls["n"] == 1


def test_generate_creates_separate_voice_per_path(engine, monkeypatch, tmp_path):
    """Cache is keyed by voice_path — different paths must each load once."""
    engine.VOICE_CACHE.clear()
    paths = iter([str(tmp_path / "a.onnx"), str(tmp_path / "b.onnx")])
    monkeypatch.setattr(engine, "get_voice_path", lambda lang: next(paths))

    calls = {"n": 0}
    original_load = engine.PiperVoice.load

    def counting_load(path):
        calls["n"] += 1
        return original_load(path)

    monkeypatch.setattr(engine.PiperVoice, "load", staticmethod(counting_load))

    engine.generate("a", {"language": "en"})
    engine.generate("b", {"language": "en"})

    assert calls["n"] == 2


# voices.json manifest — schema sanity check (network)

EXPECTED_HASH_KEYS = {"sha256", "md5_digest", "md5"}


def try_fetch_manifest() -> dict | None:
    try:
        req = urllib.request.Request(VOICES_JSON_URL, headers={"User-Agent": "ttsgen-tests"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, OSError, ValueError):
        return None


@pytest.fixture(scope="module")
def manifest() -> dict:
    data = try_fetch_manifest()
    if data is None:
        pytest.skip(f"manifest not reachable: {VOICES_JSON_URL}")
    assert data is not None
    return data


def test_manifest_has_entry_for_every_voice_we_install(manifest: dict) -> None:
    missing = [code for code in VOICES if VOICES[code][1] not in manifest]
    assert not missing, f"voices.json missing entries for: {missing}"


def test_every_voice_file_has_a_known_hash_key(manifest: dict) -> None:
    """For each voice we ship, both .onnx and .onnx.json must expose at least
    one of (sha256 | md5_digest | md5). If upstream renames the field this
    test fails — better than expected_hash silently returning None."""
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
    """Round-trip through the helper itself — any voice for which
    expected_hash returns None means verify_checksum will be skipped at
    install time, which is what we want to know about now (not later)."""
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
