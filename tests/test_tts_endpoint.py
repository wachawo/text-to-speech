#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""POST/GET /api/tts: success + error paths."""

from libs.exceptions import EngineNotAvailableError, TTSException

INTERNAL_MARKER = "INTERNAL-MARKER-9876"


def test_tts_post_success_wav(client):
    resp = client.post("/api/tts", json={"text": "hello"})
    assert resp.status_code == 200
    assert resp.mimetype in ("audio/wav", "audio/mpeg")
    assert len(resp.data) > 44  # WAV header + samples


def test_tts_get_success(client):
    resp = client.get("/api/tts?text=hi")
    assert resp.status_code == 200


def test_tts_empty_text_400(client):
    resp = client.post("/api/tts", json={"text": ""})
    assert resp.status_code == 400
    body = resp.get_json()
    assert set(body.keys()) == {"error", "request_id"}
    assert body["error"] == "Bad Request"


def test_tts_missing_text_400(client):
    resp = client.post("/api/tts", json={})
    assert resp.status_code == 400
    body = resp.get_json()
    assert set(body.keys()) == {"error", "request_id"}


def test_tts_text_too_long_400(client):
    resp = client.post("/api/tts", json={"text": "a" * 1_000_001})
    assert resp.status_code == 400
    body = resp.get_json()
    assert set(body.keys()) == {"error", "request_id"}


def test_tts_long_text_under_limit_ok(client):
    """Text under 1M chars passes validation — chunking is downstream."""
    resp = client.post("/api/tts", json={"text": "a" * 50_000})
    assert resp.status_code == 200


def test_tts_invalid_language_400(client):
    resp = client.post("/api/tts", json={"text": "hi", "language": "english"})
    assert resp.status_code == 400
    body = resp.get_json()
    assert set(body.keys()) == {"error", "request_id"}


def test_tts_engine_not_available_503(client, monkeypatch, app_module):
    def boom(text, engine=None, language=None):
        raise EngineNotAvailableError("Engine xyz not installed")

    monkeypatch.setattr(app_module, "text_to_speech_bytes", boom)
    resp = client.post("/api/tts", json={"text": "hi", "engine": "xyz"})
    assert resp.status_code == 503
    body = resp.get_json()
    assert set(body.keys()) == {"error", "request_id"}
    assert body["error"] == "Service Unavailable"


def test_tts_internal_failure_no_leak(client, monkeypatch, app_module):
    """Critical regression guard: internals must not appear in the body."""

    def boom(text, engine=None, language=None):
        raise TTSException(INTERNAL_MARKER)

    monkeypatch.setattr(app_module, "text_to_speech_bytes", boom)
    resp = client.post("/api/tts", json={"text": "hi"})
    assert resp.status_code == 500
    body_bytes = resp.get_data()
    body_str = body_bytes.decode("utf-8", errors="replace")
    assert INTERNAL_MARKER not in body_str
    assert "TTSException" not in body_str
    body = resp.get_json()
    assert set(body.keys()) == {"error", "request_id"}
    assert body["error"] == "TTS failed"


def test_tts_unexpected_exception_no_leak(client, monkeypatch, app_module):
    def boom(text, engine=None, language=None):
        raise RuntimeError(INTERNAL_MARKER)

    monkeypatch.setattr(app_module, "text_to_speech_bytes", boom)
    resp = client.post("/api/tts", json={"text": "hi"})
    assert resp.status_code == 500
    body_str = resp.get_data().decode("utf-8", errors="replace")
    assert INTERNAL_MARKER not in body_str
    assert "RuntimeError" not in body_str
    body = resp.get_json()
    assert set(body.keys()) == {"error", "request_id"}
    assert body["error"] == "Internal Server Error"
