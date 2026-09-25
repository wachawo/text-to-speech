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


# Voice selection


def voice(voice_id, languages=None, name=None):
    """Build a pyttsx3-like voice object with the given id, languages and name."""
    return types.SimpleNamespace(id=voice_id, languages=languages or [], name=name or voice_id)


ESPEAK_VOICES = [
    voice("default", [b"\x05en"], "default"),
    voice("gmw/en", [b"\x05en"], "English (Great Britain)"),
    voice("gmw/en-US", [b"\x05en-us"], "English (America)"),
    voice("roa/de", [b"\x05de"], "German"),
    voice("zle/ru", [b"\x05ru"], "Russian"),
]


def import_engine_with_voices(monkeypatch, voices):
    """Fresh-import engines.pyttsx3 against a fake pyttsx3 that reports `voices`."""
    monkeypatch.setitem(sys.modules, "pyttsx3", make_fake_pyttsx3(voices=voices))
    monkeypatch.delitem(sys.modules, "engines.pyttsx3", raising=False)
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    return importlib.import_module("engines.pyttsx3")


def test_generate_picks_voice_by_language(monkeypatch):
    """config['language'] selects the first voice whose language tag starts with the code."""
    eng = import_engine_with_voices(monkeypatch, ESPEAK_VOICES)
    eng.generate("hi", {"language": "ru"})
    assert sys.modules["pyttsx3"].state["voice"] == "zle/ru"


def test_generate_picks_voice_by_explicit_voice_id(monkeypatch):
    """config['voice'] wins over the language and matches the voice id case-insensitively."""
    eng = import_engine_with_voices(monkeypatch, ESPEAK_VOICES)
    eng.generate("hi", {"language": "ru", "voice": "gmw/en-us"})
    assert sys.modules["pyttsx3"].state["voice"] == "gmw/en-US"


def test_generate_picks_voice_by_explicit_voice_name(monkeypatch):
    """config['voice'] also matches the human-readable voice name."""
    eng = import_engine_with_voices(monkeypatch, ESPEAK_VOICES)
    eng.generate("hi", {"language": "en", "voice": "german"})
    assert sys.modules["pyttsx3"].state["voice"] == "roa/de"


def test_generate_unknown_voice_falls_back_to_language(monkeypatch):
    """A voice the driver does not offer falls back to the language match, not to voices[0]."""
    eng = import_engine_with_voices(monkeypatch, ESPEAK_VOICES)
    eng.generate("hi", {"language": "de", "voice": "nonexistent"})
    assert sys.modules["pyttsx3"].state["voice"] == "roa/de"


def test_generate_unmatched_language_falls_back_to_first_voice(monkeypatch):
    """A language no voice serves keeps the historical voices[0] choice."""
    eng = import_engine_with_voices(monkeypatch, ESPEAK_VOICES)
    eng.generate("hi", {"language": "zz"})
    assert sys.modules["pyttsx3"].state["voice"] == "default"


# espeak lists a region voice for en-gb, but only 'zh' / 'pt' for Chinese and Portuguese.
ESPEAK_REGION_VOICES = [
    voice("gmw/en", [b"\x02en-gb", b"\x02en"], "English (Great Britain)"),
    voice("gmw/en-US", [b"\x02en-us"], "English (America)"),
    voice("sit/cmn", [b"\x05zh-cmn", b"\x05zh"], "Chinese (Mandarin)"),
    voice("roa/pt", [b"\x05pt"], "Portuguese (Portugal)"),
]


@pytest.mark.parametrize(
    "language,expected",
    [
        ("zh-cn", "sit/cmn"),
        ("pt-br", "roa/pt"),
        ("en-us", "gmw/en-US"),
        ("zh", "sit/cmn"),
        ("xx-yy", "gmw/en"),
    ],
)
def test_generate_picks_voice_by_language_part_of_a_tag(monkeypatch, language, expected):
    """A tag no voice lists uses its language part; a listed tag keeps its own voice; no match keeps voices[0]."""
    eng = import_engine_with_voices(monkeypatch, ESPEAK_REGION_VOICES)
    eng.generate("hi", {"language": language})
    assert sys.modules["pyttsx3"].state["voice"] == expected


@pytest.mark.parametrize(
    "voice_obj,language,expected",
    [
        (voice("en", ["en"]), "en", True),
        (voice("english", [b"\x05en"]), "en", True),
        (voice("gmw/en-US", []), "en", True),
        (voice("en_US", []), "en", True),
        (voice("default", []), "de", False),
        (voice("zle/ru", [b"\x05ru"]), "en", False),
    ],
)
def test_voice_matches_language(engine, voice_obj, language, expected):
    """Language tags match by prefix; ids match exactly, by last segment, or before '-' / '_'."""
    assert engine.voice_matches_language(voice_obj, language) is expected


# Concurrency


def test_engine_calls_are_serialised(monkeypatch):
    """init/save_to_file/runAndWait/stop never overlap across threads."""
    import threading

    state = {"inside": 0, "overlap": 0, "calls": 0}
    guard = threading.Lock()
    fake = make_fake_pyttsx3()
    real_init = fake.init

    def tracked_init():
        """Count callers between init() and stop() at the same time."""
        with guard:
            state["inside"] += 1
            state["calls"] += 1
            if state["inside"] > 1:
                state["overlap"] += 1
        engine_obj = real_init()
        real_stop = engine_obj.stop

        def tracked_stop():
            """Leave the critical section after the real stop."""
            real_stop()
            with guard:
                state["inside"] -= 1

        engine_obj.stop = tracked_stop
        return engine_obj

    fake.init = tracked_init
    monkeypatch.setitem(sys.modules, "pyttsx3", fake)
    monkeypatch.delitem(sys.modules, "engines.pyttsx3", raising=False)
    # A short real pause instead of the 0.5s flush wait keeps the section open long enough to overlap.
    monkeypatch.setattr(time, "sleep", lambda seconds: threading.Event().wait(0.02))
    eng = importlib.import_module("engines.pyttsx3")

    threads = [threading.Thread(target=eng.generate, args=("hi", {})) for unused in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert state["calls"] == 4
    assert state["overlap"] == 0
