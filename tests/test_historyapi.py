#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the /api/history endpoints: create, list, get, audio, delete."""

import queue
import re
import types

import pytest

ITEM_ID = re.compile(r"^\d{8}_\d{6}_[0-9a-f]{6}$")


@pytest.fixture
def history_dir(tmp_path, monkeypatch, app_module):
    """Redirect TTS_HISTORY_DIR to a fresh directory for one test."""
    target = tmp_path / "history"
    monkeypatch.setattr(app_module, "TTS_HISTORY_DIR", str(target))
    return target


def create(client, text="hello", **extra):
    """POST one history item and return the response."""
    return client.post("/api/history", json={"text": text, **extra})


def test_create_returns_item(client, history_dir, make_wav):
    """Creating an item synthesizes, stores wav plus json and answers 201 with the full item."""
    resp = create(client, engine="gtts", language="en", voice="maria")
    assert resp.status_code == 201
    item = resp.get_json()
    assert ITEM_ID.match(item["id"])
    assert item["engine"] == "gtts"
    assert item["language"] == "en"
    assert item["voice"] == "maria"
    assert item["format"] == "wav"
    assert item["bytes"] == len(make_wav())
    assert item["seconds"] == 0.1
    assert item["text"] == "hello"
    assert item["text_chars"] == 5
    assert isinstance(item["elapsed"], float) and item["elapsed"] >= 0
    assert (history_dir / f"{item['id']}.wav").is_file()
    assert (history_dir / f"{item['id']}.json").is_file()


def test_create_defaults_engine_and_language(client, history_dir, app_module):
    """Omitted engine and language fall back to the server defaults."""
    item = create(client).get_json()
    assert item["engine"] == app_module.TTS_ENGINE_DEFAULT
    assert item["language"] == app_module.TTS_LANGUAGE_DEFAULT
    assert item["voice"] is None


def test_create_validation_400(client, history_dir):
    """Empty text, a bad language and the stream switch are all rejected."""
    for body in ({"text": ""}, {}, {"text": "hi", "language": "english"}, {"text": "hi", "stream": True}):
        resp = client.post("/api/history", json=body)
        assert resp.status_code == 400, body
        assert set(resp.get_json().keys()) == {"error", "message", "request_id"}
    assert not history_dir.exists()


def test_create_releases_slot_on_engine_error(client, history_dir, monkeypatch, app_module):
    """A synthesis failure gives the pool token back and stores nothing."""

    def boom(text, engine=None, language=None, voice=None):
        """Fail like a broken engine would."""
        raise RuntimeError("engine exploded")

    monkeypatch.setattr(app_module, "text_to_speech_bytes", boom)
    monkeypatch.setattr(app_module, "TTS_POOL_SIZE", 1)
    app_module.ENGINE_POOL.put(0)
    try:
        resp = create(client)
        assert resp.status_code == 500
        assert app_module.ENGINE_POOL.qsize() == 1
    finally:
        app_module.ENGINE_POOL.get_nowait()
    assert not history_dir.exists()


def test_create_503_when_pool_busy(client, history_dir, monkeypatch, app_module):
    """A pool that never frees a token answers 503 with the same body as /api/tts."""

    def never_free(timeout):
        """Behave like queue.Queue.get on a pool that stays empty past its timeout."""
        raise queue.Empty()

    monkeypatch.setattr(app_module, "TTS_POOL_SIZE", 1)
    monkeypatch.setattr(app_module, "ENGINE_POOL", types.SimpleNamespace(get=never_free))
    resp = create(client)
    assert resp.status_code == 503
    assert resp.get_json() == {"error": "All engine slots busy"}
    assert not history_dir.exists()


def test_list_newest_first_with_preview(client, history_dir):
    """The list is newest first, text is cut to 200 chars and text_chars keeps the full length."""
    long_text = "x" * 250
    first = create(client, "first").get_json()["id"]
    second = create(client, long_text).get_json()["id"]

    resp = client.get("/api/history")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == sorted([first, second], reverse=True)
    newest = next(item for item in body["items"] if item["id"] == second)
    assert newest["text"] == "x" * 200 + "..."
    assert newest["text_chars"] == 250


def test_list_limit_and_offset(client, history_dir):
    """limit and offset page through the items; total stays the full count."""
    ids = [create(client, str(index)).get_json()["id"] for index in range(3)]
    body = client.get("/api/history?limit=1&offset=1").get_json()
    assert body["total"] == 3
    assert [item["id"] for item in body["items"]] == [sorted(ids, reverse=True)[1]]


def test_list_bad_limit_400(client, history_dir):
    """limit=0, limit above 200 and a negative offset are bad requests."""
    for query in ("limit=0", "limit=201", "offset=-1", "limit=abc"):
        resp = client.get(f"/api/history?{query}")
        assert resp.status_code == 400, query


def test_list_empty(client, history_dir):
    """A missing history directory lists nothing instead of failing."""
    body = client.get("/api/history").get_json()
    assert body == {"total": 0, "items": []}


def test_get_item_full_text(client, history_dir):
    """GET /api/history/<id> returns the untruncated text."""
    long_text = "y" * 300
    item_id = create(client, long_text).get_json()["id"]
    resp = client.get(f"/api/history/{item_id}")
    assert resp.status_code == 200
    assert resp.get_json()["text"] == long_text


def test_get_unknown_and_bad_id_404(client, history_dir):
    """An unknown id and an id that is not even well-formed both answer 404."""
    for item_id in ("20260101_000000_abcdef", "../../etc/passwd", "nope"):
        resp = client.get(f"/api/history/{item_id}")
        assert resp.status_code == 404, item_id
        assert set(resp.get_json().keys()) == {"error", "request_id"}


def test_audio_inline_and_download(client, history_dir, make_wav):
    """Audio is served inline by default and as an attachment with ?download=1."""
    item_id = create(client).get_json()["id"]

    resp = client.get(f"/api/history/{item_id}/audio")
    assert resp.status_code == 200
    assert resp.mimetype == "audio/wav"
    assert resp.data == make_wav()
    assert not resp.headers.get("Content-Disposition", "").startswith("attachment")

    resp = client.get(f"/api/history/{item_id}/audio?download=1")
    assert resp.status_code == 200
    assert resp.mimetype == "audio/wav"
    disposition = resp.headers["Content-Disposition"]
    assert disposition.startswith("attachment")
    assert f"tts_{item_id}.wav" in disposition


def test_audio_mp3_mimetype(client, history_dir, monkeypatch, app_module):
    """An MP3-producing engine is stored as .mp3 and served as audio/mpeg with seconds unset."""
    mp3 = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xff\xfb" * 32
    monkeypatch.setattr(app_module, "text_to_speech_bytes", lambda text, engine=None, language=None, voice=None: mp3)
    item = create(client).get_json()
    assert item["format"] == "mp3"
    assert item["seconds"] is None
    resp = client.get(f"/api/history/{item['id']}/audio?download=true")
    assert resp.mimetype == "audio/mpeg"
    assert resp.data == mp3
    assert f"tts_{item['id']}.mp3" in resp.headers["Content-Disposition"]


def test_audio_unknown_and_bad_id_404(client, history_dir):
    """Audio for an unknown or malformed id is 404, never a 500."""
    for item_id in ("20260101_000000_abcdef", "..", "x.wav"):
        resp = client.get(f"/api/history/{item_id}/audio")
        assert resp.status_code == 404, item_id


def test_delete_item_then_404(client, history_dir):
    """Deleting removes both files; deleting again answers 404."""
    item_id = create(client).get_json()["id"]
    resp = client.delete(f"/api/history/{item_id}")
    assert resp.status_code == 200
    assert resp.get_json() == {"result": True}
    assert list(history_dir.iterdir()) == []

    resp = client.delete(f"/api/history/{item_id}")
    assert resp.status_code == 404
    resp = client.delete("/api/history/not-an-id")
    assert resp.status_code == 404


def test_prune_keeps_history_max(client, history_dir, monkeypatch, app_module):
    """Writing past TTS_HISTORY_MAX drops the oldest items."""
    monkeypatch.setattr(app_module, "TTS_HISTORY_MAX", 2)
    ids = [create(client, str(index)).get_json()["id"] for index in range(3)]
    body = client.get("/api/history").get_json()
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == sorted(ids, reverse=True)[:2]
