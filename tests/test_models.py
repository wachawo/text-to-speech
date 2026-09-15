#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for libs.models - the engine/model rows behind `ttsgen --list` and GET /api/models.

Model directories point at tmp_path via the *_MODELS env keys, and the lazy
`engines.is_engine_available` import is patched so no engine dependency is probed.
"""

from pathlib import Path

# Local imports
import engines
from libs.models import ENGINE_NOTES, collect_engine_rows, engine_model_sources, model_display_name


def rows_for(engine: str, rows: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    """Filter the collected rows down to one engine."""
    return [row for row in rows if row[0] == engine]


def test_engine_model_sources_reads_env_at_call_time(tmp_path, monkeypatch):
    """The model directory comes from the environment when the function runs, not at import."""
    monkeypatch.setenv("PIPERTTS_MODELS", str(tmp_path))
    model_dir, patterns = engine_model_sources()["pipertts"]
    assert model_dir == str(tmp_path)
    assert patterns == ["*.onnx"]


def test_installed_engine_lists_one_row_per_model(tmp_path, monkeypatch):
    """An installed engine with two .onnx files yields two rows carrying the display names."""
    models_dir = tmp_path / "pipertts"
    models_dir.mkdir()
    (models_dir / "en_US-amy-medium.onnx").write_bytes(b"onnx")
    (models_dir / "en_US-lessac-medium.onnx").write_bytes(b"onnx")
    monkeypatch.setenv("PIPERTTS_MODELS", str(models_dir))
    monkeypatch.setattr(engines, "is_engine_available", lambda name: name == "pipertts")

    rows = rows_for("pipertts", collect_engine_rows())

    assert rows == [
        ("pipertts", "installed", "en_US-amy-medium.onnx"),
        ("pipertts", "installed", "en_US-lessac-medium.onnx"),
    ]


def test_installed_engine_without_models_gets_dash(tmp_path, monkeypatch):
    """An installed engine whose model directory is empty yields a single "-" row."""
    models_dir = tmp_path / "pipertts"
    models_dir.mkdir()
    monkeypatch.setenv("PIPERTTS_MODELS", str(models_dir))
    monkeypatch.setattr(engines, "is_engine_available", lambda name: name == "pipertts")

    assert rows_for("pipertts", collect_engine_rows()) == [("pipertts", "installed", "-")]


def test_missing_engine_gets_dash(tmp_path, monkeypatch):
    """A missing engine reports ("x", "missing", "-") without looking at its model directory."""
    models_dir = tmp_path / "pipertts"
    models_dir.mkdir()
    (models_dir / "en_US-amy-medium.onnx").write_bytes(b"onnx")
    monkeypatch.setenv("PIPERTTS_MODELS", str(models_dir))
    monkeypatch.setattr(engines, "is_engine_available", lambda name: False)

    assert rows_for("pipertts", collect_engine_rows()) == [("pipertts", "missing", "-")]


def test_gtts_row_carries_engine_note(monkeypatch):
    """gtts has no on-disk models, so its row shows the ENGINE_NOTES text."""
    monkeypatch.setattr(engines, "is_engine_available", lambda name: name == "gtts")

    assert rows_for("gtts", collect_engine_rows()) == [("gtts", "installed", ENGINE_NOTES["gtts"])]


def test_coquitts_display_name_strips_tts_prefix_and_restores_slashes():
    """coquitts cache folders are shown as the COQUITTS_MODEL identifier users type."""
    rel = Path("tts/tts_models--multilingual--multi-dataset--xtts_v2")
    assert model_display_name("coquitts", rel) == "tts_models/multilingual/multi-dataset/xtts_v2"


def test_coquitts_rows_use_display_name(tmp_path, monkeypatch):
    """An installed coquitts lists each tts/ cache folder under its display name."""
    models_dir = tmp_path / "coquitts"
    (models_dir / "tts" / "tts_models--multilingual--multi-dataset--xtts_v2").mkdir(parents=True)
    monkeypatch.setenv("COQUITTS_MODELS", str(models_dir))
    monkeypatch.setattr(engines, "is_engine_available", lambda name: name == "coquitts")

    assert rows_for("coquitts", collect_engine_rows()) == [
        ("coquitts", "installed", "tts_models/multilingual/multi-dataset/xtts_v2"),
    ]


def test_other_engines_display_name_is_untouched():
    """Non-coqui engines show the relative path as-is."""
    assert model_display_name("pipertts", Path("en_US-amy-medium.onnx")) == "en_US-amy-medium.onnx"
