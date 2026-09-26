#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The model id rule shared by the request schemas and engine model discovery."""

import re

# What a model id may look like before it is looked up among the engine's
# models: a Coqui name (tts_models/de/thorsten/vits), a Piper voice stem
# (en_GB-alan-low), a Kokoro file name (kokoro-v1.0.int8.onnx) or a Silero id
# (v3_1_ru). An empty string is allowed and means the engine default.
MODEL_ID_REGEX = r"^(?:[A-Za-z0-9][A-Za-z0-9._/+-]{0,127})?\Z"


def is_model_id(value: object) -> bool:
    """Return True for a non-empty string a request may send as `model` (see MODEL_ID_REGEX)."""
    if not isinstance(value, str) or not value:
        return False
    return re.match(MODEL_ID_REGEX, value) is not None


def main():
    """Module entrypoint placeholder, this file is import-only."""
    pass


if __name__ == "__main__":
    main()
