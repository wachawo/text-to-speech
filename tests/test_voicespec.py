#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTTP side of voice selection and mixing: the /api/voices "mix" flag and the 128-character voice field."""

import pytest

# Local imports
from libs.exceptions import ValidationError

# 100 characters: past the old 64-character cap, inside the new 128 one.
LONG_MIX = "af_nicole(0.35)+af_jessica(0.25)+am_michael(0.25)+bf_isabella(0.15)+" + "x" * 32
KOKORO_VOICES = {"voices": ["af_bella", "af_sky", "bf_emma"], "default": "af_bella", "mix": True}
MIX_ERROR = "Unknown voice 'af_nobody' for kokorotts"


@pytest.fixture
def installed(monkeypatch, app_module):
    """Pretend kokorotts is the installed default engine, for the /v1 routes that check it."""
    monkeypatch.setattr(app_module, "get_available_engines", lambda: {"kokorotts": None})
    monkeypatch.setattr(app_module, "TTS_ENGINE_DEFAULT", "kokorotts")
    monkeypatch.setattr(app_module, "TTS_LANGUAGE_DEFAULT", "en")


def record_synthesis(monkeypatch, app_module, make_wav):
    """Stub text_to_speech_bytes with a recorder that answers a silent WAV."""
    calls = []

    def stub(text, engine=None, language=None, voice=None):
        """Remember the arguments and return canned audio."""
        calls.append({"text": text, "engine": engine, "language": language, "voice": voice})
        return make_wav()

    monkeypatch.setattr(app_module, "text_to_speech_bytes", stub)
    return calls


def refuse_synthesis(monkeypatch, app_module, message):
    """Stub text_to_speech_bytes so every call raises ValidationError(message)."""

    def stub(text, engine=None, language=None, voice=None):
        """Refuse the voice the way the engine does."""
        raise ValidationError(message)

    monkeypatch.setattr(app_module, "text_to_speech_bytes", stub)


def test_long_mix_is_100_characters():
    """The fixture itself: the voice the tests send is exactly 100 characters long."""
    assert len(LONG_MIX) == 100


def test_voices_mix_true_when_engine_says_so(client, monkeypatch, app_module):
    """/api/voices carries "mix": true when the engine listing reports it."""
    asked = []

    def fake_voices(engine, language="en"):
        """Record the lookup and answer a kokorotts-shaped listing."""
        asked.append((engine, language))
        return dict(KOKORO_VOICES)

    monkeypatch.setattr(app_module, "get_engine_voices", fake_voices)
    resp = client.get("/api/voices?engine=kokorotts&language=en")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["mix"] is True
    assert body["voices"] == ["af_bella", "af_sky", "bf_emma"]
    assert body["default"] == "af_bella"
    assert asked == [("kokorotts", "en")]


def test_voices_mix_false_for_listing_without_flag(client, monkeypatch, app_module):
    """A listing that carries no "mix" key (silerotts shape) answers "mix": false."""
    monkeypatch.setattr(app_module, "get_engine_voices", lambda engine, language: {"voices": ["baya"], "default": "baya"})
    body = client.get("/api/voices?engine=silerotts&language=ru").get_json()
    assert body["mix"] is False


def test_voices_mix_false_for_coquitts(client, tmp_path, monkeypatch):
    """coquitts lists its sample files and never mixes."""
    monkeypatch.setenv("COQUITTS_SAMPLES", str(tmp_path / "samples"))
    monkeypatch.delenv("COQUITTS_SAMPLE", raising=False)
    resp = client.get("/api/voices?engine=coquitts")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["mix"] is False
    assert body["voices"] == []


def test_voices_mix_false_for_engine_without_list_voices(client):
    """gtts has no list_voices: an empty list and "mix": false."""
    body = client.get("/api/voices?engine=gtts&language=en").get_json()
    assert body["voices"] == []
    assert body["mix"] is False


def test_openai_voices_shape_unchanged(client, installed, monkeypatch, app_module):
    """/v1/audio/voices keeps its {"voices": [...]} body and does not grow a "mix" key."""
    monkeypatch.setattr(app_module, "get_engine_voices", lambda engine, language="en": dict(KOKORO_VOICES))
    resp = client.get("/v1/audio/voices?model=kokorotts")
    assert resp.status_code == 200
    assert resp.get_json() == {"voices": ["af_bella", "af_sky", "bf_emma"]}


def test_api_tts_passes_100_character_voice(client, monkeypatch, app_module, make_wav):
    """/api/tts accepts a 100-character voice and forwards it unchanged."""
    calls = record_synthesis(monkeypatch, app_module, make_wav)
    resp = client.post("/api/tts", json={"text": "hi", "engine": "kokorotts", "language": "en", "voice": LONG_MIX})
    assert resp.status_code == 200
    assert calls == [{"text": "hi", "engine": "kokorotts", "language": "en", "voice": LONG_MIX}]


def test_api_history_passes_100_character_voice(client, tmp_path, monkeypatch, app_module, make_wav):
    """POST /api/history inherits the 128-character voice from TtsRequestSchema."""
    monkeypatch.setattr(app_module, "TTS_HISTORY_DIR", str(tmp_path / "history"))
    calls = record_synthesis(monkeypatch, app_module, make_wav)
    resp = client.post("/api/history", json={"text": "hi", "engine": "kokorotts", "language": "en", "voice": LONG_MIX})
    assert resp.status_code == 201
    assert resp.get_json()["voice"] == LONG_MIX
    assert calls[0]["voice"] == LONG_MIX


def test_openai_speech_passes_100_character_voice(client, installed, monkeypatch, app_module, make_wav):
    """/v1/audio/speech accepts a 100-character voice and forwards it unchanged."""
    calls = record_synthesis(monkeypatch, app_module, make_wav)
    resp = client.post(
        "/v1/audio/speech",
        json={"model": "kokorotts", "input": "hi", "voice": LONG_MIX, "response_format": "wav"},
    )
    assert resp.status_code == 200
    assert calls == [{"text": "hi", "engine": "kokorotts", "language": "en", "voice": LONG_MIX}]


def test_api_tts_129_character_voice_is_400(client, monkeypatch, app_module, make_wav):
    """A voice one character past 128 fails the schema before any synthesis."""
    calls = record_synthesis(monkeypatch, app_module, make_wav)
    resp = client.post("/api/tts", json={"text": "hi", "engine": "kokorotts", "voice": "v" * 129})
    assert resp.status_code == 400
    assert calls == []

    resp = client.post("/api/tts", json={"text": "hi", "engine": "kokorotts", "voice": "v" * 128})
    assert resp.status_code == 200


def test_api_history_129_character_voice_is_400(client, tmp_path, monkeypatch, app_module, make_wav):
    """POST /api/history refuses a 129-character voice too."""
    monkeypatch.setattr(app_module, "TTS_HISTORY_DIR", str(tmp_path / "history"))
    calls = record_synthesis(monkeypatch, app_module, make_wav)
    resp = client.post("/api/history", json={"text": "hi", "engine": "kokorotts", "voice": "v" * 129})
    assert resp.status_code == 400
    assert calls == []


def test_openai_speech_129_character_voice_is_400(client, installed, monkeypatch, app_module, make_wav):
    """/v1/audio/speech refuses a 129-character voice in the OpenAI error shape, naming the field."""
    calls = record_synthesis(monkeypatch, app_module, make_wav)
    resp = client.post("/v1/audio/speech", json={"model": "kokorotts", "input": "hi", "voice": "v" * 129})
    assert resp.status_code == 400
    assert resp.get_json()["error"]["param"] == "voice"
    assert calls == []


def test_api_tts_mix_validation_error_is_400_with_message(client, monkeypatch, app_module):
    """A ValidationError from the engine about a mix comes back as 400 carrying its message."""
    refuse_synthesis(monkeypatch, app_module, MIX_ERROR)
    resp = client.post("/api/tts", json={"text": "hi", "engine": "kokorotts", "voice": "af_bella(2)+af_nobody(1)"})
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["error"] == "Bad Request"
    assert body["message"] == MIX_ERROR


def test_openai_speech_mix_validation_error_is_400_with_message(client, installed, monkeypatch, app_module):
    """/v1/audio/speech answers the same refusal as an OpenAI invalid_request_error."""
    refuse_synthesis(monkeypatch, app_module, MIX_ERROR)
    resp = client.post(
        "/v1/audio/speech",
        json={"model": "kokorotts", "input": "hi", "voice": "af_bella(2)+af_nobody(1)"},
    )
    assert resp.status_code == 400
    error = resp.get_json()["error"]
    assert error["message"] == MIX_ERROR
    assert error["type"] == "invalid_request_error"
