#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline test stub for the `gtts` package, exposing the same gTTS surface without network access.

The real `gtts` package fetches audio from Google Translate over HTTP.
Tests must not hit the network, so this stub emits canned bytes instead.

Activated by prepending `tests/stubs/` to PYTHONPATH for the subprocess
under test; otherwise the real package is used.
"""

from typing import IO

# A minimal, recognisable MP3 frame header so consumers that sniff
# bytes (libs/playback.py:detect_audio_mime, ttssrv) tag this as
# audio/mpeg. The body is intentionally tiny — tests only check that
# something non-empty was produced.
FAKE_MP3 = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 64


class gTTS:
    """Stub gTTS class. Accepts the kwargs the real one does, ignores them."""

    def __init__(self, text: str = "", lang: str = "en", slow: bool = False, **kwargs) -> None:
        """Record the requested text and voice options without contacting any service."""
        self.text = text
        self.lang = lang
        self.slow = slow

    def write_to_fp(self, fp: IO[bytes]) -> None:
        """Write the canned MP3 payload into the given binary stream."""
        fp.write(FAKE_MP3)

    def save(self, savefile: str) -> None:  # pragma: no cover — present for API parity
        """Write the canned MP3 payload to `savefile`, mirroring the real API."""
        with open(savefile, "wb") as f:
            f.write(FAKE_MP3)
