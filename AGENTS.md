# AGENTS.md

Guidance for coding agents working in this repository. Human contributors will
find the same rules, with more background, in [CONTRIBUTING.md](CONTRIBUTING.md).

Machine-specific and non-public notes (deployment targets, account details,
working drafts) live in `CLAUDE.local.md` next to this file. It is gitignored
and absent in a fresh clone; read it when it is present.

## Project

`text-to-speech` puts several speech-synthesis engines behind one interface:
online gTTS, and offline pyttsx3/espeak, Piper, Silero, Kokoro, Coqui XTTS
(the Idiap community fork) and Bark. The same code is reachable four ways:

- CLIs: `ttsgen` (synthesize locally), `ttsapi` (the synthesis and output
  flags of `ttsgen` against a remote server; it has no `-I`, `-n`, `-m`, `-w`),
  `ttsplay` (play audio bytes from stdin), `ttsrec` (record a voice sample for
  XTTS cloning).
- Python: `libs.api.text_to_speech_bytes(text, engine, language, voice)` and
  friends.
- HTTP: `ttssrv`, its own REST API under `/api/*` plus an OpenAI-compatible
  API under `/v1/*`.
- Web UI: `ttswww`, a Vue 2 app without a build step served by nginx.

Engines load dynamically: only those whose dependencies are installed become
available.

## Layout

| Path | Contents |
| --- | --- |
| `engines/` | One module per engine; `engines/__init__.py` is the dynamic loader. |
| `libs/` | Shared core: `api.py` (public API), `tools.py` (validation, defaults), `audio.py` (WAV/MP3 sniffing), `cli.py` (chunking, output), `config.py` (config precedence), `models.py` (installed models), `sample_resolver.py` (coquitts voice samples), `cached_loader.py`, `exceptions.py`, `logjson.py`, `playback.py`, `tempfiles.py`. |
| `install/` | Installers behind `ttsgen --install <engine>`. |
| `ttssrv/` | Flask server: `app1.py` (routes, pool, logging), `validators.py` (Marshmallow), `history.py`, `metrics.py`, `openai_compat.py`, `streaming.py`, `entrypoint.sh`. |
| `www/` | Web UI: `index.html`, `js/app.js` (store, router, shared helpers), `views/*.vue`, `css/main.css`. |
| `nginx/`, `docker/` | The `ttswww` nginx config and the Dockerfiles (GPU, CPU, web). |
| `tests/` | pytest suite (no models, no GPU, no network); `tests/www/` holds the node tests. |
| `docs/` | Per-engine guides and the README translations. |

## Commands

```bash
pip install -e ".[dev]"            # dev install
pre-commit install

pytest                             # Python tests
ruff check . && black --check . && mypy
npm ci && npm run lint && npm test # web UI lint and node tests

ttsgen "Hello world" -e pyttsx3 --file out.wav   # local synthesis (on Linux: apt install espeak libespeak1)
ttsgen --list                      # engines and installed models
ttsgen --install kokorotts -n      # install an engine and its models, no prompts

docker compose -f docker-compose-cpu.yml up --build -d   # server on :5000, UI on :8080 / :8443
```

CI runs `lint` (pre-commit and mypy), `test` (pytest) and `www` (npm) on every
pull request. A version tag without a `v` (`1.0.7`) triggers `release.yml`,
which publishes the GitHub Release with the `### [1.0.7]` section of
`CHANGELOG.md` and the built wheel and sdist. Bump `version` in
`pyproject.toml` first: nothing checks it against the tag.

## Architecture rules

- **Engines return bytes.** `engines/<name>.py` implements `is_available()` and
  `generate(text, config) -> bytes` (WAV or MP3) and never writes files or plays
  audio. Engine settings are read from the environment inside `generate()`, not
  at import, and engines never load config files themselves. Optional
  dependencies are imported in a `try/except ImportError` that sets a
  module-level `AVAILABLE` flag, so the module itself always imports.
- **Voices.** An engine with selectable voices implements
  `list_voices(language) -> {"voices": [...], "default": str | None}` and may add
  `"mix": True` when it accepts a mix (kokorotts: `af_bella(2)+af_sky(1)`). The
  voice listings run outside the engine pool, so `list_voices` should stay
  cheap (silerotts still loads its model there). The request voice arrives as
  `config["voice"]`; an unknown voice is a `libs.exceptions.ValidationError`
  without filesystem paths in the message, except in pyttsx3, which falls back
  to a voice of the language.
- **Threads.** The server runs requests on a thread pool. Engines load their
  model once through `libs.cached_loader.load_cached()` and serialize inference
  with a module-level lock. The engine pool (`TTS_POOL_SIZE`; 0 removes the
  cap and the warmup) bounds concurrent synthesis, and the wait queue
  (`TTS_QUEUE_SIZE`; 0 means no request waits) bounds the requests waiting
  for a busy pool.
- **Server.** Every synthesis call, the startup warmup included, goes through
  `synthesize()` in `ttssrv/app1.py`, which logs one `Synthesis` line and feeds
  `ttssrv/metrics.py`. Request validation lives in `ttssrv/validators.py`.
  Every route sits under `/api/`, `/v1/` or `/metrics` behind
  `@token_required`, except `/api/health`; the check lets everything through
  while `TTS_TOKENS` is empty, which is the default.
- **Config precedence**, strongest first: CLI flags, shell environment,
  `./ttsgen.conf`, `~/.config/ttsgen.conf`, `./.env.local`, `./.env`. Files never
  override the shell; entrypoints call `libs.config.load_config()` once. A
  server in Docker sees only what compose passes it: `./.env` and the
  `environment:` block.
- **Audio format** is detected from the bytes (`libs/audio.py`), never from the
  engine name or a file suffix.
- **Temporary files** are removed with `libs.tempfiles.safe_unlink()` on every
  exit path, failures included (a `finally` block).
- **PyTorch** is installed by the installers from the explicit index
  (`whl/cpu` or `whl/cu121`) through `install.common.install_torch_choice()`;
  the default PyPI wheels need drivers newer than many hosts have. The Docker
  images take torch from `docker/{cpu,gpu}/requirements.txt` instead.

## Conventions

- English only in code, comments, docstrings, log messages, docs, commit
  messages and pull requests; `docs/*_<LANG>.md` translations are the
  exception. Never use the em dash or the middle dot character; write a hyphen
  with a space on each side instead.
- Python: shebang, coding line and a one-line module docstring at the top,
  `main()` plus the `__main__` guard at the bottom, type hints on public
  functions, no names with a leading underscore (`unused_arg`), no `print()`
  for diagnostics, errors logged as
  `f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"`, functions over
  classes, no decorative comment separators.
- Web UI: Vue 2.7 from `www/vendor` (no build step, components loaded by
  httpVueLoader), short labels of one to three words and no explanatory text on
  screens, solid Bootstrap buttons (never `btn-outline-*`) with at least 85px
  of content width (`.btn-w85`),
  SAVE next to CLOSE in a dialog footer, colors only through the palette tokens
  in `css/main.css`.
- Tests never download models or touch a GPU: optional dependencies are faked in
  `sys.modules`. A bug fix comes with a test that fails before it.
- Keep changes surgical: no drive-by reformatting or refactoring.
- One topic per branch and pull request, an entry under `### [Unreleased]` in
  `CHANGELOG.md` (three hashes: `release.yml` reads that level), squash merge. Commit messages and pull request descriptions
  carry no tool-attribution trailers.
