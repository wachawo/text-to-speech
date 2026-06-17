## Changelog

### [Unreleased]

#### Added
- **Streaming synthesis — `/api/tts?stream=true`.** Synthesizes the text one
  chunk at a time (via `libs.cli.chunk_text`) and streams audio with chunked
  transfer encoding, so a client hears the first sentence without waiting for the
  whole utterance. WAV engines emit a single streaming WAV (one header with
  placeholder sizes + concatenated PCM); gtts (MP3) concatenates per-chunk bytes.
  One engine-pool slot is held for the duration of the stream. New
  `TTS_STREAM_MAX_CHARS` env (default 200) controls chunk size. Works for both
  `GET` and `POST`. New module `ttssrv/streaming.py` + `tests/test_stream.py`.

#### Changed
- **Docker layout — compose files moved back to the repo root**
  (`docker-compose.yml` for GPU, `docker-compose-cpu.yml` for CPU);
  Dockerfiles + requirements stay under `docker/{cpu,gpu}/`. Compose now
  auto-discovers the root `.env` for `${VAR}` interpolation — no
  `--env-file` flag needed. `TTS_PORT` drives the bind end-to-end
  (`${TTS_PORT}:${TTS_PORT}` plus the healthcheck), so the container is
  reachable on the exact port set in `.env`.

#### Fixed
- `ttssrv` logging: removed a stray `logging.basicConfig()` in `libs/api.py`
  that grabbed the root logger and turned each entrypoint's own
  `basicConfig(**LOGGING)` into a no-op — losing the unified format and all
  INFO lines, including the uvicorn startup banner. Server logs (uvicorn
  included) now share the standard `YYYY-MM-DD HH:MM:SS.mmm [LEVEL]` format.
- Silenced the `pkg_resources` deprecation warning that pygame prints at
  import time.

### [1.0.2] — 2026-05-11

#### Changed
- **BREAKING — env-var naming convention normalised to `<ENGINE>_MODELS`.**
  In 1.0.1 `engines/{pipertts,silerotts,barktts}.py` already read
  `<ENGINE>_MODELS`, while `engines/{coquitts,kokorotts}.py` read
  `<ENGINE>_PATH`, and config examples (`env.example`,
  `ttsgen.conf.example`, `README.md`, `docker/{cpu,gpu}/docker-compose.yml`)
  used `<ENGINE>_PATH` for all five. Result: pipertts/silerotts/barktts
  silently ignored their config-file override and fell back to the
  built-in default. Canonical name is now **`<ENGINE>_MODELS`** across
  the board (engine code, installers, `ttsgen.py`, `libs/config.py`,
  tests, docker compose, env templates, README, per-engine docs). Users
  with `KOKOROTTS_PATH=...` or `COQUITTS_PATH=...` in `.env` /
  `~/.config/ttsgen.conf` must rename to `..._MODELS`. **No alias
  support.**

#### Fixed (docs)
- `docs/PIPERTTS.md` — translated from Russian to English; model paths
  switched from upstream-style `~/.local/share/piper/voices` to this
  project's canonical `cache/pipertts/` with priority resolution
  documented; obsolete `piper --download-dir` invocation removed.
- `docs/ENGINES.md` — `### piper.py` section renamed to `pipertts.py`,
  `--engine piper` → `--engine pipertts`, dead link `docs/PIPER.md` →
  `docs/PIPERTTS.md`; `pip install TTS` → `pip install "coqui-tts[codec]"`
  (Idiap fork; upstream `TTS` package is abandoned); removed misleading
  "Optional Functions" `to_file()`/`to_bytes()` block in favour of an
  explicit "engines return bytes only" contract note; Custom-engine
  example fixed to use `from libs.exceptions import ...` (was a broken
  `sys.path.insert(...)` + `from exceptions import` that triggers
  `ModuleNotFoundError`); folder listing updated to include
  `kokorotts.py` and to drop the never-existed `custom.py` stub.
- `docs/COQUITTS.md` — `COQUI_TTS_CACHE_DIR` (upstream Coqui var) renamed
  to this project's canonical `COQUITTS_MODELS`; all `pip install TTS`
  (abandoned upstream package) replaced with `pip install "coqui-tts[codec]"`
  pinned alongside `transformers>=4.46,<5.0`.
- `docs/BARKTTS.md` — engine name typos fixed across the file
  (`engine="bark"` → `engine="barktts"`, `TTS_ENGINE=bark` →
  `TTS_ENGINE=barktts`, `engines/bark.py` → `engines/barktts.py`, `piper`
  → `pipertts` in alternative-engine suggestions); added explicit note
  that `BARKTTS_MODELS=...` does **not** relocate Bark's hard-coded
  `~/.cache/suno/bark_v0/` cache — symlink the directory instead.
- `README.md` — engine-count update ("Six" → "Seven engines"); git-tag
  example bumped (`v0.2.1` → `v1.0.2`); project-structure listing
  reflects current files (added `kokorotts.py` to `engines/` and
  `install/`, added `KOKOROTTS.md` to `docs/`, replaced non-existent
  `test_tts.py` with `tests/` directory note); test count updated
  (`162` → `260`) and coverage figure refreshed (`~56%` project / `~72%`
  non-engine → `~76%` project-wide); removed self-contradicting claim
  that `ttssrv` is a console-script (it is not registered in
  `pyproject.toml:[project.scripts]`); Documentation section now
  includes `docs/KOKOROTTS.md` and marks `REVIEW.md` / `ROADMAP.md` as
  local-only (gitignored).

### [1.0.1] — 2026-05-11

#### Added
- Kokoro TTS engine (`engines/kokorotts.py`) — offline ONNX synthesis via
  `kokoro-onnx`, multi-language (en/fr/it/ja/zh/es/hi/pt), per-language default
  voices and `KOKOROTTS_VOICE` / `KOKOROTTS_SPEED` overrides.
- `ttsgen --install kokorotts` installer — picks `onnxruntime` (CPU) or
  `onnxruntime-gpu`, installs `kokoro-onnx` + `soundfile`, downloads
  `kokoro-v1.0.onnx` and `voices-v1.0.bin` from the upstream `nazdridoy/kokoro-tts`
  v1.0.0 release. Note: downloads are **not** SHA256-verified (upstream
  release does not publish hashes). Compare with the Piper installer which
  does verify.
- `docs/KOKOROTTS.md` setup and usage guide.
- `tests/test_kokorotts.py` — unit coverage for `get_models_directory()`,
  `get_model_paths()`, and `generate()` happy/error paths with a faked
  `kokoro_onnx`.
- `ttssrv/entrypoint.sh` — lazy engine install on container startup
  (`install.run(TTS_ENGINE, non_interactive=True)`). First start of a
  non-default engine downloads its wheels into a `PYTHONUSERBASE` volume,
  so `healthcheck.start_period` is bumped to 600s.

#### Changed
- **BREAKING — model cache layout:** per-engine directories
  `.pipertts/`, `.silerotts/`, `.coquitts/`, `.barktts/` are replaced by a
  single `cache/<engine>/` root. Existing installs must `mv .pipertts
  cache/pipertts` (and the same for the other three) or re-run
  `ttsgen --install <engine>`. Env-var overrides
  (`PIPERTTS_MODELS=` etc.) still work unchanged.
- **BREAKING — Docker layout:** `docker-compose.yml` and
  `docker-compose-cpu.yml` at the repo root are removed in favour of
  `docker/{cpu,gpu}/docker-compose.yml` + Dockerfile + requirements.txt.
  Use `docker compose -f docker/gpu/docker-compose.yml up` (or `cpu`).
  Build context is the repo root.
- **BREAKING — server-side auth env var rename:** Docker compose now
  passes `TTS_TOKENS` (comma-separated allow-list) instead of
  `TTS_TOKEN`. A pre-existing `TTS_TOKEN=...` in `.env` is silently
  ignored by the new compose files — rename to `TTS_TOKENS=...`.
  The client-side `TTS_TOKEN=` env (used by `ttsapi`) is unchanged.
- **`ttsgen --list` output format:** switched from a free-form indented
  block to a fixed-width `ENGINE STATUS MODEL` table for grep-friendly
  diffing.
- Docker images now bake the heavy ML stack (`torch`/`torchaudio`/
  `coqui-tts`/`transformers`) at build time via
  `docker/{cpu,gpu}/requirements.txt` and use `uv` instead of pip for
  faster builds with a BuildKit cache mount.
- `install_torch_choice()` short-circuits when `torch` is already
  importable — protects Docker GPU builds from being downgraded to CPU
  wheels by an interactive install.
- `warn_no_venv()` now skips the prompt entirely in `non_interactive=True`
  mode (required for the Docker entrypoint).

### [1.0.0] — 2026-05-09

First public release. Highlights of this release:

#### Added
- Universal CLI suite: `ttsgen` (synthesize), `ttsplay` (playback),
  `ttsrec` (record voice sample), `ttsapi` (remote client),
  `ttssrv` (HTTP server, Docker-only).
- Single canonical install flow for optional engines via
  `ttsgen --install <engine>` (piper, silero, coqui, bark).
- `.env.local` local override on top of `.env`, supported in every
  entry point.
- HTTP server with structured error responses, request IDs, and
  pre-warmed engine pool.
- Producer/consumer audio pipeline that streams playback while the
  next chunk is being generated and propagates per-chunk failures
  with a non-zero exit code.
- Per-engine text-length limits so callers fail fast on inputs the
  engine cannot reasonably handle.
- Piper installer that fetches the upstream voice manifest and
  verifies download checksums.
- Comprehensive test suite, runs via `pytest`. `pre-commit` hooks
  for `black`, `ruff`, and `pytest`.

#### Changed
- Slimmed packaging: only the `[dev]` extras group is published;
  optional engine dependencies are installed through
  `ttsgen --install`.
- Docker compose images bind-mount the project sources for fast
  iteration; `COQUITTS_SAMPLE` is environment-driven (default
  `default.wav`).
- Docker images now include `ffmpeg` for `torchaudio` MP3/M4A
  support.

