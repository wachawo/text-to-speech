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
