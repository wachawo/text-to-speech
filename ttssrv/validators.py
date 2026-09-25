#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Marshmallow validation schemas for TTS API."""

from marshmallow import EXCLUDE, Schema, ValidationError, fields, validate, validates_schema

# Local imports
from libs.languages import LANGUAGE_CODE_ERROR, is_language_code
from ttssrv.openai_compat import RESPONSE_FORMATS

# Upper bound of the `message` built from schema errors, so a payload with many
# bad fields cannot produce an unbounded error body.
MAX_VALIDATION_MESSAGE_LENGTH = 1000

# What a model id may look like before it is looked up among the engine's
# models: a Coqui name (tts_models/de/thorsten/vits), a Piper voice stem
# (en_GB-alan-low), a Kokoro file name (kokoro-v1.0.int8.onnx) or a Silero id
# (v3_1_ru). An empty string is allowed and means the engine default.
MODEL_ID_REGEX = r"^(?:[A-Za-z0-9][A-Za-z0-9._/+-]{0,127})?\Z"


def validate_language_field(value: str) -> None:
    """Reject a language that is neither 2 characters nor a tag such as 'zh-cn', 'pt_BR' or 'es-419'."""
    if not is_language_code(value):
        raise ValidationError(LANGUAGE_CODE_ERROR)


def flatten_validation_messages(messages: object) -> str:
    """Join the messages under one field (a string, a list or a nested dict) into one line."""
    if isinstance(messages, dict):
        return "; ".join(f"{key}: {flatten_validation_messages(value)}" for key, value in messages.items())
    if isinstance(messages, list | tuple):
        return " ".join(flatten_validation_messages(item) for item in messages)
    return str(messages)


def format_validation_messages(messages: dict | list) -> str:
    """Render Marshmallow's `messages` as "field: msg msg; field2: msg", cut to MAX_VALIDATION_MESSAGE_LENGTH."""
    text = flatten_validation_messages(messages)
    if len(text) > MAX_VALIDATION_MESSAGE_LENGTH:
        return text[: MAX_VALIDATION_MESSAGE_LENGTH - 3] + "..."
    return text


class TtsRequestSchema(Schema):
    """Request body / query string for /api/tts."""

    # Long text is chunked downstream by libs.cli.chunk_text; the upper bound
    # here only guards against pathological inputs (memory / multi-hour stalls).
    text = fields.Str(required=True, validate=validate.Length(min=1, max=1_000_000))
    engine = fields.Str(load_default=None)
    # A 2-character code, or a tag such as 'zh-cn' / 'pt_BR'.
    language = fields.Str(load_default=None, validate=validate_language_field)
    # Engine-specific voice/speaker id (e.g. Silero 'baya'). Validated against the
    # engine's available voices downstream; None keeps the engine default.
    # 128, not 64: a four-voice kokorotts mix such as
    # "af_nicole(0.35)+af_jessica(0.25)+am_michael(0.25)+bf_isabella(0.15)" runs past 64.
    voice = fields.Str(load_default=None, validate=validate.Length(max=128))
    # When true, stream audio chunk-by-chunk (chunked transfer) for low latency.
    stream = fields.Bool(load_default=False)
    # A model id from GET /api/engines/<engine>; null or "" keeps the engine
    # default. Checked against the engine's models before synthesis.
    model = fields.Str(load_default=None, validate=validate.Regexp(MODEL_ID_REGEX))

    @validates_schema
    def reject_model_with_stream(self, data: dict, **kwargs) -> None:
        """Refuse `model` with stream=true: streaming keeps the engine default model."""
        if data.get("model") and data.get("stream"):
            raise ValidationError("model is supported only for file generation (stream=false)", field_name="model")


class HistoryCreateSchema(TtsRequestSchema):
    """JSON body for POST /api/history: a TTS request without the streaming switch."""

    class Meta:
        """Drop `stream`: history items are always synthesized in one piece."""

        exclude = ("stream",)


class HistoryListSchema(Schema):
    """Query string for GET /api/history."""

    limit = fields.Int(load_default=50, validate=validate.Range(min=1, max=200))
    offset = fields.Int(load_default=0, validate=validate.Range(min=0))


class VoicesListSchema(Schema):
    """Query string for GET /api/voices: only `model` is checked, `engine` and `language` are read as before."""

    class Meta:
        """Leave `engine`, `language` and any other argument to the route."""

        unknown = EXCLUDE

    # The same rule as on /api/tts, so an unknown id echoed in the 400 message
    # and the log is short and has no control characters.
    model = fields.Str(load_default=None, validate=validate.Regexp(MODEL_ID_REGEX))


class VoiceUploadSchema(Schema):
    """Form fields of POST /api/voices and DELETE /api/voices/<name> (the WAV travels as `file`)."""

    # A bare file stem, the same rule as libs.sample_resolver.VOICE_NAME_REGEX:
    # no dots or separators, so the name can never leave the samples directory.
    name = fields.Str(required=True, validate=validate.Regexp(r"^[A-Za-z0-9_-]{1,48}\Z"))
    # Only coquitts clones voices from samples; the other engines have nothing to upload to.
    engine = fields.Str(required=True, validate=validate.OneOf(["coquitts"]))


class SpeechRequestSchema(Schema):
    """JSON body for POST /v1/audio/speech, the OpenAI audio API shape plus a `language` extension."""

    class Meta:
        """Ignore the fields OpenAI clients send that have no meaning here (instructions, stream_format, ...)."""

        unknown = EXCLUDE

    # An engine name, or an OpenAI model name that stands for the default engine.
    model = fields.Str(load_default=None, validate=validate.Length(min=1, max=64))
    # OpenAI's own limit; the engines accept up to 5000 characters in one call.
    input = fields.Str(required=True, validate=validate.Length(min=1, max=4096))
    # An OpenAI voice name means the engine default; anything else is the engine voice id
    # or a kokorotts mix, hence the same 128 as TtsRequestSchema.
    voice = fields.Str(load_default=None, validate=validate.Length(max=128))
    response_format = fields.Str(load_default="mp3", validate=validate.OneOf(sorted(RESPONSE_FORMATS)))
    speed = fields.Float(load_default=1.0, validate=validate.Range(min=0.25, max=4.0))
    language = fields.Str(load_default=None, validate=validate_language_field)
