#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for watch_disconnects(): a stream stops synthesizing, and frees its slot, once its client has gone."""

import asyncio
import json
import queue
import warnings

HEADER = b"x-tts-disconnect-id"
LONG_TEXT = ("One two three four five. " * 40).strip()


def disconnect_ids(headers):
    """Return every value of the disconnect-id header in an ASGI header list."""
    return [value.decode() for name, value in headers if name == HEADER]


def test_wrapper_replays_the_body_and_sets_its_own_header(app_module):
    """The app sees the whole body and exactly one disconnect id, never the client's forged one."""
    seen = {}

    async def inner(scope, receive, send):
        """Read the body the way the WSGI bridge does and note what the request carried."""
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break
        seen["body"] = body
        seen["ids"] = disconnect_ids(scope["headers"])
        seen["registered"] = seen["ids"][0] in app_module.DISCONNECT_EVENTS

    incoming = [
        {"type": "http.request", "body": b"ab", "more_body": True},
        {"type": "http.request", "body": b"cd", "more_body": False},
    ]

    async def receive():
        """Deliver the body in two parts, then nothing: the client stays connected."""
        if incoming:
            return incoming.pop(0)
        await asyncio.Event().wait()

    scope = {"type": "http", "headers": [(HEADER, b"forged"), (b"host", b"tts")]}
    asyncio.run(app_module.watch_disconnects(inner)(scope, receive, None))
    assert seen["body"] == b"abcd"
    assert len(seen["ids"]) == 1 and seen["ids"][0] != "forged"
    assert seen["registered"] is True
    assert seen["ids"][0] not in app_module.DISCONNECT_EVENTS


def test_wrapper_flags_http_disconnect(app_module):
    """http.disconnect on the real channel sets the request's Event and reaches the app's receive."""
    seen = {}

    async def inner(scope, receive, send):
        """Take the body, let the client leave, then wait for the disconnect like an ASGI app would."""
        event = app_module.DISCONNECT_EVENTS[disconnect_ids(scope["headers"])[0]]
        await receive()
        seen["before"] = event.is_set()
        client_gone.set()
        seen["message"] = await receive()
        seen["after"] = event.is_set()

    async def receive():
        """Deliver an empty body, then http.disconnect once the test says the client has left."""
        if not body_sent:
            body_sent.append(True)
            return {"type": "http.request", "body": b"", "more_body": False}
        await client_gone.wait()
        return {"type": "http.disconnect"}

    async def serve():
        """Run the wrapper inside one event loop."""
        await app_module.watch_disconnects(inner)({"type": "http", "headers": []}, receive, None)

    body_sent: list = []
    client_gone = asyncio.Event()
    asyncio.run(serve())
    assert seen["before"] is False
    assert seen["message"] == {"type": "http.disconnect"}
    assert seen["after"] is True
    assert app_module.DISCONNECT_EVENTS == {}


def test_wrapper_passes_other_scopes_through(app_module):
    """The lifespan scope reaches the wrapped app untouched."""
    seen = []

    async def inner(scope, receive, send):
        """Record the scope."""
        seen.append(scope)

    scope = {"type": "lifespan"}
    asyncio.run(app_module.watch_disconnects(inner)(scope, None, None))
    assert seen == [scope]


def one_slot_pool(monkeypatch, app_module) -> queue.Queue:
    """Give the server a pool of one free slot and return it."""
    pool: queue.Queue = queue.Queue()
    pool.put(0)
    monkeypatch.setattr(app_module, "ENGINE_POOL", pool)
    monkeypatch.setattr(app_module, "TTS_POOL_SIZE", 1)
    return pool


def test_stream_stops_once_the_event_is_set(client, monkeypatch, app_module, make_wav):
    """stream_tts checks the request's Event before each chunk: set during chunk 1, nothing more is synthesized."""
    pool = one_slot_pool(monkeypatch, app_module)
    event = app_module.threading.Event()
    monkeypatch.setitem(app_module.DISCONNECT_EVENTS, "abc", event)
    calls = []

    def synth(text, engine=None, language=None, voice=None):
        """Count the chunk and let the client leave during the first one."""
        calls.append(text)
        event.set()
        return make_wav()

    monkeypatch.setattr(app_module, "text_to_speech_bytes", synth)
    resp = client.post("/api/tts", json={"text": LONG_TEXT, "stream": True}, headers={"X-TTS-Disconnect-Id": "abc"})
    assert resp.status_code == 200
    # Reading the body runs the generator to its end: the header and chunk 1 only.
    assert len(resp.get_data()) == 44 + len(app_module.wav_data(make_wav()))
    resp.close()
    assert len(app_module.chunk_text(LONG_TEXT, max_len=app_module.TTS_STREAM_MAX_CHARS)) >= 4
    assert len(calls) == 1
    assert pool.qsize() == 1


def run_through_uvicorn_bridge(app_module, body: bytes, connection: dict) -> list:
    """Serve one POST /api/tts through watch_disconnects and uvicorn's WSGI bridge.

    `connection["hang_up"]` is filled with a thread-safe callable that makes
    the fake connection report http.disconnect, for the engine stub to call.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from uvicorn.middleware.wsgi import WSGIMiddleware

        bridge = WSGIMiddleware(app_module.close_wsgi_responses(app_module.app), workers=2)
    asgi = app_module.watch_disconnects(bridge)
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/tts",
        "raw_path": b"/api/tts",
        "root_path": "",
        "query_string": b"",
        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
        "server": ("tts", 5000),
        "client": ("127.0.0.1", 40000),
    }
    sent: list = []

    async def serve():
        """Run the request in one loop; receive() reports the disconnect once hang_up() was called."""
        client_gone = asyncio.Event()
        loop = asyncio.get_running_loop()
        connection["hang_up"] = lambda: loop.call_soon_threadsafe(client_gone.set)
        pending = [{"type": "http.request", "body": body, "more_body": False}]

        async def receive():
            """The request body, then http.disconnect once the client has hung up."""
            if pending:
                return pending.pop(0)
            await client_gone.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            """Record what the server sent."""
            sent.append(message)

        await asgi(scope, receive, send)

    asyncio.run(serve())
    return sent


def test_stream_stops_after_a_disconnect_through_the_uvicorn_bridge(client, monkeypatch, app_module, make_wav):
    """Through the stack main() serves, a client gone during chunk 2 stops the stream there and frees the slot."""
    pool = one_slot_pool(monkeypatch, app_module)
    connection: dict = {}
    calls = []

    def synth(text, engine=None, language=None, voice=None):
        """Count the chunk; during chunk 2 hang up and wait until the wrapper has flagged it, so the order is fixed."""
        calls.append(text)
        if len(calls) == 2:
            (event,) = app_module.DISCONNECT_EVENTS.values()
            connection["hang_up"]()
            assert event.wait(10), "the disconnect never reached the WSGI thread"
        return make_wav()

    monkeypatch.setattr(app_module, "text_to_speech_bytes", synth)
    sent = run_through_uvicorn_bridge(app_module, json.dumps({"text": LONG_TEXT, "stream": True}).encode(), connection)
    assert sent[0]["type"] == "http.response.start" and sent[0]["status"] == 200
    assert sent[-1] == {"type": "http.response.body", "body": b"", "more_body": False}
    assert len(calls) == 2
    assert pool.qsize() == 1
    assert app_module.DISCONNECT_EVENTS == {}
