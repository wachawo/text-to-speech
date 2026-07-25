#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for ttsapi client: Authorization Bearer header handling."""

import sys
from pathlib import Path

import pytest

# The repository root must be on sys.path before `ttsapi` is imported,
# so that import deliberately stays below this insert (E402 is expected).
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Local imports
import ttsapi  # noqa: E402


class FakeResponse:
    """Minimal stand-in for `requests.Response` used by the mocked HTTP calls."""

    def __init__(self, status: int = 200, content: bytes = b"abc", json_data: dict | None = None):
        """Store the canned status, body and JSON payload to hand back to the client."""
        self.status_code = status
        self.content = content
        self.json_payload = json_data or {}
        self.text = ""

    def json(self):
        """Return the canned JSON payload."""
        return self.json_payload

    def raise_for_status(self):
        """Raise for 4xx/5xx status codes, mirroring the requests contract."""
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


@pytest.fixture
def captured_calls(monkeypatch):
    """Capture (verb, url, kwargs) for each requests.{post,get} call."""
    calls: list[tuple[str, str, dict]] = []

    def fake_post(url, **kwargs):
        """Record a POST and answer with canned audio bytes."""
        calls.append(("POST", url, kwargs))
        return FakeResponse(status=200, content=b"audio")

    def fake_get(url, **kwargs):
        """Record a GET and answer with a canned engine listing."""
        calls.append(("GET", url, kwargs))
        return FakeResponse(status=200, json_data={"engines": ["gtts"], "default": "gtts"})

    monkeypatch.setattr(ttsapi.requests, "post", fake_post)
    monkeypatch.setattr(ttsapi.requests, "get", fake_get)
    return calls


def test_fetch_audio_sends_bearer_when_token_set(monkeypatch, captured_calls):
    """A configured TTS_TOKEN is sent as a Bearer header on the synthesis POST."""
    monkeypatch.setenv("TTS_TOKEN", "deadbeef")
    monkeypatch.setenv("TTS_URL", "http://example:5000")

    ttsapi.fetch_audio("hi", "gtts", "en")

    assert len(captured_calls) == 1
    verb, url, kwargs = captured_calls[0]
    assert verb == "POST"
    assert url == "http://example:5000/api/tts"
    assert kwargs["headers"] == {"Authorization": "Bearer deadbeef"}
    assert kwargs["json"] == {"text": "hi", "engine": "gtts", "language": "en"}


def test_fetch_audio_no_auth_header_when_token_empty(monkeypatch, captured_calls):
    """An empty TTS_TOKEN produces no Authorization header at all."""
    monkeypatch.setenv("TTS_TOKEN", "")
    monkeypatch.setenv("TTS_URL", "http://example:5000")

    ttsapi.fetch_audio("hi", "gtts", "en")

    assert len(captured_calls) == 1
    unused_verb, unused_url, kwargs = captured_calls[0]
    assert "Authorization" not in kwargs["headers"]
    assert kwargs["headers"] == {}


def test_fetch_engines_sends_bearer_when_token_set(monkeypatch, captured_calls):
    """The engine listing GET carries the same Bearer header and returns the parsed body."""
    monkeypatch.setenv("TTS_TOKEN", "tokenA")
    monkeypatch.setenv("TTS_URL", "http://example:5000")

    data = ttsapi.fetch_engines()

    assert data == {"engines": ["gtts"], "default": "gtts"}
    assert len(captured_calls) == 1
    verb, url, kwargs = captured_calls[0]
    assert verb == "GET"
    assert url == "http://example:5000/api/engines"
    assert kwargs["headers"] == {"Authorization": "Bearer tokenA"}


def test_token_is_stripped_of_whitespace(monkeypatch):
    """Whitespace-only tokens behave like empty (no header)."""
    monkeypatch.setenv("TTS_TOKEN", "   ")
    assert ttsapi.get_headers() == {}


def test_get_url_strips_trailing_slash(monkeypatch):
    """A trailing slash in TTS_URL is removed so endpoint paths never double up."""
    monkeypatch.setenv("TTS_URL", "http://example:5000/")
    assert ttsapi.get_url() == "http://example:5000"


def test_get_url_default_when_unset(monkeypatch):
    """With TTS_URL unset the client targets the local default server."""
    monkeypatch.delenv("TTS_URL", raising=False)
    assert ttsapi.get_url() == "http://localhost:5000"
