#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""End-to-end CLI smoke test for ttsgen.

Spawns ttsgen.py as a real subprocess with the gtts package stubbed (no
network), verifies the file output mode produces a non-empty audio file
and exits 0. Also asserts a non-zero exit when the stub raises, exercising
the new sentinel error propagation in libs.cli.rec_worker.
"""

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TTSGEN = REPO_ROOT / "ttsgen.py"
STUBS_DIR = Path(__file__).resolve().parent / "stubs"


def _stubbed_env(extra: dict | None = None) -> dict:
    """Return os.environ + PYTHONPATH prefix that resolves `import gtts` to our stub."""
    env = os.environ.copy()
    pp = str(STUBS_DIR)
    if "PYTHONPATH" in env:
        pp = pp + os.pathsep + env["PYTHONPATH"]
    env["PYTHONPATH"] = pp
    # Force the engine + disable any user config files leaking in
    env["TTS_ENGINE"] = "gtts"
    env["TTS_LANGUAGE"] = "en"
    if extra:
        env.update(extra)
    return env


def _run_ttsgen(args: list[str], env: dict, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TTSGEN), *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(REPO_ROOT),
    )


def test_ttsgen_file_output_writes_audio(tmp_path):
    out = tmp_path / "out.mp3"
    env = _stubbed_env({"AUDIO_DIRECTORY": str(tmp_path)})
    result = _run_ttsgen(
        ["Hello", "--engine", "gtts", "--output", "file", "--file", str(out)],
        env=env,
    )
    assert result.returncode == 0, f"ttsgen exit {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    # The file mode auto-numbers chunks: <base>_001.mp3 — so look for any sibling.
    siblings = list(tmp_path.glob("out_*.mp3")) + ([out] if out.exists() else [])
    assert siblings, f"no output file produced; tmp dir contents: {list(tmp_path.iterdir())}"
    chosen = max(siblings, key=lambda p: p.stat().st_size)
    assert chosen.stat().st_size > 0


def test_ttsgen_engine_failure_returns_nonzero(tmp_path):
    """Sentinel error propagation: rec_worker failure → exit 3."""
    out = tmp_path / "out.mp3"

    # Stub that raises inside write_to_fp — propagates as TTSException through
    # engines/gtts.py and into rec_worker, which now surfaces it via failures.
    failing_stub = STUBS_DIR.parent / "stubs_failing"
    failing_stub.mkdir(exist_ok=True)
    pkg = failing_stub / "gtts"
    pkg.mkdir(exist_ok=True)
    (pkg / "__init__.py").write_text(
        "class gTTS:\n"
        "    def __init__(self, *a, **kw): pass\n"
        "    def write_to_fp(self, fp):\n"
        "        raise RuntimeError('synthetic gTTS network failure')\n"
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(failing_stub) + os.pathsep + env.get("PYTHONPATH", "")
    env["TTS_ENGINE"] = "gtts"

    try:
        result = _run_ttsgen(
            ["Hello world", "--engine", "gtts", "--output", "file", "--file", str(out)],
            env=env,
        )
    finally:
        # Clean stub
        (pkg / "__init__.py").unlink(missing_ok=True)
        try:
            pkg.rmdir()
            failing_stub.rmdir()
        except OSError:
            pass

    assert result.returncode == 3, (
        f"expected exit 3 for chunk failure, got {result.returncode}\n" f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert "synthetic gTTS network failure" in result.stderr or "Chunk" in result.stderr


def test_ttsgen_help_runs(tmp_path):
    """Cheapest CLI smoke: --help should exit 0 and print usage."""
    env = _stubbed_env()
    result = _run_ttsgen(["--help"], env=env, timeout=10)
    assert result.returncode == 0
    assert "Usage" in result.stdout or "usage" in result.stdout
