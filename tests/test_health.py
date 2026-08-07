#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the open /api/health endpoint."""


def test_health_ok(client):
    """Health returns 200 with the status flag and the engine/pool diagnostics."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert "engine" in body
    assert "pool_size" in body
    assert "available" in body
