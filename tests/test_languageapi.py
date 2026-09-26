#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for language tags and TTS_LANGUAGE_STRICT in the HTTP API."""

import pytest

# Local imports
from libs import tools as tools_mod

KOKORO_LANGUAGES = ["en", "es", "fr", "hi", "it", "ja", "pt", "zh"]


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
def strict(monkeypatch, app_module):
    """Turn TTS_LANGUAGE_STRICT on; every engine declares the kokorotts languages except pyttsx3, which declares none."""
    monkeypatch.setattr(app_module, "TTS_LANGUAGE_STRICT", True)
    monkeypatch.setattr(tools_mod, "get_engine_languages", lambda engine: None if engine == "pyttsx3" else KOKORO_LANGUAGES)


@pytest.fixture
def installed(monkeypatch, app_module):
    """Pretend kokorotts is installed and the default engine, as the /v1 routes require."""
    monkeypatch.setattr(app_module, "get_available_engines", lambda: {"kokorotts": None})
    monkeypatch.setattr(app_module, "TTS_ENGINE_DEFAULT", "kokorotts")


# Language tags


@pytest.mark.parametrize(
    ("language", "expected"),
    [("zh-cn", "zh-cn"), ("pt_BR", "pt-br"), ("es-419", "es-419"), ("EN-GB", "en-gb"), ("EN", "en")],
)
def test_tts_accepts_language_tag(client, monkeypatch, app_module, make_wav, language, expected):
    """A tag reaches synthesis lowercased and written with '-'; a 2-character code is only lowercased."""
    calls = record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post("/api/tts", json={"text": "hi", "language": language})
    assert resp.status_code == 200
    assert calls[-1]["language"] == expected


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


@pytest.mark.parametrize(("language", "expected"), [("zh-cn", "zh-cn"), ("pt_BR", "pt-br"), ("zh", "zh")])
def test_stream_accepts_language_tag(client, monkeypatch, app_module, make_wav, language, expected):
    """stream=true takes a tag in the request as file generation does, and passes it on normalized."""
    calls = record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post("/api/tts", json={"text": "hi", "language": language, "stream": True})
    assert resp.status_code == 200
    assert resp.data  # drain the stream so its pool slot and request context are released
    assert calls[-1]["language"] == expected


def test_stream_uses_a_tag_set_as_the_default_language(client, monkeypatch, app_module, make_wav):
    """A stream request without `language` uses TTS_LANGUAGE, a tag included, normalized."""
    calls = record_synthesis(monkeypatch, app_module, make_wav())
    monkeypatch.setattr(app_module, "TTS_LANGUAGE_DEFAULT", "ZH_cn")
    resp = client.post("/api/tts", json={"text": "hi", "stream": True})
    assert resp.status_code == 200
    assert resp.data  # drain the stream so its pool slot and request context are released
    assert calls[-1]["language"] == "zh-cn"


def test_malformed_language_message_matches_libs_tools(client):
    """The API names the field and then gives the exact sentence libs.tools.validate_language raises."""
    from libs.exceptions import ValidationError
    from libs.languages import LANGUAGE_CODE_ERROR

    resp = client.post("/api/tts", json={"text": "hi", "language": "english"})
    assert resp.get_json()["message"] == f"language: {LANGUAGE_CODE_ERROR}"
    with pytest.raises(ValidationError) as excinfo:
        tools_mod.validate_language("english")
    assert str(excinfo.value) == LANGUAGE_CODE_ERROR


def test_history_accepts_language_tag(client, history_dir, monkeypatch, app_module, make_wav):
    """POST /api/history stores the tag it synthesized with."""
    record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post("/api/history", json={"text": "hi", "language": "pt-br"})
    assert resp.status_code == 201
    assert resp.get_json()["language"] == "pt-br"


def test_history_stores_normalized_language(client, history_dir, monkeypatch, app_module, make_wav):
    """The history item keeps the code the audio was made with, not the raw spelling of the request."""
    calls = record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post("/api/history", json={"text": "hi", "language": "pt_BR"})
    assert resp.status_code == 201
    assert resp.get_json()["language"] == "pt-br"
    assert calls[-1]["language"] == "pt-br"
    listed = client.get("/api/history").get_json()
    assert listed["items"][0]["language"] == "pt-br"


def test_openai_speech_accepts_language_tag(client, installed, monkeypatch, app_module, make_wav):
    """/v1/audio/speech takes a tag in its `language` extension; `model` still names the engine."""
    calls = record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post(
        "/v1/audio/speech", json={"model": "kokorotts", "input": "hi", "language": "pt-br", "response_format": "wav"}
    )
    assert resp.status_code == 200
    assert calls[-1]["engine"] == "kokorotts"
    assert calls[-1]["language"] == "pt-br"


def test_openai_speech_normalizes_language_tag(client, installed, monkeypatch, app_module, make_wav):
    """/v1/audio/speech passes a tag on lowercased and written with '-'."""
    calls = record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post(
        "/v1/audio/speech", json={"model": "kokorotts", "input": "hi", "language": "PT_br", "response_format": "wav"}
    )
    assert resp.status_code == 200
    assert calls[-1]["language"] == "pt-br"


# TTS_LANGUAGE_STRICT


def test_unsupported_language_falls_back_when_not_strict(client, monkeypatch, app_module, make_wav):
    """By default a language the engine does not list still reaches the engine, which falls back."""
    monkeypatch.setattr(tools_mod, "get_engine_languages", lambda engine: KOKORO_LANGUAGES)
    calls = record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post("/api/tts", json={"text": "hi", "engine": "kokorotts", "language": "ru"})
    assert resp.status_code == 200
    assert calls[-1]["language"] == "ru"


def test_strict_rejects_unsupported_language_before_taking_a_slot(client, strict, monkeypatch, app_module, make_wav):
    """With TTS_LANGUAGE_STRICT the request is a 400 that names the language, and the pool is left alone."""
    calls = record_synthesis(monkeypatch, app_module, make_wav())
    monkeypatch.setattr(app_module, "TTS_POOL_SIZE", 1)
    app_module.ENGINE_POOL.put(0)
    try:
        resp = client.post("/api/tts", json={"text": "hi", "engine": "kokorotts", "language": "ru"})
        assert app_module.ENGINE_POOL.qsize() == 1
    finally:
        app_module.ENGINE_POOL.get_nowait()
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["error"] == "Bad Request"
    assert body["message"].startswith("Language 'ru' is not supported by engine 'kokorotts'. Supported: en, es")
    assert calls == []


@pytest.mark.parametrize("language", ["en", "en-gb", "pt_BR"])
def test_strict_accepts_listed_language_and_tags(client, strict, monkeypatch, app_module, make_wav, language):
    """A listed language, or a tag of one, passes in strict mode."""
    record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post("/api/tts", json={"text": "hi", "engine": "kokorotts", "language": language})
    assert resp.status_code == 200


def test_strict_passes_engine_that_declares_no_languages(client, strict, monkeypatch, app_module, make_wav):
    """An engine without a language list accepts every code even in strict mode."""
    record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post("/api/tts", json={"text": "hi", "engine": "pyttsx3", "language": "ru"})
    assert resp.status_code == 200


def test_strict_does_not_apply_to_stream(client, strict, monkeypatch, app_module, make_wav):
    """Streaming keeps the engine fallback in strict mode."""
    calls = record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post("/api/tts", json={"text": "hi", "engine": "kokorotts", "language": "ru", "stream": True})
    assert resp.status_code == 200
    assert resp.data  # drain the stream so its pool slot and request context are released
    assert calls[-1]["language"] == "ru"


def test_strict_message_names_normalized_language(client, strict, monkeypatch, app_module, make_wav):
    """The strict-mode 400 names the language as normalized, not as the request spelled it."""
    record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post("/api/tts", json={"text": "hi", "engine": "kokorotts", "language": "RU_ru"})
    assert resp.status_code == 400
    assert resp.get_json()["message"].startswith("Language 'ru-ru' is not supported by engine 'kokorotts'")


def test_strict_rejects_history_request(client, strict, history_dir, monkeypatch, app_module, make_wav):
    """POST /api/history refuses the language and stores nothing."""
    record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post("/api/history", json={"text": "hi", "engine": "kokorotts", "language": "ru"})
    assert resp.status_code == 400
    assert "not supported by engine 'kokorotts'" in resp.get_json()["message"]
    assert not history_dir.exists()


def test_strict_rejects_openai_speech_in_openai_shape(client, strict, installed, monkeypatch, app_module, make_wav):
    """/v1/audio/speech answers the unsupported language in the OpenAI error envelope."""
    record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post("/v1/audio/speech", json={"model": "kokorotts", "input": "hi", "language": "ru"})
    assert resp.status_code == 400
    error = resp.get_json()["error"]
    assert error["type"] == "invalid_request_error"
    assert "Language 'ru' is not supported by engine 'kokorotts'" in error["message"]
