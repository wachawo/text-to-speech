#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the WSGI response wrapper ttssrv serves through uvicorn."""


def test_close_wsgi_responses_closes_the_iterable(app_module):
    """The wrapper yields every chunk and then calls close() on the response."""
    closed = []

    class Response:
        """A minimal WSGI response iterable that records close()."""

        def __iter__(self):
            """Yield two chunks."""
            yield b"a"
            yield b"b"

        def close(self):
            """Record that the app's close() hook ran."""
            closed.append(True)

    wrapped = app_module.close_wsgi_responses(lambda environ, start_response: Response())
    assert list(wrapped({}, lambda status, headers: None)) == [b"a", b"b"]
    assert closed == [True]


def test_close_wsgi_responses_closes_on_early_exit(app_module):
    """Dropping the generator before it is exhausted still closes the response."""
    closed = []

    class Response:
        """A response that would yield forever if not abandoned."""

        def __iter__(self):
            """Yield chunks until the consumer stops."""
            while True:
                yield b"x"

        def close(self):
            """Record that the app's close() hook ran."""
            closed.append(True)

    generator = app_module.close_wsgi_responses(lambda environ, start_response: Response())({}, lambda s, h: None)
    assert next(generator) == b"x"
    generator.close()
    assert closed == [True]


def test_close_wsgi_responses_tolerates_a_plain_list(app_module):
    """A response without close() (a plain list) is passed through untouched."""
    wrapped = app_module.close_wsgi_responses(lambda environ, start_response: [b"ok"])
    assert list(wrapped({}, lambda status, headers: None)) == [b"ok"]


def test_acquire_slot_rejects_when_the_wait_queue_is_full(app_module, monkeypatch):
    """With every wait permit taken, a new request is refused at once instead of holding a thread."""
    import queue
    import threading

    monkeypatch.setattr(app_module, "TTS_POOL_SIZE", 1)
    monkeypatch.setattr(app_module, "WAIT_QUEUE", threading.Semaphore(0))
    try:
        app_module.acquire_slot()
    except queue.Empty:
        pass
    else:
        raise AssertionError("acquire_slot should raise queue.Empty when the wait queue is full")


def test_acquire_slot_returns_the_wait_permit_with_the_token(app_module, monkeypatch):
    """Taking a token gives the wait permit back, so only waiting requests count against the queue."""
    import threading

    permits = threading.Semaphore(1)
    monkeypatch.setattr(app_module, "TTS_POOL_SIZE", 1)
    monkeypatch.setattr(app_module, "WAIT_QUEUE", permits)
    app_module.ENGINE_POOL.put(0)
    try:
        assert app_module.acquire_slot() == 0
    finally:
        app_module.release_slot(0)
        app_module.ENGINE_POOL.get_nowait()
    assert permits.acquire(blocking=False)
