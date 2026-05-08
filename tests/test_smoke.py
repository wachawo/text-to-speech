#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke test — exercises /api/tts end-to-end with the stubbed audio pipeline.

Writes to pytest's tmp_path to stay race-free under `pytest -n auto` and
shared CI workspaces; the file is discarded after the run.
"""


def test_smoke_writes_sample(client, tmp_path):
    resp = client.post("/api/tts", json={"text": "smoke test"})
    assert resp.status_code == 200
    assert len(resp.data) > 44

    out = tmp_path / "test.mp3"
    out.write_bytes(resp.data)
    assert out.stat().st_size == len(resp.data)
