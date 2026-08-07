#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for the dynamic engine loader in engines/__init__.py.

The package is the project's plugin system: each engine module declares
is_available()/generate(); the loader hides the rest. These tests pin
down its behaviour without depending on torch/coqui/etc.
"""

import importlib
import types

import engines as engines_pkg
from engines import (
    get_engine_function,
    get_engine_module_path,
    is_engine_available,
    load_engine,
)

# get_engine_module_path


def test_module_path_for_known_engine_is_a_file():
    """gtts.py exists in the real engines/ directory."""
    p = get_engine_module_path("gtts")
    assert p is not None
    assert p.is_file()
    assert p.name == "gtts.py"


def test_module_path_for_unknown_returns_none():
    """An engine name with no matching module file resolves to None."""
    assert get_engine_module_path("definitely_not_a_real_engine_xyz") is None


# load_engine — exercises real engine modules; result depends on optional deps


def test_load_engine_unknown_returns_none():
    """Loading an engine that has no module file yields None instead of raising."""
    assert load_engine("definitely_not_a_real_engine_xyz") is None


def test_load_engine_returns_module_when_dependencies_available():
    """gtts requires only `requests` which is in the dev venv."""
    module = load_engine("gtts")
    assert module is not None
    assert hasattr(module, "is_available")
    assert hasattr(module, "generate")


def test_load_engine_returns_none_when_module_reports_unavailable(monkeypatch):
    """If a module imports cleanly but is_available() is False, loader hides it."""
    fake = types.ModuleType("fake_engine")
    fake.is_available = lambda: False
    fake.generate = lambda text, config: b""

    monkeypatch.setattr(importlib, "import_module", lambda name, package=None: fake)
    # Real path lookup must succeed (gtts.py exists) so we reach the import branch.
    assert load_engine("gtts") is None


def test_load_engine_swallows_importerror(monkeypatch, caplog):
    """A missing optional dependency yields None plus a warning, never propagates."""

    def explode(name, package=None):
        """Simulate an engine module whose optional dependency is absent."""
        raise ImportError("simulated missing dep")

    monkeypatch.setattr(importlib, "import_module", explode)
    with caplog.at_level("WARNING"):
        result = load_engine("gtts")
    assert result is None
    assert any("Failed to import" in r.message for r in caplog.records)


def test_load_engine_swallows_unexpected_exception(monkeypatch, caplog):
    """Any other exception during import yields None instead of crashing."""

    def explode(name, package=None):
        """Simulate an engine module that blows up for a non-import reason."""
        raise RuntimeError("boom")

    monkeypatch.setattr(importlib, "import_module", explode)
    with caplog.at_level("WARNING"):
        result = load_engine("gtts")
    assert result is None
    assert any("Error loading" in r.message for r in caplog.records)


# is_engine_available — thin wrapper on load_engine


def test_is_engine_available_true_for_loaded_module(monkeypatch):
    """Any module the loader returns counts as an available engine."""
    monkeypatch.setattr(engines_pkg, "load_engine", lambda name: types.ModuleType("x"))
    assert is_engine_available("anything") is True


def test_is_engine_available_false_when_loader_returns_none(monkeypatch):
    """A loader miss reports the engine as unavailable."""
    monkeypatch.setattr(engines_pkg, "load_engine", lambda name: None)
    assert is_engine_available("anything") is False


# get_engine_function


def test_get_engine_function_returns_callable_when_module_has_generate(monkeypatch):
    """The module's generate attribute is handed back ready to call."""
    fake = types.ModuleType("fake")
    fake.generate = lambda text, config: b"audio"
    monkeypatch.setattr(engines_pkg, "load_engine", lambda name: fake)
    fn = get_engine_function("any")
    assert callable(fn)
    assert fn("hi", {}) == b"audio"


def test_get_engine_function_returns_none_when_module_lacks_generate(monkeypatch):
    """A loaded module missing generate yields None, not an AttributeError."""
    fake = types.ModuleType("incomplete")
    monkeypatch.setattr(engines_pkg, "load_engine", lambda name: fake)
    assert get_engine_function("any") is None


def test_get_engine_function_returns_none_when_loader_returns_none(monkeypatch):
    """No module means no callable."""
    monkeypatch.setattr(engines_pkg, "load_engine", lambda name: None)
    assert get_engine_function("any") is None
