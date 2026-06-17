#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Flask TTS server — preloads engine, exposes HTTP API for synthesis.

Architecture mirrors `speech-to-text/stt_server.py`:
- `init_engine_pool()` warms up the default engine and seeds a `queue.Queue` with
  N tokens for concurrency control. Per-request: acquire token, synthesize via
  `text_to_speech_bytes()` (engine-level `TTS_CACHE` hits), release token.
- Heavy model load happens once at startup, not per-request.
- The actual TTS is the same `libs.api.text_to_speech_bytes` ttsgen uses;
  this server is a thin HTTP veneer over the offline pipeline.
"""

import hmac
import io
import logging
import os
import queue
import sys
import time
import traceback
import uuid
from datetime import date, datetime
from functools import wraps
from pathlib import Path

import pytz
import werkzeug.exceptions
from flask import Flask, g, jsonify, request, send_file
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
from marshmallow import ValidationError as MarshmallowValidationError
from werkzeug.middleware.proxy_fix import ProxyFix

# Local imports — project root must be on sys.path so engines/ and libs/ resolve
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import find_dotenv, load_dotenv  # noqa: E402

from engines import get_available_engines  # noqa: E402
from libs.api import text_to_speech_bytes  # noqa: E402
from libs.exceptions import (  # noqa: E402
    CustomError,
    EngineNotAvailableError,
    TTSException,
    ValidationError,
)
from ttssrv.validators import TtsRequestSchema  # noqa: E402

# .env via find_dotenv (walks up from cwd) → then .env.local override.
found = find_dotenv(usecwd=True)
if found:
    load_dotenv(found)
local_env = PROJECT_ROOT / ".env.local"
if local_env.exists():
    load_dotenv(local_env, override=True)

# Config
TRUE_VALUES = ("1", "true", "yes", "on", "enabled")
TTS_HOST = os.getenv("TTS_HOST", "0.0.0.0")
TTS_PORT = int(os.getenv("TTS_PORT", "5000"))
TTS_DEBUG = os.getenv("TTS_DEBUG", "False").lower() in TRUE_VALUES
TTS_TOKENS = {t.strip() for t in os.getenv("TTS_TOKENS", "").split(",") if t.strip()}
TTS_POOL_SIZE = int(os.getenv("TTS_POOL_SIZE", "1"))
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
# Hard cap on request body size — Marshmallow validates `text` after parsing,
# so without this Werkzeug would buffer arbitrarily large bodies into memory.
TTS_MAX_BODY_BYTES = int(os.getenv("TTS_MAX_BODY_BYTES", str(2 * 1024 * 1024)))
TTS_ENGINE_DEFAULT = os.getenv("TTS_ENGINE", "gtts")
TTS_LANGUAGE_DEFAULT = os.getenv("TTS_LANGUAGE", "en")
TIMEZONE = pytz.timezone(os.getenv("TZ", "America/New_York"))
DATETIME_FMT = "%Y-%m-%d %H:%M:%S"

# Logging
LOGGING = {
    "handlers": [logging.StreamHandler()],
    "format": "%(asctime)s.%(msecs)03d [%(levelname)s]: (%(name)s.%(funcName)s) %(message)s",
    "level": logging.DEBUG if TTS_DEBUG else logging.INFO,
    "datefmt": "%Y-%m-%d %H:%M:%S",
}
logging.basicConfig(**LOGGING)  # type: ignore[arg-type]
logger = logging.getLogger(__name__)

# Engine pool — semaphore tokens; the actual model is cached inside engine module
# (see engines/coquitts.py:TTS_CACHE). Pool limits concurrent synthesis calls.
ENGINE_POOL: queue.Queue = queue.Queue()


def init_engine_pool(size: int = TTS_POOL_SIZE) -> None:
    """Warm the default engine cache and seed pool with N tokens."""
    if size < 1:
        logger.info("TTS_POOL_SIZE=0 → unlimited concurrency, no warmup")
        return

    if TTS_ENGINE_DEFAULT not in ("gtts", "pyttsx3"):
        logger.info(f"Warming up {TTS_ENGINE_DEFAULT}...")
        t0 = time.monotonic()
        try:
            text_to_speech_bytes(text=".", engine=TTS_ENGINE_DEFAULT, language=TTS_LANGUAGE_DEFAULT)
            logger.info(f"Warmup OK ({time.monotonic() - t0:.2f}s)")
        except Exception as exc:
            logger.warning(f"Warmup failed: {type(exc).__name__}: {exc} — will retry on first request")

    for i in range(size):
        ENGINE_POOL.put(i)
    logger.info(f"Pool ready: {size} slot(s) for {TTS_ENGINE_DEFAULT}")


class JSONProvider(DefaultJSONProvider):
    """Custom JSON provider — datetime/date as 'YYYY-MM-DD HH:MM:SS'."""

    def default(self, o):
        if isinstance(o, datetime | date):
            return o.strftime(DATETIME_FMT)
        return super().default(o)


app = Flask(__name__)
app.json = JSONProvider(app)
app.url_map.strict_slashes = False
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1)
app.config.update(
    dict(
        JSON_DATETIME_FORMAT=DATETIME_FMT,
        JSON_SORT_KEYS=False,
        MAX_CONTENT_LENGTH=TTS_MAX_BODY_BYTES,
    )
)
CORS(app, resources={r"/api/*": {"origins": CORS_ORIGINS}})


def get_req_id() -> str:
    return getattr(g, "request_id", "")


def detect_audio_mime(audio_bytes: bytes) -> "tuple[str, str]":
    """Return (mimetype, extension) by sniffing audio bytes header."""
    if audio_bytes.startswith(b"ID3") or audio_bytes[0:2] == b"\xff\xfb":
        return "audio/mpeg", "mp3"
    if audio_bytes.startswith(b"RIFF"):
        return "audio/wav", "wav"
    return "application/octet-stream", "bin"


def parse_tts_payload() -> dict:
    """Read tts request from JSON body, form data, or query string and validate."""
    payload = request.get_json(silent=True) if request.is_json else None
    if not payload:
        payload = request.form.to_dict() or request.args.to_dict()

    schema = TtsRequestSchema()
    errors = schema.validate(payload)
    if errors:
        raise MarshmallowValidationError(errors)
    return schema.load(payload)


def token_required(view):
    """Require Authorization: Bearer <token> when TTS_TOKENS is non-empty."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        if not TTS_TOKENS:
            return view(*args, **kwargs)

        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme != "Bearer" or not token:
            logger.warning(f"[{get_req_id()}] Auth missing/invalid scheme: {scheme!r}")
            return jsonify({"error": "Unauthorized", "request_id": get_req_id()}), 401

        for known in TTS_TOKENS:
            if hmac.compare_digest(token, known):
                return view(*args, **kwargs)

        logger.warning(f"[{get_req_id()}] Auth invalid token")
        return jsonify({"error": "Unauthorized", "request_id": get_req_id()}), 401

    return wrapper


@app.before_request
def assign_request_id():
    g.request_id = uuid.uuid4().hex[:12]
    g.start_time = time.monotonic()


@app.after_request
def after_request(resp):
    log_fn = logger.debug if request.path == "/api/health" else logger.info
    elapsed = time.monotonic() - getattr(g, "start_time", time.monotonic())
    log_fn(f"[{get_req_id()}] {request.method} {request.path}: {resp.status} ({elapsed:.3f}s)")
    return resp


@app.route("/api/health", methods=["GET"])
def health():
    return (
        jsonify(
            {
                "status": "ok",
                "engine": TTS_ENGINE_DEFAULT,
                "pool_size": TTS_POOL_SIZE,
                "available": ENGINE_POOL.qsize(),
            }
        ),
        200,
    )


@app.route("/api/engines", methods=["GET"])
@token_required
def engines_list():
    available = list(get_available_engines().keys())
    return (
        jsonify(
            {
                "engines": sorted(available),
                "default": TTS_ENGINE_DEFAULT,
            }
        ),
        200,
    )


@app.route("/api/tts", methods=["GET", "POST"])
@token_required
def tts_generate():
    data = parse_tts_payload()
    text = data["text"]
    engine = data.get("engine") or TTS_ENGINE_DEFAULT
    language = data.get("language") or TTS_LANGUAGE_DEFAULT

    logger.info(f"[{get_req_id()}] TTS request: engine={engine} language={language} chars={len(text)}")

    slot = None
    if TTS_POOL_SIZE > 0:
        try:
            slot = ENGINE_POOL.get(timeout=120)
        except queue.Empty:
            return jsonify({"error": "All engine slots busy (timeout)"}), 503
    try:
        audio_bytes = text_to_speech_bytes(text=text, engine=engine, language=language)
    finally:
        if slot is not None:
            ENGINE_POOL.put(slot)

    mimetype, ext = detect_audio_mime(audio_bytes)
    timestamp = datetime.now(TIMEZONE).strftime("%Y%m%d_%H%M%S")
    return send_file(
        io.BytesIO(audio_bytes),
        mimetype=mimetype,
        as_attachment=True,
        download_name=f"tts_{timestamp}.{ext}",
    )


@app.errorhandler(MarshmallowValidationError)
def handle_marshmallow_validation_error(error):
    logger.warning(f"[{get_req_id()}] Validation error: {error.messages}")
    return jsonify({"error": "Bad Request", "request_id": get_req_id()}), 400


@app.errorhandler(ValidationError)
def handle_tts_validation_error(error):
    logger.warning(f"[{get_req_id()}] {type(error).__name__}: {str(error)}")
    return jsonify({"error": "Bad Request", "request_id": get_req_id()}), 400


@app.errorhandler(EngineNotAvailableError)
def handle_engine_not_available(error):
    logger.warning(f"[{get_req_id()}] {type(error).__name__}: {str(error)}")
    return jsonify({"error": "Service Unavailable", "request_id": get_req_id()}), 503


@app.errorhandler(CustomError)
def handle_custom_error(error):
    # Engine produced a structured payload — return it verbatim, log a one-liner.
    body = dict(error.payload)
    body.setdefault("request_id", get_req_id())
    summary = (body.get("message") or body.get("error") or "").splitlines()[0][:200]
    logger.warning(f"[{get_req_id()}] CustomError ({body.get('error')}): {summary}")
    return jsonify(body), error.status


@app.errorhandler(TTSException)
def handle_tts_exception(error):
    logger.error(f"[{get_req_id()}] {type(error).__name__}: {str(error)}\n{traceback.format_exc()}")
    return jsonify({"error": "TTS failed", "request_id": get_req_id()}), 500


@app.errorhandler(Exception)
def handle_exception(exc):
    if isinstance(exc, werkzeug.exceptions.HTTPException):
        logger.warning(f"[{get_req_id()}] HTTP {exc.code} {exc.name}")
        return jsonify({"error": exc.name, "request_id": get_req_id()}), exc.code
    logger.error(f"[{get_req_id()}] {type(exc).__name__}: {str(exc)}\n{traceback.format_exc()}")
    return jsonify({"error": "Internal Server Error", "request_id": get_req_id()}), 500


def main() -> int:
    logger.info(
        f"Starting TTS server on {TTS_HOST}:{TTS_PORT} "
        f"debug={TTS_DEBUG} engine={TTS_ENGINE_DEFAULT} pool={TTS_POOL_SIZE} "
        f"auth={'on' if TTS_TOKENS else 'off'}"
    )
    init_engine_pool()
    if TTS_DEBUG:
        app.run(host=TTS_HOST, port=TTS_PORT, debug=True)
    else:
        import uvicorn
        from asgiref.wsgi import WsgiToAsgi

        uvicorn.run(
            WsgiToAsgi(app),
            host=TTS_HOST,
            port=TTS_PORT,
            log_config=None,  # always None: keep our LOGGING, never run uvicorn's own dictConfig
            access_log=False,  # after_request logs every request line; only /api/health is demoted to debug
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
