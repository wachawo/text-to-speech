#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for POST /api/voices (sample upload) and DELETE /api/voices/<name>."""

import io

import pytest

# Local imports
from engines import coquitts


@pytest.fixture
def samples_dir(tmp_path, monkeypatch):
    """Point COQUITTS_SAMPLES at a fresh directory and unset the default sample."""
    samples = tmp_path / "samples"
    monkeypatch.setenv("COQUITTS_SAMPLES", str(samples))
    monkeypatch.delenv("COQUITTS_SAMPLE", raising=False)
    return samples


def upload(client, wav_bytes, name="maria", engine="coquitts", filename="voice.wav"):
    """POST a multipart voice upload and return the response."""
    data = {"name": name, "engine": engine}
    if wav_bytes is not None:
        data["file"] = (io.BytesIO(wav_bytes), filename)
    return client.post("/api/voices", data=data, content_type="multipart/form-data")


def test_upload_wav_creates_sample_and_lists_it(client, make_wav, samples_dir, monkeypatch, app_module):
    """A PCM WAV upload lands as <samples>/<name>.wav and shows up in the voice catalogue."""
    resp = upload(client, make_wav(duration_ms=500, rate=22050))
    assert resp.status_code == 201
    body = resp.get_json()
    assert body == {
        "engine": "coquitts",
        "voice": "maria",
        "bytes": len(make_wav(duration_ms=500, rate=22050)),
        "rate": 22050,
        "channels": 1,
        "seconds": 0.5,
    }
    assert (samples_dir / "maria.wav").is_file()
    assert not (samples_dir / "maria.wav.tmp").exists()

    # The listing must not need torch: the route reads the samples directory
    # even on a host where the engine itself is unavailable.
    monkeypatch.setattr(coquitts, "AVAILABLE", False)
    listed = client.get("/api/voices?engine=coquitts")
    assert listed.status_code == 200
    assert listed.get_json()["voices"] == ["maria"]


def test_upload_duplicate_name_400(client, make_wav, samples_dir):
    """A second upload under an existing name is refused and the first file is kept."""
    assert upload(client, make_wav()).status_code == 201
    before = (samples_dir / "maria.wav").read_bytes()
    resp = upload(client, make_wav(duration_ms=300))
    assert resp.status_code == 400
    body = resp.get_json()
    assert set(body.keys()) == {"error", "message", "request_id"}
    assert body["message"] == "Voice 'maria' already exists"
    assert (samples_dir / "maria.wav").read_bytes() == before


def test_upload_non_wav_400(client, samples_dir):
    """Bytes that `wave` cannot open (MP3, truncated RIFF, empty) are refused and nothing is written."""
    for blob in (b"ID3\x03\x00\x00\x00\x00\x00\x00not audio at all", b"RIFF" + b"\x00" * 40, b""):
        resp = upload(client, blob)
        assert resp.status_code == 400, blob[:4]
        assert resp.get_json()["error"] == "Bad Request"
    assert not samples_dir.exists() or list(samples_dir.iterdir()) == []


def test_upload_too_large_413(client, make_wav, samples_dir, monkeypatch, app_module):
    """A sample above TTS_MAX_SAMPLE_BYTES is refused even when the body cap is larger."""
    monkeypatch.setattr(app_module, "TTS_MAX_SAMPLE_BYTES", 1024)
    resp = upload(client, make_wav(duration_ms=500))
    assert resp.status_code == 413
    assert resp.get_json()["error"] == "Payload Too Large"
    assert not samples_dir.exists()


def test_upload_bad_name_400(client, make_wav, samples_dir):
    """A name with a path separator, a dot or a trailing newline fails the schema regexp."""
    for name in ("../escape", "a.b", "", "x" * 49, "maria\n"):
        resp = upload(client, make_wav(), name=name)
        assert resp.status_code == 400, name
    assert not samples_dir.exists()


def test_upload_other_engine_400(client, make_wav, samples_dir):
    """Only coquitts clones voices from samples; other engines are refused."""
    resp = upload(client, make_wav(), engine="silerotts")
    assert resp.status_code == 400
    assert not samples_dir.exists()


def test_upload_missing_file_400(client, samples_dir):
    """A form without the `file` part is a bad request, not a 500."""
    resp = upload(client, None)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Bad Request"


def test_delete_voice_then_404(client, make_wav, samples_dir):
    """Deleting removes the file; a second delete answers 404."""
    assert upload(client, make_wav()).status_code == 201
    resp = client.delete("/api/voices/maria?engine=coquitts")
    assert resp.status_code == 200
    assert resp.get_json() == {"result": True}
    assert not (samples_dir / "maria.wav").exists()

    resp = client.delete("/api/voices/maria?engine=coquitts")
    assert resp.status_code == 404
    assert set(resp.get_json().keys()) == {"error", "request_id"}


def test_delete_default_voice_allowed(client, make_wav, samples_dir, monkeypatch):
    """The voice named by COQUITTS_SAMPLE can be deleted like any other sample."""
    assert upload(client, make_wav()).status_code == 201
    monkeypatch.setenv("COQUITTS_SAMPLE", str(samples_dir / "maria.wav"))
    resp = client.delete("/api/voices/maria?engine=coquitts")
    assert resp.status_code == 200
    assert not (samples_dir / "maria.wav").exists()


def test_voices_list_describes_samples(client, make_wav, samples_dir, monkeypatch):
    """GET /api/voices for coquitts carries size, rate, channels and seconds per sample."""
    monkeypatch.setattr(coquitts, "AVAILABLE", False)
    wav = make_wav(duration_ms=500, rate=22050)
    assert upload(client, wav).status_code == 201
    (samples_dir / "broken.wav").write_bytes(b"RIFF" + b"\x00" * 8)

    body = client.get("/api/voices?engine=coquitts").get_json()
    assert body["voices"] == ["broken", "maria"]
    assert body["samples"] == [
        {"name": "broken", "bytes": 12, "rate": None, "channels": None, "seconds": None},
        {"name": "maria", "bytes": len(wav), "rate": 22050, "channels": 1, "seconds": 0.5},
    ]


def test_delete_bad_name_400_without_touching_disk(client, samples_dir):
    """An invalid name is rejected by the schema before any filesystem lookup."""
    resp = client.delete("/api/voices/a.b?engine=coquitts")
    assert resp.status_code == 400
    resp = client.delete("/api/voices/maria%0A?engine=coquitts")
    assert resp.status_code == 400
    resp = client.delete("/api/voices/maria?engine=gtts")
    assert resp.status_code == 400
    resp = client.delete("/api/voices/maria")
    assert resp.status_code == 400


def test_voice_audio_inline_and_download(client, make_wav, samples_dir):
    """The sample is served as WAV inline by default and as an attachment with ?download=1."""
    wav = make_wav(duration_ms=200)
    assert upload(client, wav).status_code == 201

    resp = client.get("/api/voices/maria/audio?engine=coquitts")
    assert resp.status_code == 200
    assert resp.mimetype == "audio/wav"
    assert resp.data == wav
    assert "attachment" not in resp.headers.get("Content-Disposition", "")

    resp = client.get("/api/voices/maria/audio?engine=coquitts&download=1")
    assert resp.status_code == 200
    assert resp.headers["Content-Disposition"] == "attachment; filename=maria.wav"


def test_voice_audio_missing_404_and_bad_name_400(client, samples_dir):
    """An unknown voice answers 404; a name outside the regexp is refused before any disk access."""
    resp = client.get("/api/voices/maria/audio?engine=coquitts")
    assert resp.status_code == 404
    assert set(resp.get_json().keys()) == {"error", "request_id"}

    resp = client.get("/api/voices/..%2Fetc/audio?engine=coquitts")
    assert resp.status_code in (400, 404)
    assert not samples_dir.exists()
