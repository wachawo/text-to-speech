#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The ttsplay and ttsrec console scripts return exit code 1 on Ctrl+C or a stray error, never a raw traceback."""

import sys
from pathlib import Path

import pytest

# The repository root must be on sys.path before the scripts are imported,
# so those imports deliberately stay below this insert (E402 is expected).
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Local imports
import ttsplay  # noqa: E402
import ttsrec  # noqa: E402


def raiser(raised):
    """Return a callable that raises `raised` whatever it is called with."""

    def fail(*args, **kwargs):
        """Raise the configured exception."""
        raise raised

    return fail


@pytest.mark.parametrize("raised", [KeyboardInterrupt, RuntimeError("config broke")])
def test_ttsplay_main_catches_config_errors(monkeypatch, raised):
    """A failure while loading config is an exit code, like every later failure."""
    monkeypatch.setattr(ttsplay, "load_config", raiser(raised))
    try:
        rc = ttsplay.main()
    except BaseException as exc:
        pytest.fail(f"{type(exc).__name__} escaped main()")
    assert rc == 1


@pytest.mark.parametrize("raised", [KeyboardInterrupt, RuntimeError("path broke")])
def test_ttsrec_main_catches_errors_outside_recording(monkeypatch, tmp_path, raised):
    """Resolving the output path happens outside the recording try block and must not leak a traceback."""
    monkeypatch.setattr(sys, "argv", ["ttsrec", str(tmp_path / "voice.wav"), "--yes"])
    monkeypatch.setattr("libs.config.load_config", lambda: None)
    monkeypatch.setattr(ttsrec, "resolve_output_path", raiser(raised))
    try:
        rc = ttsrec.main()
    except BaseException as exc:
        pytest.fail(f"{type(exc).__name__} escaped main()")
    assert rc == 1
