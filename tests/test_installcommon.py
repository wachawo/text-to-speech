#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for install.common: download_file and resolve_models_dir."""

import urllib.error
import urllib.request
from pathlib import Path

import pytest

# Local imports
import libs.models
from install.common import download_file, resolve_models_dir


def test_interrupted_download_leaves_nothing_to_skip(monkeypatch, tmp_path):
    """A download cut off half way leaves no file, so the next run downloads again instead of skipping."""

    def cut_off(url, filename, reporthook=None):
        """Write part of the file, then fail like a dropped connection."""
        with open(filename, "wb") as handle:
            handle.write(b"\x00" * 1024)
        raise urllib.error.ContentTooShortError("retrieval incomplete", None)

    monkeypatch.setattr(urllib.request, "urlretrieve", cut_off)
    dest = tmp_path / "model.onnx"
    with pytest.raises(urllib.error.ContentTooShortError):
        download_file("https://example.invalid/model.onnx", dest)
    assert list(tmp_path.iterdir()) == []


def test_complete_download_lands_at_dest(monkeypatch, tmp_path):
    """A finished download is renamed into place and no .part file is left beside it."""

    def complete(url, filename, reporthook=None):
        """Write the whole file."""
        with open(filename, "wb") as handle:
            handle.write(b"model")

    monkeypatch.setattr(urllib.request, "urlretrieve", complete)
    dest = tmp_path / "model.onnx"
    download_file("https://example.invalid/model.onnx", dest)
    assert dest.read_bytes() == b"model"
    assert list(tmp_path.iterdir()) == [dest]


def test_existing_file_is_skipped(monkeypatch, tmp_path):
    """A non-empty file already at dest is kept and nothing is fetched."""

    def fail(url, filename, reporthook=None):
        """Fail the test if a download is attempted."""
        raise AssertionError("download attempted")

    monkeypatch.setattr(urllib.request, "urlretrieve", fail)
    dest = tmp_path / "model.onnx"
    dest.write_bytes(b"model")
    download_file("https://example.invalid/model.onnx", dest)
    assert dest.read_bytes() == b"model"


def test_relative_models_dir_lands_where_the_engine_looks(monkeypatch, tmp_path):
    """A relative *_MODELS value is anchored on the project root, so an install run elsewhere fills the engine's directory."""
    project = tmp_path / "project"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.setattr(libs.models, "PROJECT_ROOT", str(project))
    monkeypatch.chdir(elsewhere)
    monkeypatch.setenv("PIPERTTS_MODELS", "cache/pipertts")

    target = resolve_models_dir("Piper TTS", "PIPERTTS_MODELS", tmp_path / "default", project / "cache" / "pipertts")

    assert target == (project / "cache" / "pipertts").resolve()
    assert target.is_dir()
    assert target == Path(libs.models.models_directory("pipertts")).resolve()
    assert list(elsewhere.iterdir()) == []
