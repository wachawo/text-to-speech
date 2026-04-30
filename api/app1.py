#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Flask API server for TTS — accepts text, returns audio file."""

import io
import logging
import os
import sys
import traceback
from datetime import date, datetime
from pathlib import Path

import pytz
from flask import Flask, jsonify, request, send_file
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
from marshmallow import ValidationError as MarshmallowValidationError
from werkzeug.middleware.proxy_fix import ProxyFix
import werkzeug.exceptions

# Local imports — project root must be on sys.path so engines/ and libs/ resolve
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engines import get_available_engines  # noqa: E402
from libs.api import text_to_speech_bytes  # noqa: E402
from libs.exceptions import (  # noqa: E402
    EngineNotAvailableError,
    TTSException,
    ValidationError,
)

from api.validators import TtsRequestSchema  # noqa: E402

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

# Config
TRUE_VALUES = ("1", "true", "yes", "on", "enabled")
FLASK_HOST            = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT            = int(os.getenv("FLASK_PORT", "5000"))
FLASK_DEBUG           = os.getenv("FLASK_DEBUG", "False").lower() in TRUE_VALUES
SECRET_KEY            = os.getenv("SECRET_KEY", "SuP3rS3cr3tK3y!")
TIMEZONE              = pytz.timezone(os.getenv("TZ", "America/New_York"))
TTS_ENGINE_DEFAULT    = os.getenv("TTS_ENGINE", "gtts")
TTS_LANGUAGE_DEFAULT  = os.getenv("TTS_LANGUAGE", "en")
DATETIME_FMT          = "%Y-%m-%d %H:%M:%S"

# Logging
LOGGING = {
    "handlers": [
        logging.StreamHandler(),
    ],
    "format":  "%(asctime)s.%(msecs)03d [%(levelname)s]: (%(name)s) %(message)s",
    "level":   logging.INFO,
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
app.config.update(dict(
    SECRET_KEY=SECRET_KEY,
    JSON_DATETIME_FORMAT=DATETIME_FMT,
    JSON_SORT_KEYS=False,
))
CORS(app, resources={r"/api/*": {"origins": "*"}})


def detect_audio_mime(audio_bytes: bytes) -> tuple[str, str]:
    """Return (mimetype, extension) by sniffing audio bytes header."""
    if audio_bytes.startswith(b"ID3") or audio_bytes[0:2] == b"\xff\xfb":
        return "audio/mpeg", "mp3"
    if audio_bytes.startswith(b"RIFF"):
        return "audio/wav", "wav"
    return "application/octet-stream", "bin"


def parse_tts_payload() -> dict:
    """Read tts request from JSON body or query string and validate."""
    payload = request.get_json(silent=True) if request.is_json else None
    if not payload:
        payload = request.args.to_dict()

    schema = TtsRequestSchema()
    errors = schema.validate(payload)
    if errors:
        raise MarshmallowValidationError(errors)
    return schema.load(payload)


@app.before_request
def before_request():
    pass


@app.after_request
def after_request(resp):
    logger.info(f"{request.method} {request.path}: {resp.status_code} {resp.status}")
    return resp


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/api/engines", methods=["GET"])
def engines_list():
    available = list(get_available_engines().keys())
    return jsonify({
        "engines": sorted(available),
        "default": TTS_ENGINE_DEFAULT,
    }), 200


@app.route("/api/tts", methods=["GET", "POST"])
def tts_generate():
    data = parse_tts_payload()
    text     = data["text"]
    engine   = data.get("engine")   or TTS_ENGINE_DEFAULT
    language = data.get("language") or TTS_LANGUAGE_DEFAULT

    logger.info(f"TTS request: engine={engine} language={language} chars={len(text)}")

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
    logger.warning(f"Validation error: {error.messages}")
    return jsonify({"error": error.messages}), 400


@app.errorhandler(ValidationError)
def handle_tts_validation_error(error):
    logger.warning(f"TTS validation error: {error}")
    return jsonify({"error": str(error)}), 400


@app.errorhandler(EngineNotAvailableError)
def handle_engine_not_available(error):
    logger.warning(f"Engine not available: {error}")
    return jsonify({"error": str(error)}), 503


@app.errorhandler(TTSException)
def handle_tts_exception(error):
    logger.error(
        f"{type(error).__name__}: {str(error)}\n{traceback.format_exc()}"
    )
    return jsonify({"error": f"{type(error).__name__}: {str(error)}"}), 500


@app.errorhandler(400)
def bad_request(error):
    return jsonify({"error": "Bad Request", "message": str(error)}), 400


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not Found", "message": str(error)}), 404


@app.errorhandler(Exception)
def handle_exception(exc):
    if isinstance(exc, werkzeug.exceptions.HTTPException):
        return jsonify({"error": exc.name, "message": exc.description}), exc.code
    logger.error(
        f"{type(exc).__name__}: {str(exc)}\n{traceback.format_exc()}"
    )
    response = jsonify({"error": f"{type(exc).__name__}: {str(exc)}"})
    response.status_code = 500
    return response


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
