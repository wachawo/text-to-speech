#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for libs.sample_resolver.resolve_sample_path.

Bare names search ./samples then ~/.config; values with a separator
are passed through expanduser+abspath.
"""

import os

from libs.sample_resolver import resolve_sample_path


def test_bare_name_found_in_samples(tmp_path, monkeypatch):
    """First-priority lookup: <cwd>/samples/<name>."""
    monkeypatch.chdir(tmp_path)
    samples = tmp_path / "samples"
    samples.mkdir()
    target = samples / "voice.wav"
    target.write_bytes(b"RIFF")

    assert resolve_sample_path("voice.wav") == str(target.resolve())


def test_bare_name_falls_back_to_user_config(tmp_path, monkeypatch):
    """Second-priority lookup: ~/.config/<name> when ./samples doesn't have it."""
    monkeypatch.chdir(tmp_path)
    fake_home = tmp_path / "home"
    (fake_home / ".config").mkdir(parents=True)
    target = fake_home / ".config" / "voice.wav"
    target.write_bytes(b"RIFF")
    monkeypatch.setenv("HOME", str(fake_home))

    assert resolve_sample_path("voice.wav") == str(target)


def test_bare_name_nowhere_returns_samples_candidate(tmp_path, monkeypatch):
    """When neither location has the file, return cwd/samples candidate
    so the caller's error message points at the conventional spot."""
    monkeypatch.chdir(tmp_path)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    expected = str((tmp_path / "samples" / "missing.wav").resolve())
    assert resolve_sample_path("missing.wav") == expected


def test_absolute_path_passed_through(tmp_path):
    """Values containing '/' are not searched — used verbatim (abspath)."""
    target = tmp_path / "explicit.wav"
    target.write_bytes(b"RIFF")
    assert resolve_sample_path(str(target)) == str(target)


def test_tilde_path_expanded(tmp_path, monkeypatch):
    """~/... gets expanduser'd to $HOME-relative absolute path."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    result = resolve_sample_path("~/voice.wav")
    assert result == str(fake_home / "voice.wav")


def test_relative_with_separator_passed_through(tmp_path, monkeypatch):
    """A relative path WITH a separator is treated as an explicit path,
    not as a bare name to be searched in standard locations."""
    monkeypatch.chdir(tmp_path)
    sub = tmp_path / "custom"
    sub.mkdir()
    explicit = sub / "v.wav"
    explicit.write_bytes(b"RIFF")

    assert resolve_sample_path("custom/v.wav") == str(explicit.resolve())


def test_samples_wins_over_user_config(tmp_path, monkeypatch):
    """If both locations contain the file, ./samples (priority 1) wins."""
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
