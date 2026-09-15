#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for GET /api/models and the `language` field added to GET /api/engines."""


def test_models_maps_rows_to_objects(client, monkeypatch, app_module):
    """Every (engine, status, model) row becomes one object, order preserved."""
    rows = [
        ("coquitts", "installed", "tts_models/multilingual/multi-dataset/xtts_v2"),
        ("gtts", "installed", "cloud - no local models"),
        ("pipertts", "missing", "-"),
    ]
    monkeypatch.setattr(app_module, "collect_engine_rows", lambda: rows)
    resp = client.get("/api/models")
    assert resp.status_code == 200
    assert resp.get_json() == {
        "models": [
            {"engine": "coquitts", "status": "installed", "model": "tts_models/multilingual/multi-dataset/xtts_v2"},
            {"engine": "gtts", "status": "installed", "model": "cloud - no local models"},
            {"engine": "pipertts", "status": "missing", "model": "-"},
        ]
    }


def test_models_empty(client, monkeypatch, app_module):
    """No rows at all still answers a well-formed empty list."""
    monkeypatch.setattr(app_module, "collect_engine_rows", lambda: [])
    resp = client.get("/api/models")
    assert resp.status_code == 200
    assert resp.get_json() == {"models": []}


def test_models_real_rows_have_the_documented_shape(client):
    """The unpatched listing yields one object per shipped engine with the three documented keys."""
    resp = client.get("/api/models")
    assert resp.status_code == 200
    models = resp.get_json()["models"]
    assert models, "at least the shipped engines must be listed"
    for row in models:
        assert set(row.keys()) == {"engine", "status", "model"}
        assert row["status"] in ("installed", "missing")
    assert "gtts" in {row["engine"] for row in models}


def test_models_rejects_post(client):
    """The listing is read-only."""
    resp = client.post("/api/models")
    assert resp.status_code == 405
    assert set(resp.get_json().keys()) == {"error", "request_id"}


def test_engines_reports_default_language(client, app_module):
    """/api/engines now carries the server default language next to the default engine."""
    resp = client.get("/api/engines")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["language"] == app_module.TTS_LANGUAGE_DEFAULT
    assert body["default"] == app_module.TTS_ENGINE_DEFAULT
    assert set(body.keys()) == {"supported", "available", "preload", "default", "language"}
