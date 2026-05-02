#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Flask API server for TTS — accepts text, returns audio file."""

import hmac
import io
import logging
import os
import sys
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

from api.validators import TtsRequestSchema  # noqa: E402
from engines import get_available_engines  # noqa: E402
from libs.api import text_to_speech_bytes  # noqa: E402
from libs.exceptions import (  # noqa: E402
    EngineNotAvailableError,
    TTSException,
    ValidationError,
)

load_dotenv(find_dotenv())

# Config
TRUE_VALUES = ("1", "true", "yes", "on", "enabled")
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() in TRUE_VALUES
SECRET_KEY = os.getenv("SECRET_KEY", "SuP3rS3cr3tK3y!")
TIMEZONE = pytz.timezone(os.getenv("TZ", "America/New_York"))
TTS_ENGINE_DEFAULT = os.getenv("TTS_ENGINE", "gtts")
TTS_LANGUAGE_DEFAULT = os.getenv("TTS_LANGUAGE", "en")
TTS_TOKENS = {t.strip() for t in os.getenv("TTS_TOKENS", "").split(",") if t.strip()}
DATETIME_FMT = "%Y-%m-%d %H:%M:%S"

# Logging
LOGGING = {
    "handlers": [
        logging.StreamHandler(),
    ],
    "format": "%(asctime)s.%(msecs)03d [%(levelname)s]: (%(name)s) %(message)s",
    "level": logging.INFO,
    "datefmt": "%Y-%m-%d %H:%M:%S",
}
logging.basicConfig(**LOGGING)  # type: ignore[arg-type]
logger = logging.getLogger(__name__)


class JSONProvider(DefaultJSONProvider):
    """Custom JSON provider — datetime/date serialized as 'YYYY-MM-DD HH:MM:SS'."""

    def default(self, o):
        if isinstance(o, (datetime, date)):
            return o.strftime(DATETIME_FMT)
        return super().default(o)


app = Flask(__name__)
app.json = JSONProvider(app)
app.url_map.strict_slashes = False
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1)
app.config.from_object(__name__)
app.config.update(
    dict(
        SECRET_KEY=SECRET_KEY,
        JSON_DATETIME_FORMAT=DATETIME_FMT,
        JSON_SORT_KEYS=False,
    )
)
CORS(app, resources={r"/api/*": {"origins": "*"}})


def get_req_id() -> str:
    return getattr(g, "request_id", "")


def detect_audio_mime(audio_bytes: bytes) -> tuple[str, str]:
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


@app.after_request
def after_request(resp):
    logger.info(f"[{get_req_id()}] {request.method} {request.path}: {resp.status_code} {resp.status}")
    return resp


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


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

    audio_bytes = text_to_speech_bytes(text=text, engine=engine, language=language)
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


def main():
    logger.info(f"Starting TTS API on {FLASK_HOST}:{FLASK_PORT} debug={FLASK_DEBUG} default_engine={TTS_ENGINE_DEFAULT}")
    if FLASK_DEBUG:
        app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
    else:
        import uvicorn
        from asgiref.wsgi import WsgiToAsgi

        uvicorn.run(WsgiToAsgi(app), host=FLASK_HOST, port=FLASK_PORT, log_level="info")


if __name__ == "__main__":
    main()
