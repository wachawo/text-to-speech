# Contributing

Thanks for taking the time to contribute. This page covers the local setup,
the checks a pull request has to pass, and the conventions the code follows.

## Development setup

Python 3.11 or newer is required.

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

The `[dev]` extra installs the linters, `pytest`, and the web stack
(`Flask`, `uvicorn`, `marshmallow`) so the `ttssrv` tests run without Docker.
Engine dependencies (torch, piper, coqui, bark) are not part of it: the tests
mock them, and `ttsgen --install <engine>` is the only way to install one.

Playback needs `libportaudio2` and `libsndfile1` on Linux (see the `apt-get`
step in `.github/workflows/ci.yml`).

## Running the checks

Python:

```bash
pytest                      # tests, no models, no GPU, no network
ruff check .                # lint
black --check .             # formatting
mypy                        # type check, targets come from pyproject.toml
pre-commit run --all-files  # black + ruff, the same hooks CI runs
```

Web UI (Node 18 or newer):

```bash
npm ci
npm run lint                # eslint on www/
npm test                    # node --test tests/www/
```

CI runs the same commands: job `lint` (pre-commit and mypy), job `test`
(pytest) and job `www` (npm).

## Adding an engine

Engines are plugins. There is no registry: `engines/__init__.py` imports every
`engines/<name>.py` it finds, and an engine is listed when its `is_available()`
returns `True`. A module needs two functions:

```python
def is_available() -> bool:
    """Return True when the optional dependency imports."""

def generate(text: str, config: dict) -> bytes:
    """Return MP3 or WAV bytes for `text`."""
```

Rules that keep the layers apart:

- Engines return bytes only. File output and playback belong to `libs/api.py`
  and `libs/playback.py`; an engine never writes a file or plays audio.
- Import the optional dependency inside a `try/except ImportError` at module
  level and set an `AVAILABLE` flag (see `engines/gtts.py`). A missing
  dependency disables the engine; it must not break `import engines`.
- Read engine-specific settings (`<NAME>_MODEL`, `<NAME>_PATH`, ...) from the
  environment inside `generate()`, not at import time, so CLI flags and config
  files take effect without a re-import.
- Raise `libs.exceptions.TTSException` (or a subclass) on failure.

A new engine ships with:

- `docs/<NAME>.md` describing installation, models and the config keys;
- an installer module in `install/` if it needs models or a specific torch
  wheel index;
- tests in `tests/test_<name>.py` with the dependency mocked
  (`tests/test_pipertts.py` shows the pattern: a fake module injected into
  `sys.modules`, then `importlib.reload`). Tests never download models, never
  touch the network and never need a GPU.

## Branches and pull requests

- Branch from `main`. One pull request per topic; unrelated changes go in
  separate PRs.
- Add an entry under `[Unreleased]` in `CHANGELOG.md`
  (Keep a Changelog format: Added / Changed / Fixed / Removed).
- Fill in the pull request template: what changed, why, how it was tested.
- PRs are squash-merged, so the PR title becomes the commit message on `main`.
- Releases are tags without a `v` prefix (`1.0.6`). Pushing a tag builds the
  wheel and sdist and publishes a GitHub Release with the matching CHANGELOG
  section. There is no PyPI release.

## Style

- English only, in code, comments, docstrings, log messages, docs and commit
  messages. The exception is `docs/*_<LANG>.md` translations.
- Use a hyphen with spaces (` - `) where you would write a dash. The em dash
  and middle dot characters do not appear anywhere in the repository.
- No `print()` for diagnostics; use `logging.getLogger(__name__)`. The only
  `print()` calls are for shell-pipeable output (a file name on stdout) and
  the `ttsgen --list` table.
- Log errors as `f"{type(exc).__name__}: {str(exc)}\n{traceback.format_exc()}"`.
- Names do not start with an underscore, including callbacks and unused
  arguments (`unused_arg`, not `_arg`). Dunder methods are the only exception.
- Type hints on public functions. Functions over classes; classes are for
  models and framework subclasses.
- Every module starts with the shebang, the `# -*- coding: utf-8 -*-` line
  and a one-line docstring, and ends with `main()` plus the
  `if __name__ == "__main__":` guard.
- Formatting is `black` with line length 128; `ruff` runs with the rule set
  in `pyproject.toml`. Do not add `noqa` pragmas for rules that are already
  ignored there.

`docs/ENGINES.md` and the per-engine guides in `docs/` describe how the
existing engines are wired.

## Security issues

Do not open a public issue for a vulnerability. See [SECURITY.md](SECURITY.md).
