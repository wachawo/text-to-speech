#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for libs.sample_resolver.

Bare names search the samples directory (COQUITTS_SAMPLES, default
./samples) then ~/.config; values with a separator are passed through
expanduser+abspath. Voice names map to <samples dir>/<name>.wav and are
validated so they can never leave that directory.
"""

import os

import pytest

# Local imports
from libs.exceptions import ValidationError
from libs.sample_resolver import (
    get_samples_dir,
    list_sample_files,
    resolve_sample_path,
    sample_path_for_voice,
)


def test_bare_name_found_in_samples(tmp_path, monkeypatch):
    """A bare name is resolved first against <cwd>/samples/<name>."""
    monkeypatch.chdir(tmp_path)
    samples = tmp_path / "samples"
    samples.mkdir()
    target = samples / "voice.wav"
    target.write_bytes(b"RIFF")

    assert resolve_sample_path("voice.wav") == str(target.resolve())


def test_bare_name_falls_back_to_user_config(tmp_path, monkeypatch):
    """A bare name missing from ./samples is looked up in ~/.config/<name>."""
    monkeypatch.chdir(tmp_path)
    fake_home = tmp_path / "home"
    (fake_home / ".config").mkdir(parents=True)
    target = fake_home / ".config" / "voice.wav"
    target.write_bytes(b"RIFF")
    monkeypatch.setenv("HOME", str(fake_home))

    assert resolve_sample_path("voice.wav") == str(target)


def test_bare_name_nowhere_returns_samples_candidate(tmp_path, monkeypatch):
    """A bare name found nowhere still yields the cwd/samples candidate so errors point at the conventional spot."""
    monkeypatch.chdir(tmp_path)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    expected = str((tmp_path / "samples" / "missing.wav").resolve())
    assert resolve_sample_path("missing.wav") == expected


def test_absolute_path_passed_through(tmp_path):
    """A value containing a separator is used verbatim (abspath) rather than searched."""
    target = tmp_path / "explicit.wav"
    target.write_bytes(b"RIFF")
    assert resolve_sample_path(str(target)) == str(target)


def test_tilde_path_expanded(tmp_path, monkeypatch):
    """A leading ~ is expanded to an absolute path under $HOME."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    result = resolve_sample_path("~/voice.wav")
    assert result == str(fake_home / "voice.wav")


def test_relative_with_separator_passed_through(tmp_path, monkeypatch):
    """A relative path with a separator counts as explicit and skips the standard search locations."""
    monkeypatch.chdir(tmp_path)
    sub = tmp_path / "custom"
    sub.mkdir()
    explicit = sub / "v.wav"
    explicit.write_bytes(b"RIFF")

    assert resolve_sample_path("custom/v.wav") == str(explicit.resolve())


def test_samples_wins_over_user_config(tmp_path, monkeypatch):
    """When both locations hold the file, ./samples takes priority over ~/.config."""
    monkeypatch.chdir(tmp_path)
    fake_home = tmp_path / "home"
    (fake_home / ".config").mkdir(parents=True)
    cfg = fake_home / ".config" / "voice.wav"
    cfg.write_bytes(b"home")
    monkeypatch.setenv("HOME", str(fake_home))

    samples = tmp_path / "samples"
    samples.mkdir()
    near = samples / "voice.wav"
    near.write_bytes(b"local")

    result = resolve_sample_path("voice.wav")
    assert result == str(near.resolve())
    # Sanity — make sure we resolved to the local one, not config one.
    assert os.path.dirname(result) == str(samples.resolve())


# get_samples_dir


def test_get_samples_dir_defaults_to_cwd_samples(tmp_path, monkeypatch):
    """Without COQUITTS_SAMPLES the samples dir is <cwd>/samples."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COQUITTS_SAMPLES", raising=False)
    assert get_samples_dir() == str((tmp_path / "samples").resolve())


def test_get_samples_dir_from_env(tmp_path, monkeypatch):
    """COQUITTS_SAMPLES overrides the samples dir and is read at call time (expanduser + abspath)."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("COQUITTS_SAMPLES", "~/voices")
    assert get_samples_dir() == str(fake_home / "voices")
    monkeypatch.setenv("COQUITTS_SAMPLES", str(tmp_path / "other"))
    assert get_samples_dir() == str(tmp_path / "other")


def test_bare_name_found_in_env_samples_dir(tmp_path, monkeypatch):
    """A bare name is resolved against COQUITTS_SAMPLES, not the cwd, when the env var is set."""
    monkeypatch.chdir(tmp_path)
    custom = tmp_path / "custom_samples"
    custom.mkdir()
    target = custom / "voice.wav"
    target.write_bytes(b"RIFF")
    monkeypatch.setenv("COQUITTS_SAMPLES", str(custom))

    assert resolve_sample_path("voice.wav") == str(target)


# list_sample_files


def test_list_sample_files_sorted_stems(tmp_path, monkeypatch):
    """Only direct *.wav files are listed, as sorted stems; other files and subdirectories are skipped."""
    samples = tmp_path / "samples"
    samples.mkdir()
    for name in ("zoe.wav", "adam.wav", "Maria.wav"):
        (samples / name).write_bytes(b"RIFF")
    (samples / "notes.txt").write_text("skip")
    (samples / "nested.wav").mkdir()
    (samples / "nested.wav" / "deep.wav").write_bytes(b"RIFF")
    monkeypatch.setenv("COQUITTS_SAMPLES", str(samples))

    assert list_sample_files() == ["Maria", "adam", "zoe"]


def test_list_sample_files_missing_dir(tmp_path, monkeypatch):
    """A samples dir that does not exist yields an empty list rather than an error."""
    monkeypatch.setenv("COQUITTS_SAMPLES", str(tmp_path / "nowhere"))
    assert list_sample_files() == []


# sample_path_for_voice


def test_sample_path_for_voice_joins_samples_dir(tmp_path, monkeypatch):
    """A valid name maps to <samples dir>/<name>.wav even when the file does not exist."""
    monkeypatch.setenv("COQUITTS_SAMPLES", str(tmp_path))
    assert sample_path_for_voice("maria") == str(tmp_path / "maria.wav")


@pytest.mark.parametrize("bad_voice", ["../etc", "a.b", "", "x" * 49, "maria\n"])
def test_sample_path_for_voice_rejects_invalid_names(tmp_path, monkeypatch, bad_voice):
    """Separators, dots, empty, over-long and newline-terminated names are refused before touching the filesystem."""
    monkeypatch.setenv("COQUITTS_SAMPLES", str(tmp_path))
    with pytest.raises(ValidationError, match="Invalid voice name"):
        sample_path_for_voice(bad_voice)
