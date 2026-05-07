#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Health endpoint."""


def test_health_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert "engine" in body
    assert "pool_size" in body
    assert "available" in body
