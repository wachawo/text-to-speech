#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for libs.tools — pure validation plus the functional helpers.

Each test asserts ONE behavioural invariant; combined they pin down the
full contract of validate_*, get_default_config, compose, with_engine,
with_language, generate_timestamp_filename, ensure_audio_directory.
"""

import re

import pytest

from libs import tools as tools_mod
from libs.exceptions import EngineNotAvailableError, ValidationError
from libs.tools import (
    compose,
    ensure_audio_directory,
    generate_timestamp_filename,
    get_default_config,
    validate_engine,
    validate_engine_language,
    validate_language,
    validate_model,
    validate_text,
    with_engine,
    with_language,
)

# get_default_config — must return a fresh dict each time so callers can mutate freely


def test_get_default_config_keys():
    """The default config exposes exactly the five documented keys."""
    cfg = get_default_config()
    assert set(cfg) == {"engine", "language", "rate", "volume", "slow"}


def test_get_default_config_returns_fresh_dict():
    """Two calls return independent dicts, so mutating one cannot leak into the next."""
    a = get_default_config()
    a["engine"] = "mutated"
    b = get_default_config()
    assert b["engine"] != "mutated"


# validate_text


@pytest.mark.parametrize("bad", [None, 123, b"bytes", [], {}])
def test_validate_text_rejects_non_string(bad):
    """Anything that is not a str is refused before synthesis is attempted."""
    with pytest.raises(ValidationError, match="must be a string"):
        validate_text(bad)


@pytest.mark.parametrize("blank", ["", "   ", "\t\n  "])
def test_validate_text_rejects_blank(blank):
    """Text that is empty or whitespace-only is refused."""
    with pytest.raises(ValidationError, match="cannot be empty"):
        validate_text(blank)


def test_validate_text_strips_surrounding_whitespace():
    """Accepted text comes back trimmed of leading and trailing whitespace."""
    assert validate_text("   hello   ") == "hello"


def test_validate_text_accepts_long_text_under_limit():
    """Text just under the hard cap is accepted — splitting it is the chunker's job."""
    text = "x" * 999_999
    assert len(validate_text(text)) == 999_999


def test_validate_text_rejects_pathological_length():
    """Text above the 1M-character cap is refused rather than silently truncated."""
    with pytest.raises(ValidationError, match="too long"):
        validate_text("x" * 1_000_001)


# validate_language


@pytest.mark.parametrize("ok,expected", [("en", "en"), ("EN", "en"), ("Ru", "ru")])
def test_validate_language_lowercases_two_char_code(ok, expected):
    """A valid two-letter code is accepted and normalised to lowercase."""
    assert validate_language(ok) == expected


@pytest.mark.parametrize("bad", ["e", "eng", "", "english", 42, None])
def test_validate_language_rejects_wrong_shape(bad):
    """Anything that is not a two-character string is refused."""
    with pytest.raises(ValidationError, match="2-character"):
        validate_language(bad)


@pytest.mark.parametrize("ok,expected", [("zh-CN", "zh-cn"), ("pt_BR", "pt-br"), ("es-419", "es-419")])
def test_validate_language_normalizes_tags(ok, expected):
    """A tag is accepted, lowercased and written with '-'."""
    assert validate_language(ok) == expected


@pytest.mark.parametrize("bad", ["zh-", "zh-toolong", "zh cn"])
def test_validate_language_rejects_malformed_tags(bad):
    """A dangling, too long or space-separated subtag is refused with the same message."""
    with pytest.raises(ValidationError, match="tag such as 'zh-cn'"):
        validate_language(bad)


# validate_engine_language


def test_validate_engine_language_passes_when_engine_declares_nothing(monkeypatch):
    """An engine without a list_languages() hook accepts every code."""
    monkeypatch.setattr(tools_mod, "get_engine_languages", lambda engine: None)
    validate_engine_language("pyttsx3", "xx")


@pytest.mark.parametrize("language", ["en", "en-gb", "EN"])
def test_validate_engine_language_passes_listed_codes(monkeypatch, language):
    """A listed code, or a tag of a listed language, passes."""
    monkeypatch.setattr(tools_mod, "get_engine_languages", lambda engine: ["en", "ru"])
    validate_engine_language("kokorotts", language)


def test_validate_engine_language_rejects_unlisted_code(monkeypatch):
    """An unlisted code is refused with the engine name and the codes it does serve."""
    monkeypatch.setattr(tools_mod, "get_engine_languages", lambda engine: ["en", "ru"])
    with pytest.raises(ValidationError) as exc:
        validate_engine_language("kokorotts", "de")
    assert str(exc.value) == "Language 'de' is not supported by engine 'kokorotts'. Supported: en, ru"


def test_validate_engine_language_checks_the_named_model(monkeypatch):
    """With a model, that model's languages are checked and the message names it."""
    calls = []

    def languages_of(engine, model=None):
        """Return the languages of the model the check asks about."""
        calls.append((engine, model))
        return ["en"] if model == "en-only" else ["en", "de"]

    monkeypatch.setattr(tools_mod, "get_engine_languages", languages_of)
    validate_engine_language("pipertts", "de")
    with pytest.raises(ValidationError) as exc:
        validate_engine_language("pipertts", "de", "en-only")
    assert str(exc.value) == "Language 'de' is not supported by engine 'pipertts' model 'en-only'. Supported: en"
    assert calls == [("pipertts", None), ("pipertts", "en-only")]


# validate_model


PIPER_MODELS = [
    {"id": "en_US-lessac-medium", "languages": ["en", "en-us"], "installed": True},
    {"id": "en_GB-alan-low", "languages": ["en", "en-gb"], "installed": True},
]


@pytest.mark.parametrize("model", [None, ""])
def test_validate_model_empty_means_engine_default(monkeypatch, model):
    """No model, or an empty one, is the engine default and needs no lookup."""
    monkeypatch.setattr(tools_mod, "get_engine_models", lambda engine: pytest.fail("no lookup expected"))
    assert validate_model("pipertts", model) is None


def test_validate_model_returns_a_listed_model(monkeypatch):
    """A model the engine lists is returned unchanged."""
    monkeypatch.setattr(tools_mod, "get_engine_models", lambda engine: PIPER_MODELS)
    assert validate_model("pipertts", "en_GB-alan-low") == "en_GB-alan-low"


@pytest.mark.parametrize("model", ["en_GB-missing-low", "../../etc/passwd", "/tmp/en_GB-alan-low"])
def test_validate_model_rejects_an_unlisted_model(monkeypatch, model):
    """An unlisted id is refused with the id, the engine and the ids it has, and no filesystem path."""
    monkeypatch.setattr(tools_mod, "get_engine_models", lambda engine: PIPER_MODELS)
    with pytest.raises(ValidationError) as exc:
        validate_model("pipertts", model)
    assert str(exc.value) == (f"Unknown model '{model}' for engine 'pipertts'. Available: en_US-lessac-medium, en_GB-alan-low")


def test_validate_model_message_names_no_filesystem_path(monkeypatch, tmp_path):
    """The real pipertts listing gives stems only, so the message carries no directory."""
    (tmp_path / "en_US-lessac-medium.onnx").write_bytes(b"x")
    monkeypatch.setenv("PIPERTTS_MODELS", str(tmp_path))
    with pytest.raises(ValidationError) as exc:
        validate_model("pipertts", "nope")
    assert "Available:" in str(exc.value)
    assert str(tmp_path) not in str(exc.value)


def test_validate_model_caps_the_listed_ids(monkeypatch):
    """A long catalogue lists the first ids and counts the rest."""
    models = [{"id": f"m{index:02d}", "languages": None, "installed": True} for index in range(25)]
    monkeypatch.setattr(tools_mod, "get_engine_models", lambda engine: models)
    with pytest.raises(ValidationError) as exc:
        validate_model("kokorotts", "zz")
    assert str(exc.value).endswith("m18, m19 (+5 more)")


def test_validate_model_engine_without_models(monkeypatch):
    """An engine that lists no models refuses any model."""
    monkeypatch.setattr(tools_mod, "get_engine_models", lambda engine: [])
    with pytest.raises(ValidationError, match="Engine 'gtts' has no selectable models"):
        validate_model("gtts", "standard")


@pytest.mark.parametrize("engine", ["definitely_not_a_real_engine_xyz", "../libs"])
def test_validate_model_unknown_engine(engine):
    """A model for an engine that does not exist is refused before any lookup."""
    with pytest.raises(ValidationError, match="not found"):
        validate_model(engine, "x")


# validate_engine — exercises real engines/__init__ logic against tests/stubs/gtts


def test_validate_engine_accepts_gtts():
    """An engine whose module exists and whose deps are importable validates cleanly."""
    assert validate_engine("gtts") == "gtts"


def test_validate_engine_rejects_unknown_module():
    """An engine name with no matching module is reported as not found."""
    with pytest.raises(ValidationError, match="not found"):
        validate_engine("nonexistent_engine_xyz")


@pytest.mark.parametrize("bad", ["", None, 0])
def test_validate_engine_rejects_falsy_or_non_string(bad):
    """Falsy or non-string engine names are refused with a type-oriented message."""
    with pytest.raises(ValidationError, match="non-empty string"):
        validate_engine(bad)


def test_validate_engine_distinguishes_missing_deps_from_missing_file(monkeypatch):
    """An existing engine module with unmet deps reports missing dependencies, not a missing module."""
    monkeypatch.setattr(tools_mod, "is_engine_available", lambda name: False)
    # silerotts.py exists (heavy deps absent in CI/dev venv).
    with pytest.raises(EngineNotAvailableError, match="dependencies not installed"):
        validate_engine("silerotts")


# compose — right-to-left function composition


def test_compose_two_functions_applies_right_to_left():
    """The rightmost function runs first, matching mathematical composition order."""

    def add_one(x):
        """Return the argument incremented by one."""
        return x + 1

    def times_two(x):
        """Return the argument doubled."""
        return x * 2

    pipeline = compose(add_one, times_two)
    # times_two applied first (rightmost), then add_one
    assert pipeline(3) == (3 * 2) + 1


def test_compose_three_functions_chains_in_order():
    """Three functions chain right-to-left through a single call."""
    f = compose(lambda x: x + "!", lambda x: x.upper(), lambda x: x.strip())
    assert f("  hi  ") == "HI!"


def test_compose_zero_functions_is_identity():
    """Composing nothing yields the identity function."""
    assert compose()(42) == 42


def test_compose_single_function_acts_like_the_function():
    """Composing one function behaves exactly like calling that function."""
    assert compose(str.upper)("abc") == "ABC"


# with_engine / with_language — kwarg injection wrappers


def test_with_engine_injects_kwarg_into_call():
    """The wrapper supplies the engine kwarg while leaving other arguments untouched."""
    captured = {}

    def fake_synth(text, engine=None, language=None):
        """Record the arguments the wrapper forwarded."""
        captured.update(text=text, engine=engine, language=language)
        return b"audio"

    bound = with_engine("piper")(fake_synth)
    bound("hello", language="en")
    assert captured["engine"] == "piper"
    assert captured["language"] == "en"
    assert captured["text"] == "hello"


def test_with_engine_overrides_caller_supplied_engine():
    """The bound engine wins over an engine kwarg passed by the caller."""
    captured = {}

    def fake_synth(text, engine=None):
        """Record the engine the wrapper forwarded."""
        captured["engine"] = engine

    with_engine("piper")(fake_synth)("hi", engine="gtts")
    assert captured["engine"] == "piper"


def test_with_language_composes_with_with_engine():
    """Stacking both wrappers injects engine and language without either clobbering the other."""
    captured = {}

    def fake_synth(text, engine=None, language=None):
        """Record the engine and language the wrappers forwarded."""
        captured.update(engine=engine, language=language)

    bound = with_engine("piper")(with_language("ru")(fake_synth))
    bound("hi")
    assert captured == {"engine": "piper", "language": "ru"}


# generate_timestamp_filename / ensure_audio_directory


def test_generate_timestamp_filename_format_without_prefix():
    """Without a prefix the name is just the timestamp plus the requested extension."""
    name = generate_timestamp_filename(extension="wav")
    assert re.match(r"^\d{8}_\d{6}\.wav$", name)


def test_generate_timestamp_filename_format_with_prefix():
    """A prefix is joined to the timestamp with an underscore."""
    name = generate_timestamp_filename(prefix="speech", extension="mp3")
    assert re.match(r"^speech_\d{8}_\d{6}\.mp3$", name)


def test_ensure_audio_directory_creates_when_missing(tmp_path):
    """A missing audio directory is created and its path returned."""
    target = tmp_path / "fresh_audio"
    assert not target.exists()
    result = ensure_audio_directory(str(target))
    assert target.is_dir()
    assert result == str(target)


def test_ensure_audio_directory_is_idempotent(tmp_path):
    """Calling it again on an existing directory succeeds instead of raising."""
    target = tmp_path / "audio"
    ensure_audio_directory(str(target))
    ensure_audio_directory(str(target))  # second call must not raise
    assert target.is_dir()
