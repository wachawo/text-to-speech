#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for libs.exceptions.CustomError and its ttssrv error handler.

CustomError carries a structured payload that the HTTP layer returns
verbatim (plus request_id) with an explicit status code. No tracebacks
in logs, no 500 for predictable misconfiguration.
"""

import re

import pytest

from libs.exceptions import CustomError, TTSException

HEX12 = re.compile(r"^[0-9a-f]{12}$")


def test_payload_kept_intact():
    """Keep a defensive copy of the payload so later caller mutations do not leak in."""
    payload = {"error": "x", "message": "hello"}
    exc = CustomError(payload)
    assert exc.payload == payload
    # Defensive copy — caller mutating the dict afterwards must not affect us.
    payload["error"] = "mutated"
    assert exc.payload["error"] == "x"


def test_default_status_is_422():
    """Fall back to 422 when no status is supplied."""
    assert CustomError({"error": "x", "message": "y"}).status == 422


def test_explicit_status_respected():
    """Honour a status passed to the constructor."""
    assert CustomError({"error": "x"}, status=503).status == 503


def test_str_uses_message_then_error():
    """Render as message, then error code, then the class name as last resort."""
    assert str(CustomError({"error": "code", "message": "human text"})) == "human text"
    assert str(CustomError({"error": "only_code"})) == "only_code"
    assert str(CustomError({})) == "CustomError"


def test_is_a_ttsexception():
    """Must be catchable as TTSException for backwards compatibility."""
    with pytest.raises(TTSException):
        raise CustomError({"error": "x", "message": "y"})


def test_handler_returns_payload_verbatim(client, app_module, monkeypatch):
    """Server must mirror payload as response body and use exc.status."""

    def boom(text, engine=None, language=None, voice=None):
        """Stand in for synthesis and raise a CustomError with a rich payload."""
        raise CustomError({"error": "voice_sample_missing", "message": "no wav at /opt/x.wav", "path": "/opt/x.wav"})

    monkeypatch.setattr(app_module, "text_to_speech_bytes", boom)

    resp = client.post("/api/tts", json={"text": "hi"})
    assert resp.status_code == 422
    body = resp.get_json()
    assert body["error"] == "voice_sample_missing"
    assert body["message"] == "no wav at /opt/x.wav"
    assert body["path"] == "/opt/x.wav"
    assert HEX12.match(body["request_id"])


def test_handler_uses_custom_status(client, app_module, monkeypatch):
    """503 from CustomError(status=503) must reach the wire as 503, not 422/500."""

    def boom(text, engine=None, language=None, voice=None):
        """Stand in for synthesis and raise a CustomError carrying status 503."""
        raise CustomError({"error": "busy", "message": "all backends down"}, status=503)

    monkeypatch.setattr(app_module, "text_to_speech_bytes", boom)
    resp = client.post("/api/tts", json={"text": "hi"})
    assert resp.status_code == 503
    body = resp.get_json()
    assert body["error"] == "busy"


def test_handler_does_not_overwrite_existing_request_id(client, app_module, monkeypatch):
    """Preserve a request_id already present in the payload (setdefault semantics)."""

    def boom(text, engine=None, language=None, voice=None):
        """Stand in for synthesis and raise a CustomError that pre-sets request_id."""
        raise CustomError({"error": "x", "message": "m", "request_id": "deadbeef0000"})

    monkeypatch.setattr(app_module, "text_to_speech_bytes", boom)
    resp = client.post("/api/tts", json={"text": "hi"})
    body = resp.get_json()
    assert body["request_id"] == "deadbeef0000"
