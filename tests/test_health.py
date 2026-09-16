#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the open /api/health endpoint."""


def test_health_ok(client):
    """Health returns 200 with the status flag and the engine/pool diagnostics."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert body["auth"] is False
    assert "engine" in body
    assert "pool_size" in body
    assert "available" in body


def test_health_reports_auth_when_tokens_are_set(client, monkeypatch, app_module):
    """With TTS_TOKENS configured the open health endpoint says a token is required."""
    monkeypatch.setattr(app_module, "TTS_TOKENS", {"secret"}, raising=False)
    body = client.get("/api/health").get_json()
    assert body["auth"] is True
