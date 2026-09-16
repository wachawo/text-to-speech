#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for libs.audio, the single container sniffer, and its use in libs.api."""

import importlib.util
import sys
from pathlib import Path

import pytest

# Local imports
from libs import audio

ROOT = Path(__file__).resolve().parent.parent

MPEG2_FRAME = b"\xff\xf3\x64\xc4" + b"\x00" * 8  # tagless gTTS output
MPEG1_FRAME = b"\xff\xfb\x90\x64" + b"\x00" * 8
ID3_TAGGED = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 8
GARBAGE = b"\x00\x01\x02\x03" + b"\x00" * 8


@pytest.mark.parametrize("data", [MPEG2_FRAME, MPEG1_FRAME, ID3_TAGGED])
def test_is_mp3_accepts_id3_and_frame_sync(data):
    """Both MPEG frame syncs and an ID3 tag are MP3."""
    assert audio.is_mp3(data)
    assert not audio.is_wav(data)
    assert audio.audio_format(data) == "mp3"
    assert audio.audio_mime(data) == "audio/mpeg"
    assert audio.extension_for(data) == "mp3"


def test_is_wav_accepts_riff(make_wav):
    """A RIFF header is WAV."""
    data = make_wav()
    assert audio.is_wav(data)
    assert not audio.is_mp3(data)
    assert audio.audio_format(data) == "wav"
    assert audio.audio_mime(data) == "audio/wav"
    assert audio.extension_for(data) == "wav"


@pytest.mark.parametrize("data", [GARBAGE, b"", b"\xff", b"\xff\x00" + b"\x00" * 8, b"RIF"])
def test_garbage_is_bin(data):
    """Anything without a recognised header is reported as bin."""
    assert not audio.is_mp3(data)
    assert not audio.is_wav(data)
    assert audio.audio_format(data) == "bin"
    assert audio.audio_mime(data) == "application/octet-stream"
    assert audio.extension_for(data) == "bin"


def load_real_api():
    """Import the real libs/api.py; conftest keeps a stub under sys.modules["libs.api"]."""
    spec = importlib.util.spec_from_file_location("libs.api_real", ROOT / "libs" / "api.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_text_to_speech_file_names_mp3_from_bytes(monkeypatch, tmp_path):
    """Auto-named output takes its extension from the audio header, not from a fixed guess."""
    monkeypatch.chdir(tmp_path)
    real_api = load_real_api()
    assert real_api is not sys.modules["libs.api"]
    monkeypatch.setattr(real_api, "text_to_speech_bytes", lambda text, engine, language: MPEG2_FRAME)
    written = real_api.text_to_speech_file("hello", filename=None)
    assert written.endswith(".mp3")
    assert (tmp_path / written).read_bytes() == MPEG2_FRAME


def test_text_to_speech_file_names_wav_from_bytes(monkeypatch, tmp_path, make_wav):
    """WAV bytes get a .wav name."""
    monkeypatch.chdir(tmp_path)
    real_api = load_real_api()
    monkeypatch.setattr(real_api, "text_to_speech_bytes", lambda text, engine, language: make_wav())
    written = real_api.text_to_speech_file("hello", filename=None)
    assert written.endswith(".wav")
