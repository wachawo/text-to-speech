#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for engines/gtts.py, the online Google TTS engine.

The real `gtts` package is in the dev venv, so the engine imports cleanly.
Tests below pin the contract of is_available()/generate() with a fake
gTTS class so no network call is ever made.
"""

import importlib
import sys
import types

import pytest

from libs.exceptions import EngineNotAvailableError, TTSException


@pytest.fixture
def engine(monkeypatch):
    """Replace `gtts.gTTS` with a fake that produces deterministic bytes."""
    fake_gtts_pkg = types.ModuleType("gtts")

    class FakeGTTS:
        """Stand-in for gtts.gTTS that records its arguments instead of calling out."""

        def __init__(self, text, lang="en", slow=False):
            """Store the synthesis parameters handed over by the engine."""
            self.text = text
            self.lang = lang
            self.slow = slow

        def write_to_fp(self, fp):
            """Write marker bytes encoding the stored parameters into `fp`."""
            # Marker bytes so we can assert pass-through.
            fp.write(f"MP3:{self.lang}:{self.slow}:{self.text}".encode())

    fake_gtts_pkg.gTTS = FakeGTTS
    monkeypatch.setitem(sys.modules, "gtts", fake_gtts_pkg)
    monkeypatch.delitem(sys.modules, "engines.gtts", raising=False)
    return importlib.import_module("engines.gtts")


# is_available


def test_is_available_true_when_gtts_imports(engine):
    """The engine advertises itself once the gtts import succeeded."""
    assert engine.is_available() is True


def test_is_available_false_when_flag_off(engine, monkeypatch):
    """is_available() mirrors the module-level AVAILABLE flag."""
    monkeypatch.setattr(engine, "AVAILABLE", False)
    assert engine.is_available() is False


# is_available — ImportError path (line 18-20 of gtts.py)


def test_is_available_false_when_gtts_not_installed(monkeypatch):
    """If gtts cannot be imported, AVAILABLE must be False after fresh import."""
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def fake_import(name, *args, **kwargs):
        """Delegate to the real importer except for gtts, which is made to fail."""
        if name == "gtts" or name.startswith("gtts."):
            raise ImportError("gtts not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setitem(sys.modules, "gtts", None)  # poison cache
    monkeypatch.delitem(sys.modules, "gtts", raising=False)
    monkeypatch.setattr("builtins.__import__", fake_import)
    monkeypatch.delitem(sys.modules, "engines.gtts", raising=False)

    eng = importlib.import_module("engines.gtts")
    assert eng.is_available() is False


# generate


def test_generate_passes_lang_and_slow_to_gtts(engine):
    """The language and slow config keys reach gTTS unchanged."""
    audio = engine.generate("hello", {"language": "ru", "slow": True})
    assert audio == b"MP3:ru:True:hello"


def test_generate_defaults_language_to_en_and_slow_to_false(engine):
    """An empty config synthesizes English at normal speed."""
    audio = engine.generate("hi", {})
    assert audio == b"MP3:en:False:hi"


# Language tags


@pytest.fixture
def gtts_langs(monkeypatch):
    """Serve a small gTTS language table as `gtts.lang`, spelled the way gTTS spells its tags."""
    fake_lang = types.ModuleType("gtts.lang")
    fake_lang.tts_langs = lambda: {"en": "English", "pt": "Portuguese", "zh-CN": "Chinese", "fr-CA": "French (Canada)"}
    monkeypatch.setitem(sys.modules, "gtts.lang", fake_lang)


@pytest.mark.parametrize(
    "language,expected",
    [
        ("zh-cn", "zh-CN"),
        ("ZH_cn", "zh-CN"),
        ("fr-ca", "fr-CA"),
        ("pt-br", "pt"),
        ("en", "en"),
        ("xx", "xx"),
        ("xx-yy", "xx-yy"),
    ],
)
def test_gtts_language_maps_tags_to_gtts_spelling(engine, gtts_langs, language, expected):
    """A listed tag gets gTTS's spelling, an unlisted one its primary subtag, anything else passes unchanged."""
    assert engine.gtts_language(language) == expected


def test_generate_sends_the_gtts_spelling(engine, gtts_langs):
    """generate() hands gTTS the tag as gTTS spells it."""
    assert engine.generate("ni hao", {"language": "zh-cn"}) == b"MP3:zh-CN:False:ni hao"


def test_list_languages_are_lowercased_gtts_tags(engine, gtts_langs):
    """list_languages() declares gTTS's own table, lowercased and sorted."""
    assert engine.list_languages() == ["en", "fr-ca", "pt", "zh-cn"]


def test_list_languages_none_without_language_table(engine, monkeypatch):
    """Without a readable gtts.lang the engine declares nothing and passes codes through unchanged."""
    monkeypatch.setitem(sys.modules, "gtts.lang", None)
    assert engine.list_languages() is None
    assert engine.gtts_language("zh-cn") == "zh-cn"


def test_generate_raises_engine_not_available_when_flag_off(engine, monkeypatch):
    """Synthesis refuses to run while the engine reports itself unavailable."""
    monkeypatch.setattr(engine, "AVAILABLE", False)
    with pytest.raises(EngineNotAvailableError, match="not available"):
        engine.generate("hi", {})


def test_generate_wraps_underlying_failure_as_tts_exception(engine, monkeypatch):
    """A network or library error inside gTTS surfaces as TTSException, never as the raw upstream type."""

    class BoomGTTS:
        """Stand-in for gtts.gTTS that fails during construction."""

        def __init__(self, *a, **kw):
            """Raise as if the network were unreachable."""
            raise RuntimeError("network down")

    # `engines.gtts` did `from gtts import gTTS`, so the symbol lives on the
    # engine module itself — patch there, not on sys.modules['gtts'].
    monkeypatch.setattr(engine, "gTTS", BoomGTTS)
    with pytest.raises(TTSException, match="gTTS generation failed"):
        engine.generate("hi", {"language": "en"})
