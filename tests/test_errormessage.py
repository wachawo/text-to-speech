#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the `message` that every schema 400 under /api/ carries, and the helper that builds it."""

import pytest

# Local imports
from ttssrv.validators import MAX_VALIDATION_MESSAGE_LENGTH, format_validation_messages


@pytest.fixture
def history_dir(tmp_path, monkeypatch, app_module):
    """Redirect TTS_HISTORY_DIR to a fresh directory for one test."""
    target = tmp_path / "history"
    monkeypatch.setattr(app_module, "TTS_HISTORY_DIR", str(target))
    return target


# format_validation_messages


def test_format_validation_messages_joins_fields_and_messages():
    """Each field becomes "field: msg msg", fields are joined with "; "."""
    messages = {"text": ["Missing data for required field."], "language": ["Bad.", "Worse."]}
    assert format_validation_messages(messages) == "text: Missing data for required field.; language: Bad. Worse."


def test_format_validation_messages_flattens_nested_and_list_messages():
    """Nested dicts keep their keys; a bare list is joined with spaces."""
    assert format_validation_messages({"items": {"0": ["Not a string."]}}) == "items: 0: Not a string."
    assert format_validation_messages(["One.", "Two."]) == "One. Two."


def test_format_validation_messages_is_capped():
    """A very long message is cut to MAX_VALIDATION_MESSAGE_LENGTH characters."""
    text = format_validation_messages({f"field{index}": ["x" * 50] for index in range(100)})
    assert len(text) == MAX_VALIDATION_MESSAGE_LENGTH
    assert text.endswith("...")


# `message` in every schema 400


def test_history_list_schema_error_has_message(client, history_dir):
    """GET /api/history with a bad limit names the field in `message`."""
    resp = client.get("/api/history?limit=0")
    assert resp.status_code == 400
    body = resp.get_json()
    assert set(body) == {"error", "message", "request_id"}
    assert body["message"].startswith("limit: ")


def test_voice_upload_schema_error_has_message(client):
    """POST /api/voices with a bad name and engine names both fields in `message`."""
    resp = client.post("/api/voices", data={"name": "../x", "engine": "gtts"}, content_type="multipart/form-data")
    assert resp.status_code == 400
    body = resp.get_json()
    assert set(body) == {"error", "message", "request_id"}
    assert "name: " in body["message"] and "engine: " in body["message"]
