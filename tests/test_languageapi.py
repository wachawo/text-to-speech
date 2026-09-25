#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for language tags in the HTTP API."""

import pytest


def record_synthesis(monkeypatch, app_module, audio_bytes):
    """Stub text_to_speech_bytes to return `audio_bytes` and collect the arguments of each call."""
    calls = []

    def stub(text, engine=None, language=None, voice=None):
        """Return canned audio and remember what was asked for."""
        calls.append({"text": text, "engine": engine, "language": language, "voice": voice})
        return audio_bytes

    monkeypatch.setattr(app_module, "text_to_speech_bytes", stub)
    return calls


@pytest.fixture
def history_dir(tmp_path, monkeypatch, app_module):
    """Redirect TTS_HISTORY_DIR to a fresh directory for one test."""
    target = tmp_path / "history"
    monkeypatch.setattr(app_module, "TTS_HISTORY_DIR", str(target))
    return target


@pytest.fixture
def installed(monkeypatch, app_module):
    """Pretend kokorotts is installed and the default engine, as the /v1 routes require."""
    monkeypatch.setattr(app_module, "get_available_engines", lambda: {"kokorotts": None})
    monkeypatch.setattr(app_module, "TTS_ENGINE_DEFAULT", "kokorotts")


# Language tags


@pytest.mark.parametrize("language", ["zh-cn", "pt_BR", "es-419", "en-gb"])
def test_tts_accepts_language_tag(client, monkeypatch, app_module, make_wav, language):
    """A tag reaches synthesis as sent; libs.api normalizes it."""
    calls = record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post("/api/tts", json={"text": "hi", "language": language})
    assert resp.status_code == 200
    assert calls[-1]["language"] == language


def test_tts_get_accepts_language_tag(client, monkeypatch, app_module, make_wav):
    """The query-string form takes a tag too."""
    calls = record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.get("/api/tts?text=hi&language=zh-cn")
    assert resp.status_code == 200
    assert calls[-1]["language"] == "zh-cn"


@pytest.mark.parametrize("language", ["english", "zh-", "zh-toolong", "e"])
def test_tts_rejects_malformed_language(client, language):
    """Neither 2 characters nor a tag: 400 with the language field named."""
    resp = client.post("/api/tts", json={"text": "hi", "language": language})
    assert resp.status_code == 400
    assert resp.get_json()["message"].startswith("language: ")


def test_stream_keeps_two_character_rule(client, monkeypatch, app_module, make_wav):
    """Streaming is unchanged: a tag is refused there, a 2-character code still streams."""
    calls = record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post("/api/tts", json={"text": "hi", "language": "zh-cn", "stream": True})
    assert resp.status_code == 400
    assert "stream=false" in resp.get_json()["message"]
    assert calls == []

    resp = client.post("/api/tts", json={"text": "hi", "language": "zh", "stream": True})
    assert resp.status_code == 200
    assert resp.data  # drain the stream so its pool slot and request context are released
    assert calls[-1]["language"] == "zh"


def test_history_accepts_language_tag(client, history_dir, monkeypatch, app_module, make_wav):
    """POST /api/history stores the tag it synthesized with."""
    record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post("/api/history", json={"text": "hi", "language": "pt-br"})
    assert resp.status_code == 201
    assert resp.get_json()["language"] == "pt-br"


def test_openai_speech_accepts_language_tag(client, installed, monkeypatch, app_module, make_wav):
    """/v1/audio/speech takes a tag in its `language` extension; `model` still names the engine."""
    calls = record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post(
        "/v1/audio/speech", json={"model": "kokorotts", "input": "hi", "language": "pt-br", "response_format": "wav"}
    )
    assert resp.status_code == 200
    assert calls[-1]["engine"] == "kokorotts"
    assert calls[-1]["language"] == "pt-br"
