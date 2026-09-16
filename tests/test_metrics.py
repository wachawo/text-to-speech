#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for ttssrv.metrics: registry math, thread safety, the two metrics routes and the warmup flag."""

import threading

import pytest

from libs.exceptions import ValidationError
from ttssrv import metrics


@pytest.fixture
def registry(app_module):
    """Empty the shared registry before and after a test so earlier synthesis calls do not count."""
    metrics.reset()
    yield metrics
    metrics.reset()


def snapshot_of(available=()):
    """Snapshot with fixed pool numbers, for tests that only look at the engines."""
    return metrics.snapshot(pool_size=1, pool_available=1, queue_size=8, available=available)


def test_percentile_nearest_rank():
    """p50/p95/p99 pick the nearest-rank element of the sorted values; empty input gives None."""
    values = list(range(100, 0, -1))
    assert metrics.percentile(values, 50) == 50
    assert metrics.percentile(values, 95) == 95
    assert metrics.percentile(values, 99) == 99
    assert metrics.percentile([7], 99) == 7
    assert metrics.percentile([], 50) is None


def test_record_and_snapshot_math(registry):
    """Counts, failures, last error and the latency statistics add up for one engine."""
    for ms in (10, 20, 30, 40):
        registry.record("gtts", ms, True)
    registry.record("gtts", 100, False, "RuntimeError")
    engine = snapshot_of(available=["gtts"])["engines"]["gtts"]
    assert engine["calls"] == 5
    assert engine["failures"] == 1
    assert engine["last_error"] == "RuntimeError"
    assert engine["last_error_at"] is not None
    assert engine["p50_ms"] == 30
    assert engine["p95_ms"] == 100
    assert engine["p99_ms"] == 100
    assert engine["avg_ms"] == 40
    assert engine["sum_ms"] == 200
    assert engine["available"] is True
    assert engine["warm"] is False


def test_latency_window_is_capped(registry):
    """Only the last 1000 latencies feed the percentiles, while the counters keep every call."""
    for ms in range(2000):
        registry.record("gtts", ms, True)
    stats = registry.ENGINES["gtts"]
    assert len(stats["latencies"]) == 1000
    assert stats["latencies"][0] == 1000
    assert snapshot_of()["engines"]["gtts"]["calls"] == 2000


def test_record_is_thread_safe(registry):
    """8 threads recording 200 calls each end with exactly 1600 calls and 800 failures."""

    def work():
        """Record 200 calls, every other one failing."""
        for index in range(200):
            registry.record("gtts", index, index % 2 == 0, None if index % 2 == 0 else "Boom")

    threads = [threading.Thread(target=work) for unused_index in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    engine = snapshot_of()["engines"]["gtts"]
    assert engine["calls"] == 1600
    assert engine["failures"] == 800


def test_wait_end_returns_counter_to_zero(registry):
    """wait_begin raises the waiting gauge to 1 and wait_end brings it back to 0."""
    registry.wait_begin()
    assert snapshot_of()["pool"]["waiting"] == 1
    registry.wait_end()
    assert snapshot_of()["pool"]["waiting"] == 0


def test_escape_label(registry):
    """Backslash, quote and newline in a label value are escaped as the exposition format requires."""
    assert metrics.escape_label('a\\b"c\nd') == 'a\\\\b\\"c\\nd'
    text = metrics.prometheus_text(
        {"uptime_s": 0, "pool": {"size": 1, "available": 1, "queue_size": 8, "waiting": 0}, "engines": {}}
    )
    assert "tts_synthesis_total" in text
    registry.record('we"ird', 5, True)
    text = metrics.prometheus_text(snapshot_of())
    assert 'tts_synthesis_total{engine="we\\"ird",result="ok"} 1' in text


def synthesize_three(client, monkeypatch, app_module):
    """Two successful stubbed /api/tts calls and one that fails inside the engine."""
    for unused_index in range(2):
        assert client.post("/api/tts", json={"text": "hi", "engine": "gtts"}).status_code == 200

    def boom(text, engine=None, language=None, voice=None):
        """Fail like a broken engine would."""
        raise RuntimeError("engine exploded")

    monkeypatch.setattr(app_module, "text_to_speech_bytes", boom)
    assert client.post("/api/tts", json={"text": "hi", "engine": "gtts"}).status_code == 500


def test_api_metrics_counts_calls(client, registry, monkeypatch, app_module):
    """GET /api/metrics reports calls=3 failures=1 with the error name after two ok calls and a failure."""
    monkeypatch.setattr(app_module, "get_available_engines", lambda: {"gtts": None})
    synthesize_three(client, monkeypatch, app_module)
    resp = client.get("/api/metrics")
    assert resp.status_code == 200
    body = resp.get_json()
    engine = body["engines"]["gtts"]
    assert engine["calls"] == 3
    assert engine["failures"] == 1
    assert engine["last_error"] == "RuntimeError"
    assert engine["available"] is True
    assert engine["p50_ms"] >= 0
    assert body["uptime_s"] >= 0


def test_prometheus_metrics_text(client, registry, monkeypatch, app_module):
    """GET /metrics carries the counters, the quantile lines and the exposition content type."""
    synthesize_three(client, monkeypatch, app_module)
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert resp.content_type == "text/plain; version=0.0.4; charset=utf-8"
    text = resp.get_data(as_text=True)
    assert 'tts_synthesis_total{engine="gtts",result="ok"} 2' in text
    assert 'tts_synthesis_total{engine="gtts",result="failed"} 1' in text
    for quantile in ("0.5", "0.95", "0.99"):
        assert f'tts_synthesis_latency_ms{{engine="gtts",quantile="{quantile}"}} ' in text
    assert 'tts_synthesis_latency_ms_count{engine="gtts"} 3' in text
    assert 'tts_engine_available{engine="gtts"} 0' in text
    assert "# TYPE tts_synthesis_latency_ms summary" in text


def test_metrics_pool_matches_health(client, registry):
    """The pool block of /api/metrics carries the same numbers /api/health does."""
    health = client.get("/api/health").get_json()
    pool = client.get("/api/metrics").get_json()["pool"]
    assert pool["size"] == health["pool_size"]
    assert pool["available"] == health["available"]
    assert pool["queue_size"] == health["queue_size"]
    assert pool["waiting"] == 0


def test_waiting_drops_back_after_a_pooled_request(client, registry, monkeypatch, app_module):
    """With one pool slot a request waits for it and the waiting gauge is 0 again once it is served."""
    monkeypatch.setattr(app_module, "TTS_POOL_SIZE", 1)
    app_module.ENGINE_POOL.put(0)
    try:
        assert client.post("/api/tts", json={"text": "hi"}).status_code == 200
        assert client.get("/api/metrics").get_json()["pool"]["waiting"] == 0
    finally:
        while not app_module.ENGINE_POOL.empty():
            app_module.ENGINE_POOL.get_nowait()


def test_unknown_engine_name_is_not_recorded(client, registry, monkeypatch, app_module):
    """A request refused by validation never reached an engine, so its name does not become a registry key."""

    def refuse(text, engine=None, language=None, voice=None):
        """Refuse the engine name the way validate_engine does for a module that does not exist."""
        raise ValidationError(f"Unknown engine: {engine}")

    monkeypatch.setattr(app_module, "text_to_speech_bytes", refuse)
    for index in range(5):
        assert client.post("/api/tts", json={"text": "hi", "engine": f"{index}" * 1000}).status_code == 400
    assert client.get("/api/metrics").get_json()["engines"] == {}


def test_metrics_routes_require_token(client, registry, monkeypatch, app_module):
    """Both metrics routes answer 401 without a bearer token once TTS_TOKENS is set."""
    monkeypatch.setattr(app_module, "TTS_TOKENS", {"secret"}, raising=False)
    assert client.get("/api/metrics").status_code == 401
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer secret"}).status_code == 200


def warm_up(app_module, monkeypatch, synth):
    """Run init_engine_pool with one slot for a fake engine and drain the pool afterwards."""
    monkeypatch.setattr(app_module, "text_to_speech_bytes", synth)
    monkeypatch.setattr(app_module, "TTS_ENGINES", ["fakeengine"])
    app_module.init_engine_pool(size=1)
    try:
        return metrics.snapshot(1, app_module.ENGINE_POOL.qsize(), 8, [])["engines"]["fakeengine"]
    finally:
        while not app_module.ENGINE_POOL.empty():
            app_module.ENGINE_POOL.get_nowait()


def test_warmup_outcome_sets_warm(app_module, registry, monkeypatch, make_wav):
    """A successful warmup marks the engine warm and counts as its first call; a failed one does neither."""
    engine = warm_up(app_module, monkeypatch, lambda text, engine=None, language=None, voice=None: make_wav())
    assert engine["warm"] is True
    assert engine["calls"] == 1
    assert engine["failures"] == 0

    def boom(text, engine=None, language=None, voice=None):
        """Fail like a model that did not load."""
        raise RuntimeError("no model")

    metrics.reset()
    engine = warm_up(app_module, monkeypatch, boom)
    assert engine["warm"] is False
    assert engine["calls"] == 1
    assert engine["failures"] == 1
    assert engine["last_error"] == "RuntimeError"
