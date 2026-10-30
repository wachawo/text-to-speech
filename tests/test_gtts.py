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
from gtts.tts import gTTS as RealGTTS

from libs.exceptions import EngineNotAvailableError, TTSException, ValidationError


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


def test_generate_unsupported_language_is_validation_error(engine, monkeypatch):
    """A language gTTS does not speak is a bad request (400), not a synthesis failure (500).

    The real gTTS class is used: its constructor checks the language against the
    static gtts.lang table, so the refusal comes before any network request.
    """
    monkeypatch.setattr(engine, "gTTS", RealGTTS)
    with pytest.raises(ValidationError) as excinfo:
        engine.generate("hi", {"language": "xx"})
    assert str(excinfo.value) == "Language 'xx' is not supported by gtts"


@pytest.mark.parametrize("text", ["...", ",;:"])
def test_generate_punctuation_only_text_is_validation_error(engine, monkeypatch, text):
    """A text gTTS has nothing to send for is a bad request (400), not a synthesis failure (500).

    The real gTTS class is used: it tokenizes the text and asserts that something
    is left before it opens any connection.
    """
    monkeypatch.setattr(engine, "gTTS", RealGTTS)
    with pytest.raises(ValidationError) as excinfo:
        engine.generate(text, {"language": "en"})
    assert str(excinfo.value) == "Text cannot be empty for gtts: nothing in it can be pronounced"


def test_generate_holds_the_inference_lock_around_the_request(engine, monkeypatch):
    """The request to Google runs under INFERENCE_LOCK, one at a time per process."""
    seen = []

    class LockProbeGTTS:
        """Record whether the engine lock is held while the audio is fetched."""

        def __init__(self, text, lang="en", slow=False):
            """Accept the arguments the engine passes."""

        def write_to_fp(self, fp):
            """Note the lock state and write a marker."""
            seen.append(engine.INFERENCE_LOCK.locked())
            fp.write(b"MP3")

    monkeypatch.setattr(engine, "gTTS", LockProbeGTTS)
    engine.generate("hi", {"language": "en"})
    assert seen == [True]
    assert engine.INFERENCE_LOCK.locked() is False
