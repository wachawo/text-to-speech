#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exception hierarchy shared by every TTS engine, CLI and HTTP handler."""


class TTSException(Exception):
    """Base class for every error raised by this library."""


class EngineNotAvailableError(TTSException):
    """Raised when the requested engine exists but its dependencies are missing."""


class ValidationError(TTSException):
    """Raised when caller-supplied input fails validation."""


class CustomError(TTSException):
    """Engine-level failure carrying a structured JSON payload for the HTTP API.

    Engines build a `payload` dict (must include at least `error` and
    `message`); the HTTP server returns it verbatim as the response body.
    `status` is the HTTP status code (default 422 — predictable
    misconfiguration, not an internal error).

    Local CLI consumers can show `payload['message']` from `str(exc)`.
    """

    def __init__(self, payload: dict, status: int = 422):
        """Store a copy of the payload and clamp the status to a 4xx/5xx code.

        Args:
            payload: Response body returned verbatim by the HTTP server.
            status: HTTP status code; clamped to 400-599 so a buggy engine
                cannot return a 2xx with an `error` payload (which a client
                would interpret as success).
        """
        self.payload = dict(payload)
        self.status = max(400, min(599, int(status)))
        super().__init__(self.payload.get("message") or self.payload.get("error") or "CustomError")
