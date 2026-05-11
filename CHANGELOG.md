## Changelog

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
  (`PIPERTTS_PATH=` etc.) still work unchanged.
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

