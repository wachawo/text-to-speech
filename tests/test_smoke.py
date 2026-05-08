#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke test — exercises /api/tts and writes the result to samples/test.mp3.

The file is gitignored (see .gitignore: samples/) and serves as a manual
artifact you can play after `pytest` to confirm the audio pipeline works
end-to-end.
"""

from pathlib import Path

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"
SAMPLE_FILE = SAMPLES_DIR / "test.mp3"


def test_smoke_writes_sample(client):
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    resp = client.post("/api/tts", json={"text": "smoke test"})
    assert resp.status_code == 200
    assert len(resp.data) > 44

    SAMPLE_FILE.write_bytes(resp.data)
    assert SAMPLE_FILE.exists()
    assert SAMPLE_FILE.stat().st_size == len(resp.data)
