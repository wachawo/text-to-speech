#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Checks that every place naming the default API port agrees with the server."""

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PORT = "5052"


def read(relative: str) -> str:
    """Return the text of a repository file."""
    return (ROOT / relative).read_text(encoding="utf-8")


def test_server_default_port():
    """ttssrv listens on 5052 when TTS_PORT is not set."""
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


WWW_PORT = "5054"


@pytest.mark.parametrize("compose", ["docker-compose.yml", "docker-compose-cpu.yml"])
def test_web_ui_has_one_port_https_by_default(compose):
    """ttswww publishes one port, 5054, the same number nginx listens on, in https mode by default."""
    text = read(compose)
    assert set(re.findall(r"\$\{TTS_WWW_PORT:-(\d+)\}", text)) == {WWW_PORT}
    assert set(re.findall(r"\$\{TTS_WWW_SCHEME:-(\w+)\}", text)) == {"https"}
    assert '- "${TTS_WWW_PORT:-5054}:${TTS_WWW_PORT:-5054}"' in text
    assert "TTS_WWW_TLS_PORT" not in text


@pytest.mark.parametrize("compose", ["docker-compose.yml", "docker-compose-cpu.yml"])
def test_web_healthcheck_uses_the_internal_http_port(compose):
    """The healthcheck asks the plain-http server the template binds to 127.0.0.1, whatever the scheme."""
    port = re.search(r"listen 127\.0\.0\.1:(\d+);", read("nginx/templates/default.conf.template")).group(1)
    assert f"http://127.0.0.1:{port}/nginx-healthz" in read(compose)


def test_env_example_names_the_web_defaults():
    """env.example sets the web port and mode to their compose defaults."""
    text = read("env.example")
    assert re.search(r"^TTS_WWW_PORT=(\d+)$", text, re.MULTILINE).group(1) == WWW_PORT
    assert re.search(r"^TTS_WWW_SCHEME=(\w+)$", text, re.MULTILINE).group(1) == "https"


@pytest.mark.parametrize("scheme", ["https", "http"])
def test_template_includes_a_snippet_for_each_scheme(scheme):
    """default.conf includes scheme-<mode>.inc, and both modes have a snippet listening on TTS_WWW_PORT."""
    assert "include /etc/nginx/conf.d/scheme-${TTS_WWW_SCHEME}.inc;" in read("nginx/templates/default.conf.template")
    snippet = read(f"nginx/templates/scheme-{scheme}.inc.template")
    listen = "listen ${TTS_WWW_PORT} ssl;" if scheme == "https" else "listen ${TTS_WWW_PORT};"
    assert listen in snippet


@pytest.mark.parametrize(
    ("scheme", "port", "code"),
    [("https", "5054", 0), ("http", "5054", 0), ("ftp", "5054", 1), ("", "5054", 1), ("https", "", 1), ("https", "54x", 1)],
)
def test_scheme_check_script(scheme, port, code):
    """05-www-scheme.sh lets only https/http and a numeric port through, before nginx starts."""
    env = {"PATH": "/usr/bin:/bin", "TTS_WWW_SCHEME": scheme, "TTS_WWW_PORT": port}
    result = subprocess.run(["sh", str(ROOT / "nginx/05-www-scheme.sh")], env=env, capture_output=True, text=True)
    assert result.returncode == code
