#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the per-request `model` and the GET /api/engines/<engine> discovery route."""

import pytest

# Local imports
from libs import tools as tools_mod

KOKORO_MODELS = [
    {"id": "kokoro-v1.0.onnx", "languages": ["en", "ja"], "installed": True},
    {"id": "kokoro-v1.0.int8.onnx", "languages": ["en"], "installed": True},
]

ENGINE_DETAIL_KEYS = {
    "engine",
    "installed",
    "preloaded",
    "default",
    "models",
    "default_model",
    "model_selectable",
    "languages",
    "default_language",
    "language_strict",
    "voice_selectable",
    "voices_endpoint",
    "output_format",
    "max_text_length",
    "stream",
}


def record_synthesis(monkeypatch, app_module, audio_bytes):
    """Stub text_to_speech_bytes to return `audio_bytes` and collect the keyword arguments of each call."""
    calls = []

    def stub(text, engine=None, language=None, voice=None, **kwargs):
        """Return canned audio and remember what was asked for, `model` only when it was passed."""
        calls.append({"text": text, "engine": engine, "language": language, "voice": voice, **kwargs})
        return audio_bytes

    monkeypatch.setattr(app_module, "text_to_speech_bytes", stub)
    return calls


@pytest.fixture
def kokoro_models(monkeypatch):
    """Make kokorotts list KOKORO_MODELS to the model check."""
    monkeypatch.setattr(tools_mod, "list_engine_models", lambda engine: KOKORO_MODELS if engine == "kokorotts" else [])


@pytest.fixture
def history_dir(tmp_path, monkeypatch, app_module):
    """Redirect TTS_HISTORY_DIR to a fresh directory for one test."""
    target = tmp_path / "history"
    monkeypatch.setattr(app_module, "TTS_HISTORY_DIR", str(target))
    return target


# /api/tts


def test_tts_passes_model_to_synthesis(client, kokoro_models, monkeypatch, app_module, make_wav):
    """A listed model reaches text_to_speech_bytes and the file comes back as before."""
    calls = record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post("/api/tts", json={"text": "hi", "engine": "kokorotts", "model": "kokoro-v1.0.int8.onnx"})
    assert resp.status_code == 200
    assert resp.mimetype == "audio/wav"
    assert calls[-1]["model"] == "kokoro-v1.0.int8.onnx"


@pytest.mark.parametrize("payload", [{}, {"model": None}, {"model": ""}])
def test_tts_without_model_calls_synthesis_as_before(client, monkeypatch, app_module, make_wav, payload):
    """No model, null or "" keeps the call without a `model` keyword, so older stubs and engines work unchanged."""
    calls = record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post("/api/tts", json={"text": "hi", "engine": "kokorotts", **payload})
    assert resp.status_code == 200
    assert "model" not in calls[-1]


def test_tts_get_takes_model_from_query(client, kokoro_models, monkeypatch, app_module, make_wav):
    """The query-string form takes `model` too."""
    calls = record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.get("/api/tts?text=hi&engine=kokorotts&model=kokoro-v1.0.onnx")
    assert resp.status_code == 200
    assert calls[-1]["model"] == "kokoro-v1.0.onnx"


def test_tts_form_takes_model(client, kokoro_models, monkeypatch, app_module, make_wav):
    """A form-encoded request takes `model` as well."""
    calls = record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post("/api/tts", data={"text": "hi", "engine": "kokorotts", "model": "kokoro-v1.0.onnx"})
    assert resp.status_code == 200
    assert calls[-1]["model"] == "kokoro-v1.0.onnx"


def test_model_with_stream_is_refused(client, kokoro_models, monkeypatch, app_module, make_wav):
    """Streaming keeps the engine default model, so `model` with stream=true is a 400 before any synthesis."""
    calls = record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post("/api/tts", json={"text": "hi", "engine": "kokorotts", "model": "kokoro-v1.0.onnx", "stream": True})
    assert resp.status_code == 400
    body = resp.get_json()
    assert set(body) == {"error", "message", "request_id"}
    assert body["message"] == "model: model is supported only for file generation (stream=false)"
    assert calls == []


def test_stream_with_empty_model_streams(client, monkeypatch, app_module, make_wav):
    """An empty model is no model, so a stream request carrying one still streams."""
    calls = record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post("/api/tts", json={"text": "hi", "model": "", "stream": True})
    assert resp.status_code == 200
    assert resp.data  # drain the stream so its pool slot and request context are released
    assert "model" not in calls[-1]


def test_unknown_model_is_refused_before_taking_a_slot(client, kokoro_models, monkeypatch, app_module, make_wav):
    """An unlisted model is a 400 that names it and the models the engine has; the pool is left alone."""
    calls = record_synthesis(monkeypatch, app_module, make_wav())
    monkeypatch.setattr(app_module, "TTS_POOL_SIZE", 1)
    app_module.ENGINE_POOL.put(0)
    try:
        resp = client.post("/api/tts", json={"text": "hi", "engine": "kokorotts", "model": "kokoro-v9.onnx"})
        assert app_module.ENGINE_POOL.qsize() == 1
    finally:
        app_module.ENGINE_POOL.get_nowait()
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["error"] == "Bad Request"
    assert body["message"] == (
        "Unknown model 'kokoro-v9.onnx' for engine 'kokorotts'. Available: kokoro-v1.0.onnx, kokoro-v1.0.int8.onnx"
    )
    assert calls == []


def test_model_for_engine_without_models_is_refused(client, monkeypatch, app_module, make_wav):
    """gtts has no models, so any model is a 400 that says so."""
    calls = record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post("/api/tts", json={"text": "hi", "engine": "gtts", "model": "standard"})
    assert resp.status_code == 400
    assert resp.get_json()["message"] == "Engine 'gtts' has no selectable models"
    assert calls == []


@pytest.mark.parametrize("model", ["a b", "x" * 200, "../etc/passwd", "-leading-dash", "semi;colon"])
def test_malformed_model_is_a_schema_error(client, monkeypatch, app_module, make_wav, model):
    """A model id with characters no engine uses, or longer than 128, is refused by the schema with `message`."""
    calls = record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post("/api/tts", json={"text": "hi", "engine": "kokorotts", "model": model})
    assert resp.status_code == 400
    assert resp.get_json()["message"].startswith("model: ")
    assert calls == []


def test_tts_logs_model_only_when_set(client, kokoro_models, monkeypatch, app_module, make_wav, caplog):
    """The request and Synthesis lines name the model when one is asked for, and are unchanged otherwise."""
    record_synthesis(monkeypatch, app_module, make_wav())
    caplog.set_level("INFO")
    client.post("/api/tts", json={"text": "hi", "engine": "kokorotts", "model": "kokoro-v1.0.onnx"})
    client.post("/api/tts", json={"text": "hi", "engine": "kokorotts"})
    lines = [record.getMessage() for record in caplog.records if "Synthesis:" in record.getMessage()]
    assert "voice=None model=kokoro-v1.0.onnx chars=2 " in lines[0]
    assert "voice=None chars=2 " in lines[1]
    synthesis_records = [record for record in caplog.records if "Synthesis:" in record.getMessage()]
    assert [record.model for record in synthesis_records] == ["kokoro-v1.0.onnx", None]


def test_tts_model_listing_failure_is_a_server_error(client, monkeypatch, app_module, make_wav):
    """A model listing that fails on the server is a 500, not a 400 that says the engine has no models."""
    calls = record_synthesis(monkeypatch, app_module, make_wav())

    def unreadable(engine):
        """Fail like a models directory without read permission."""
        raise PermissionError(13, "Permission denied", "./voices")

    monkeypatch.setattr(tools_mod, "list_engine_models", unreadable)
    resp = client.post("/api/tts", json={"text": "hi", "engine": "pipertts", "model": "en_US-lessac-medium"})
    assert resp.status_code == 500
    assert resp.get_json()["error"] == "TTS failed"
    assert calls == []


def test_tts_model_for_the_package_file_is_not_found(client, monkeypatch, app_module, make_wav):
    """engines/__init__.py is not an engine: a model for it is refused as an engine that does not exist."""
    record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post("/api/tts", json={"text": "hi", "engine": "__init__", "model": "x"})
    assert resp.status_code == 400
    assert resp.get_json()["message"] == "Engine '__init__' not found"


# /api/history


def test_history_stores_the_model(client, kokoro_models, history_dir, monkeypatch, app_module, make_wav):
    """POST /api/history synthesizes with the model and the item records it; without one it is null."""
    calls = record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post("/api/history", json={"text": "hi", "engine": "kokorotts", "model": "kokoro-v1.0.onnx"})
    assert resp.status_code == 201
    assert resp.get_json()["model"] == "kokoro-v1.0.onnx"
    assert calls[-1]["model"] == "kokoro-v1.0.onnx"
    item_id = resp.get_json()["id"]
    assert client.get(f"/api/history/{item_id}").get_json()["model"] == "kokoro-v1.0.onnx"

    resp = client.post("/api/history", json={"text": "hi", "engine": "kokorotts"})
    assert resp.status_code == 201
    assert resp.get_json()["model"] is None


def test_history_refuses_unknown_model(client, kokoro_models, history_dir, monkeypatch, app_module, make_wav):
    """An unknown model is a 400 and nothing is stored."""
    record_synthesis(monkeypatch, app_module, make_wav())
    resp = client.post("/api/history", json={"text": "hi", "engine": "kokorotts", "model": "nope"})
    assert resp.status_code == 400
    assert resp.get_json()["message"].startswith("Unknown model 'nope'")
    assert not history_dir.exists()


# TTS_LANGUAGE_STRICT with a model


def test_strict_checks_the_languages_of_the_model(client, kokoro_models, monkeypatch, app_module, make_wav):
    """In strict mode a language is checked against the requested model's own languages."""
    record_synthesis(monkeypatch, app_module, make_wav())
    monkeypatch.setattr(app_module, "TTS_LANGUAGE_STRICT", True)
    languages = {None: ["en", "ja"], "kokoro-v1.0.int8.onnx": ["en"]}
    monkeypatch.setattr(tools_mod, "get_engine_languages", lambda engine, model=None: languages[model])
    ok = client.post("/api/tts", json={"text": "hi", "engine": "kokorotts", "language": "ja"})
    assert ok.status_code == 200
    resp = client.post(
        "/api/tts", json={"text": "hi", "engine": "kokorotts", "language": "ja", "model": "kokoro-v1.0.int8.onnx"}
    )
    assert resp.status_code == 400
    assert resp.get_json()["message"] == (
        "Language 'ja' is not supported by engine 'kokorotts' model 'kokoro-v1.0.int8.onnx'. Supported: en"
    )


def test_model_is_checked_without_strict_mode(client, kokoro_models, monkeypatch, app_module, make_wav):
    """The model check is not part of TTS_LANGUAGE_STRICT: an unknown model is a 400 in the default mode."""
    record_synthesis(monkeypatch, app_module, make_wav())
    monkeypatch.setattr(app_module, "TTS_LANGUAGE_STRICT", False)
    resp = client.post("/api/tts", json={"text": "hi", "engine": "kokorotts", "language": "ru", "model": "x"})
    assert resp.status_code == 400


def test_openai_speech_model_still_names_the_engine(client, monkeypatch, app_module, make_wav):
    """/v1/audio/speech keeps `model` as the engine and synthesizes with the engine default model."""
    calls = record_synthesis(monkeypatch, app_module, make_wav())
    monkeypatch.setattr(app_module, "get_available_engines", lambda: {"kokorotts": None})
    resp = client.post("/v1/audio/speech", json={"model": "kokorotts", "input": "hi", "response_format": "wav"})
    assert resp.status_code == 200
    assert calls[-1]["engine"] == "kokorotts"
    assert "model" not in calls[-1]


# GET /api/voices?model=


def test_voices_with_unknown_model_is_refused(client, kokoro_models):
    """?model= must name a listed model."""
    resp = client.get("/api/voices?engine=kokorotts&language=en&model=bad")
    assert resp.status_code == 400
    assert resp.get_json()["message"].startswith("Unknown model 'bad' for engine 'kokorotts'")


@pytest.mark.parametrize("model", ["x\n2026-01-01 00:00:00.000 [INFO]: forged", "a b", "m" * 200])
def test_voices_with_malformed_model_is_refused_by_the_schema(client, kokoro_models, model, caplog):
    """?model= follows the /api/tts id rule, so a raw value is neither echoed in the message nor logged."""
    caplog.set_level("WARNING")
    resp = client.get("/api/voices", query_string={"engine": "kokorotts", "language": "en", "model": model})
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["message"] == "model: String does not match expected pattern."
    assert model not in caplog.text


@pytest.mark.parametrize("engine", ["\n2026-01-01 [INFO] forged", "a" * 5000])
def test_voices_with_malformed_engine_is_not_echoed(client, engine, caplog):
    """An engine name that is not a module stem gets a short 400 that neither repeats nor logs the raw value."""
    caplog.set_level("WARNING")
    resp = client.get("/api/voices", query_string={"engine": engine, "model": "x"})
    assert resp.status_code == 400
    assert resp.get_json()["message"] == "Engine not found"
    assert engine not in caplog.text


def test_voices_with_model_lists_that_models_voices(client, kokoro_models, monkeypatch, app_module):
    """A listed model is passed on to the voices listing and echoed back."""
    calls = []

    def voices_of(engine, language, model=None):
        """Record the call and return one voice."""
        calls.append((engine, language, model))
        return {"voices": ["af_bella"], "default": "af_bella"}

    monkeypatch.setattr(app_module, "get_engine_voices", voices_of)
    body = client.get("/api/voices?engine=kokorotts&language=en&model=kokoro-v1.0.onnx").get_json()
    assert body["model"] == "kokoro-v1.0.onnx"
    assert body["voices"] == ["af_bella"]
    assert calls == [("kokorotts", "en", "kokoro-v1.0.onnx")]


def test_voices_without_model_reports_null(client, monkeypatch, app_module):
    """Without ?model= the listing is called as before and `model` is null."""
    calls = []

    def voices_of(engine, language):
        """Take exactly two arguments, as before models existed."""
        calls.append((engine, language))
        return {"voices": [], "default": None}

    monkeypatch.setattr(app_module, "get_engine_voices", voices_of)
    body = client.get("/api/voices?engine=kokorotts&language=en").get_json()
    assert body["model"] is None
    assert calls == [("kokorotts", "en")]


# GET /api/engines/<engine>


@pytest.fixture
def kokoro_dir(monkeypatch, tmp_path):
    """A kokorotts models directory with two model files and no voices file."""
    (tmp_path / "kokoro-v1.0.onnx").write_bytes(b"x")
    (tmp_path / "kokoro-v1.0.int8.onnx").write_bytes(b"x")
    monkeypatch.setenv("KOKOROTTS_MODELS", str(tmp_path))
    for name in ("KOKOROTTS_MODEL", "KOKOROTTS_VOICES"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path


def test_engine_details_describe_kokorotts(client, kokoro_dir, monkeypatch, app_module):
    """The route answers every documented key from the engine hooks and the server config."""
    monkeypatch.setattr(app_module, "TTS_ENGINES", ["kokorotts"])
    monkeypatch.setattr(app_module, "TTS_ENGINE_DEFAULT", "kokorotts")
    monkeypatch.setattr(app_module, "TTS_LANGUAGE_DEFAULT", "en")
    resp = client.get("/api/engines/kokorotts")
    assert resp.status_code == 200
    body = resp.get_json()
    assert set(body) == ENGINE_DETAIL_KEYS
    assert body["engine"] == "kokorotts"
    assert isinstance(body["installed"], bool)
    assert body["preloaded"] is True
    assert body["default"] is True
    assert [model["id"] for model in body["models"]] == ["kokoro-v1.0.int8.onnx", "kokoro-v1.0.onnx"]
    default_model = next(model for model in body["models"] if model["id"] == "kokoro-v1.0.onnx")
    assert default_model["default_for"] == body["languages"]
    assert body["default_model"] == "kokoro-v1.0.onnx"
    assert body["model_selectable"] is True
    assert "en" in body["languages"]
    assert body["default_language"] == "en"
    assert body["language_strict"] is False
    assert body["voice_selectable"] is True
    assert body["voices_endpoint"] == "/api/voices?engine=kokorotts"
    assert body["output_format"] == "wav"
    assert body["max_text_length"] == 50_000
    assert body["stream"] == "chunked"


def test_engine_details_of_an_engine_without_models(client):
    """gtts has no models and no voice listing, and answers MP3."""
    body = client.get("/api/engines/gtts").get_json()
    assert set(body) == ENGINE_DETAIL_KEYS
    assert body["models"] == []
    assert body["default_model"] is None
    assert body["model_selectable"] is False
    assert body["voice_selectable"] is False
    assert body["voices_endpoint"] is None
    assert body["output_format"] == "mp3"


def test_engine_details_follow_language_strict(client, monkeypatch, app_module):
    """language_strict reports TTS_LANGUAGE_STRICT."""
    monkeypatch.setattr(app_module, "TTS_LANGUAGE_STRICT", True)
    assert client.get("/api/engines/gtts").get_json()["language_strict"] is True


def test_engine_details_never_load_a_model(client, kokoro_dir, monkeypatch):
    """Discovery reads only file names: the kokorotts loader is never called."""
    import engines

    module = engines.get_engine_module("kokorotts")

    def refuse(*args, **kwargs):
        """Fail the test: discovery must not load a model."""
        raise AssertionError("get_kokoro was called")

    monkeypatch.setattr(module, "get_kokoro", refuse)
    assert client.get("/api/engines/kokorotts").status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/api/engines/nope",
        "/api/engines/__init__",
        "/api/engines/..%2Flibs",
        "/api/engines/Gtts",
        "/api/engines/a.b",
    ],
)
def test_engine_details_unknown_engine_is_404(client, path):
    """An engine without a module, the package file itself or a name that is not a module stem: the plain 404 body."""
    resp = client.get(path)
    assert resp.status_code == 404
    body = resp.get_json()
    assert set(body) == {"error", "request_id"}
    assert body["error"] == "Not Found"


def test_engine_details_broken_engine_is_not_a_404(client, monkeypatch):
    """A shipped engine whose module fails to import is a server error, not an unknown engine."""
    import engines as engines_pkg

    def broken_import(name):
        """Fail like an engine module with a syntax error."""
        raise ImportError("broken engine module")

    monkeypatch.setattr(engines_pkg, "get_engine_module", broken_import)
    resp = client.get("/api/engines/kokorotts")
    assert resp.status_code == 500


def test_engines_list_is_unchanged(client):
    """GET /api/engines keeps exactly its keys."""
    body = client.get("/api/engines").get_json()
    assert set(body) == {"supported", "available", "preload", "default", "language"}


# libs.api.text_to_speech_bytes


def load_real_api():
    """Import the real libs/api.py; conftest keeps a stub under sys.modules["libs.api"]."""
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("libs.api_real", Path(__file__).resolve().parent.parent / "libs" / "api.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def recorded_configs(monkeypatch):
    """Run the real text_to_speech_bytes against a recording kokorotts generate() and return the configs it got."""
    real_api = load_real_api()
    configs = []

    def generate(text, config):
        """Remember the config the engine was called with."""
        configs.append(dict(config))
        return b"RIFF"

    monkeypatch.setattr(tools_mod, "is_engine_available", lambda engine: True)
    monkeypatch.setattr(tools_mod, "list_engine_models", lambda engine: KOKORO_MODELS)
    monkeypatch.setattr(real_api, "get_engine_function", lambda engine: generate)
    return real_api, configs


def test_text_to_speech_bytes_passes_a_listed_model(recorded_configs):
    """A listed model reaches the engine as config["model"]; None and "" leave it None."""
    real_api, configs = recorded_configs
    assert real_api.text_to_speech_bytes("hi", "kokorotts", "en", model="kokoro-v1.0.int8.onnx") == b"RIFF"
    real_api.text_to_speech_bytes("hi", "kokorotts", "en", model=None)
    real_api.text_to_speech_bytes("hi", "kokorotts", "en", model="")
    real_api.text_to_speech_bytes("hi", "kokorotts", "en")
    assert [config["model"] for config in configs] == ["kokoro-v1.0.int8.onnx", None, None, None]


def test_text_to_speech_bytes_refuses_an_unlisted_model(recorded_configs):
    """An id the engine does not list is a ValidationError before generate() runs."""
    real_api, configs = recorded_configs
    with pytest.raises(real_api.ValidationError, match="Unknown model 'nope' for engine 'kokorotts'"):
        real_api.text_to_speech_bytes("hi", "kokorotts", "en", model="nope")
    assert configs == []
