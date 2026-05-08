"""
TTS Exceptions

Custom exceptions for TTS operations.
"""


class TTSException(Exception):
    """Base exception for TTS operations."""

    pass


class EngineNotAvailableError(TTSException):
    """Raised when a TTS engine is not available."""

    pass


class ValidationError(TTSException):
    """Raised when input validation fails."""

    pass


class CustomError(TTSException):
    """Engine-level failure with a structured JSON payload for the HTTP API.

    Engines build a `payload` dict (must include at least `error` and
    `message`); the HTTP server returns it verbatim as the response body.
    `status` is the HTTP status code (default 422 — predictable
    misconfiguration, not an internal error).

    Local CLI consumers can show `payload['message']` from `str(exc)`.
    """

    def __init__(self, payload: dict, status: int = 422):
        self.payload = dict(payload)
        self.status = status
        super().__init__(self.payload.get("message") or self.payload.get("error") or "CustomError")
