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
