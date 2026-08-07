#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for engines/pyttsx3.py — offline TTS via espeak.

A fake `pyttsx3` is injected into sys.modules before importing the engine
so the tests run without the real package or any audio backend.
"""

import importlib
import sys
import time
import types

import pytest

from libs.exceptions import EngineNotAvailableError, TTSException


def make_fake_pyttsx3(write_bytes: bytes = b"RIFFFAKE", voices: list | None = None):
    """Return a fake pyttsx3 module whose engine writes `write_bytes` to file."""
    fake = types.ModuleType("pyttsx3")
    state: dict = {}

    class FakeEngine:
        """Stand-in for a pyttsx3 engine that records properties instead of speaking."""

        def getProperty(self, name):
            """Return the recorded value for `name`, or the canned voice list."""
            if name == "voices":
                return voices if voices is not None else [types.SimpleNamespace(id="v1")]
            return state.get(name)

        def setProperty(self, name, value):
            """Record a property assignment so tests can assert on it."""
            state[name] = value

        def save_to_file(self, text, filename):
            """Write the canned payload to `filename` and remember the spoken text."""
            with open(filename, "wb") as f:
                f.write(write_bytes)
            state["last_text"] = text

        def runAndWait(self):
            """Mark that the synthesis queue was flushed."""
            state["ran"] = True

        def stop(self):
            """Mark that the engine was stopped."""
            state["stopped"] = True

    fake.init = lambda: FakeEngine()
    fake.state = state  # expose for assertions
    return fake


@pytest.fixture
def engine(monkeypatch):
    """Fresh-import engines.pyttsx3 with the fake pyttsx3 in sys.modules."""
    monkeypatch.setitem(sys.modules, "pyttsx3", make_fake_pyttsx3())
    monkeypatch.delitem(sys.modules, "engines.pyttsx3", raising=False)
    # Make sure time.sleep doesn't actually sleep 0.5s per test.
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    return importlib.import_module("engines.pyttsx3")


# is_available


def test_is_available_true_when_pyttsx3_imports(engine):
    """The engine reports itself usable once the pyttsx3 import succeeds."""
    assert engine.is_available() is True


def test_is_available_false_when_module_flag_off(engine, monkeypatch):
    """Clearing the AVAILABLE flag makes the engine report itself unusable."""
    monkeypatch.setattr(engine, "AVAILABLE", False)
    assert engine.is_available() is False


# generate — happy path + properties wiring


def test_generate_returns_file_bytes(engine):
    """generate returns the bytes the backend wrote to its temporary file."""
    audio = engine.generate("hello", {"language": "en", "rate": 200, "volume": 0.5})
    assert audio == b"RIFFFAKE"


def test_generate_passes_text_to_engine(engine):
    """The text reaches the backend unmodified, including non-ASCII characters."""
    fake = sys.modules["pyttsx3"]
    engine.generate("Grüße", {})
    assert fake.state["last_text"] == "Grüße"


def test_generate_applies_rate_and_volume_from_config(engine):
    """Rate and volume supplied in the config are pushed onto the backend."""
    fake = sys.modules["pyttsx3"]
    engine.generate("hi", {"rate": 220, "volume": 0.7})
    assert fake.state["rate"] == 220
    assert fake.state["volume"] == 0.7


def test_generate_uses_defaults_when_config_lacks_keys(engine):
    """An empty config falls back to the documented default rate and volume."""
    fake = sys.modules["pyttsx3"]
    engine.generate("hi", {})
    assert fake.state["rate"] == 150  # documented default
    assert fake.state["volume"] == 0.9


# generate — error paths


def test_generate_raises_engine_not_available_when_flag_off(engine, monkeypatch):
    """Synthesising with AVAILABLE cleared raises EngineNotAvailableError."""
    monkeypatch.setattr(engine, "AVAILABLE", False)
    with pytest.raises(EngineNotAvailableError, match="not available"):
        engine.generate("hi", {})


def test_generate_raises_tts_exception_when_file_is_empty(monkeypatch):
    """A zero-byte result raises TTSException instead of returning an unusable payload."""
    monkeypatch.setitem(sys.modules, "pyttsx3", make_fake_pyttsx3(write_bytes=b""))
    monkeypatch.delitem(sys.modules, "engines.pyttsx3", raising=False)
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    eng = importlib.import_module("engines.pyttsx3")

    with pytest.raises(TTSException, match="failed to generate"):
        eng.generate("hi", {})


def test_generate_handles_no_voices(monkeypatch):
    """An empty voice list is tolerated — the engine simply skips voice selection."""
    monkeypatch.setitem(sys.modules, "pyttsx3", make_fake_pyttsx3(voices=[]))
    monkeypatch.delitem(sys.modules, "engines.pyttsx3", raising=False)
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    eng = importlib.import_module("engines.pyttsx3")
    audio = eng.generate("hi", {})
    assert audio == b"RIFFFAKE"


def test_generate_wraps_unexpected_exception_as_tts_exception(engine, monkeypatch):
    """A backend crash during init() surfaces as TTSException rather than the raw error."""
    fake = sys.modules["pyttsx3"]

    def boom():
        """Fail the way a broken audio backend would."""
        raise RuntimeError("backend dead")

    fake.init = boom
    with pytest.raises(TTSException, match="generation failed"):
        engine.generate("hi", {})
