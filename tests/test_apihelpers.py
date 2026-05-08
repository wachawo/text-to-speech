#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for ttsapi.py helpers — argparse, file reading, list-engines.

Network is mocked via monkeypatching `requests.get/post`; no real socket
is opened.
"""

import logging
import sys
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ttsapi  # noqa: E402


# read_text_file

def test_read_text_file_reads_and_strips(tmp_path):
    f = tmp_path / "in.txt"
    f.write_text("  hello world  \n")
    assert ttsapi.read_text_file(str(f)) == "hello world"


def test_read_text_file_raises_on_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="Not a file"):
        ttsapi.read_text_file(str(tmp_path / "nope.txt"))


def test_read_text_file_raises_on_empty(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("   \n\n  ")
    with pytest.raises(ValueError, match="empty"):
        ttsapi.read_text_file(str(f))


def test_read_text_file_rejects_directory(tmp_path):
    """A directory passes os.path.exists but not os.path.isfile."""
    with pytest.raises(FileNotFoundError):
        ttsapi.read_text_file(str(tmp_path))


# parse_arguments — argparse contract

def test_parser_requires_text_or_input_or_list():
    parser = ttsapi.parse_arguments()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parser_text_and_input_are_mutually_exclusive():
    parser = ttsapi.parse_arguments()
    with pytest.raises(SystemExit):
        parser.parse_args(["hello", "-i", "file.txt"])


def test_parser_accepts_positional_text():
    parser = ttsapi.parse_arguments()
    args = parser.parse_args(["hello"])
    assert args.text == "hello"
    assert args.text_file is None
    assert args.list is False


def test_parser_accepts_input_file():
    parser = ttsapi.parse_arguments()
    args = parser.parse_args(["-i", "input.txt"])
    assert args.text_file == "input.txt"


def test_parser_accepts_list_flag():
    parser = ttsapi.parse_arguments()
    args = parser.parse_args(["--list"])
    assert args.list is True


def test_parser_file_flag_with_explicit_path():
    parser = ttsapi.parse_arguments()
    args = parser.parse_args(["hello", "-f", "out.mp3"])
    assert args.file == "out.mp3"


def test_parser_file_flag_without_path_yields_empty_string():
    """`--file` (no value) is the magic 'auto-name' marker."""
    parser = ttsapi.parse_arguments()
    args = parser.parse_args(["hello", "-f"])
    assert args.file == ""


def test_parser_default_language_is_en():
    parser = ttsapi.parse_arguments()
    args = parser.parse_args(["hello"])
    assert args.language == "en"


# setup_logging

@pytest.mark.parametrize(
    "verbose,quiet,expected_level",
    [
        (False, False, logging.INFO),
        (True, False, logging.DEBUG),
        (False, True, logging.ERROR),
        (True, True, logging.ERROR),  # quiet wins when both set
    ],
)
def test_setup_logging_levels(verbose, quiet, expected_level):
    ttsapi.setup_logging(verbose=verbose, quiet=quiet)
    assert logging.getLogger().level == expected_level


# list_remote_engines — exit code + output format

def test_list_remote_engines_marks_default_with_asterisk(monkeypatch, capsys):
    monkeypatch.setattr(
        ttsapi,
        "fetch_engines",
        lambda: {"engines": ["gtts", "coquitts", "pyttsx3"], "default": "coquitts"},
    )
    rc = ttsapi.list_remote_engines()
    assert rc == 0
    out = capsys.readouterr().out
    assert "* coquitts" in out
    # Non-default entries get a leading space (no asterisk)
    assert "  gtts" in out
    assert "  pyttsx3" in out


def test_list_remote_engines_returns_1_on_network_failure(monkeypatch, caplog):
    def boom():
        raise requests.exceptions.ConnectionError("conn refused")

    monkeypatch.setattr(ttsapi, "fetch_engines", boom)
    with caplog.at_level("ERROR"):
        rc = ttsapi.list_remote_engines()
    assert rc == 1
    assert any("Failed to fetch" in r.message for r in caplog.records)


def test_list_remote_engines_handles_empty_engine_list(monkeypatch, capsys):
    """No engines on server is a degenerate but valid response — exit 0."""
    monkeypatch.setattr(ttsapi, "fetch_engines", lambda: {"engines": [], "default": ""})
    rc = ttsapi.list_remote_engines()
    assert rc == 0
    # Header still printed; just no engine rows
    out = capsys.readouterr().out
    assert "Remote engines on" in out


# fetch_audio — error paths (success path covered in test_ttsapi_auth)

def test_fetch_audio_raises_on_4xx_with_status_code_and_body(monkeypatch):
    class FakeResp:
        status_code = 422
        text = '{"error":"voice_sample_missing","message":"..."}'
        content = b""

    monkeypatch.setattr(requests, "post", lambda *a, **kw: FakeResp())
    with pytest.raises(RuntimeError, match=r"422"):
        ttsapi.fetch_audio("hi", "coquitts", "en")


def test_fetch_audio_returns_response_content_on_2xx(monkeypatch):
    class FakeResp:
        status_code = 200
        content = b"RIFFdata"
        text = ""

    monkeypatch.setattr(requests, "post", lambda *a, **kw: FakeResp())
    assert ttsapi.fetch_audio("hi", "gtts", "en") == b"RIFFdata"


def test_fetch_audio_truncates_long_error_body_in_message(monkeypatch):
    """Server error bodies bigger than 500 chars must NOT spam the exception."""
    huge = "x" * 5000

    class FakeResp:
        status_code = 500
        text = huge
        content = b""

    monkeypatch.setattr(requests, "post", lambda *a, **kw: FakeResp())
    with pytest.raises(RuntimeError) as excinfo:
        ttsapi.fetch_audio("hi", "gtts", "en")
    # Message contains at most 500 chars of the body, not all 5000.
    assert "x" * 500 in str(excinfo.value)
    assert "x" * 600 not in str(excinfo.value)
