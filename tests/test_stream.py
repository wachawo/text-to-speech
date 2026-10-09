#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for chunked streaming responses from /api/tts?stream=true."""

import io
import queue
import wave

from ttssrv.streaming import streaming_wav_header, wav_data, wav_params


def test_stream_post_success_wav(client):
    """A streamed POST returns a RIFF/WAV body whose length fields are the streaming placeholder."""
    resp = client.post("/api/tts", json={"text": "One. Two. Three.", "stream": True})
    assert resp.status_code == 200
    assert resp.mimetype == "audio/wav"
    assert resp.data[:4] == b"RIFF"
    # Streaming header uses placeholder (0xFFFFFFFF) length fields.
    assert resp.data[4:8] == b"\xff\xff\xff\xff"
    assert len(resp.data) > 44  # header + concatenated PCM


def test_stream_get_success(client):
    """Streaming is reachable over GET with query parameters, not only over POST."""
    resp = client.get("/api/tts?text=hi&stream=true")
    assert resp.status_code == 200
    assert resp.mimetype == "audio/wav"


def test_stream_single_chunk(client):
    """Text short enough for a single chunk still produces a well-formed WAV stream."""
    resp = client.post("/api/tts", json={"text": "hi", "stream": True})
    assert resp.status_code == 200
    assert resp.data[:4] == b"RIFF"


def test_stream_multichunk_longer_than_single(client):
    """Text past the chunk limit splits into several chunks and streams more PCM."""
    long_text = ("One two three four five. " * 20).strip()  # > 200 chars -> multiple chunks
    one = client.post("/api/tts", json={"text": "One.", "stream": True}).data
    many = client.post("/api/tts", json={"text": long_text, "stream": True}).data
    assert len(many) > len(one)


def test_stream_validates_empty_text(client):
    """Empty text is rejected up front with 400 instead of opening an empty stream."""
    resp = client.post("/api/tts", json={"text": "", "stream": True})
    assert resp.status_code == 400


def test_streaming_header_is_well_formed():
    """The synthetic streaming header is a canonical 44-byte RIFF/WAVE prologue."""
    header = streaming_wav_header(48000, 1, 2)
    assert header[:4] == b"RIFF"
    assert header[8:12] == b"WAVE"
    assert len(header) == 44


def test_wav_helpers_roundtrip():
    """wav_params and wav_data read back exactly the format and payload that were written."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 800)  # 50 ms @ 16 kHz
    wav = buf.getvalue()
    assert wav_params(wav) == (16000, 1, 2)
    assert len(wav_data(wav)) == 800 * 2


def use_one_slot_pool(monkeypatch, app_module) -> queue.Queue:
    """Give the server a pool of one free slot and return it."""
    pool: queue.Queue = queue.Queue()
    pool.put(0)
    monkeypatch.setattr(app_module, "ENGINE_POOL", pool)
    monkeypatch.setattr(app_module, "TTS_POOL_SIZE", 1)
    return pool


def test_stream_head_releases_slot(client, monkeypatch, app_module):
    """HEAD closes the stream before its generator starts, and the slot still comes back."""
    pool = use_one_slot_pool(monkeypatch, app_module)
    resp = client.head("/api/tts?text=hi&stream=true")
    resp.close()
    assert resp.status_code == 200
    assert pool.qsize() == 1


def test_stream_closed_unread_releases_slot(client, monkeypatch, app_module):
    """A client that leaves before reading any chunk does not keep the slot."""
    pool = use_one_slot_pool(monkeypatch, app_module)
    resp = client.get("/api/tts?text=hi&stream=true", buffered=False)
    resp.close()
    assert pool.qsize() == 1


def test_stream_read_to_end_releases_slot_once(client, monkeypatch, app_module):
    """A stream read to the end gives the slot back exactly once."""
    pool = use_one_slot_pool(monkeypatch, app_module)
    resp = client.post("/api/tts", json={"text": "One. Two. Three.", "stream": True})
    resp.close()
    assert resp.status_code == 200
    assert pool.qsize() == 1
