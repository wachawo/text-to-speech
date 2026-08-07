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

# The repository root must be on sys.path before `ttsapi` is imported,
# so that import deliberately stays below this insert (E402 is expected).
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Local imports
import ttsapi  # noqa: E402

# read_text_file


def test_read_text_file_reads_and_strips(tmp_path):
    """Surrounding whitespace and newlines are trimmed from the file content."""
    f = tmp_path / "in.txt"
    f.write_text("  hello world  \n")
    assert ttsapi.read_text_file(str(f)) == "hello world"


def test_read_text_file_raises_on_missing(tmp_path):
    """A non-existent path fails with FileNotFoundError instead of an empty read."""
    with pytest.raises(FileNotFoundError, match="Not a file"):
        ttsapi.read_text_file(str(tmp_path / "nope.txt"))


def test_read_text_file_raises_on_empty(tmp_path):
    """A file holding only whitespace is rejected as empty input."""
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
    """Invoking the CLI with no arguments exits rather than synthesizing nothing."""
    parser = ttsapi.parse_arguments()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parser_text_and_input_are_mutually_exclusive():
    """Positional text and `-i FILE` cannot be supplied together."""
    parser = ttsapi.parse_arguments()
    with pytest.raises(SystemExit):
        parser.parse_args(["hello", "-i", "file.txt"])


def test_parser_accepts_positional_text():
    """Plain positional text populates `text` and leaves the other input modes off."""
    parser = ttsapi.parse_arguments()
    args = parser.parse_args(["hello"])
    assert args.text == "hello"
    assert args.text_file is None
    assert args.list is False


def test_parser_accepts_input_file():
    """`-i` stores the input path under `text_file`."""
    parser = ttsapi.parse_arguments()
    args = parser.parse_args(["-i", "input.txt"])
    assert args.text_file == "input.txt"


def test_parser_accepts_list_flag():
    """`--list` is a standalone flag that needs no text argument."""
    parser = ttsapi.parse_arguments()
    args = parser.parse_args(["--list"])
    assert args.list is True


def test_parser_file_flag_with_explicit_path():
    """`-f PATH` keeps the caller-provided output path verbatim."""
    parser = ttsapi.parse_arguments()
    args = parser.parse_args(["hello", "-f", "out.mp3"])
    assert args.file == "out.mp3"


def test_parser_file_flag_without_path_yields_empty_string():
    """`--file` (no value) is the magic 'auto-name' marker."""
    parser = ttsapi.parse_arguments()
    args = parser.parse_args(["hello", "-f"])
    assert args.file == ""


def test_parser_default_language_is_en():
    """Omitting `--language` falls back to English."""
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
    """The verbose/quiet flag pair maps to the expected root logger level."""
    ttsapi.setup_logging(verbose=verbose, quiet=quiet)
    assert logging.getLogger().level == expected_level


# list_remote_engines — exit code + output format


def test_list_remote_engines_marks_default_with_asterisk(monkeypatch, capsys):
    """The server's default engine is flagged with an asterisk, the rest are indented."""
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
    """An unreachable server yields exit code 1 and an error log, not a traceback."""

    def boom():
        """Simulate a connection failure while fetching the engine list."""
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
    """A 4xx response is turned into a RuntimeError naming the status code."""

    class FakeResp:
        """Canned 422 response carrying a structured error body."""

        status_code = 422
        text = '{"error":"voice_sample_missing","message":"..."}'
        content = b""

    monkeypatch.setattr(requests, "post", lambda *a, **kw: FakeResp())
    with pytest.raises(RuntimeError, match=r"422"):
        ttsapi.fetch_audio("hi", "coquitts", "en")


def test_fetch_audio_returns_response_content_on_2xx(monkeypatch):
    """A successful response hands back the raw audio body untouched."""

    class FakeResp:
        """Canned 200 response carrying WAV bytes."""

        status_code = 200
        content = b"RIFFdata"
        text = ""

    monkeypatch.setattr(requests, "post", lambda *a, **kw: FakeResp())
    assert ttsapi.fetch_audio("hi", "gtts", "en") == b"RIFFdata"


def test_fetch_audio_truncates_long_error_body_in_message(monkeypatch):
    """Server error bodies bigger than 500 chars must NOT spam the exception."""
    huge = "x" * 5000

    class FakeResp:
        """Canned 500 response with an oversized error body."""

        status_code = 500
        text = huge
        content = b""

    monkeypatch.setattr(requests, "post", lambda *a, **kw: FakeResp())
    with pytest.raises(RuntimeError) as excinfo:
        ttsapi.fetch_audio("hi", "gtts", "en")
    # Message contains at most 500 chars of the body, not all 5000.
    assert "x" * 500 in str(excinfo.value)
    assert "x" * 600 not in str(excinfo.value)
