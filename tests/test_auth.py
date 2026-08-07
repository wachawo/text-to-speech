#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Optional static-token auth via TTS_TOKENS / Authorization: Bearer."""


def test_no_tokens_allows_all(client):
    """TTS_TOKENS empty (default) → no auth required."""
    resp = client.post("/api/tts", json={"text": "hi"})
    assert resp.status_code == 200


def test_missing_token_when_required(client, monkeypatch, app_module):
    """With tokens configured, an unauthenticated request gets 401 and a minimal body."""
    monkeypatch.setattr(app_module, "TTS_TOKENS", {"secret"})
    resp = client.post("/api/tts", json={"text": "hi"})
    assert resp.status_code == 401
    body = resp.get_json()
    assert set(body.keys()) == {"error", "request_id"}
    assert body["error"] == "Unauthorized"


def test_wrong_bearer_token(client, monkeypatch, app_module):
    """A Bearer token that is not in TTS_TOKENS is rejected with 401."""
    monkeypatch.setattr(app_module, "TTS_TOKENS", {"secret"})
    resp = client.post(
        "/api/tts",
        json={"text": "hi"},
        headers={"Authorization": "Bearer wrong"},
    )
    assert resp.status_code == 401


def test_invalid_scheme(client, monkeypatch, app_module):
    """Only the Bearer scheme is honoured — Basic credentials are rejected."""
    monkeypatch.setattr(app_module, "TTS_TOKENS", {"secret"})
    resp = client.post(
        "/api/tts",
        json={"text": "hi"},
        headers={"Authorization": "Basic c2VjcmV0"},
    )
    assert resp.status_code == 401


def test_correct_bearer_token(client, monkeypatch, app_module):
    """A Bearer token listed in TTS_TOKENS grants access to the synthesis endpoint."""
    monkeypatch.setattr(app_module, "TTS_TOKENS", {"secret"})
    resp = client.post(
        "/api/tts",
        json={"text": "hi"},
        headers={"Authorization": "Bearer secret"},
    )
    assert resp.status_code == 200


def test_health_does_not_require_token(client, monkeypatch, app_module):
    """docker-compose healthchecks must keep working with auth enabled."""
    monkeypatch.setattr(app_module, "TTS_TOKENS", {"secret"})
    resp = client.get("/api/health")
    assert resp.status_code == 200
