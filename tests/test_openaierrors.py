#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Every error answered on a /v1 path uses the OpenAI envelope; the /api routes keep their own shape."""

import json

import pytest

# Local imports
from libs.exceptions import CustomError, EngineNotAvailableError, TTSException, ValidationError

INSTALLED = {"gtts": None, "silerotts": None}


@pytest.fixture
def installed(monkeypatch, app_module):
    """Pretend gtts and silerotts are installed and make gtts the default engine."""
    monkeypatch.setattr(app_module, "get_available_engines", lambda: dict(INSTALLED))
    monkeypatch.setattr(app_module, "TTS_ENGINE_DEFAULT", "gtts")


def openai_error_of(resp, status, error_type):
    """Assert `resp` is `status` with exactly the OpenAI envelope of `error_type`, and return the error object."""
    assert resp.status_code == status
    body = resp.get_json()
    assert set(body.keys()) == {"error"}
    error = body["error"]
    assert set(error.keys()) == {"message", "type", "param", "code"}
    assert error["type"] == error_type
    assert isinstance(error["message"], str) and error["message"]
    return error


def fail_with(monkeypatch, app_module, exc):
    """Make every synthesis call raise `exc`."""

    def boom(text, engine=None, language=None, voice=None):
        """Raise the prepared engine failure."""
        raise exc

    monkeypatch.setattr(app_module, "text_to_speech_bytes", boom)


def speech(client):
    """POST a valid /v1/audio/speech request."""
    return client.post("/v1/audio/speech", json={"model": "tts-1", "input": "Hello there.", "response_format": "wav"})


def test_v1_unauthorized_is_openai_shaped(client, installed, monkeypatch, app_module):
    """A /v1 request without a valid token gets 401 in the envelope, code invalid_api_key; /api keeps its shape."""
    monkeypatch.setattr(app_module, "TTS_TOKENS", {"secret"}, raising=False)
    error = openai_error_of(speech(client), 401, "invalid_request_error")
    assert error["code"] == "invalid_api_key"
    wrong = client.get("/v1/models", headers={"Authorization": "Bearer nope"})
    assert openai_error_of(wrong, 401, "invalid_request_error")["code"] == "invalid_api_key"
    api = client.get("/api/engines")
    assert api.status_code == 401
    assert set(api.get_json().keys()) == {"error", "request_id"}


def test_v1_engine_failures_are_openai_shaped(client, installed, monkeypatch, app_module):
    """TTSException, EngineNotAvailableError and an unexpected exception keep their status as server_error."""
    fail_with(monkeypatch, app_module, TTSException("model broke at /opt/secret/path"))
    error = openai_error_of(speech(client), 500, "server_error")
    assert error["message"] == "TTS failed"
    fail_with(monkeypatch, app_module, EngineNotAvailableError("no weights at /opt/secret/path"))
    error = openai_error_of(speech(client), 503, "server_error")
    assert "/opt/secret" not in error["message"]
    fail_with(monkeypatch, app_module, RuntimeError("engine exploded"))
    error = openai_error_of(speech(client), 500, "server_error")
    assert error["message"] == "Internal Server Error"


def test_v1_custom_error_keeps_status_and_names_the_code(client, installed, monkeypatch, app_module):
    """An engine CustomError keeps its status, its message and its error name as `code`."""
    payload = {"error": "voice_sample_missing", "message": "Record a voice sample first."}
    fail_with(monkeypatch, app_module, CustomError(payload, status=422))
    error = openai_error_of(speech(client), 422, "invalid_request_error")
    assert error["message"] == "Record a voice sample first."
    assert error["code"] == "voice_sample_missing"


def test_v1_http_errors_are_openai_shaped(client, installed):
    """404, 405 and 413 on /v1 paths answer the envelope with the same status."""
    openai_error_of(client.get("/v1/nothing-here"), 404, "invalid_request_error")
    openai_error_of(client.get("/v1/audio/speech"), 405, "invalid_request_error")
    body = json.dumps({"input": "a" * (3 * 1024 * 1024)})
    resp = client.post("/v1/audio/speech", data=body, content_type="application/json")
    assert "2 MB" in openai_error_of(resp, 413, "invalid_request_error")["message"]


def test_v1_voices_validation_errors_are_openai_shaped(client, installed, monkeypatch, app_module):
    """A bad query or a refused engine on /v1/audio/voices is a 400 envelope, not the /api Bad Request body."""
    error = openai_error_of(client.get("/v1/audio/voices?language=r"), 400, "invalid_request_error")
    assert error["param"] == "language"

    def refuse(engine, language="en"):
        """Refuse the engine the way validate_engine does."""
        raise ValidationError(f"Unknown engine: {engine}")

    monkeypatch.setattr(app_module, "get_engine_voices", refuse)
    error = openai_error_of(client.get("/v1/audio/voices?model=nope"), 400, "invalid_request_error")
    assert error["message"] == "Unknown engine: nope"


def test_api_errors_keep_their_shape(client, monkeypatch, app_module):
    """The /api routes still answer {error, request_id} and the engine payload verbatim."""
    fail_with(monkeypatch, app_module, TTSException("model broke"))
    resp = client.post("/api/tts", json={"text": "hi"})
    assert resp.status_code == 500
    assert resp.get_json()["error"] == "TTS failed"
    assert set(resp.get_json().keys()) == {"error", "request_id"}
    fail_with(monkeypatch, app_module, CustomError({"error": "voice_sample_missing", "message": "Record one."}))
    resp = client.post("/api/tts", json={"text": "hi"})
    assert resp.status_code == 422
    assert resp.get_json()["error"] == "voice_sample_missing"
    resp = client.get("/api/nothing-here")
    assert set(resp.get_json().keys()) == {"error", "request_id"}
