#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for engines/pyttsx3.py — offline TTS via espeak.

Fake `pyttsx3` is injected into sys.modules before importing the engine
so the tests run without the real package or any audio backend.
"""

import importlib
import sys
import types

import pytest

from libs.exceptions import EngineNotAvailableError, TTSException


def make_fake_pyttsx3(write_bytes: bytes = b"RIFFFAKE", voices: list | None = None):
    """Return a fake pyttsx3 module whose engine writes `write_bytes` to file."""
    fake = types.ModuleType("pyttsx3")
    state: dict = {}

    class FakeEngine:
        def getProperty(self, name):
            if name == "voices":
                return voices if voices is not None else [types.SimpleNamespace(id="v1")]
            return state.get(name)

        def setProperty(self, name, value):
            state[name] = value

        def save_to_file(self, text, filename):
            with open(filename, "wb") as f:
                f.write(write_bytes)
            state["last_text"] = text

        def runAndWait(self):
            state["ran"] = True

        def stop(self):
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
    import time as time_mod

    monkeypatch.setattr(time_mod, "sleep", lambda s: None)
    return importlib.import_module("engines.pyttsx3")


# is_available


def test_is_available_true_when_pyttsx3_imports(engine):
    assert engine.is_available() is True


def test_is_available_false_when_module_flag_off(engine, monkeypatch):
    monkeypatch.setattr(engine, "AVAILABLE", False)
    assert engine.is_available() is False


# generate — happy path + properties wiring


def test_generate_returns_file_bytes(engine):
    audio = engine.generate("hello", {"language": "en", "rate": 200, "volume": 0.5})
    assert audio == b"RIFFFAKE"


def test_generate_passes_text_to_engine(engine):
    fake = sys.modules["pyttsx3"]
    engine.generate("привет", {})
    assert fake.state["last_text"] == "привет"


def test_generate_applies_rate_and_volume_from_config(engine):
    fake = sys.modules["pyttsx3"]
    engine.generate("hi", {"rate": 220, "volume": 0.7})
    assert fake.state["rate"] == 220
    assert fake.state["volume"] == 0.7


def test_generate_uses_defaults_when_config_lacks_keys(engine):
    fake = sys.modules["pyttsx3"]
    engine.generate("hi", {})
    assert fake.state["rate"] == 150  # documented default
    assert fake.state["volume"] == 0.9


# generate — error paths


def test_generate_raises_engine_not_available_when_flag_off(engine, monkeypatch):
    monkeypatch.setattr(engine, "AVAILABLE", False)
    with pytest.raises(EngineNotAvailableError, match="not available"):
        engine.generate("hi", {})


def test_generate_raises_tts_exception_when_file_is_empty(monkeypatch):
    """If save_to_file produces zero bytes, generate must raise TTSException —
    not silently return an unusable empty payload."""
    monkeypatch.setitem(sys.modules, "pyttsx3", make_fake_pyttsx3(write_bytes=b""))
    monkeypatch.delitem(sys.modules, "engines.pyttsx3", raising=False)
    import time as time_mod

    monkeypatch.setattr(time_mod, "sleep", lambda s: None)
    eng = importlib.import_module("engines.pyttsx3")

    with pytest.raises(TTSException, match="failed to generate"):
        eng.generate("hi", {})


def test_generate_handles_no_voices(monkeypatch):
    """voices=None must not crash — engine just skips setProperty('voice')."""
    monkeypatch.setitem(sys.modules, "pyttsx3", make_fake_pyttsx3(voices=[]))
    monkeypatch.delitem(sys.modules, "engines.pyttsx3", raising=False)
    import time as time_mod

    monkeypatch.setattr(time_mod, "sleep", lambda s: None)
    eng = importlib.import_module("engines.pyttsx3")
    audio = eng.generate("hi", {})
    assert audio == b"RIFFFAKE"


def test_generate_wraps_unexpected_exception_as_tts_exception(engine, monkeypatch):
    """A backend crash during init() must surface as TTSException, not raw."""
    fake = sys.modules["pyttsx3"]

    def boom():
        raise RuntimeError("backend dead")

    fake.init = boom
    with pytest.raises(TTSException, match="generation failed"):
        engine.generate("hi", {})
