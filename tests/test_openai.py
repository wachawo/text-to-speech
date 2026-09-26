#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the OpenAI-compatible routes: /v1/audio/speech, /v1/models, /v1/audio/voices."""

import queue
import shutil
import types

import pytest

# Local imports
from ttssrv import openai_compat

MP3_BYTES = b"ID3" + b"\x00" * 64
INSTALLED = {"gtts": None, "silerotts": None}


@pytest.fixture
def installed(monkeypatch, app_module):
    """Pretend gtts and silerotts are installed and make gtts the default engine."""
    monkeypatch.setattr(app_module, "get_available_engines", lambda: dict(INSTALLED))
    monkeypatch.setattr(app_module, "TTS_ENGINE_DEFAULT", "gtts")
    monkeypatch.setattr(app_module, "TTS_LANGUAGE_DEFAULT", "en")


@pytest.fixture
def no_ffmpeg(monkeypatch):
    """Hide every binary from shutil.which so the transcoder is reported missing."""
    monkeypatch.setattr(shutil, "which", lambda name, *args, **kwargs: None)
    openai_compat.warn_speed_ignored.cache_clear()


@pytest.fixture
def fake_ffmpeg(monkeypatch):
    """Report ffmpeg as present and record transcode calls instead of running it."""
    calls = []
    monkeypatch.setattr(shutil, "which", lambda name, *args, **kwargs: "/usr/bin/ffmpeg")

    def fake_transcode(audio_bytes, response_format, speed=1.0):
        """Record the call and return bytes that name the format."""
        calls.append((audio_bytes, response_format, speed))
        return f"{response_format}@{speed}".encode()

    monkeypatch.setattr(openai_compat, "transcode", fake_transcode)
    return calls


def record_synthesis(monkeypatch, app_module, audio_bytes):
    """Stub text_to_speech_bytes to return `audio_bytes` and collect its keyword arguments."""
    calls = []

    def stub(text, engine=None, language=None, voice=None):
        """Return canned audio and remember what was asked for."""
        calls.append({"text": text, "engine": engine, "language": language, "voice": voice})
        return audio_bytes

    monkeypatch.setattr(app_module, "text_to_speech_bytes", stub)
    return calls


def speech(client, **body):
    """POST /v1/audio/speech with `input` defaulting to a short sentence."""
    body.setdefault("input", "Hello there.")
    return client.post("/v1/audio/speech", json=body)


def error_of(resp):
    """Return the OpenAI error object of a JSON error response, asserting its shape."""
    body = resp.get_json()
    assert set(body.keys()) == {"error"}
    assert set(body["error"].keys()) == {"message", "type", "param", "code"}
    assert body["error"]["code"] is None
    return body["error"]


def test_tts1_maps_to_default_engine_and_openai_voice_to_none(client, installed, monkeypatch, app_module, make_wav):
    """tts-1 synthesizes with TTS_ENGINE_DEFAULT and an OpenAI voice name means the engine default."""
    calls = record_synthesis(monkeypatch, app_module, make_wav())
    resp = speech(client, model="tts-1", voice="alloy", response_format="wav")
    assert resp.status_code == 200
    assert calls == [{"text": "Hello there.", "engine": "gtts", "language": "en", "voice": None}]


def test_engine_voice_and_language_pass_through(client, installed, monkeypatch, app_module, make_wav):
    """An engine name as model, a non-OpenAI voice and the language extension reach the engine as given."""
    calls = record_synthesis(monkeypatch, app_module, make_wav())
    resp = speech(client, model="silerotts", voice="baya", language="ru", response_format="wav")
    assert resp.status_code == 200
    assert calls[0]["engine"] == "silerotts"
    assert calls[0]["voice"] == "baya"
    assert calls[0]["language"] == "ru"


def test_wav_engine_wav_format_returns_bytes_untouched(client, installed, no_ffmpeg, monkeypatch, app_module, make_wav):
    """Native WAV asked as wav is returned as is with audio/wav, even without ffmpeg."""
    wav = make_wav()
    record_synthesis(monkeypatch, app_module, wav)
    resp = speech(client, model="gtts", response_format="wav")
    assert resp.status_code == 200
    assert resp.mimetype == "audio/wav"
    assert resp.data == wav


def test_native_mp3_default_format_returns_audio_mpeg(client, installed, no_ffmpeg, monkeypatch, app_module):
    """The default response_format is mp3, so a native MP3 goes out untouched as audio/mpeg."""
    record_synthesis(monkeypatch, app_module, MP3_BYTES)
    resp = speech(client, model="gtts")
    assert resp.status_code == 200
    assert resp.mimetype == "audio/mpeg"
    assert resp.data == MP3_BYTES


def test_mismatch_without_ffmpeg_400_names_native_format(client, installed, no_ffmpeg, monkeypatch, app_module, make_wav):
    """A WAV engine asked for mp3 without ffmpeg answers 400 telling the caller to ask for wav."""
    record_synthesis(monkeypatch, app_module, make_wav())
    resp = speech(client, model="gtts", response_format="mp3")
    assert resp.status_code == 400
    error = error_of(resp)
    assert error["type"] == "invalid_request_error"
    assert error["param"] == "response_format"
    assert "'wav'" in error["message"]
    assert "ffmpeg" in error["message"]


def test_speed_without_ffmpeg_is_ignored(client, installed, no_ffmpeg, monkeypatch, app_module, make_wav):
    """Same format with speed != 1.0 and no ffmpeg returns the native bytes rather than failing."""
    wav = make_wav()
    record_synthesis(monkeypatch, app_module, wav)
    resp = speech(client, model="gtts", response_format="wav", speed=1.5)
    assert resp.status_code == 200
    assert resp.data == wav


@pytest.mark.parametrize(
    "response_format, mimetype",
    [("mp3", "audio/mpeg"), ("pcm", "audio/pcm"), ("opus", "audio/opus"), ("flac", "audio/flac"), ("aac", "audio/aac")],
)
def test_mismatch_with_ffmpeg_calls_transcoder(
    client, installed, fake_ffmpeg, monkeypatch, app_module, make_wav, response_format, mimetype
):
    """Every non-native format goes through the transcoder with the requested format and speed."""
    wav = make_wav()
    record_synthesis(monkeypatch, app_module, wav)
    resp = speech(client, model="gtts", response_format=response_format, speed=2.0)
    assert resp.status_code == 200
    assert resp.mimetype == mimetype
    assert resp.data == f"{response_format}@2.0".encode()
    assert fake_ffmpeg == [(wav, response_format, 2.0)]


def test_same_format_with_speed_transcodes_when_ffmpeg_present(
    client, installed, fake_ffmpeg, monkeypatch, app_module, make_wav
):
    """wav in, wav out, but speed 0.5 still needs ffmpeg, so the transcoder runs."""
    record_synthesis(monkeypatch, app_module, make_wav())
    resp = speech(client, model="gtts", response_format="wav", speed=0.5)
    assert resp.status_code == 200
    assert fake_ffmpeg[0][1:] == ("wav", 0.5)


def test_unknown_model_400_param_model(client, installed):
    """A model that is neither an installed engine nor an OpenAI name is refused with param model."""
    resp = speech(client, model="coquitts")
    assert resp.status_code == 400
    error = error_of(resp)
    assert error["param"] == "model"
    assert "coquitts" in error["message"]


def test_missing_input_400(client, installed):
    """The input field is required."""
    resp = client.post("/v1/audio/speech", json={"model": "tts-1"})
    assert resp.status_code == 400
    assert error_of(resp)["param"] == "input"


def test_input_over_4096_chars_400(client, installed):
    """OpenAI's 4096-character limit applies."""
    resp = speech(client, model="tts-1", input="x" * 4097)
    assert resp.status_code == 400
    assert error_of(resp)["param"] == "input"


@pytest.mark.parametrize("body", [{"speed": 5.0}, {"speed": 0.1}, {"response_format": "ogg"}, {"language": "english"}])
def test_out_of_range_fields_400(client, installed, body):
    """speed, response_format and language are validated with the failing field named as param."""
    resp = speech(client, model="tts-1", **body)
    assert resp.status_code == 400
    assert error_of(resp)["param"] == next(iter(body))


def test_unknown_extra_fields_are_ignored(client, installed, monkeypatch, app_module, make_wav):
    """Fields other OpenAI clients send (instructions, stream_format) do not fail the request."""
    record_synthesis(monkeypatch, app_module, make_wav())
    resp = speech(client, model="tts-1", response_format="wav", instructions="cheerful", stream_format="audio")
    assert resp.status_code == 200


def test_pool_busy_503_in_openai_shape(client, installed, monkeypatch, app_module, make_wav):
    """A pool that never frees a token answers 503 with the OpenAI server_error envelope."""

    def never_free(timeout):
        """Behave like queue.Queue.get on a pool that stays empty past its timeout."""
        raise queue.Empty()

    record_synthesis(monkeypatch, app_module, make_wav())
    monkeypatch.setattr(app_module, "TTS_POOL_SIZE", 1)
    monkeypatch.setattr(app_module, "ENGINE_POOL", types.SimpleNamespace(get=never_free, get_nowait=lambda: never_free(0)))
    resp = speech(client, model="tts-1", response_format="wav")
    assert resp.status_code == 503
    error = error_of(resp)
    assert error["type"] == "server_error"
    assert error["param"] is None


def test_engine_error_releases_slot(client, installed, monkeypatch, app_module):
    """A synthesis failure gives the pool token back."""

    def boom(text, engine=None, language=None, voice=None):
        """Fail like a broken engine would."""
        raise RuntimeError("engine exploded")

    monkeypatch.setattr(app_module, "text_to_speech_bytes", boom)
    monkeypatch.setattr(app_module, "TTS_POOL_SIZE", 1)
    app_module.ENGINE_POOL.put(0)
    try:
        resp = speech(client, model="tts-1")
        assert resp.status_code == 500
        assert app_module.ENGINE_POOL.qsize() == 1
    finally:
        app_module.ENGINE_POOL.get_nowait()


def test_models_list_contains_engines_and_tts1(client, installed):
    """/v1/models lists every installed engine plus tts-1 in the OpenAI list envelope."""
    resp = client.get("/v1/models")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["object"] == "list"
    assert [model["id"] for model in body["data"]] == ["gtts", "silerotts", "tts-1"]
    for model in body["data"]:
        assert model == {"id": model["id"], "object": "model", "created": 0, "owned_by": "text-to-speech"}


def test_voices_list_returns_engine_voices(client, installed, monkeypatch, app_module):
    """/v1/audio/voices?model=<engine> returns the voices of that engine for the default language."""
    asked = []

    def fake_voices(engine, language="en"):
        """Record the lookup and return a canned voice list."""
        asked.append((engine, language))
        return {"voices": ["baya", "kseniya"], "default": "baya"}

    monkeypatch.setattr(app_module, "get_engine_voices", fake_voices)
    resp = client.get("/v1/audio/voices?model=silerotts&language=ru")
    assert resp.status_code == 200
    assert resp.get_json() == {"voices": ["baya", "kseniya"]}
    assert asked == [("silerotts", "ru")]

    resp = client.get("/v1/audio/voices?model=tts-1")
    assert resp.status_code == 200
    assert asked[-1] == ("gtts", "en")


def test_atempo_chain_stays_within_stage_limits():
    """Speeds outside 0.5..2.0 are split into stages that each stay inside the atempo range."""
    assert openai_compat.atempo_chain(1.0) == "atempo=1.0"
    assert openai_compat.atempo_chain(4.0) == "atempo=2.0,atempo=2.0"
    assert openai_compat.atempo_chain(3.0) == "atempo=2.0,atempo=1.5"
    assert openai_compat.atempo_chain(0.25) == "atempo=0.5,atempo=0.5"
    assert openai_compat.atempo_chain(0.3) == "atempo=0.5,atempo=0.6"


def test_ffmpeg_command_shapes():
    """The argv reads stdin, writes stdout, names the muxer and adds atempo only when speed differs."""
    assert openai_compat.ffmpeg_command("mp3") == ["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-f", "mp3", "pipe:1"]
    pcm = openai_compat.ffmpeg_command("pcm", 2.0)
    assert pcm[5:7] == ["-filter:a", "atempo=2.0"]
    assert pcm[7:] == ["-f", "s16le", "-ar", "24000", "-ac", "1", "pipe:1"]


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")
def test_real_ffmpeg_transcodes_wav_to_mp3(client, installed, monkeypatch, app_module, make_wav):
    """With a real ffmpeg on PATH a WAV engine answers an mp3 request with MPEG audio."""
    record_synthesis(monkeypatch, app_module, make_wav(duration_ms=300))
    resp = speech(client, model="gtts", response_format="mp3", speed=1.5)
    assert resp.status_code == 200
    assert resp.mimetype == "audio/mpeg"
    assert len(resp.data) > 0
    assert app_module.history.is_mp3(resp.data)
