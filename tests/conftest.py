#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test fixtures.

Stubs `libs.api` and `engines.get_available_engines` BEFORE importing
`ttssrv.app1` so the test suite never pulls pygame, torch, coqui or any other
heavy dependency. The HTTP layer is what we actually exercise.
"""

import io
import sys
import types
import wave
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Real exception classes — pure-python, safe to import.
from libs.exceptions import (  # noqa: E402
    EngineNotAvailableError,
    TTSException,
    ValidationError,
)


def build_silent_wav(duration_ms: int = 100, rate: int = 22050) -> bytes:
    """Build a valid 16-bit mono PCM WAV with `duration_ms` of silence."""
    nframes = int(rate * duration_ms / 1000)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * nframes)
    return buf.getvalue()


def default_text_to_speech_bytes(text, engine=None, language=None):
    return build_silent_wav()


# Stub libs.api before ttssrv.app1 imports it.
fake_libs_api = types.ModuleType("libs.api")
fake_libs_api.text_to_speech_bytes = default_text_to_speech_bytes
fake_libs_api.text_to_speech_file = lambda text, filename=None, engine=None, language=None: filename or "out.wav"
fake_libs_api.text_to_speech_bytesio = lambda text, engine=None, language=None: io.BytesIO(default_text_to_speech_bytes(text))
fake_libs_api.play_audio = lambda data: None
fake_libs_api.play_audio_file = lambda filename: None
fake_libs_api.play_audio_bytes = lambda data: None
fake_libs_api.TTSException = TTSException
fake_libs_api.ValidationError = ValidationError
fake_libs_api.EngineNotAvailableError = EngineNotAvailableError
sys.modules["libs.api"] = fake_libs_api

# Prevent engines.get_available_engines from importing real engine modules.
import engines as engines_pkg  # noqa: E402

engines_pkg.get_available_engines = lambda: {}

# Now safe to import the Flask app.
from werkzeug.exceptions import abort  # noqa: E402

from ttssrv import app1 as app1_module  # noqa: E402


def abort_view(code: int):
    abort(code)


# Register before first request so Flask accepts the rule.
app1_module.app.add_url_rule(
    "/__test_abort/<int:code>",
    "abort_view",
    abort_view,
)


@pytest.fixture
def app_module():
    """Direct handle to the imported `ttssrv.app1` module."""
    return app1_module


@pytest.fixture
def client(monkeypatch):
    """Flask test client with auth disabled and stubbed synthesis."""
    monkeypatch.setattr(app1_module, "TTS_TOKENS", set(), raising=False)
    monkeypatch.setattr(app1_module, "TTS_POOL_SIZE", 0, raising=False)
    monkeypatch.setattr(app1_module, "text_to_speech_bytes", default_text_to_speech_bytes)
    app1_module.app.config.update(TESTING=True)
    return app1_module.app.test_client()


@pytest.fixture
def make_wav():
    return build_silent_wav
