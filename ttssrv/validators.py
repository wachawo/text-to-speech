#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Marshmallow validation schemas for TTS API."""

from marshmallow import Schema, fields, validate


class TtsRequestSchema(Schema):
    """Request body / query string for /api/tts."""

    # Long text is chunked downstream by libs.cli.chunk_text; the upper bound
    # here only guards against pathological inputs (memory / multi-hour stalls).
    text = fields.Str(required=True, validate=validate.Length(min=1, max=1_000_000))
    engine = fields.Str(load_default=None)
    language = fields.Str(load_default=None, validate=validate.Length(equal=2))
    # Engine-specific voice/speaker id (e.g. Silero 'baya'). Validated against the
    # engine's available voices downstream; None keeps the engine default.
    voice = fields.Str(load_default=None, validate=validate.Length(max=64))
    # When true, stream audio chunk-by-chunk (chunked transfer) for low latency.
    stream = fields.Bool(load_default=False)


class HistoryCreateSchema(TtsRequestSchema):
    """JSON body for POST /api/history: a TTS request without the streaming switch."""

    class Meta:
        """Drop `stream`: history items are always synthesized in one piece."""

        exclude = ("stream",)


class HistoryListSchema(Schema):
    """Query string for GET /api/history."""

    limit = fields.Int(load_default=50, validate=validate.Range(min=1, max=200))
    offset = fields.Int(load_default=0, validate=validate.Range(min=0))


class VoiceUploadSchema(Schema):
    """Form fields of POST /api/voices and DELETE /api/voices/<name> (the WAV travels as `file`)."""

    # A bare file stem, the same rule as libs.sample_resolver.VOICE_NAME_REGEX:
    # no dots or separators, so the name can never leave the samples directory.
    name = fields.Str(required=True, validate=validate.Regexp(r"^[A-Za-z0-9_-]{1,48}\Z"))
    # Only coquitts clones voices from samples; the other engines have nothing to upload to.
    engine = fields.Str(required=True, validate=validate.OneOf(["coquitts"]))
