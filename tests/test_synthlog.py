#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the per-request Synthesis log line written by ttssrv.app1.synthesize."""

import re
import time

import pytest

MS_VALUE = re.compile(r" ms=(\d+) ")


@pytest.fixture
def synth_lines(caplog):
    """Capture INFO records and return a callable listing the Synthesis lines seen so far."""
    caplog.set_level("INFO")
    return lambda: [record.getMessage() for record in caplog.records if " Synthesis" in record.getMessage()]


@pytest.fixture
def installed(monkeypatch, app_module):
    """Pretend gtts is installed so /v1/audio/speech accepts the default model."""
    monkeypatch.setattr(app_module, "get_available_engines", lambda: {"gtts": None})
    monkeypatch.setattr(app_module, "TTS_ENGINE_DEFAULT", "gtts")


def ms_of(line: str) -> int:
    """Return the ms= value of a Synthesis line as an int."""
    match = MS_VALUE.search(line)
    assert match, line
    return int(match.group(1))


def test_tts_writes_one_ok_line(client, synth_lines, make_wav):
    """A non-stream /api/tts call logs one Synthesis line with engine, chars, bytes, ms and ok."""
    text = "Hello there, world."
    resp = client.post("/api/tts", json={"text": text, "engine": "gtts", "language": "en"})
    assert resp.status_code == 200
    lines = synth_lines()
    assert len(lines) == 1
    line = lines[0]
    assert "] Synthesis: engine=gtts language=en voice=None" in line
    assert f" chars={len(text)} " in line
    assert f" bytes={len(make_wav())} " in line
    assert line.endswith(" ok")
    assert ms_of(line) >= 0


def test_tts_ms_measures_engine_time(client, synth_lines, monkeypatch, app_module, make_wav):
    """The ms value reflects the time spent inside the engine call."""

    def slow(text, engine=None, language=None, voice=None):
        """Take a measurable amount of time before answering."""
        time.sleep(0.03)
        return make_wav()

    monkeypatch.setattr(app_module, "text_to_speech_bytes", slow)
    resp = client.post("/api/tts", json={"text": "hi"})
    assert resp.status_code == 200
    assert ms_of(synth_lines()[0]) >= 30


def test_tts_failure_logs_and_releases_slot(client, synth_lines, monkeypatch, app_module):
    """An engine error answers 500, logs a failed line with the exception name and returns the slot."""

    def boom(text, engine=None, language=None, voice=None):
        """Fail like a broken engine would."""
        raise RuntimeError("engine exploded")

    monkeypatch.setattr(app_module, "text_to_speech_bytes", boom)
    monkeypatch.setattr(app_module, "TTS_POOL_SIZE", 1)
    app_module.ENGINE_POOL.put(0)
    try:
        resp = client.post("/api/tts", json={"text": "hi"})
        assert resp.status_code == 500
        assert app_module.ENGINE_POOL.qsize() == 1
    finally:
        while not app_module.ENGINE_POOL.empty():
            app_module.ENGINE_POOL.get_nowait()
    lines = synth_lines()
    assert len(lines) == 1
    assert lines[0].endswith(" failed RuntimeError")
    assert " bytes=" not in lines[0]
    assert ms_of(lines[0]) >= 0


def test_stream_labels_every_chunk(client, synth_lines, monkeypatch, app_module):
    """A streamed request logs one Synthesis line per chunk, labelled chunk i/N."""
    monkeypatch.setattr(app_module, "TTS_STREAM_MAX_CHARS", 12)
    resp = client.post("/api/tts", json={"text": "Alpha one. Beta two. Gamma three.", "stream": True})
    assert resp.status_code == 200
    assert len(resp.data) > 44
    lines = synth_lines()
    assert [line.split(": engine=")[0].split("] ")[1] for line in lines] == [
        "Synthesis chunk 1/3",
        "Synthesis chunk 2/3",
        "Synthesis chunk 3/3",
    ]
    assert all(line.endswith(" ok") for line in lines)


def test_openai_speech_writes_one_line(client, synth_lines, installed):
    """POST /v1/audio/speech logs exactly one Synthesis line."""
    resp = client.post("/v1/audio/speech", json={"input": "Hello there.", "model": "tts-1"})
    assert resp.status_code == 200
    lines = synth_lines()
    assert len(lines) == 1
    assert " chars=12 " in lines[0]
    assert lines[0].endswith(" ok")


def test_history_create_writes_one_line(client, synth_lines, tmp_path, monkeypatch, app_module):
    """POST /api/history logs exactly one Synthesis line with an integer ms value."""
    monkeypatch.setattr(app_module, "TTS_HISTORY_DIR", str(tmp_path / "history"))
    resp = client.post("/api/history", json={"text": "hello"})
    assert resp.status_code == 201
    lines = synth_lines()
    assert len(lines) == 1
    assert " chars=5 " in lines[0]
    assert lines[0].endswith(" ok")
    assert ms_of(lines[0]) >= 0
