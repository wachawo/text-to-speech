#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generic error response shape: {error, request_id} and nothing else."""

import re

HEX12 = re.compile(r"^[0-9a-f]{12}$")


def test_404_shape(client):
    resp = client.get("/api/nonexistent")
    assert resp.status_code == 404
    body = resp.get_json()
    assert set(body.keys()) == {"error", "request_id"}
    assert HEX12.match(body["request_id"])


def test_405_shape(client):
    resp = client.post("/api/health")
    assert resp.status_code == 405
    body = resp.get_json()
    assert set(body.keys()) == {"error", "request_id"}
    assert HEX12.match(body["request_id"])
    # Must surface exc.name, NOT a generic "Internal Server Error".
    assert body["error"] == "Method Not Allowed"


def test_arbitrary_http_exception_preserved(client):
    """An HTTP error with no dedicated handler reaches the client with exc.name, not as 500."""
    resp = client.get("/__test_abort/451")
    assert resp.status_code == 451
    body = resp.get_json()
    assert set(body.keys()) == {"error", "request_id"}
    assert body["error"] == "Unavailable For Legal Reasons"


def test_payload_too_large_shape(client):
    """413 has a dedicated handler that also reports the configured byte limit."""
    resp = client.get("/__test_abort/413")
    assert resp.status_code == 413
    body = resp.get_json()
    assert set(body.keys()) == {"error", "limit_mb", "request_id"}
    assert body["error"] == "Payload Too Large"
    assert isinstance(body["limit_mb"], int)


def test_unauthorized_http_exception_preserved(client):
    """abort(401) must reach the client as 401, not 500."""
    resp = client.get("/__test_abort/401")
    assert resp.status_code == 401
    body = resp.get_json()
    assert set(body.keys()) == {"error", "request_id"}
    assert body["error"] == "Unauthorized"


def test_request_id_changes_per_request(client):
    a = client.get("/api/nonexistent").get_json()["request_id"]
    b = client.get("/api/nonexistent").get_json()["request_id"]
    assert a != b
    assert HEX12.match(a) and HEX12.match(b)
