#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""POST/GET /api/tts?stream=true: chunked streaming responses."""

from ttssrv.streaming import streaming_wav_header, wav_data, wav_params


def test_stream_post_success_wav(client):
    resp = client.post("/api/tts", json={"text": "One. Two. Three.", "stream": True})
    assert resp.status_code == 200
    assert resp.mimetype == "audio/wav"
    assert resp.data[:4] == b"RIFF"
    # Streaming header uses placeholder (0xFFFFFFFF) length fields.
    assert resp.data[4:8] == b"\xff\xff\xff\xff"
    assert len(resp.data) > 44  # header + concatenated PCM


def test_stream_get_success(client):
    resp = client.get("/api/tts?text=hi&stream=true")
    assert resp.status_code == 200
    assert resp.mimetype == "audio/wav"


def test_stream_single_chunk(client):
    resp = client.post("/api/tts", json={"text": "hi", "stream": True})
    assert resp.status_code == 200
    assert resp.data[:4] == b"RIFF"


def test_stream_multichunk_longer_than_single(client):
    """Text past the chunk limit splits into several chunks → more PCM streamed."""
    long_text = ("One two three four five. " * 20).strip()  # > 200 chars -> multiple chunks
    one = client.post("/api/tts", json={"text": "One.", "stream": True}).data
    many = client.post("/api/tts", json={"text": long_text, "stream": True}).data
    assert len(many) > len(one)


def test_stream_validates_empty_text(client):
    resp = client.post("/api/tts", json={"text": "", "stream": True})
    assert resp.status_code == 400


def test_streaming_header_is_well_formed():
    header = streaming_wav_header(48000, 1, 2)
    assert header[:4] == b"RIFF"
    assert header[8:12] == b"WAVE"
    assert len(header) == 44


def test_wav_helpers_roundtrip():
    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 800)  # 50 ms @ 16 kHz
    wav = buf.getvalue()
    assert wav_params(wav) == (16000, 1, 2)
    assert len(wav_data(wav)) == 800 * 2
