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
