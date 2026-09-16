#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for libs.logjson.JsonFormatter and the structured fields ttssrv.app1 attaches to its log lines."""

import io
import json
import logging
import sys

import pytest

from libs.logjson import JsonFormatter


def make_record(msg="hello", **extra):
    """Build a LogRecord the way logging does for logger.info(msg, extra=...)."""
    record = logging.LogRecord("demo", logging.INFO, __file__, 1, msg, (), None, func="demo_func")
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_basic_fields_are_valid_json():
    """The line parses as JSON and carries ts, level, logger, func and msg."""
    line = JsonFormatter().format(make_record("hello %s"))
    body = json.loads(line)
    assert body["level"] == "INFO"
    assert body["logger"] == "demo"
    assert body["func"] == "demo_func"
    assert body["msg"] == "hello %s"
    assert len(body["ts"]) == 23 and body["ts"][10] == "T" and body["ts"][19] == "."
    assert "request_id" not in body
    assert "exc" not in body


def test_extras_and_request_id_appear_as_keys():
    """Fields attached through extra= become top-level keys, request_id included."""
    body = json.loads(JsonFormatter().format(make_record(request_id="abc123", engine="gtts", ms=12, ok=True)))
    assert body["request_id"] == "abc123"
    assert body["engine"] == "gtts"
    assert body["ms"] == 12
    assert body["ok"] is True


def test_exc_info_adds_traceback():
    """A record logged with exc_info carries the formatted traceback under exc."""
    try:
        raise ValueError("bad value")
    except ValueError:
        record = logging.LogRecord("demo", logging.ERROR, __file__, 1, "failed", (), sys.exc_info())
    body = json.loads(JsonFormatter().format(record))
    assert "ValueError: bad value" in body["exc"]
    assert "Traceback" in body["exc"]


def test_non_serializable_extra_becomes_string():
    """A value json cannot encode is written through str() instead of failing the log call."""
    marker = object()
    body = json.loads(JsonFormatter().format(make_record(handle=marker)))
    assert body["handle"] == str(marker)


@pytest.fixture
def json_lines(app_module):
    """Attach a JsonFormatter handler to the app logger and return a callable that parses its lines."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    app_logger = logging.getLogger("ttssrv.app1")
    # An earlier CLI test may have left the root logger at ERROR; INFO is what the server runs at.
    previous_level = app_logger.level
    app_logger.setLevel(logging.INFO)
    app_logger.addHandler(handler)
    try:
        yield lambda: [json.loads(line) for line in stream.getvalue().splitlines() if line]
    finally:
        app_logger.removeHandler(handler)
        app_logger.setLevel(previous_level)


def test_app_lines_carry_structured_fields(client, json_lines, make_wav):
    """In JSON mode the request line and the Synthesis line carry request_id and their fields."""
    resp = client.post("/api/tts", json={"text": "hello", "engine": "gtts", "language": "en"})
    assert resp.status_code == 200
    request_id = resp.headers["X-Request-Id"]
    records = json_lines()
    synthesis = [record for record in records if record.get("event") == "synthesis"]
    assert len(synthesis) == 1
    assert synthesis[0]["request_id"] == request_id
    assert synthesis[0]["engine"] == "gtts"
    assert synthesis[0]["language"] == "en"
    assert synthesis[0]["voice"] is None
    assert synthesis[0]["chars"] == 5
    assert synthesis[0]["bytes"] == len(make_wav())
    assert synthesis[0]["ms"] >= 0
    assert synthesis[0]["ok"] is True
    assert synthesis[0]["error"] is None
    request_lines = [record for record in records if record.get("path") == "/api/tts"]
    assert len(request_lines) == 1
    assert request_lines[0]["request_id"] == request_id
    assert request_lines[0]["method"] == "POST"
    assert request_lines[0]["status"] == 200
    assert request_lines[0]["ms"] >= 0


def test_failed_synthesis_line_names_the_error(client, json_lines, monkeypatch, app_module):
    """A failing engine call logs ok=false with the exception class name and no bytes."""

    def boom(text, engine=None, language=None, voice=None):
        """Fail like a broken engine would."""
        raise RuntimeError("engine exploded")

    monkeypatch.setattr(app_module, "text_to_speech_bytes", boom)
    assert client.post("/api/tts", json={"text": "hi"}).status_code == 500
    synthesis = [record for record in json_lines() if record.get("event") == "synthesis"]
    assert synthesis[0]["ok"] is False
    assert synthesis[0]["error"] == "RuntimeError"
    assert synthesis[0]["bytes"] is None


def test_incoming_request_id_is_echoed(client):
    """A well-formed X-Request-Id is kept as the correlation id and sent back."""
    resp = client.get("/api/health", headers={"X-Request-Id": "trace-1.2_3"})
    assert resp.headers["X-Request-Id"] == "trace-1.2_3"


@pytest.mark.parametrize("bad", ["has space", "x" * 100, 'quote"d', ""])
def test_invalid_request_id_is_replaced(client, bad):
    """An X-Request-Id with spaces, quotes, over 64 chars or empty is replaced by a generated one."""
    resp = client.get("/api/health", headers={"X-Request-Id": bad})
    echoed = resp.headers["X-Request-Id"]
    assert echoed != bad
    assert len(echoed) == 12


def test_error_responses_carry_request_id(client):
    """Error responses go through after_request too, so they echo the id in the header and body."""
    resp = client.get("/api/history/nope", headers={"X-Request-Id": "err-42"})
    assert resp.status_code == 404
    assert resp.headers["X-Request-Id"] == "err-42"
    assert resp.get_json()["request_id"] == "err-42"
