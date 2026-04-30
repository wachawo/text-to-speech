#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Marshmallow validation schemas for TTS API."""

from marshmallow import Schema, fields, validate


class TtsRequestSchema(Schema):
    """Request body / query string for /api/tts."""

    text     = fields.Str(required=True,        validate=validate.Length(min=1, max=5000))
    engine   = fields.Str(load_default=None)
    language = fields.Str(load_default=None,    validate=validate.Length(equal=2))
