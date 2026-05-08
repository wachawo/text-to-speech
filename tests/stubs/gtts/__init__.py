#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test stub for the `gtts` package — used by tests/test_ttsgen_cli.py.

The real `gtts` package fetches audio from Google Translate over HTTP.
Tests must not hit the network, so this stub exposes the same `gTTS`
class with a `write_to_fp` method that emits canned bytes.

Activated by prepending `tests/stubs/` to PYTHONPATH for the subprocess
under test; otherwise the real package is used.
"""

from typing import IO

# A minimal, recognisable MP3 frame header so consumers that sniff
# bytes (libs/playback.py:detect_audio_mime, ttssrv) tag this as
# audio/mpeg. The body is intentionally tiny — tests only check that
# something non-empty was produced.
_FAKE_MP3 = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 64


class gTTS:
    """Stub gTTS class. Accepts the kwargs the real one does, ignores them."""

    def __init__(self, text: str = "", lang: str = "en", slow: bool = False, **kwargs) -> None:
        self.text = text
        self.lang = lang
        self.slow = slow

    def write_to_fp(self, fp: IO[bytes]) -> None:
        fp.write(_FAKE_MP3)

    def save(self, savefile: str) -> None:  # pragma: no cover — present for API parity
        with open(savefile, "wb") as f:
            f.write(_FAKE_MP3)
