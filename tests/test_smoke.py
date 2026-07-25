#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke test exercising /api/tts end-to-end against the stubbed audio pipeline.

Writes to pytest's tmp_path to stay race-free under `pytest -n auto` and
shared CI workspaces; the file is discarded after the run.
"""


def test_smoke_writes_sample(client, tmp_path):
    """A minimal synthesis request returns playable audio that survives a round-trip to disk."""
    resp = client.post("/api/tts", json={"text": "smoke test"})
    assert resp.status_code == 200
    assert len(resp.data) > 44

    out = tmp_path / "test.mp3"
    out.write_bytes(resp.data)
    assert out.stat().st_size == len(resp.data)
