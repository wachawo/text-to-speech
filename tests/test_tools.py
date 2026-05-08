#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for libs.tools — pure validation + functional helpers.

Each test asserts ONE behavioural invariant; combined they pin down the
full contract of validate_*, get_default_config, compose, with_engine,
with_language, generate_timestamp_filename, ensure_audio_directory.
"""

import re

import pytest

from libs.exceptions import EngineNotAvailableError, ValidationError
from libs.tools import (
    compose,
    ensure_audio_directory,
    generate_timestamp_filename,
    get_default_config,
    validate_engine,
    validate_language,
    validate_text,
    with_engine,
    with_language,
)

# get_default_config — must return a fresh dict each time so callers can mutate freely


def test_get_default_config_keys():
    cfg = get_default_config()
    assert set(cfg) == {"engine", "language", "rate", "volume", "slow"}


def test_get_default_config_returns_fresh_dict():
    """Two calls must return independent dicts — no shared mutable state."""
    a = get_default_config()
    a["engine"] = "mutated"
    b = get_default_config()
    assert b["engine"] != "mutated"


# validate_text


@pytest.mark.parametrize("bad", [None, 123, b"bytes", [], {}])
def test_validate_text_rejects_non_string(bad):
    with pytest.raises(ValidationError, match="must be a string"):
        validate_text(bad)


@pytest.mark.parametrize("blank", ["", "   ", "\t\n  "])
def test_validate_text_rejects_blank(blank):
    with pytest.raises(ValidationError, match="cannot be empty"):
        validate_text(blank)


def test_validate_text_strips_surrounding_whitespace():
    assert validate_text("   hello   ") == "hello"


def test_validate_text_accepts_long_text_under_limit():
    """Up to 1M chars is the chunker's job, not the validator's."""
    text = "x" * 999_999
    assert len(validate_text(text)) == 999_999


def test_validate_text_rejects_pathological_length():
    with pytest.raises(ValidationError, match="too long"):
        validate_text("x" * 1_000_001)


# validate_language


@pytest.mark.parametrize("ok,expected", [("en", "en"), ("EN", "en"), ("Ru", "ru")])
def test_validate_language_lowercases_two_char_code(ok, expected):
    assert validate_language(ok) == expected


@pytest.mark.parametrize("bad", ["e", "eng", "", "english", 42, None])
def test_validate_language_rejects_wrong_shape(bad):
    with pytest.raises(ValidationError, match="2-character"):
        validate_language(bad)


# validate_engine — exercises real engines/__init__ logic against tests/stubs/gtts


def test_validate_engine_accepts_gtts():
    """gtts.py exists in engines/ AND requests is importable in dev venv."""
    assert validate_engine("gtts") == "gtts"


def test_validate_engine_rejects_unknown_module():
    with pytest.raises(ValidationError, match="not found"):
        validate_engine("nonexistent_engine_xyz")


@pytest.mark.parametrize("bad", ["", None, 0])
def test_validate_engine_rejects_falsy_or_non_string(bad):
    with pytest.raises(ValidationError, match="non-empty string"):
        validate_engine(bad)


def test_validate_engine_distinguishes_missing_deps_from_missing_file(monkeypatch):
    """When the engine FILE exists but is_available() is False, the error
    must clearly point at deps, not at the module being missing."""
    import libs.tools as tools_mod

    monkeypatch.setattr(tools_mod, "is_engine_available", lambda name: False)
    # silerotts.py exists (heavy deps absent in CI/dev venv).
    with pytest.raises(EngineNotAvailableError, match="dependencies not installed"):
        validate_engine("silerotts")


# compose — right-to-left function composition


def test_compose_two_functions_applies_right_to_left():
    def add_one(x):
        return x + 1

    def times_two(x):
        return x * 2

    pipeline = compose(add_one, times_two)
    # times_two applied first (rightmost), then add_one
    assert pipeline(3) == (3 * 2) + 1


def test_compose_three_functions_chains_in_order():
    f = compose(lambda x: x + "!", lambda x: x.upper(), lambda x: x.strip())
    assert f("  hi  ") == "HI!"


def test_compose_zero_functions_is_identity():
    """compose() with no args returns the input unchanged."""
    assert compose()(42) == 42


def test_compose_single_function_acts_like_the_function():
    assert compose(str.upper)("abc") == "ABC"


# with_engine / with_language — kwarg injection wrappers


def test_with_engine_injects_kwarg_into_call():
    captured = {}

    def fake_synth(text, engine=None, language=None):
        captured.update(text=text, engine=engine, language=language)
        return b"audio"

    bound = with_engine("piper")(fake_synth)
    bound("hello", language="en")
    assert captured["engine"] == "piper"
    assert captured["language"] == "en"
    assert captured["text"] == "hello"


def test_with_engine_overrides_caller_supplied_engine():
    """Wrapper's engine wins over the kwarg the caller passed in."""
    captured = {}

    def fake_synth(text, engine=None):
        captured["engine"] = engine

    with_engine("piper")(fake_synth)("hi", engine="gtts")
    assert captured["engine"] == "piper"


def test_with_language_composes_with_with_engine():
    """Both wrappers must stack without conflict."""
    captured = {}

    def fake_synth(text, engine=None, language=None):
        captured.update(engine=engine, language=language)

    bound = with_engine("piper")(with_language("ru")(fake_synth))
    bound("hi")
    assert captured == {"engine": "piper", "language": "ru"}


# generate_timestamp_filename / ensure_audio_directory


def test_generate_timestamp_filename_format_without_prefix():
    name = generate_timestamp_filename(extension="wav")
    assert re.match(r"^\d{8}_\d{6}\.wav$", name)


def test_generate_timestamp_filename_format_with_prefix():
    name = generate_timestamp_filename(prefix="speech", extension="mp3")
    assert re.match(r"^speech_\d{8}_\d{6}\.mp3$", name)


def test_ensure_audio_directory_creates_when_missing(tmp_path):
    target = tmp_path / "fresh_audio"
    assert not target.exists()
    result = ensure_audio_directory(str(target))
    assert target.is_dir()
    assert result == str(target)


def test_ensure_audio_directory_is_idempotent(tmp_path):
    target = tmp_path / "audio"
    ensure_audio_directory(str(target))
    ensure_audio_directory(str(target))  # second call must not raise
    assert target.is_dir()
