# text-to-speech

Universal text-to-speech system with online and offline engines behind a single CLI and Python API.

## Overview

Switch transparently between cloud and local TTS engines via a single interface. Seven engines are supported out of the box; adding an eighth is one file in `engines/`.

| Engine | Quality | Speed (CPU) | Offline | Best for |
|---|---|---|---|---|
| `gtts` | 4/5 | Fast | ❌ | Online, 100+ languages, easy |
| `pyttsx3` | 2/5 | Fast | ✅ | Minimal install, robotic |
| `pipertts` | 4/5 | Very fast | ✅ | Fast offline, English |
| `silerotts` | 4/5 | Very fast | ✅ | Fast offline, Russian |
| `coquitts` | 5/5 | Slow (fast w/ GPU) | ✅ | Best quality, voice cloning |
| `barktts` | 5/5 | Very slow (fast w/ GPU) | ✅ | Emotions, music, singing |
| `kokorotts` | 4/5 | Very fast | ✅ | Fast offline, multi-language, ONNX |

See [`docs/ENGINES.md`](docs/ENGINES.md) for the full engine matrix and tuning.

## Quick start

```bash
# Install the CLI (lightweight deps only — gtts, pyttsx3, pygame)
pip install git+https://github.com/wachawo/text-to-speech.git

# Synthesize and play (default engine: gtts, online)
ttsgen "Hello world"

# Save to a file instead of playing
ttsgen "Hello world" --file output.mp3

# Pick a different engine (pyttsx3 is fully offline)
ttsgen "Hello world" -e pyttsx3

# Install an offline neural engine, then use it
ttsgen --install coquitts
ttsgen "Hello world" -e coquitts -f out.wav
```

`gtts` (online) and `pyttsx3` (offline) work right after install. Offline neural
engines — `pipertts`, `silerotts`, `coquitts`, `barktts`, `kokorotts` — pull
heavier deps and models on demand via `ttsgen --install <engine>`; see
[Adding optional engines](#adding-optional-engines). Most flags have short forms
(`-e/--engine`, `-f/--file`, `-l/--language`, `-o/--output`, …); the full command
reference is in [Usage](#usage).

## Features

- One CLI, one API for all engines
- Online (gTTS) and offline (espeak, Piper, Silero, Coqui, Bark)
- Multi-language (100+ via gTTS, 50+ via Piper)
- Streaming pipeline: playback starts before long-text generation finishes
- Multiple outputs in one pass (play, save, stdout)
- HTTP API server (Flask) and Docker Compose deployment
- Pluggable engine system (drop a `.py` into `engines/`)

## Installation

### Install from GitHub (recommended)

```bash
# System dependencies (Linux) — only needed for the pyttsx3/espeak engine
sudo apt install espeak espeak-data libespeak1

# Latest from main
pip install git+https://github.com/wachawo/text-to-speech.git

# Specific tag, branch, or commit
pip install git+https://github.com/wachawo/text-to-speech.git@v1.0.2
pip install git+https://github.com/wachawo/text-to-speech.git@main
```

That installs the CLI **with only lightweight deps** (~10 MB: gtts, pyttsx3, pygame, sounddevice, numpy). **`torch`, `coqui-tts`, `bark`, and CUDA wheels are NOT pulled** — they're only fetched by `ttsgen --install <engine>` for `silerotts`/`coquitts`/`barktts`/`kokorotts` (see [Adding optional engines](#adding-optional-engines) below).

After install, four console scripts are on your `$PATH`:

```bash
ttsgen "Hello world"          # synthesize locally — play (or save with --file)
echo "..." | ttsplay          # play raw audio bytes from stdin
ttsrec ~/voice.wav            # record a voice sample from microphone
ttsapi "Hello world"          # send to a remote ttssrv via HTTP (TTS_URL/TTS_TOKEN from config)
```

The HTTP server `ttssrv` is **not** a console-script — it's deployed via Docker (see below) or run as `python3 ttssrv/app1.py` from a clone.

#### Adding optional engines

There are no pip extras for `pipertts` / `silerotts` / `coquitts` / `barktts` / `kokorotts`. Use the dedicated installer instead — it picks the right PyTorch wheel index (cpu / cu121), respects driver constraints, persists the model directory to `~/.config/ttsgen.conf`, verifies download checksums where supported, and stages models under `cache/<engine>/` in the project root:

```bash
ttsgen --install pipertts        # piper-tts + voice models from HuggingFace
ttsgen --install silerotts       # torch + torchaudio + omegaconf + Silero models
ttsgen --install coquitts        # coqui-tts (Idiap fork) + torch + transformers
ttsgen --install barktts         # bark (git) + scipy + numpy (~10–15 GB models)
ttsgen --install kokorotts       # kokoro-onnx + onnxruntime + ~340 MB ONNX/voices

ttsgen --install pipertts --non-interactive   # accept defaults, no prompts
```

Per-engine guides: [`docs/PIPERTTS.md`](docs/PIPERTTS.md), [`docs/SILEROTTS.md`](docs/SILEROTTS.md), [`docs/COQUITTS.md`](docs/COQUITTS.md), [`docs/BARKTTS.md`](docs/BARKTTS.md), [`docs/KOKOROTTS.md`](docs/KOKOROTTS.md).

### Install for development

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech
pip install -e ".[dev]"
```

### Uninstall

```bash
# Remove the package (engine packages installed via `ttsgen --install` stay
# until you remove them explicitly; see the lines below)
pip uninstall text-to-speech

# Also remove engine deps installed via `ttsgen --install`
pip uninstall piper-tts                       # if pipertts was installed
pip uninstall torch torchaudio omegaconf      # if silerotts was installed
pip uninstall coqui-tts torchcodec transformers # if coquitts was installed
pip uninstall bark scipy numpy                # if barktts was installed
pip uninstall kokoro-onnx soundfile onnxruntime # if kokorotts was installed

# Remove downloaded model files (optional — these can be 10+ GB)
rm -rf cache/                                              # all per-engine model caches
rm -rf ~/.cache/torch/hub/snakers4_silero-models_master   # silero (if stored in standard cache)
rm -rf ~/.cache/suno/bark_v0/                              # bark
```

### Legacy install (without packaging)

```bash
sudo apt install espeak espeak-data libespeak1 python3-pip
pip install -r requirements.txt
python ttsgen.py "Hello world"
```

## Usage

### CLI

```bash
# Play (default)
ttsgen "Hello world"

# Pick an engine / language
ttsgen "Hello world"   --engine pyttsx3
ttsgen "Hola amigo!"   --language es
ttsgen "Привет"        --engine silerotts --language ru

# Save to file (auto-named timestamp or explicit)
ttsgen "Hello world" --file
ttsgen "Hello world" --file output.mp3
ttsgen "Hello world" --file audio/

# Read from a text file
ttsgen -i input.txt
ttsgen -i input.txt --file output.mp3

# Stream over a pipe
ttsgen "Hello world" --stdout | ttsplay

# Multi-output in one pass
ttsgen "Hello world" --output play,file
ttsgen "Hello world" --output file,stdout

# List engines and installed models
ttsgen --list

# coqui-tts with explicit model + voice sample (no .env needed)
ttsgen "Hello world" --engine coquitts \
  --coqui-model tts_models/en/ljspeech/tacotron2-DDC \
  --coqui-sample samples/default.wav

# Same via env vars (handy in scripts and CI)
COQUITTS_MODEL=tts_models/en/ljspeech/tacotron2-DDC \
COQUITTS_SAMPLE=samples/default.wav \
ttsgen "Hello world" --engine coquitts
```

Without a local `.env` (e.g. after `pip install git+...`), pass engine config via flags:
- `--engine NAME` — pick an engine (`gtts`, `pyttsx3`, `pipertts`, `silerotts`, `coquitts`, `barktts`, `kokorotts`).
- `--language XX` — 2-letter language code.
- `--coqui-model MODEL`, `--coqui-sample PATH` — override `COQUITTS_MODEL` / `COQUITTS_SAMPLE` for one run. Same flags work with `ttsgen --install coquitts`.

### Configuration priority

`ttsgen` reads settings from multiple sources, **highest priority first**:

1. **Process env / CLI flags** — `--coqui-model`, `--coqui-sample`, or `COQUITTS_MODEL=... ttsgen ...` from the shell.
2. **`./ttsgen.conf`** — project-local override (next to where you run `ttsgen`).
3. **`~/.config/ttsgen.conf`** — user-wide defaults. Auto-created with commented examples on first run.
4. **`.env`** — legacy file in the current directory (kept for backward compatibility).
5. **Built-in defaults** — `TTS_ENGINE=gtts`, `TTS_LANGUAGE=en`, etc.

All config files use the same `KEY=VALUE` format. Available keys: `TTS_ENGINE`, `TTS_LANGUAGE`, `AUDIO_DIRECTORY`, `COQUITTS_MODELS`, `COQUITTS_MODEL`, `COQUITTS_SAMPLE`, `PIPERTTS_MODELS`, `SILEROTTS_MODELS`, `BARKTTS_MODELS`, `KOKOROTTS_MODELS`. Example:

```ini
TTS_ENGINE=coquitts
TTS_LANGUAGE=en
COQUITTS_MODEL=tts_models/en/ljspeech/tacotron2-DDC
COQUITTS_SAMPLE=samples/default.wav
```

### Python API

```python
from libs.api import text_to_speech_file, text_to_speech_bytes, text_to_speech_bytesio

# Save to file
filename = text_to_speech_file("Hello world!", engine="gtts")

# Get as bytes (web apps, HTTP responses)
audio_bytes = text_to_speech_bytes("Hello world!", engine="gtts", language="en")

# Get as BytesIO (streaming)
buf = text_to_speech_bytesio("Hello world!", engine="pipertts")
```

### HTTP server (`ttssrv`) and client (`ttsapi`)

The Flask server (`ttssrv`) preloads the engine once at startup, then serves synthesis requests with a `queue.Queue`-based pool (concurrency limit = `TTS_POOL_SIZE`). Two Docker variants:

```bash
# GPU (CUDA 12.1, requires nvidia-container-toolkit on host) — the default
docker compose up --build -d

# CPU-only
docker compose -f docker-compose-cpu.yml up --build -d
```

Direct HTTP usage:

```bash
curl http://localhost:5000/api/health
# {"status":"ok","engine":"coquitts","pool_size":1,"available":1}

curl http://localhost:5000/api/engines \
  -H "Authorization: Bearer $TTS_TOKEN"

# List selectable voices for an engine + language (e.g. Silero Russian speakers)
curl "http://localhost:5000/api/voices?engine=silerotts&language=ru" \
  -H "Authorization: Bearer $TTS_TOKEN"
# {"engine":"silerotts","language":"ru","voices":["aidar","baya","kseniya","xenia","eugene","random"],"default":"aidar"}

curl -X POST http://localhost:5000/api/tts \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world","engine":"gtts"}' -o out.mp3

# Pick a specific voice (optional; omit for the language default)
curl -X POST http://localhost:5000/api/tts \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Здравствуйте","engine":"silerotts","language":"ru","voice":"baya"}' -o out.wav
```

Or via the matching client `ttsapi` — mirror of `ttsgen` with the same flags, but synthesis runs on the server:

```bash
ttsapi --list                                          # GET /api/engines
ttsapi "Hello world"                                   # POST /api/tts → play
ttsapi -i long.txt --output play,file --file out.mp3   # chunked, multi-output
ttsapi "Привет" --engine coquitts --language ru
```

`ttsapi` reads `TTS_URL` and `TTS_TOKEN` from the same config chain as `ttsgen` (`./ttsgen.conf` > `~/.config/ttsgen.conf` > `.env`). Default URL is `http://localhost:5000`. Empty `TTS_TOKEN` disables auth.

Run server without Docker (from a clone — `ttssrv` is not a console-script):

```bash
python3 ttssrv/app1.py
```

## Adding a new engine

The engine system is a plugin loader — drop a file in `engines/` and it appears in the CLI and API automatically. The contract is two functions:

```python
# engines/myengine.py
def is_available() -> bool:
    """True if all deps are importable."""
    ...

def generate(text: str, config: dict) -> bytes:
    """Return audio bytes (MP3 or WAV). config has 'language', 'rate', 'volume', etc."""
    ...
```

Then:

```bash
ttsgen "Hello" --engine myengine
```

Full guide: [`docs/ENGINES.md`](docs/ENGINES.md).

## Project structure

```
text-to-speech/
├── ttsgen.py                    # CLI entry-point (`ttsgen` command)
├── ttsplay.py                   # stdin player (`ttsplay` command)
├── ttsrec.py                    # microphone recorder (`ttsrec` command)
├── pyproject.toml            # Package config and dependencies
├── docker/                   # Docker configs (split by accelerator)
│   ├── gpu/                  #   GPU build: Dockerfile + docker-compose.yml + requirements.txt (cu121)
│   └── cpu/                  #   CPU build: same files, cpu wheel index
├── cache/                    # Per-engine model caches (cache/coquitts, cache/kokorotts, …)
├── engines/                  # Pluggable TTS engines
│   ├── __init__.py           #   Dynamic loader
│   ├── gtts.py
│   ├── pyttsx3.py
│   ├── pipertts.py
│   ├── silerotts.py
│   ├── coquitts.py
│   ├── barktts.py
│   └── kokorotts.py
├── libs/                     # Core library
│   ├── api.py                #   text_to_speech_bytes / _file / _bytesio
│   ├── tools.py              #   Validation, config, pipelines
│   ├── playback.py           #   pygame wrapper
│   └── exceptions.py
├── ttssrv/                   # Flask HTTP server (NOT a console script — run via Docker or `python3 ttssrv/app1.py`)
│   ├── __init__.py
│   ├── app1.py               #   Endpoints, pool, token auth
│   ├── validators.py
│   ├── gu.py
│   ├── entrypoint.sh         #   Container init: ensures TTS_ENGINE is installed
│   └── requirements.txt      #   Light web stack (Flask, gtts, pyttsx3, …)
├── ttsapi.py                 # HTTP client (`ttsapi` console script — mirror of ttsgen)
├── install/                  # Engine installers (`ttsgen --install <engine>`)
│   ├── __init__.py           #   Dispatcher
│   ├── common.py             #   pip / download / prompt helpers
│   ├── pipertts.py
│   ├── silerotts.py
│   ├── coquitts.py
│   ├── barktts.py
│   └── kokorotts.py
├── docs/                     # Per-engine guides
│   ├── ENGINES.md
│   ├── PIPERTTS.md
│   ├── SILEROTTS.md
│   ├── COQUITTS.md
│   ├── BARKTTS.md
│   └── KOKOROTTS.md
├── tests/                    # pytest suite (260 tests, all engines mocked)
├── samples/                  # Voice samples (used by coquitts)
├── env.example               # `.env` template
├── ttsgen.conf.example       # `./ttsgen.conf` / `~/.config/ttsgen.conf` template
├── requirements.txt          # Legacy
├── requirements-dev.txt      # Legacy
├── REVIEW.md                 # Code review (local-only, gitignored)
├── ROADMAP.md                # Improvement roadmap (local-only, gitignored)
└── CLAUDE.md                 # Notes for Claude Code
```

## Development

```bash
pip install -e ".[dev]"

# Tests + coverage (config lives in pyproject.toml — `pytest` runs both)
pytest                    # full suite, prints per-module coverage
pytest --no-cov           # disable coverage for a faster local re-run
pytest --cov

# Test suite layout (260 tests in tests/test_<word>.py, ~1.5s on a laptop):
#   srv-side    test_health, test_auth, test_endpoint, test_errors, test_smoke
#   client-side test_apiauth, test_apihelpers, test_apimain
#   ttsgen CLI  test_gencli
#   library     test_cli, test_config, test_tools, test_tempfiles,
#               test_resolver, test_engines, test_customerror
#   engines     test_gtts, test_pyttsx3, test_pipertts, test_silerotts,
#               test_coquitts, test_barktts, test_kokorotts
#
# Coverage today: ~76% project-wide. Engines fake their heavy deps
# (torch, coqui-tts, kokoro_onnx, etc.) in fixture-level stubs, so the
# suite runs without any model files or GPU.

# Lint / typecheck / format
flake8 .
black .

# List engines available in the current environment
python -c "from engines import get_available_engines; print('\n'.join(get_available_engines().keys()))"
```

## Documentation

- [`docs/ENGINES.md`](docs/ENGINES.md) — engine system, comparison, custom-engine guide
- [`docs/PIPERTTS.md`](docs/PIPERTTS.md), [`docs/SILEROTTS.md`](docs/SILEROTTS.md), [`docs/COQUITTS.md`](docs/COQUITTS.md), [`docs/BARKTTS.md`](docs/BARKTTS.md), [`docs/KOKOROTTS.md`](docs/KOKOROTTS.md) — per-engine setup
- `REVIEW.md` — code review (local-only, gitignored)
- `ROADMAP.md` — improvement roadmap (local-only, gitignored)

## License

MIT License
