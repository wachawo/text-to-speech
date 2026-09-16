#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audio container sniffing shared by the CLIs, the API layer and the server."""

MIME_TYPES = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "bin": "application/octet-stream",
}


def is_wav(data: bytes) -> bool:
    """Report whether the bytes open with a RIFF header."""
    return data.startswith(b"RIFF")


def is_mp3(data: bytes) -> bool:
    """Report whether the bytes open with an ID3 tag or an MPEG audio frame sync.

    The frame sync is 11 set bits, so the second byte is masked rather than
    compared: gTTS emits tagless MPEG-2 layer III (\xff\xf3), other encoders
    MPEG-1 (\xff\xfb), and both are MP3.
    """
    if data.startswith(b"ID3"):
        return True
    return len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0


def audio_format(data: bytes) -> str:
    """Return "wav", "mp3" or "bin" by sniffing the header."""
    if is_mp3(data):
        return "mp3"
    if is_wav(data):
        return "wav"
    return "bin"


def audio_mime(data: bytes) -> str:
    """Return the MIME type matching the sniffed container."""
    return MIME_TYPES[audio_format(data)]


def extension_for(data: bytes) -> str:
    """Return the file extension (without the dot) matching the sniffed container."""
    return audio_format(data)


def main():
    """Module entrypoint placeholder, this file is import-only."""
    pass


if __name__ == "__main__":
    main()
