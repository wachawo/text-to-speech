#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Checks that the Docker build context leaves out runtime state and secrets."""

from pathlib import Path

import pytest

DOCKERIGNORE = Path(__file__).resolve().parent.parent / ".dockerignore"


def read_patterns() -> set[str]:
    """Return the patterns of .dockerignore without comments and blank lines."""
    lines = DOCKERIGNORE.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.startswith("#")}


@pytest.mark.parametrize("pattern", ["data/", "node_modules/", "cache/", ".env"])
def test_build_context_excludes(pattern):
    """Every image builds from the repo root, so data/ (pip cache, history, data/certs/tts.key) must stay out."""
    assert pattern in read_patterns()
