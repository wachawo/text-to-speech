# text-to-speech

Universal text-to-speech system with online and offline engines behind a single CLI and Python API.

## Overview

Switch transparently between cloud and local TTS engines via a single interface. Six engines are supported out of the box; adding a seventh is one file in `engines/`.

| Engine | Quality | Speed (CPU) | Offline | Best for |
|---|---|---|---|---|
| `gtts` | 4/5 | Fast | ❌ | Online, 100+ languages, easy |
| `pyttsx3` | 2/5 | Fast | ✅ | Minimal install, robotic |
| `pipertts` | 4/5 | Very fast | ✅ | Fast offline, English |
| `silerotts` | 4/5 | Very fast | ✅ | Fast offline, Russian |
| `coquitts` | 5/5 | Slow (fast w/ GPU) | ✅ | Best quality, voice cloning |
| `barktts` | 5/5 | Very slow (fast w/ GPU) | ✅ | Emotions, music, singing |

See [`docs/ENGINES.md`](docs/ENGINES.md) for the full engine matrix and tuning.

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
pip install git+https://github.com/wachawo/text-to-speech.git@v0.2.0
pip install git+https://github.com/wachawo/text-to-speech.git@main
```

That installs the CLI plus the lightweight engines (`gtts`, `pyttsx3`). For heavier engines and their model files, use `ttsgen --install <engine>` after the base install (see [Optional engine model downloads](#optional-engine-model-downloads) below).

After install, three console scripts are on your `$PATH`:

```bash
ttsgen "Hello world"          # synthesize and play (or save with --file)
echo "..." | ttsplay          # play raw audio bytes from stdin
ttsrec ~/voice.wav            # record a voice sample from microphone (needs [recorder] extra)
```

For `ttsrec` install the recorder extra:

```bash
pip install "text-to-speech[recorder] @ git+https://github.com/wachawo/text-to-speech.git"
```

### Install for development

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech
pip install -e ".[dev]"
```

### Uninstall

```bash
# Remove the package (keeps optional engine extras like torch/TTS/bark unless you remove them too)
pip uninstall text-to-speech

# Also remove engine deps installed via `ttsgen --install`
pip uninstall piper-tts                       # if pipertts was installed
pip uninstall torch torchaudio omegaconf      # if silerotts was installed
pip uninstall coqui-tts torchcodec transformers # if coquitts was installed
pip uninstall bark scipy numpy                # if barktts was installed

# Remove downloaded model files (optional — these can be 10+ GB)
rm -rf .pipertts/ .silerotts/ .coquitts/ .barktts/
rm -rf ~/.cache/torch/hub/snakers4_silero-models_master   # silero (if stored in standard cache)
rm -rf ~/.cache/suno/bark_v0/                              # bark
```

### Legacy install (without packaging)

```bash
sudo apt install espeak espeak-data libespeak1 python3-pip
pip install -r requirements.txt
python ttsgen.py "Hello world"
```

### Optional engine model downloads

Heavier engines need model files. The `ttsgen --install` command downloads them into per-engine dotfolders (`.pipertts/`, `.silerotts/`, `.coquitts/`, `.barktts/`):

```bash
ttsgen --install pipertts        # interactive
ttsgen --install silerotts
ttsgen --install coquitts
ttsgen --install barktts

ttsgen --install pipertts --non-interactive   # accept defaults, no prompts
```

Per-engine guides: [`docs/PIPERTTS.md`](docs/PIPERTTS.md), [`docs/SILEROTTS.md`](docs/SILEROTTS.md), [`docs/COQUITTS.md`](docs/COQUITTS.md), [`docs/BARKTTS.md`](docs/BARKTTS.md).

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
  --coqui-sample samples/Maria.wav

# Same via env vars (handy in scripts and CI)
COQUITTS_MODEL=tts_models/en/ljspeech/tacotron2-DDC \
COQUITTS_SAMPLE=samples/Maria.wav \
ttsgen "Hello world" --engine coquitts
```

Without a local `.env` (e.g. after `pip install git+...`), pass engine config via flags:
- `--engine NAME` — pick an engine (`gtts`, `pyttsx3`, `pipertts`, `silerotts`, `coquitts`, `barktts`).
- `--language XX` — 2-letter language code.
- `--coqui-model MODEL`, `--coqui-sample PATH` — override `COQUITTS_MODEL` / `COQUITTS_SAMPLE` for one run. Same flags work with `ttsgen --install coquitts`.

### Configuration priority

`ttsgen` reads settings from multiple sources, **highest priority first**:

1. **Process env / CLI flags** — `--coqui-model`, `--coqui-sample`, or `COQUITTS_MODEL=... ttsgen ...` from the shell.
2. **`./ttsgen.conf`** — project-local override (next to where you run `ttsgen`).
3. **`~/.config/ttsgen.conf`** — user-wide defaults. Auto-created with commented examples on first run.
4. **`.env`** — legacy file in the current directory (kept for backward compatibility).
5. **Built-in defaults** — `TTS_ENGINE=gtts`, `TTS_LANGUAGE=en`, etc.

All config files use the same `KEY=VALUE` format. Available keys: `TTS_ENGINE`, `TTS_LANGUAGE`, `AUDIO_DIRECTORY`, `COQUITTS_PATH`, `COQUITTS_MODEL`, `COQUITTS_SAMPLE`, `PIPERTTS_PATH`, `SILEROTTS_PATH`, `BARKTTS_PATH`. Example:

```ini
TTS_ENGINE=coquitts
TTS_LANGUAGE=en
COQUITTS_MODEL=tts_models/en/ljspeech/tacotron2-DDC
COQUITTS_SAMPLE=samples/Maria.wav
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

### HTTP API + Docker

A Flask API server is included. Bring it up with Docker Compose:

```bash
docker compose up --build -d

# Health
curl http://localhost:5000/api/health

# List available engines (depends on what's installed in the image)
curl http://localhost:5000/api/engines

# GET — engine and language are optional, default to TTS_ENGINE/TTS_LANGUAGE from .env
curl -o out.mp3 "http://localhost:5000/api/tts?text=Hello%20world&engine=gtts"

# POST
curl -X POST http://localhost:5000/api/ttsgen \
  -H "Content-Type: application/json" \
  -d '{"text":"Привет мир","engine":"gtts","language":"ru"}' \
  -o ru.mp3
```

The container service is named `tts_api` on network `tts_network`. To enable heavier engines in the API container, uncomment the relevant lines in `api/requirements.txt` and rebuild with `docker compose build`.

To run the API without Docker:

```bash
pip install "text-to-speech[api] @ git+https://github.com/wachawo/text-to-speech.git"
python -m api.app1
# or, after editable install:
python api/app1.py
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
├── docker-compose.yml        # tts_api service definition
├── engines/                  # Pluggable TTS engines
│   ├── __init__.py           #   Dynamic loader
│   ├── gtts.py
│   ├── pyttsx3.py
│   ├── pipertts.py
│   ├── silerotts.py
│   ├── coquitts.py
│   └── barktts.py
├── libs/                     # Core library
│   ├── api.py                #   text_to_speech_bytes / _file / _bytesio
│   ├── tools.py              #   Validation, config, pipelines
│   ├── playback.py           #   pygame wrapper
│   └── exceptions.py
├── api/                      # Flask HTTP API
│   ├── app1.py
│   ├── validators.py
│   ├── gu.py
│   ├── Dockerfile
│   └── requirements.txt
├── install/                  # Engine installers (`ttsgen --install <engine>`)
│   ├── __init__.py           #   Dispatcher
│   ├── common.py             #   pip / download / prompt helpers
│   ├── pipertts.py
│   ├── silerotts.py
│   ├── coquitts.py
│   └── barktts.py
├── docs/                     # Per-engine guides
│   ├── ENGINES.md
│   ├── PIPERTTS.md
│   ├── SILEROTTS.md
│   ├── COQUITTS.md
│   └── BARKTTS.md
├── samples/                  # Voice samples (used by coquitts)
├── test_tts.py
├── env.example               # `.env` template
├── ttsgen.conf.example       # `./ttsgen.conf` / `~/.config/ttsgen.conf` template
├── requirements.txt          # Legacy
├── requirements-dev.txt      # Legacy
├── REVIEW.md                 # Code review
├── ROADMAP.md                # Improvement roadmap
└── CLAUDE.md                 # Notes for Claude Code
```

## Development

```bash
pip install -e ".[dev]"

# Tests
python test_tts.py
python -m pytest test_tts.py -v

# Lint / typecheck / format
flake8 .
mypy .
black .

# List engines available in the current environment
python -c "from engines import get_available_engines; print('\n'.join(get_available_engines().keys()))"
```

## Documentation

- [`docs/ENGINES.md`](docs/ENGINES.md) — engine system, comparison, custom-engine guide
- [`docs/PIPERTTS.md`](docs/PIPERTTS.md), [`docs/SILEROTTS.md`](docs/SILEROTTS.md), [`docs/COQUITTS.md`](docs/COQUITTS.md), [`docs/BARKTTS.md`](docs/BARKTTS.md) — per-engine setup
- [`REVIEW.md`](REVIEW.md) — current code review
- [`ROADMAP.md`](ROADMAP.md) — planned improvements

## License

MIT License
