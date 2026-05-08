## Changelog

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

