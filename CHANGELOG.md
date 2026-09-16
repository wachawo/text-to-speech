## Changelog

### [Unreleased]

#### Added
- `ttssrv` logs one line per engine call (`Synthesis: engine= language= voice=
  chars= bytes= ms= ok`, or `failed <Exception>`), including one per chunk of a
  streamed response, so a slow engine can be told apart from a request that
  waited for a pool slot; the request line still carries the total time.
- OpenAI-compatible audio API: `POST /v1/audio/speech` (`model` is an engine
  name or `tts-1`, `voice`, `response_format` mp3/wav/pcm/opus/flac/aac with
  ffmpeg transcoding, `speed`, and a `language` extension), `GET /v1/models`
  and `GET /v1/audio/voices`; errors use the OpenAI shape. Open WebUI,
  SillyTavern and the official SDKs work with `base_url` pointing at the server.
  nginx proxies `/v1/` next to `/api/`.
- `TTS_QUEUE_SIZE` (default 8): how many synthesis requests may wait for a
  free engine slot; any more are answered 503 at once, so a burst of `/api/tts`
  cannot hold every server thread. `/api/health` reports it as `queue_size`.
- `libs/audio.py`: one sniffer (`is_wav`, `is_mp3`, `audio_format`,
  `audio_mime`, `extension_for`) used by the CLIs, the library, playback, the
  history store and the server.
- `CONTRIBUTING.md`, `SECURITY.md`, issue and pull request templates, a
  Dependabot config, and a release workflow that publishes a GitHub Release
  with the matching CHANGELOG section and the built wheel and sdist on every
  version tag.
- Frontend checks: `npm run lint` (eslint with eslint-plugin-vue) and
  `npm test` (node tests for the WAV encoder and resampler, template
  compilation of every `.vue`, a palette check on the CSS); CI runs them in a
  `www` job and runs mypy in `lint`.
- README: Configuration table, API reference, Security notes, the
  `cp env.example .env` step and the CDI prerequisite for the GPU compose file.

#### Changed
- Frontend lint moved to eslint 10 with a flat config (`eslint.config.js`) and
  eslint-plugin-vue 10 in its Vue 2 preset; Dependabot no longer proposes a
  Vue 3 bump, the UI runs on the vendored Vue 2.7 and `vue-template-compiler`
  must match it.
- Config precedence is now, strongest first: CLI flags, shell environment,
  `./ttsgen.conf`, `~/.config/ttsgen.conf`, `./.env.local`, `./.env`. Every
  file loads with `override=False`, so no file beats the shell or a flag, and
  `.env` is read only from the current directory. Engines no longer load config
  at import time; the entrypoints do it once.
- `ttsgen --file NAME` and `ttsapi --file NAME` write exactly `NAME` (chunks
  are concatenated) instead of `NAME_001`, `NAME_002`; auto-named files take
  their extension from the audio header; `--language` falls back to
  `TTS_LANGUAGE`; `-o file` honours `-d`; saved files follow the umask instead
  of being created mode 0600.
- Engines are safe under the multithreaded server: model caches load once
  behind a lock, synthesis inside coquitts, silerotts, kokorotts, barktts and
  pyttsx3 is serialized per engine, environment variables are set once at load
  time instead of on every call, and pyttsx3 picks its voice by `voice` or
  `language`.
- The web UI fetches history and sample audio through the API client, so
  playback and downloads work when `TTS_TOKENS` is set; the curl card prints
  `$TTS_TOKEN` instead of the token; the language list, the engine and voice
  catalogues, the wait queue and the waiting banner live in one place each;
  ~100 lines of unused CSS are gone.
- `docker compose up` works without a `.env` file; the `.env` bind mount is
  gone (the env file already carries every key).
- Web stack and dev tooling moved off their 2023 pins: Flask 3.1, flask-cors
  6.0, marshmallow 3.26, uvicorn 0.53, mypy 2.x, black 26, ruff 0.16;
  third-party GitHub Actions are pinned by commit SHA.
- Engine docs use the installed `ttsgen` command, the `cu121` torch index,
  Python 3.11+, the maintained Coqui fork, one section on where models live,
  and no longer suggest editing engine source to pick a voice.

#### Removed
- `gunicorn` and `ttssrv/gu.py`: the server runs under uvicorn and nothing
  referenced them. `types-PyYAML`: no YAML in the code.

#### Fixed
- `text_to_speech_file(filename=None)` saved gTTS output as `.wav`: the sniffer
  knew only one MP3 frame-sync byte pattern.
- Bark wrote float32 WAV, which the streaming path and the history duration
  reader could not parse; it is int16 PCM now.
- A failure inside the streaming generator is logged with its traceback.
- The Confirm dialog left the page unscrollable when the route changed while it
  was open; a screen that fails to load reports the reason instead of a blank
  "Screen unavailable".
- `ttssrv` served the Flask app through asgiref's `WsgiToAsgi`, which runs every
  request on one shared thread and guards it with a contextvar that a keep-alive
  connection could carry into the next request: that request then failed with
  `Single thread executor already being used, would deadlock` before reaching
  Flask, as a plain-text 500. A long synthesis also blocked `/api/health`, and
  `TTS_POOL_SIZE` above 1 never allowed parallel synthesis. The server now uses
  uvicorn's own WSGI bridge on a thread pool sized from `TTS_POOL_SIZE` and
  `TTS_QUEUE_SIZE` plus eight threads kept for the light routes; the engine pool
  still bounds concurrency, and `asgiref` is no longer a dependency.

### [1.0.6] - 2026-09-16

#### Added
- The web UI signs in when the server has `TTS_TOKENS`: `/api/health` reports
  `auth`, the sign-in screen tries the token against `/api/engines`, keeps it in
  the browser and sends it with every request; a 401 anywhere returns to sign-in.
  The `curl` example carries that token.
- `TTS_MAX_SAMPLES` (default 100) caps the number of voice samples.

#### Changed
- A second fence behind the voice-name and history-id whitelists refuses any
  path that resolves outside the samples or history directory; engine names
  from a query string must be a plain module stem.

#### Removed
- `TTS_WWW_TOKEN`: nginx no longer injects a token into proxied requests, and
  `/ui-config.json` no longer publishes one. A deployment that relied on it
  signs in through the UI instead.

### [1.0.5] - 2026-09-16

#### Added
- `ttswww` also listens on https (`TTS_WWW_TLS_PORT`, default 8443) with a
  self-signed certificate minted into `./data/certs` on first start, so the
  microphone recording on the Voices screen works over the LAN, not only on
  localhost.
- Web UI in a new `ttswww` service (both compose files, `http://localhost:8080`,
  `TTS_WWW_PORT`): the Studio, Voices and Models screens, Vue 2 without a build
  step, served by nginx with the API proxied under `/api/`. It has no
  authentication of its own; nginx adds `TTS_WWW_TOKEN` to every proxied request.
- `GET /api/models` returns the installed / missing model rows that `ttsgen --list`
  prints; the table logic moved from `ttsgen.py` into `libs/models.py` so the
  server can reach it.
- Per-request voice for `coquitts`: `voice` in a request names a WAV in the samples
  directory (`COQUITTS_SAMPLES`, default `samples`), and `GET /api/voices?engine=coquitts`
  lists those samples with `COQUITTS_SAMPLE` as the default, plus a `samples` list
  with the size, rate, channels and seconds of each file.
- `POST /api/voices` uploads a voice sample WAV (`file`, `name`, `engine=coquitts`)
  into the samples directory; `GET /api/voices/<name>/audio?engine=coquitts` serves it
  back (inline, or as a download with `?download=1`); `DELETE /api/voices/<name>?engine=coquitts`
  removes one. Uploads are capped by `TTS_MAX_SAMPLE_BYTES` (default 16 MiB).
- Server-side generation history: `POST /api/history` synthesizes and stores the
  result, `GET /api/history`, `GET /api/history/<id>`,
  `GET /api/history/<id>/audio?download=1` and `DELETE /api/history/<id>` manage it.
  Items live as audio plus a JSON sidecar under `TTS_HISTORY_DIR` (default
  `data/history`), and the oldest are pruned past `TTS_HISTORY_MAX` (default 200).
- Settings dialog behind the gear in the header: a default engine, language and
  voice that the Studio remembers, and whether the curl example is shown. The
  choices live in the browser (`localStorage`), not on the server.
- The Studio shows a `curl` example for the current request, with a COPY button;
  it carries the `TTS_WWW_TOKEN` header when the server has tokens (nginx publishes
  the token and the https port to the UI at `/ui-config.json`).
- The Voices table lists each sample with its size, rate, channels and length,
  and plays, downloads or deletes it in place.
- The Voices screen records a sample from the microphone; the browser encodes it
  as 22050 Hz 16-bit mono WAV and uploads it like a file.

#### Changed
- The Studio summary line prints the format in upper case.
- `GET /api/engines` now also returns `language`, the server's default language.
- `ENGINE_MODEL_SOURCES` became `libs.models.engine_model_sources()`, which reads the
  `*_MODELS` directories at call time; `ttsgen --list` therefore reads them after the
  config files are loaded, so values from `ttsgen.conf` are honoured.
- The `./samples` volume in both compose files is mounted writable so that voice
  sample uploads land on the host.
- **Readability pass across the whole codebase, no behaviour change.** Every module
  now opens with the canonical `#!/usr/bin/env python3` / `# -*- coding: utf-8 -*-`
  header plus a one-sentence summary docstring, and every function, method, class,
  fixture and closure — in `libs/`, `engines/`, `install/`, `ttssrv/`, the four CLIs
  and `tests/` — carries a docstring stating what it does rather than restating its
  name. Import blocks were regrouped into stdlib / third-party / local, the
  `MAX_TEXT_LENGTH` constants that sat wedged between imports in five engines were
  moved below them, and legacy `typing.Dict/List/Optional/Union/Callable` were
  migrated to PEP 585/604 syntax.
- **Diagnostics go through logging.** The three `traceback.print_exc()` calls in the
  installers and `ttsgen` were replaced with the house error format
  (`f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"`). The remaining
  `print()`/`sys.stdout.write` sites — the `--list` table, the shell-pipeable saved
  filename, and the carriage-return download progress bar — are deliberate and now
  carry a comment saying why they bypass logging.
- **`libs/` and `engines/` are linted again.** Both packages were excluded from ruff,
  black and pre-commit; the excludes are gone and the 71 findings they were hiding
  (unused imports, unordered import blocks, missing exception chaining) are fixed.
  Every re-raise inside an `except` block now uses `raise ... from exc`.
- Magic numbers became named constants: `DEFAULT_CHUNK_CHARS` / `PIPELINE_QUEUE_SIZE`
  in `ttsgen.py`, `SILENT_PEAK_THRESHOLD` / `INT16_MAX` in `ttsrec.py`, the mixer
  sample-rate and buffer literals in `libs/playback.py`, `MAX_TEXT_LENGTH` in
  `libs/tools.py`.
- `ttsgen.main()` shed five behaviour-identical helpers (`resolve_output_formats`,
  `log_run_summary`, `save_chunk_files`, `write_stdout_audio`, `collect_engine_rows`);
  `install/common.py` gained `persist_env_choice()` and `install/coquitts.py`
  `confirm_xtts_license()`, each replacing a verbatim duplicate.
- Deliberately unused names are spelled `unused_*` instead of `_`; ruff's
  `dummy-variable-rgx` was widened so the convention is machine-checked.

#### Fixed
- `POST /api/tts` served gTTS output as `application/octet-stream` with a `.bin`
  download name: the MP3 sniff only knew the `ID3` tag and the MPEG-1 frame sync
  (`\xff\xfb`), while gTTS returns tagless MPEG-2 layer III (`\xff\xf3`). The sniff
  now masks the 11-bit frame sync, and the history store shares it.
- `GET /api/voices` went through the engine loader, which drops an engine whose
  optional dependencies are not importable, so the coquitts sample catalogue came
  back empty on a host without torch even though uploads to it succeeded. Voice
  listing now imports the engine module without that gate; engines whose listing
  genuinely needs their dependencies still raise `EngineNotAvailableError`.
- The generated `~/.config/ttsgen.conf` template offered `TTS_TOKEN` for the HTTP
  server, but `ttssrv` reads `TTS_TOKENS` — a user who followed the template got a
  server with authentication silently disabled.
- `libs/config.py` documented its own priority chain backwards. The corrected order
  is `.env.local` (loaded with `override=True`, so it beats even shell variables) >
  process environment > `.env` > `~/.config/ttsgen.conf` > `./ttsgen.conf`.
- `libs/playback.py` no longer swallows the reason a WAV header could not be read
  before falling back to 22050 Hz mono; it logs a warning naming the file.
- `logger.info(voice_path)` in `engines/pipertts.py` emitted a bare filesystem path
  with no label during every run; it now reads `Piper voice: <path>`.
- Removed the stale 29-line `ttsgen.py` module docstring that documented a
  `--format bytesio` flag the parser never defined, and the same dead flag from the
  `ttsplay.py` usage example.
- `libs/__init__.py` pointed readers at a `tts_lib.py` that does not exist.
- Dropped `output_formats`, `audio_rate` and `audio_volume` from `ttsgen.get_config()`
  — nothing ever read them, so `DEFAULT_OUTPUT_FORMAT`, `AUDIO_RATE` and
  `AUDIO_VOLUME` never had any effect.
- Both Dockerfiles copied a hand-written list of `ttssrv/` files that omitted
  `streaming.py`, which `app1.py` imports unconditionally — the built image could
  only start because compose bind-mounts `./ttssrv` over it. They now copy the
  package directory.
- Replaced the Cyrillic usage examples printed by the coqui, piper and silero
  installers with Latin-script equivalents, matching the repo's English-only rule
  for anything that ships.

### [1.0.4] — 2026-06-23

#### Added
- **Voice/speaker selection.** `/api/tts` accepts an optional `voice` field that
  selects the engine speaker (e.g. Silero `baya`/`kseniya` for a female Russian
  voice); omitted keeps the per-language default. For SileroTTS the value is
  validated against the model's `speakers` — an unknown voice returns `400`.
  Threaded through `libs.api.text_to_speech_bytes(..., voice=...)`, the streaming
  path, and `engines/silerotts.py` (model load refactored into `load_model()`).
- **`GET /api/voices`** lists the selectable voices for an `engine` + `language`,
  returning `{engine, language, voices, default}`. Engines without voice selection
  return an empty list; SileroTTS exposes its model's speakers via `list_voices()`
  and a generic `engines.get_engine_voices()` dispatcher.

#### Fixed
- Engine error messages now point to the correct per-engine docs
  (`docs/PIPERTTS.md`, `docs/BARKTTS.md`) instead of non-existent
  `docs/PIPER.md` / `docs/BARK.md`.
- Corrected the COQUITTS docs: the Idiap fork (`coqui-tts`) supports Python
  3.11+ (including 3.12) and pins `transformers>=4.46,<5.0`; removed the
  outdated "Python 3.9–3.11 only / `transformers==4.33.0`" instructions.
- Removed an invalid voice-samples URL from `docs/SILEROTTS.md`.
- Corrected stale `docker-compose` path references — the compose files live at
  the repo root, not under `docker/{cpu,gpu}/`.
- `engines/coquitts.py` now imports its heavy deps (`torch`, the `coqui-tts`
  fork) inside the `try/except` that sets `AVAILABLE`, so the module follows the
  engine-plugin contract and imports cleanly when those deps are absent.

#### Removed
- Dead commented-out code and a stray developer note from `ttsgen.py`.

### [1.0.3] — 2026-06-17

#### Added
- **`ttssrv` can preload several engines at once via `TTS_ENGINES`**
  (comma-separated, e.g. `coquitts,silerotts`). Each engine is installed by
  `entrypoint.sh` and warmed by `init_engine_pool()` at startup, so its model
  stays resident and is selected per request through the `engine` field —
  letting a fast engine (silerotts, ~0.1s) serve requests alongside a heavy
  one (coquitts) without a reload. `TTS_ENGINE` remains the request default and
  the fallback when `TTS_ENGINES` is unset. The pool stays a single shared
  semaphore capping total concurrent synthesis across all engines.
- **Streaming synthesis — `/api/tts?stream=true`.** Synthesizes the text one
  chunk at a time (via `libs.cli.chunk_text`) and streams audio with chunked
  transfer encoding, so a client hears the first sentence without waiting for the
  whole utterance. WAV engines emit a single streaming WAV (one header with
  placeholder sizes + concatenated PCM); gtts (MP3) concatenates per-chunk bytes.
  One engine-pool slot is held for the duration of the stream. New
  `TTS_STREAM_MAX_CHARS` env (default 200) controls chunk size. Works for both
  `GET` and `POST`. New module `ttssrv/streaming.py` + `tests/test_stream.py`.
- `GET /api/engines` now reports `supported` (engine modules shipped),
  `available` (deps installed), `preload` (startup set) and `default`.

#### Fixed
- **SileroTTS encodes WAV via the stdlib `wave` module** instead of
  `torchaudio.save()`. Under torchaudio ≥ 2.9 `save()` routes through the
  torchcodec backend, whose encoder cannot write to a file-like object (it needs
  a real path + extension) and raised *"Couldn't allocate AVFormatContext"* on a
  `BytesIO` — failing every SileroTTS synthesis (both batch and streaming) with a
  500. The waveform is now converted to 16-bit PCM and written directly.
- **SileroTTS now caches its loaded model** (`TTS_CACHE` keyed by
  `(model_id, device)`), mirroring CoquiTTS. Previously `generate()` re-ran
  `torch.hub.load` on every call, re-instantiating the model each time.
- SileroTTS dependency `omegaconf` is now declared in the GPU/CPU Docker
  requirements (its torch.hub model package imports it), so the engine no
  longer fails at synthesis time when only the default engine was installed.

#### Changed
- `ttssrv` request log now reports duration and drops the duplicate status
  code: `POST /api/tts: 200 OK (0.123s)`.
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

