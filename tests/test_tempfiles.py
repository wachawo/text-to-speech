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
    target = tmp_path / "ghost.tmp"
    assert not target.exists()
    assert safe_unlink(str(target)) is True


def test_removes_existing_file(tmp_path):
    target = tmp_path / "real.tmp"
    target.write_bytes(b"data")
    assert safe_unlink(str(target)) is True
    assert not target.exists()


def test_accepts_pathlib_path(tmp_path):
    target = tmp_path / "via_path.tmp"
    target.write_bytes(b"x")
    assert safe_unlink(target) is True
    assert not target.exists()


def test_filenotfounderror_during_unlink_returns_true(tmp_path, monkeypatch):
    """Race where the file disappears between exists() and unlink()."""
    target = tmp_path / "racy.tmp"
    target.write_bytes(b"x")

    def vanish(path):
        raise FileNotFoundError(path)

    monkeypatch.setattr(os, "unlink", vanish)
    assert safe_unlink(str(target)) is True


def test_unix_permission_error_returns_false_with_warning(tmp_path, monkeypatch, caplog):
    """On non-Windows, a PermissionError is permanent — no retry, log warning."""
    target = tmp_path / "blocked.tmp"
    target.write_bytes(b"x")
    monkeypatch.setattr(tempfiles, "IS_WINDOWS", False)
    call_count = {"n": 0}

    def deny(path):
        call_count["n"] += 1
        raise PermissionError("EACCES")

    monkeypatch.setattr(os, "unlink", deny)
    with caplog.at_level("WARNING"):
        result = safe_unlink(str(target))
    assert result is False
    assert call_count["n"] == 1, "Unix path must NOT retry on PermissionError"
    assert any("Cannot delete" in rec.message for rec in caplog.records)


def test_windows_permission_error_retries_until_success(tmp_path, monkeypatch):
    """On Windows, transient PermissionError should be retried `retries` times."""
    target = tmp_path / "winlocked.tmp"
    target.write_bytes(b"x")
    monkeypatch.setattr(tempfiles, "IS_WINDOWS", True)
    monkeypatch.setattr(tempfiles.time, "sleep", lambda s: None)  # no real waiting

    state = {"calls": 0, "real_unlink": os.unlink}

    def flaky(path):
        state["calls"] += 1
        if state["calls"] < 3:
            raise PermissionError("locked")
        state["real_unlink"](path)

    monkeypatch.setattr(os, "unlink", flaky)
    assert safe_unlink(str(target), retries=5) is True
    assert state["calls"] == 3


def test_oserror_retried_then_gives_up(tmp_path, monkeypatch, caplog):
    """Persistent OSError exhausts retries → False with summary in log."""
    target = tmp_path / "stuck.tmp"
    target.write_bytes(b"x")
    monkeypatch.setattr(tempfiles.time, "sleep", lambda s: None)
    state = {"calls": 0}

    def always_fail(path):
        state["calls"] += 1
        raise OSError("EBUSY")

    monkeypatch.setattr(os, "unlink", always_fail)
    with caplog.at_level("WARNING"):
        result = safe_unlink(str(target), retries=3)
    assert result is False
    assert state["calls"] == 3
    assert any("after 3 attempts" in rec.message for rec in caplog.records)
