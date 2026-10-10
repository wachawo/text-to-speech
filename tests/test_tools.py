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
    validate_language,
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


# Auto-generated names never overwrite: claim_timestamp_path, batch_tts, text_to_speech_file


class FrozenClock:
    """Stand-in for datetime whose now() never moves, so every name lands in the same second."""

    @staticmethod
    def now():
        """Return one fixed moment."""
        from datetime import datetime

        return datetime(2026, 10, 10, 12, 0, 0)


def load_real_api():
    """Import the real libs/api.py; conftest keeps a stub under sys.modules["libs.api"]."""
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("libs.api_real", Path(tools_mod.__file__).parent / "api.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_claim_timestamp_path_adds_a_suffix_when_the_name_is_taken(tmp_path, monkeypatch):
    """Two names claimed in the same second are different files, the second one numbered."""
    monkeypatch.setattr(tools_mod, "datetime", FrozenClock)
    first = tools_mod.claim_timestamp_path(str(tmp_path), "voice", "wav")
    second = tools_mod.claim_timestamp_path(str(tmp_path), "voice", "wav")
    assert first == str(tmp_path / "voice_20261010_120000.wav")
    assert second == str(tmp_path / "voice_20261010_120000_2.wav")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["voice_20261010_120000.wav", "voice_20261010_120000_2.wav"]


def test_batch_tts_names_files_by_their_format_and_keeps_every_one(tmp_path, monkeypatch):
    """WAV output is named .wav, and two items finished in one second are two files."""
    monkeypatch.setattr(tools_mod, "datetime", FrozenClock)
    files = tools_mod.batch_tts(["one", "two"], output_dir=str(tmp_path))
    assert len(set(files)) == 2
    for name in files:
        assert name.endswith(".wav")
        with open(name, "rb") as handle:
            assert handle.read(4) == b"RIFF"
    assert len(list(tmp_path.iterdir())) == 2


def test_text_to_speech_file_failed_write_leaves_no_empty_file(tmp_path, monkeypatch, make_wav):
    """A write that fails removes the auto-generated name it claimed."""
    monkeypatch.chdir(tmp_path)
    real_api = load_real_api()
    monkeypatch.setattr(real_api, "text_to_speech_bytes", lambda text, engine, language: make_wav())
    real_open = open

    def failing_open(path, mode="r", *args, **kwargs):
        """Refuse the audio write, let every other open through."""
        if mode == "wb":
            raise OSError(28, "No space left on device")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", failing_open)
    with pytest.raises(OSError):
        real_api.text_to_speech_file("one", filename=None)
    assert list(tmp_path.iterdir()) == []


def test_text_to_speech_file_auto_name_never_overwrites(tmp_path, monkeypatch, make_wav):
    """Two auto-named files written in the same second both survive."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(tools_mod, "datetime", FrozenClock)
    real_api = load_real_api()
    monkeypatch.setattr(real_api, "text_to_speech_bytes", lambda text, engine, language: make_wav())
    first = real_api.text_to_speech_file("one", filename=None)
    second = real_api.text_to_speech_file("two", filename=None)
    assert first != second
    assert (tmp_path / first).exists() and (tmp_path / second).exists()
