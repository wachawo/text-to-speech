#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Helpers for chunked TTS streaming.

The streaming endpoint synthesizes one text chunk at a time and emits audio as
soon as each chunk is ready, so a client hears the first sentence without waiting
for the whole utterance. For WAV engines we emit a single streaming WAV: one
header with placeholder (0xFFFFFFFF) sizes followed by the raw PCM of each chunk
concatenated. For MP3 (gtts) the per-chunk bytes are simply concatenated.
"""

import io
import struct
import wave

STREAMING_SIZE = 0xFFFFFFFF  # placeholder length for an unbounded/streaming WAV


def streaming_wav_header(sample_rate: int, channels: int = 1, sample_width: int = 2) -> bytes:
    """Build a 44-byte WAV header with streaming (unknown-length) size fields.

    Args:
        sample_rate: Frames per second of the PCM payload that will follow.
        channels: Number of interleaved audio channels.
        sample_width: Bytes per sample (2 = 16-bit PCM).

    Returns:
        The header bytes, with both RIFF and data sizes set to STREAMING_SIZE.
    """
    bits = sample_width * 8
    byte_rate = sample_rate * channels * sample_width
    block_align = channels * sample_width
    return (
        b"RIFF"
        + struct.pack("<I", STREAMING_SIZE)
        + b"WAVE"
        + b"fmt "
        + struct.pack("<IHHIIHH", 16, 1, channels, sample_rate, byte_rate, block_align, bits)
        + b"data"
        + struct.pack("<I", STREAMING_SIZE)
    )


def wav_params(wav_bytes: bytes) -> tuple[int, int, int]:
    """Return (sample_rate, channels, sample_width) of a WAV blob."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as reader:
        return reader.getframerate(), reader.getnchannels(), reader.getsampwidth()


def wav_data(wav_bytes: bytes) -> bytes:
    """Return the raw PCM payload of a WAV blob (header stripped)."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as reader:
        return reader.readframes(reader.getnframes())
