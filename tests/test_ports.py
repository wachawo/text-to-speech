#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Checks that every place naming the default API port agrees with the server."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PORT = "5062"


def read(relative: str) -> str:
    """Return the text of a repository file."""
    return (ROOT / relative).read_text(encoding="utf-8")


def test_server_default_port():
    """ttssrv listens on 5062 when TTS_PORT is not set."""
    assert re.search(r'os\.getenv\("TTS_PORT", "(\d+)"\)', read("ttssrv/app1.py")).group(1) == DEFAULT_PORT


@pytest.mark.parametrize("compose", ["docker-compose.yml", "docker-compose-cpu.yml"])
def test_compose_defaults_match_the_server(compose):
    """The published port, the healthcheck and the nginx upstream fall back to the server default."""
    defaults = set(re.findall(r"\$\{TTS_PORT:-(\d+)\}", read(compose)))
    assert defaults == {DEFAULT_PORT}


@pytest.mark.parametrize("dockerfile", ["docker/gpu/Dockerfile", "docker/cpu/Dockerfile"])
def test_images_expose_the_server_default(dockerfile):
    """The images document the port the server listens on."""
    assert re.search(r"^EXPOSE (\d+)$", read(dockerfile), re.MULTILINE).group(1) == DEFAULT_PORT


@pytest.mark.parametrize("example", ["env.example", "ttsgen.conf.example"])
def test_examples_name_the_server_default(example):
    """The example configs set TTS_PORT and TTS_URL to the server default."""
    text = read(example)
    assert re.search(r"^TTS_PORT=(\d+)$", text, re.MULTILINE).group(1) == DEFAULT_PORT
    assert re.search(r"^TTS_URL=http://localhost:(\d+)$", text, re.MULTILINE).group(1) == DEFAULT_PORT
