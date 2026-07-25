#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for libs.tempfiles.safe_unlink — cross-platform delete with retry.

Pins the contract:
- True if the file is gone after the call (deleted or already absent).
- False if a non-Windows PermissionError is hit (no retry, just a warning).
- Retries on transient OSError; ultimately False if still failing.
- Accepts both str and pathlib.Path.
"""

import os

from libs import tempfiles
from libs.tempfiles import safe_unlink


def test_returns_true_when_file_already_absent(tmp_path):
    """Deleting a path that never existed is reported as success, not an error."""
    target = tmp_path / "ghost.tmp"
    assert not target.exists()
    assert safe_unlink(str(target)) is True


def test_removes_existing_file(tmp_path):
    """An ordinary file is deleted and success is reported."""
    target = tmp_path / "real.tmp"
    target.write_bytes(b"data")
    assert safe_unlink(str(target)) is True
    assert not target.exists()


def test_accepts_pathlib_path(tmp_path):
    """A pathlib.Path argument works exactly like the equivalent str."""
    target = tmp_path / "via_path.tmp"
    target.write_bytes(b"x")
    assert safe_unlink(target) is True
    assert not target.exists()


def test_filenotfounderror_during_unlink_returns_true(tmp_path, monkeypatch):
    """A file vanishing between exists() and unlink() still counts as success."""
    target = tmp_path / "racy.tmp"
    target.write_bytes(b"x")

    def vanish(path):
        """Simulate the file disappearing just before unlink runs."""
        raise FileNotFoundError(path)

    monkeypatch.setattr(os, "unlink", vanish)
    assert safe_unlink(str(target)) is True


def test_unix_permission_error_returns_false_with_warning(tmp_path, monkeypatch, caplog):
    """On non-Windows a PermissionError is treated as permanent: no retry, one warning, False."""
    target = tmp_path / "blocked.tmp"
    target.write_bytes(b"x")
    monkeypatch.setattr(tempfiles, "IS_WINDOWS", False)
    call_count = {"n": 0}

    def deny(path):
        """Always refuse the delete and count how often it was attempted."""
        call_count["n"] += 1
        raise PermissionError("EACCES")

    monkeypatch.setattr(os, "unlink", deny)
    with caplog.at_level("WARNING"):
        result = safe_unlink(str(target))
    assert result is False
    assert call_count["n"] == 1, "Unix path must NOT retry on PermissionError"
    assert any("Cannot delete" in rec.message for rec in caplog.records)


def test_windows_permission_error_retries_until_success(tmp_path, monkeypatch):
    """On Windows a transient PermissionError is retried until the delete succeeds."""
    target = tmp_path / "winlocked.tmp"
    target.write_bytes(b"x")
    monkeypatch.setattr(tempfiles, "IS_WINDOWS", True)
    monkeypatch.setattr(tempfiles.time, "sleep", lambda s: None)  # no real waiting

    state = {"calls": 0, "real_unlink": os.unlink}

    def flaky(path):
        """Fail the first two attempts, then delegate to the real unlink."""
        state["calls"] += 1
        if state["calls"] < 3:
            raise PermissionError("locked")
        state["real_unlink"](path)

    monkeypatch.setattr(os, "unlink", flaky)
    assert safe_unlink(str(target), retries=5) is True
    assert state["calls"] == 3


def test_oserror_retried_then_gives_up(tmp_path, monkeypatch, caplog):
    """A persistent OSError exhausts the retry budget and is summarised in the log."""
    target = tmp_path / "stuck.tmp"
    target.write_bytes(b"x")
    monkeypatch.setattr(tempfiles.time, "sleep", lambda s: None)
    state = {"calls": 0}

    def always_fail(path):
        """Fail every delete attempt and count the attempts."""
        state["calls"] += 1
        raise OSError("EBUSY")

    monkeypatch.setattr(os, "unlink", always_fail)
    with caplog.at_level("WARNING"):
        result = safe_unlink(str(target), retries=3)
    assert result is False
    assert state["calls"] == 3
    assert any("after 3 attempts" in rec.message for rec in caplog.records)
