#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Flask TTS server that preloads engines and exposes an HTTP API for synthesis.

`init_engine_pool()` warms up the configured engines and seeds a `queue.Queue`
with N tokens used purely as a concurrency semaphore: every request acquires a
token, synthesizes through `libs.api.text_to_speech_bytes` (which hits the
engine-level model cache), then releases it. Heavy model loading therefore
happens once at startup rather than per request, and this module stays a thin
HTTP veneer over the same offline pipeline that `ttsgen` drives.
"""

import hmac
import io
import logging
import os
import queue
import re
import sys
import threading
import time
import traceback
import uuid
import warnings
import wave
from datetime import date, datetime
from functools import wraps
from pathlib import Path

import pytz
import werkzeug.exceptions
from flask import Flask, Response, abort, g, jsonify, request, send_file, stream_with_context
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
from marshmallow import ValidationError as MarshmallowValidationError
from werkzeug.middleware.proxy_fix import ProxyFix

# Local imports — project root must be on sys.path so engines/ and libs/ resolve
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engines import get_available_engines, get_engine_voices, get_supported_engines  # noqa: E402
from libs.api import text_to_speech_bytes  # noqa: E402
from libs.audio import audio_format, audio_mime  # noqa: E402
from libs.cli import chunk_text  # noqa: E402
from libs.config import load_config  # noqa: E402
from libs.exceptions import (  # noqa: E402
    CustomError,
    EngineNotAvailableError,
    TTSException,
    ValidationError,
)
from libs.languages import normalize_language  # noqa: E402
from libs.logjson import JsonFormatter  # noqa: E402
from libs.models import collect_engine_rows  # noqa: E402
from libs.sample_resolver import (  # noqa: E402
    describe_sample_files,
    get_samples_dir,
    list_sample_files,
    sample_path_for_voice,
)
from libs.tools import validate_engine_language  # noqa: E402
from ttssrv import history, metrics  # noqa: E402
from ttssrv.openai_compat import (  # noqa: E402
    OpenAIRequestError,
    error_body,
    map_model_name,
    map_voice_name,
    prepare_audio,
    validation_error_body,
)
from ttssrv.streaming import streaming_wav_header, wav_data, wav_params  # noqa: E402
from ttssrv.validators import (  # noqa: E402
    HistoryCreateSchema,
    HistoryListSchema,
    SpeechRequestSchema,
    TtsRequestSchema,
    VoiceUploadSchema,
    format_validation_messages,
)

# Shell env > ./ttsgen.conf > ~/.config/ttsgen.conf > ./.env.local > ./.env, cwd only.
load_config()

# Config
TRUE_VALUES = ("1", "true", "yes", "on", "enabled")
TTS_HOST = os.getenv("TTS_HOST", "0.0.0.0")
TTS_PORT = int(os.getenv("TTS_PORT", "5000"))
TTS_DEBUG = os.getenv("TTS_DEBUG", "False").lower() in TRUE_VALUES
# text: the human format shared with nginx; json: one object per line with request_id and the synthesis fields.
TTS_LOG_FORMAT = os.getenv("TTS_LOG_FORMAT", "text").strip().lower()
TTS_TOKENS = {t.strip() for t in os.getenv("TTS_TOKENS", "").split(",") if t.strip()}
TTS_POOL_SIZE = int(os.getenv("TTS_POOL_SIZE", "1"))
# Synthesis requests allowed to wait for a free pool slot; any more are answered 503 at once.
TTS_QUEUE_SIZE = int(os.getenv("TTS_QUEUE_SIZE", "8"))
# Threads the WSGI bridge keeps beyond the synthesis ones, so health, history,
# voices and models never queue behind a full pool.
LIGHT_THREADS = 8
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
# Hard cap on request body size — Marshmallow validates `text` after parsing,
# so without this Werkzeug would buffer arbitrarily large bodies into memory.
TTS_MAX_BODY_BYTES = int(os.getenv("TTS_MAX_BODY_BYTES", str(2 * 1024 * 1024)))
# Voice samples are uploaded as multipart WAV and need a larger cap than JSON text.
TTS_MAX_SAMPLE_BYTES = int(os.getenv("TTS_MAX_SAMPLE_BYTES", str(16 * 1024 * 1024)))
# Ceiling on the number of voice samples, so an authenticated client cannot fill the disk one upload at a time.
TTS_MAX_SAMPLES = int(os.getenv("TTS_MAX_SAMPLES", "100"))
# Werkzeug enforces a single body cap for every route, so it is the larger of the two.
MAX_CONTENT_LENGTH = max(TTS_MAX_BODY_BYTES, TTS_MAX_SAMPLE_BYTES)
MAX_CONTENT_LENGTH_MB = MAX_CONTENT_LENGTH // (1024 * 1024)
# Generation history: audio files plus JSON sidecars, pruned to TTS_HISTORY_MAX on write.
TTS_HISTORY_DIR = os.getenv("TTS_HISTORY_DIR", "data/history")
TTS_HISTORY_MAX = int(os.getenv("TTS_HISTORY_MAX", "200"))
# TTS_ENGINES is the set to install + preload at startup (comma-separated).
# TTS_ENGINE stays the default for requests that omit `engine`. If TTS_ENGINE
# is unset it falls back to the first preloaded engine; if TTS_ENGINES is unset
# it falls back to the single default engine.
TTS_ENGINES = [e.strip() for e in os.getenv("TTS_ENGINES", "").split(",") if e.strip()]
TTS_ENGINE_DEFAULT = os.getenv("TTS_ENGINE") or (TTS_ENGINES[0] if TTS_ENGINES else "gtts")
if not TTS_ENGINES:
    TTS_ENGINES = [TTS_ENGINE_DEFAULT]
TTS_LANGUAGE_DEFAULT = os.getenv("TTS_LANGUAGE", "en")
# true: a language the engine declares it does not serve is a 400 on file
# generation (/api/tts without stream, /api/history, /v1/audio/speech);
# false keeps the engine's own fallback (English for most engines).
TTS_LANGUAGE_STRICT = os.getenv("TTS_LANGUAGE_STRICT", "False").lower() in TRUE_VALUES
TTS_STREAM_MAX_CHARS = int(os.getenv("TTS_STREAM_MAX_CHARS", "200"))
TIMEZONE = pytz.timezone(os.getenv("TZ", "America/New_York"))
DATETIME_FMT = "%Y-%m-%d %H:%M:%S"
# An X-Request-Id a client sends is kept when it looks like one; anything else is replaced.
REQUEST_ID_RE = re.compile(r"[A-Za-z0-9._-]{1,64}\Z")
# Routes polled by probes and scrapers: their request line is logged at debug level.
QUIET_PATHS = ("/api/health", "/api/metrics", "/metrics")

# Logging
LOG_HANDLER = logging.StreamHandler()
# basicConfig leaves a handler that already has a formatter alone, so the text
# format below only reaches the handler when no JsonFormatter was set on it.
if TTS_LOG_FORMAT == "json":
    LOG_HANDLER.setFormatter(JsonFormatter())
LOGGING = {
    "handlers": [LOG_HANDLER],
    "format": "%(asctime)s.%(msecs)03d [%(levelname)s]: (%(name)s.%(funcName)s) %(message)s",
    "level": logging.DEBUG if TTS_DEBUG else logging.INFO,
    "datefmt": "%Y-%m-%d %H:%M:%S",
}
logging.basicConfig(**LOGGING)  # type: ignore[arg-type]
logger = logging.getLogger(__name__)

# Engine pool — semaphore tokens; the actual model is cached inside engine module
# (see engines/coquitts.py:TTS_CACHE). Pool limits concurrent synthesis calls.
ENGINE_POOL: queue.Queue = queue.Queue()
# Permits to wait for a pool slot: bounds how many server threads a burst of
# /api/tts requests can hold while they wait.
WAIT_QUEUE = threading.Semaphore(TTS_QUEUE_SIZE)


def init_engine_pool(size: int = TTS_POOL_SIZE) -> None:
    """Warm each preloaded engine cache and seed pool with N tokens.

    The pool is a single shared semaphore — it caps total concurrent synthesis
    across all engines, not per engine. Heavy models stay resident in their
    own module caches (e.g. engines/coquitts.py:TTS_CACHE), so a warmed engine
    answers later requests without reloading.

    Args:
        size: Number of pool tokens to seed; anything below 1 disables both the
            warmup and the concurrency cap.
    """
    if size < 1:
        logger.info("TTS_POOL_SIZE=0 → unlimited concurrency, no warmup")
        return

    for engine in TTS_ENGINES:
        if engine in ("gtts", "pyttsx3"):
            # Nothing to load for these, so they count as warm from the start.
            metrics.set_warm(engine, True)
            continue
        logger.info(f"Warming up {engine}...")
        start_time = time.monotonic()
        try:
            text_to_speech_bytes(text=".", engine=engine, language=TTS_LANGUAGE_DEFAULT)
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            metrics.record(engine, elapsed_ms, True)
            metrics.set_warm(engine, True)
            logger.info(f"Warmup OK {engine} ({time.monotonic() - start_time:.2f}s)")
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            metrics.record(engine, elapsed_ms, False, type(exc).__name__)
            metrics.set_warm(engine, False)
            logger.warning(f"Warmup failed for {engine}: {type(exc).__name__}: {exc} — will retry on first request")

    for slot_index in range(size):
        ENGINE_POOL.put(slot_index)
    logger.info(f"Pool ready: {size} slot(s) for engines {TTS_ENGINES}")


class JSONProvider(DefaultJSONProvider):
    """Custom JSON provider — datetime/date as 'YYYY-MM-DD HH:MM:SS'."""

    def default(self, o):
        """Serialize datetime/date values with DATETIME_FMT, delegate the rest."""
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
        MAX_CONTENT_LENGTH=MAX_CONTENT_LENGTH,
    )
)
CORS(
    app,
    resources={r"/api/*": {"origins": CORS_ORIGINS}, r"/v1/*": {"origins": CORS_ORIGINS}},
    expose_headers=["X-Request-Id"],
)


def get_req_id() -> str:
    """Return the correlation id of the current request, or an empty string outside one."""
    return getattr(g, "request_id", "")


def detect_audio_mime(audio_bytes: bytes) -> tuple[str, str]:
    """Return (mimetype, extension) by sniffing audio bytes header."""
    return audio_mime(audio_bytes), audio_format(audio_bytes)


def parse_tts_payload() -> dict:
    """Read a TTS request from the JSON body, form data or query string.

    Returns:
        The deserialized payload as produced by TtsRequestSchema.

    Raises:
        MarshmallowValidationError: If the payload fails schema validation.
    """
    payload = request.get_json(silent=True) if request.is_json else None
    if not payload:
        payload = request.form.to_dict() or request.args.to_dict()

    schema = TtsRequestSchema()
    errors = schema.validate(payload)
    if errors:
        raise MarshmallowValidationError(errors)
    return schema.load(payload)


def acquire_slot() -> int | None:
    """Take one engine-pool token, or None when the pool is unlimited.

    Raises:
        queue.Empty: TTS_QUEUE_SIZE requests are already waiting, or no token
            freed up within 120 s (both answered as 503 by handle_pool_busy).
    """
    if TTS_POOL_SIZE <= 0:
        return None
    if not WAIT_QUEUE.acquire(blocking=False):
        raise queue.Empty()
    metrics.wait_begin()
    try:
        return ENGINE_POOL.get(timeout=120)
    finally:
        metrics.wait_end()
        WAIT_QUEUE.release()


def release_slot(slot: int | None) -> None:
    """Return a token taken by acquire_slot to the pool (no-op for None)."""
    if slot is not None:
        ENGINE_POOL.put(slot)


def resolve_request_language(requested: str | None) -> str:
    """Return the request's language, or TTS_LANGUAGE when it names none, normalized.

    A tag is lowercased and written with '-' ('pt_BR' -> 'pt-br'); a 2-character
    code is only lowercased, as libs.api does before the engine call. The logs,
    the strict-mode message and the history item then show the code the audio
    was made with.
    """
    return normalize_language(requested or TTS_LANGUAGE_DEFAULT)


def validate_selection(engine: str, language: str) -> None:
    """With TTS_LANGUAGE_STRICT, refuse a language the engine does not serve before a pool slot is taken.

    Called only on file generation; streaming keeps the engine fallback. An
    engine that does not declare its languages accepts every code.

    Raises:
        ValidationError: TTS_LANGUAGE_STRICT is on and the engine does not list the language.
    """
    if TTS_LANGUAGE_STRICT:
        validate_engine_language(engine, language)


def synthesize(text: str, engine: str, language: str, voice: str | None = None, label: str = "") -> bytes:
    """Run text_to_speech_bytes and log one Synthesis line with the engine time.

    The request line in after_request carries the whole request time, which
    includes the wait for a pool slot. This line measures only the engine call,
    so an operator can tell a slow engine from a request that waited for a slot.
    The exception, if any, is re-raised unchanged for the error handlers.

    Args:
        text: Text to synthesize.
        engine: Engine name to synthesize with.
        language: Language code passed to the engine: two letters, or a tag
            such as 'zh-cn' outside streaming.
        voice: Engine-specific voice id, or None for the engine default.
        label: Optional qualifier after "Synthesis", such as "chunk 2/5".

    Returns:
        The audio bytes produced by the engine.
    """
    start_time = time.monotonic()
    size_part = ""
    audio_size: int | None = None
    error_name: str | None = None
    status = "failed"
    # A request whose text, language or engine name failed validation never
    # reached an engine, so it must not become a registry key: the engine name
    # is request input, and one registry entry per unknown name would grow
    # /metrics without bound.
    reached_engine = True
    try:
        audio = text_to_speech_bytes(text=text, engine=engine, language=language, voice=voice)
        audio_size = len(audio)
        size_part = f"bytes={audio_size} "
        status = "ok"
        return audio
    except Exception as exc:
        error_name = type(exc).__name__
        status = f"failed {error_name}"
        reached_engine = not isinstance(exc, ValidationError)
        raise
    finally:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        name = f"Synthesis {label}" if label else "Synthesis"
        logger.info(
            f"[{get_req_id()}] {name}: engine={engine} language={language} "
            f"voice={voice} chars={len(text)} {size_part}ms={elapsed_ms} {status}",
            extra={
                "request_id": get_req_id(),
                "event": "synthesis",
                "engine": engine,
                "language": language,
                "voice": voice,
                "chars": len(text),
                "bytes": audio_size,
                "ms": elapsed_ms,
                "ok": status == "ok",
                "error": error_name,
            },
        )
        if reached_engine:
            metrics.record(engine, elapsed_ms, status == "ok", error_name)


def token_required(view):
    """Require Authorization: Bearer <token> when TTS_TOKENS is non-empty."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        """Reject the request with 401 unless it carries a known bearer token."""
        if not TTS_TOKENS:
            return view(*args, **kwargs)

        header = request.headers.get("Authorization", "")
        scheme, unused_separator, token = header.partition(" ")
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
    """Attach a correlation id (the client's X-Request-Id when well-formed) and a start timestamp."""
    incoming = request.headers.get("X-Request-Id", "")
    g.request_id = incoming if REQUEST_ID_RE.match(incoming) else uuid.uuid4().hex[:12]
    g.start_time = time.monotonic()


@app.after_request
def after_request(resp):
    """Log the request line with its status and duration, echo the request id, then return the response."""
    log_fn = logger.debug if request.path in QUIET_PATHS else logger.info
    elapsed = time.monotonic() - getattr(g, "start_time", time.monotonic())
    log_fn(
        f"[{get_req_id()}] {request.method} {request.path}: {resp.status} ({elapsed:.3f}s)",
        extra={
            "request_id": get_req_id(),
            "method": request.method,
            "path": request.path,
            "status": resp.status_code,
            "ms": int(elapsed * 1000),
        },
    )
    resp.headers["X-Request-Id"] = get_req_id()
    return resp


@app.route("/api/health", methods=["GET"])
def health():
    """Report liveness plus the configured engines and free pool slots."""
    return (
        jsonify(
            {
                "status": "ok",
                # Whether requests need a bearer token: the web UI reads this
                # before deciding to show its sign-in screen.
                "auth": bool(TTS_TOKENS),
                "engine": TTS_ENGINE_DEFAULT,
                "engines": TTS_ENGINES,
                "pool_size": TTS_POOL_SIZE,
                "queue_size": TTS_QUEUE_SIZE,
                "available": ENGINE_POOL.qsize(),
            }
        ),
        200,
    )


def metrics_snapshot() -> dict:
    """Return the registry snapshot with this server's pool numbers and the installed engines."""
    return metrics.snapshot(
        pool_size=TTS_POOL_SIZE,
        pool_available=ENGINE_POOL.qsize(),
        queue_size=TTS_QUEUE_SIZE,
        available=get_available_engines().keys(),
    )


@app.route("/api/metrics", methods=["GET"])
@token_required
def metrics_json():
    """Uptime, pool occupancy and per-engine call counts, failures and latency percentiles as JSON."""
    return jsonify(metrics_snapshot()), 200


@app.route("/metrics", methods=["GET"])
@token_required
def metrics_prometheus():
    """The same numbers in the Prometheus exposition format, for a scraper sending the bearer token."""
    return Response(metrics.prometheus_text(metrics_snapshot()), content_type=metrics.PROMETHEUS_CONTENT_TYPE)


@app.route("/api/engines", methods=["GET"])
@token_required
def engines_list():
    """List supported engines alongside the ones installed and preloaded here."""
    available = sorted(get_available_engines().keys())
    return (
        jsonify(
            {
                "supported": get_supported_engines(),
                "available": available,
                "preload": TTS_ENGINES,
                "default": TTS_ENGINE_DEFAULT,
                "language": TTS_LANGUAGE_DEFAULT,
            }
        ),
        200,
    )


@app.route("/api/models", methods=["GET"])
@token_required
def models_list():
    """List every engine with its install status and on-disk models, one row per model."""
    rows = collect_engine_rows()
    return jsonify({"models": [{"engine": engine, "status": status, "model": model} for engine, status, model in rows]}), 200


@app.route("/api/voices", methods=["GET"])
@token_required
def voices_list():
    """List selectable voices for an engine + language (e.g. Silero ru speakers)."""
    engine = request.args.get("engine") or TTS_ENGINE_DEFAULT
    language = request.args.get("language") or TTS_LANGUAGE_DEFAULT
    info = get_engine_voices(engine, language)
    # Only the sample-cloning engine has files behind its voices; the web UI
    # shows their size, rate and length in the samples table.
    samples = describe_sample_files() if engine == "coquitts" else []
    return (
        jsonify(
            {
                "engine": engine,
                "language": language,
                "voices": info.get("voices", []),
                "default": info.get("default"),
                # Whether the engine blends voices ("af_bella(2)+af_sky(1)"); the
                # Studio offers free text instead of a select when it does.
                "mix": bool(info.get("mix")),
                "samples": samples,
            }
        ),
        200,
    )


def read_wav_info(audio_bytes: bytes) -> tuple[int, int, float]:
    """Return (rate, channels, seconds) of a PCM WAV.

    Raises:
        ValidationError: The bytes are not a PCM WAV that the stdlib `wave` module can open.
    """
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
            rate = wav_file.getframerate()
            channels = wav_file.getnchannels()
            seconds = round(wav_file.getnframes() / rate, 2) if rate > 0 else 0.0
    except (wave.Error, EOFError) as exc:
        raise ValidationError(f"Upload is not a PCM WAV: {type(exc).__name__}: {exc}") from exc
    return rate, channels, seconds


@app.route("/api/voices", methods=["POST"])
@token_required
def voices_upload():
    """Store an uploaded PCM WAV as a new coquitts voice sample (multipart: file, name, engine)."""
    form = VoiceUploadSchema().load(request.form.to_dict())
    upload = request.files.get("file")
    if upload is None:
        raise ValidationError("Missing multipart field 'file'")
    audio_bytes = upload.read()
    # MAX_CONTENT_LENGTH is the larger of the two body caps, so the sample cap is checked here.
    if len(audio_bytes) > TTS_MAX_SAMPLE_BYTES:
        abort(413)
    rate, channels, seconds = read_wav_info(audio_bytes)

    target = sample_path_for_voice(form["name"])
    if os.path.exists(target):
        logger.warning(f"[{get_req_id()}] Voice '{form['name']}' already exists: {target}")
        raise ValidationError(f"Voice '{form['name']}' already exists")
    if len(list_sample_files()) >= TTS_MAX_SAMPLES:
        raise ValidationError(f"Sample limit reached ({TTS_MAX_SAMPLES}); delete one first")
    os.makedirs(get_samples_dir(), exist_ok=True)
    # Written through a .tmp neighbour so a half-written sample never shows up in list_voices().
    tmp_path = f"{target}.tmp"
    with open(tmp_path, "wb") as handle:
        handle.write(audio_bytes)
    os.replace(tmp_path, target)

    logger.info(f"[{get_req_id()}] Voice '{form['name']}' saved: {len(audio_bytes)} bytes {rate} Hz {channels} ch {seconds}s")
    return (
        jsonify(
            {
                "engine": form["engine"],
                "voice": form["name"],
                "bytes": len(audio_bytes),
                "rate": rate,
                "channels": channels,
                "seconds": seconds,
            }
        ),
        201,
    )


@app.route("/api/voices/<name>", methods=["DELETE"])
@token_required
def voices_delete(name: str):
    """Remove a coquitts voice sample, the COQUITTS_SAMPLE default included.

    Deleting the default is allowed on purpose: a request without `voice` then
    fails with the engine's voice_sample_missing message, which names the file
    to record, and the web UI warns before the click.
    """
    form = VoiceUploadSchema().load({"name": name, "engine": request.args.get("engine")})
    target = sample_path_for_voice(form["name"])
    if not os.path.isfile(target):
        abort(404)
    os.remove(target)
    logger.info(f"[{get_req_id()}] Voice '{form['name']}' deleted: {target}")
    return jsonify({"result": True}), 200


@app.route("/api/voices/<name>/audio", methods=["GET"])
@token_required
def voices_audio(name: str):
    """Serve a coquitts voice sample WAV inline, or as a download when ?download is truthy."""
    form = VoiceUploadSchema().load({"name": name, "engine": request.args.get("engine")})
    target = sample_path_for_voice(form["name"])
    if not os.path.isfile(target):
        abort(404)
    download = request.args.get("download", "").lower() in TRUE_VALUES
    return send_file(
        target,
        mimetype="audio/wav",
        as_attachment=download,
        download_name=f"{form['name']}.wav",
    )


def stream_tts(text: str, engine: str, language: str, voice: str | None = None):
    """Synthesize per chunk and stream audio as it is ready (chunked transfer).

    WAV engines emit one streaming WAV (single header + concatenated PCM); MP3
    (gtts) concatenates per-chunk bytes. One pool slot is held for the whole
    stream and released when the generator is exhausted or closed.

    Args:
        text: Full utterance; split into chunks of TTS_STREAM_MAX_CHARS.
        engine: Engine name to synthesize with.
        language: Language code passed to the engine: a two-letter code from the
            request (the schema refuses a tag there), or TTS_LANGUAGE as set,
            which may be a tag such as 'zh-cn'.
        voice: Engine-specific voice id, or None for the engine default.

    Returns:
        A streaming Response (a busy pool raises queue.Empty, answered as 503).
    """
    chunks = chunk_text(text, max_len=TTS_STREAM_MAX_CHARS) or [text]
    slot = acquire_slot()

    # Synthesize the first chunk up front so the audio format (and any engine
    # error) is known before the streaming response headers are committed.
    try:
        first = synthesize(text=chunks[0], engine=engine, language=language, voice=voice, label=f"chunk 1/{len(chunks)}")
    except Exception:
        release_slot(slot)
        raise

    mimetype, unused_ext = detect_audio_mime(first)
    is_wav = mimetype == "audio/wav"

    def generate():
        """Yield the first chunk, then each remaining chunk as it is synthesized."""
        try:
            if is_wav:
                rate, channels, width = wav_params(first)
                yield streaming_wav_header(rate, channels, width)
                yield wav_data(first)
            else:
                yield first
            for index, chunk in enumerate(chunks[1:], start=2):
                blob = synthesize(
                    text=chunk, engine=engine, language=language, voice=voice, label=f"chunk {index}/{len(chunks)}"
                )
                yield wav_data(blob) if is_wav else blob
        except Exception as exc:
            logger.error(f"[{get_req_id()}] stream aborted: {type(exc).__name__}: {exc}\n{traceback.format_exc()}")
        finally:
            release_slot(slot)

    return Response(stream_with_context(generate()), mimetype=mimetype)


@app.route("/api/tts", methods=["GET", "POST"])
@token_required
def tts_generate():
    """Synthesize the requested text and return it as a stream or a file download."""
    data = parse_tts_payload()
    text = data["text"]
    engine = data.get("engine") or TTS_ENGINE_DEFAULT
    language = resolve_request_language(data.get("language"))
    voice = data.get("voice")

    logger.info(
        f"[{get_req_id()}] TTS request: engine={engine} language={language} "
        f"voice={voice} chars={len(text)} stream={data['stream']}"
    )

    if data["stream"]:
        return stream_tts(text, engine, language, voice)

    validate_selection(engine, language)
    slot = acquire_slot()
    try:
        audio_bytes = synthesize(text=text, engine=engine, language=language, voice=voice)
    finally:
        release_slot(slot)

    mimetype, ext = detect_audio_mime(audio_bytes)
    timestamp = datetime.now(TIMEZONE).strftime("%Y%m%d_%H%M%S")
    return send_file(
        io.BytesIO(audio_bytes),
        mimetype=mimetype,
        as_attachment=True,
        download_name=f"tts_{timestamp}.{ext}",
    )


@app.route("/api/history", methods=["POST"])
@token_required
def history_create():
    """Synthesize the text in one piece, store it in the history and return the item."""
    data = HistoryCreateSchema().load(request.get_json(silent=True) or {})
    text = data["text"]
    engine = data.get("engine") or TTS_ENGINE_DEFAULT
    language = resolve_request_language(data.get("language"))
    voice = data.get("voice")
    logger.info(f"[{get_req_id()}] History request: engine={engine} language={language} voice={voice} chars={len(text)}")

    validate_selection(engine, language)
    slot = acquire_slot()
    start_time = time.monotonic()
    try:
        audio_bytes = synthesize(text=text, engine=engine, language=language, voice=voice)
    finally:
        release_slot(slot)
    elapsed = time.monotonic() - start_time

    meta = {"engine": engine, "language": language, "voice": voice, "text": text, "elapsed": elapsed}
    item = history.save_item(TTS_HISTORY_DIR, audio_bytes, meta, datetime.now(TIMEZONE), TTS_HISTORY_MAX)
    return jsonify(item), 201


@app.route("/api/history", methods=["GET"])
@token_required
def history_list():
    """Page through the history newest first, with `text` cut to a preview."""
    query = HistoryListSchema().load(request.args.to_dict())
    total, items = history.list_items(TTS_HISTORY_DIR, query["limit"], query["offset"])
    return jsonify({"total": total, "items": items}), 200


@app.route("/api/history/<item_id>", methods=["GET"])
@token_required
def history_get(item_id: str):
    """Return one history item with its full text, or 404."""
    item = history.get_item(TTS_HISTORY_DIR, item_id)
    if item is None:
        abort(404)
    return jsonify(item), 200


@app.route("/api/history/<item_id>/audio", methods=["GET"])
@token_required
def history_audio(item_id: str):
    """Serve the stored audio inline, or as a download when ?download is truthy."""
    path = history.audio_path(TTS_HISTORY_DIR, item_id)
    if path is None:
        abort(404)
    fmt = path.rsplit(".", 1)[-1]
    mimetype = {"wav": "audio/wav", "mp3": "audio/mpeg"}.get(fmt, "application/octet-stream")
    download = request.args.get("download", "").lower() in TRUE_VALUES
    # send_file resolves a relative path against the Flask root, not the cwd.
    return send_file(
        os.path.abspath(path),
        mimetype=mimetype,
        as_attachment=download,
        download_name=f"tts_{item_id}.{fmt}",
    )


@app.route("/api/history/<item_id>", methods=["DELETE"])
@token_required
def history_delete(item_id: str):
    """Remove one history item (audio plus sidecar), or 404."""
    if not history.delete_item(TTS_HISTORY_DIR, item_id):
        abort(404)
    return jsonify({"result": True}), 200


def openai_errors(view):
    """Answer the failures of a /v1 route in the OpenAI error shape instead of the /api one."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        """Map validation errors to 400 and a busy pool to 503, both as {"error": {...}}."""
        try:
            return view(*args, **kwargs)
        except MarshmallowValidationError as exc:
            logger.warning(f"[{get_req_id()}] Validation error: {exc.messages}")
            return jsonify(validation_error_body(exc.messages)), 400
        except ValidationError as exc:
            logger.warning(f"[{get_req_id()}] {type(exc).__name__}: {exc}")
            return jsonify(error_body(str(exc))), 400
        except OpenAIRequestError as exc:
            logger.warning(f"[{get_req_id()}] {type(exc).__name__}: {exc.message}")
            return jsonify(error_body(exc.message, exc.param, exc.error_type)), exc.status
        except queue.Empty:
            logger.warning(f"[{get_req_id()}] All engine slots busy")
            return jsonify(error_body("All engine slots busy", error_type="server_error")), 503

    return wrapper


@app.route("/v1/audio/speech", methods=["POST"])
@token_required
@openai_errors
def openai_speech():
    """Synthesize `input` the way OpenAI's POST /v1/audio/speech does and return the audio body."""
    data = SpeechRequestSchema().load(request.get_json(silent=True) or {})
    engine = map_model_name(data["model"], TTS_ENGINE_DEFAULT)
    if engine not in get_available_engines():
        raise OpenAIRequestError(f"Model '{data['model']}' is not an installed engine", param="model")
    text = data["input"]
    voice = map_voice_name(data["voice"])
    language = resolve_request_language(data["language"])
    response_format = data["response_format"]
    speed = data["speed"]
    logger.info(
        f"[{get_req_id()}] OpenAI speech: engine={engine} language={language} "
        f"voice={voice} chars={len(text)} format={response_format} speed={speed}"
    )

    validate_selection(engine, language)
    slot = acquire_slot()
    try:
        audio_bytes = synthesize(text=text, engine=engine, language=language, voice=voice)
    finally:
        release_slot(slot)

    unused_mime, native_format = detect_audio_mime(audio_bytes)
    body, mimetype = prepare_audio(audio_bytes, native_format, response_format, speed)
    return Response(body, mimetype=mimetype)


@app.route("/v1/models", methods=["GET"])
@token_required
def openai_models():
    """List the installed engines as OpenAI models, plus `tts-1` for clients that default to it."""
    names = sorted(get_available_engines().keys()) + ["tts-1"]
    data = [{"id": name, "object": "model", "created": 0, "owned_by": "text-to-speech"} for name in names]
    return jsonify({"object": "list", "data": data}), 200


@app.route("/v1/audio/voices", methods=["GET"])
@token_required
def openai_voices():
    """List the voices of the engine behind ?model= (default engine when omitted), as {"voices": [...]}."""
    engine = map_model_name(request.args.get("model"), TTS_ENGINE_DEFAULT)
    language = request.args.get("language") or TTS_LANGUAGE_DEFAULT
    info = get_engine_voices(engine, language)
    return jsonify({"voices": info.get("voices", [])}), 200


@app.errorhandler(queue.Empty)
def handle_pool_busy(error):
    """Answer 503 when acquire_slot found the wait queue full or waited out its timeout."""
    logger.warning(f"[{get_req_id()}] All engine slots busy")
    return jsonify({"error": "All engine slots busy"}), 503


@app.errorhandler(MarshmallowValidationError)
def handle_marshmallow_validation_error(error):
    """Answer 400 when the request payload fails schema validation, with the field messages as `message`."""
    logger.warning(f"[{get_req_id()}] Validation error: {error.messages}")
    body = {"error": "Bad Request", "message": format_validation_messages(error.messages), "request_id": get_req_id()}
    return jsonify(body), 400


@app.errorhandler(ValidationError)
def handle_tts_validation_error(error):
    """Answer 400 when the TTS layer rejects the text, language, voice or upload.

    The reason travels as `message`: the web UI shows it beside the control the
    operator just used (a duplicate voice name, a file that is not a WAV), where
    a bare "Bad Request" would read as a button that did nothing. These messages
    are written without filesystem paths, unlike the ones logged.
    """
    logger.warning(f"[{get_req_id()}] {type(error).__name__}: {str(error)}")
    return jsonify({"error": "Bad Request", "message": str(error), "request_id": get_req_id()}), 400


@app.errorhandler(EngineNotAvailableError)
def handle_engine_not_available(error):
    """Answer 503 when the requested engine has no usable installation."""
    logger.warning(f"[{get_req_id()}] {type(error).__name__}: {str(error)}")
    return jsonify({"error": "Service Unavailable", "request_id": get_req_id()}), 503


@app.errorhandler(CustomError)
def handle_custom_error(error):
    """Return the engine-supplied error payload verbatim with its own status."""
    # Engine produced a structured payload — return it verbatim, log a one-liner.
    body = dict(error.payload)
    body.setdefault("request_id", get_req_id())
    summary = (body.get("message") or body.get("error") or "").splitlines()[0][:200]
    logger.warning(f"[{get_req_id()}] CustomError ({body.get('error')}): {summary}")
    return jsonify(body), error.status


@app.errorhandler(TTSException)
def handle_tts_exception(error):
    """Answer 500 for any synthesis failure not covered by a narrower handler."""
    logger.error(f"[{get_req_id()}] {type(error).__name__}: {str(error)}\n{traceback.format_exc()}")
    return jsonify({"error": "TTS failed", "request_id": get_req_id()}), 500


@app.errorhandler(413)
def payload_too_large(error):
    """Answer 413 when the body exceeds MAX_CONTENT_LENGTH, echoing the limit."""
    logger.warning(f"[{get_req_id()}] Payload too large (limit={MAX_CONTENT_LENGTH_MB}MB)")
    return (
        jsonify(
            {
                "error": "Payload Too Large",
                "limit_mb": MAX_CONTENT_LENGTH_MB,
                "request_id": get_req_id(),
            }
        ),
        413,
    )


@app.errorhandler(Exception)
def handle_exception(exc):
    """Map any unhandled exception to its HTTP status, or to 500 with a traceback."""
    if isinstance(exc, werkzeug.exceptions.HTTPException):
        logger.warning(f"[{get_req_id()}] HTTP {exc.code} {exc.name}")
        return jsonify({"error": exc.name, "request_id": get_req_id()}), exc.code
    logger.error(f"[{get_req_id()}] {type(exc).__name__}: {str(exc)}\n{traceback.format_exc()}")
    return jsonify({"error": "Internal Server Error", "request_id": get_req_id()}), 500


def close_wsgi_responses(wsgi_app):
    """Wrap a WSGI app so every response iterable gets its close() call.

    uvicorn's WSGI bridge iterates the response and drops it without calling
    close(), which is what releases the file behind a send_file response. CPython
    closes it on the next garbage collection anyway, but the WSGI contract says
    close() is called, and the streaming generator's finally block, which
    returns its pool slot, runs when its response is closed.
    """

    def wrapper(environ, start_response):
        """Yield the wrapped app's response and close it afterwards, whatever happened."""
        response = wsgi_app(environ, start_response)
        try:
            yield from response
        finally:
            close = getattr(response, "close", None)
            if close is not None:
                close()

    return wrapper


def main() -> int:
    """Warm the engine pool and serve the app via Flask (debug) or uvicorn.

    Returns:
        The process exit code (0 once the server loop ends).
    """
    logger.info(
        f"Starting TTS server on {TTS_HOST}:{TTS_PORT} "
        f"debug={TTS_DEBUG} engines={TTS_ENGINES} default={TTS_ENGINE_DEFAULT} pool={TTS_POOL_SIZE} "
        f"queue={TTS_QUEUE_SIZE} "
        f"auth={'on' if TTS_TOKENS else 'off'}"
    )
    init_engine_pool()
    if TTS_DEBUG:
        app.run(host=TTS_HOST, port=TTS_PORT, debug=True)
    else:
        # Imported lazily: uvicorn is only needed for production serving, so a
        # debug-only install does not have to provide it.
        import uvicorn

        # uvicorn's own WSGI bridge, not asgiref's WsgiToAsgi. asgiref ran every
        # WSGI call on one shared thread, so a synthesis blocked /api/health and
        # TTS_POOL_SIZE above 1 never meant anything, and its deadlock guard is a
        # contextvar that a keep-alive connection can carry into the next
        # request: that request then died with "Single thread executor already
        # being used, would deadlock" before Flask saw it, answered as a
        # plain-text 500. uvicorn's bridge runs requests on a thread pool and
        # has no such guard. It is built here rather than through
        # interface="wsgi" because that spelling fixes the pool at 10 threads:
        # the synthesis requests allowed in (running plus waiting, see
        # acquire_slot) get their own threads and LIGHT_THREADS stay free for
        # the rest, so /api/health answers during a burst. uvicorn warns that
        # this bridge is deprecated in favour of a2wsgi; the warning is silenced
        # rather than adding a dependency to the image for the same behaviour.
        warnings.filterwarnings("ignore", message="Uvicorn's native WSGI implementation is deprecated")
        from uvicorn.middleware.wsgi import WSGIMiddleware

        threads = max(TTS_POOL_SIZE, 1) + TTS_QUEUE_SIZE + LIGHT_THREADS
        uvicorn.run(
            WSGIMiddleware(close_wsgi_responses(app), workers=threads),
            host=TTS_HOST,
            port=TTS_PORT,
            log_config=None,  # always None: keep our LOGGING, never run uvicorn's own dictConfig
            access_log=False,  # after_request logs every request line; only QUIET_PATHS are demoted to debug
            # send_file responses already carry a Date header from Werkzeug; uvicorn's
            # own copy made every audio fetch a duplicate-header warning in nginx.
            date_header=False,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
