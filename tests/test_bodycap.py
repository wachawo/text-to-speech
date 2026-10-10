#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the request body caps: TTS_MAX_BODY_BYTES on every route, TTS_MAX_SAMPLE_BYTES on the sample upload."""

import io
import json

import pytest


@pytest.fixture
def samples_dir(tmp_path, monkeypatch):
    """Point COQUITTS_SAMPLES at a fresh directory and unset the default sample."""
    samples = tmp_path / "samples"
    monkeypatch.setenv("COQUITTS_SAMPLES", str(samples))
    monkeypatch.delenv("COQUITTS_SAMPLE", raising=False)
    return samples


def test_json_body_over_the_default_cap_is_413(client):
    """A 3 MiB JSON body to /api/tts is refused against the documented 2 MiB cap, in the /api 413 shape."""
    body = json.dumps({"text": "a" * (3 * 1024 * 1024)})
    resp = client.post("/api/tts", data=body, content_type="application/json")
    assert resp.status_code == 413
    payload = resp.get_json()
    assert set(payload.keys()) == {"error", "limit_mb", "request_id"}
    assert payload["error"] == "Payload Too Large"
    assert payload["limit_mb"] == 2


def test_body_cap_follows_tts_max_body_bytes(client, monkeypatch, app_module):
    """The cap is read per request: a body over TTS_MAX_BODY_BYTES is 413 on any route, one under it is served."""
    monkeypatch.setattr(app_module, "TTS_MAX_BODY_BYTES", 1024)
    big = {"text": "a" * 2048}
    assert client.post("/api/tts", json=big).status_code == 413
    assert client.post("/api/history", json=big).status_code == 413
    assert client.post("/api/tts", json={"text": "hi"}).status_code == 200


def test_sample_upload_keeps_the_larger_cap(client, make_wav, samples_dir, monkeypatch, app_module):
    """A voice sample larger than TTS_MAX_BODY_BYTES but under TTS_MAX_SAMPLE_BYTES is still accepted."""
    monkeypatch.setattr(app_module, "TTS_MAX_BODY_BYTES", 1024)
    wav = make_wav(duration_ms=500)
    assert len(wav) > 1024
    data = {"name": "maria", "engine": "coquitts", "file": (io.BytesIO(wav), "voice.wav")}
    resp = client.post("/api/voices", data=data, content_type="multipart/form-data")
    assert resp.status_code == 201
    assert (samples_dir / "maria.wav").read_bytes() == wav
