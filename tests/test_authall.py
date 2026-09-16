#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Every /api and /v1 route except the health probe must refuse a request without a token."""

# Local imports
import pytest


def api_rules(app_module):
    """Yield (rule, method) for every /api/* and /v1/* URL rule other than /api/health."""
    for rule in app_module.app.url_map.iter_rules():
        if not rule.rule.startswith(("/api/", "/v1/")) or rule.rule == "/api/health":
            continue
        for method in sorted(rule.methods - {"HEAD", "OPTIONS"}):
            yield rule.rule, method


def test_every_api_route_requires_a_token(client, monkeypatch, app_module):
    """With TTS_TOKENS set, each route answers 401 to a request that carries no token."""
    monkeypatch.setattr(app_module, "TTS_TOKENS", {"secret"}, raising=False)
    checked = 0
    for rule, method in api_rules(app_module):
        url = rule.replace("<name>", "maria").replace("<item_id>", "20260101_000000_abcdef")
        resp = client.open(url, method=method)
        assert resp.status_code == 401, f"{method} {url} answered {resp.status_code} without a token"
        checked += 1
    assert checked >= 15
    assert ("/v1/audio/speech", "POST") in api_rules(app_module)


def test_health_stays_open(client, monkeypatch, app_module):
    """The health probe is the one route a docker healthcheck reaches without a token."""
    monkeypatch.setattr(app_module, "TTS_TOKENS", {"secret"}, raising=False)
    assert client.get("/api/health").status_code == 200


@pytest.mark.parametrize("name", ["../x", "a/b", "a.b", "A B", ""])
def test_engine_names_with_separators_never_reach_the_filesystem(name):
    """get_engine_module_path refuses anything that is not a plain module stem."""
    from engines import get_engine_module_path

    assert get_engine_module_path(name) is None
