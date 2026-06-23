## text-to-speech — popular TTS engines behind one API

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

Install popular online/offline TTS engines (gTTS, espeak, Piper, Silero, Coqui, Bark, Kokoro) and use them through one CLI, Python API, and HTTP server.

**[English](https://github.com/wachawo/text-to-speech/blob/main/README.md)** | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

- **One interface, many engines.** Pick an engine and call it the same way from the CLI (`ttsgen`), Python (`libs.api`), or HTTP — switch between cloud and local without changing code.
- **API server for your LAN.** Run `ttssrv` so other machines synthesize over HTTP (`POST /api/tts`); the model loads once at startup and requests share a pool.

### Engines

| Engine | Offline | Hardware | Quality | Best for |
|---|---|---|---|---|
| `gtts` | ❌ online | CPU | ★★★★ | 100+ languages, zero setup |
| `pyttsx3` | ✅ | CPU | ★★ | minimal install (espeak / SAPI) |
| `pipertts` | ✅ | CPU | ★★★★ | fast offline, 50+ languages |
| `silerotts` | ✅ | CPU | ★★★★ | fast offline, Russian |
| `kokorotts` | ✅ | CPU | ★★★★ | fast offline, multi-language |
| `coquitts` | ✅ | CPU / **GPU** | ★★★★★ | best quality, voice cloning |
| `barktts` | ✅ | CPU / **GPU** | ★★★★★ | emotions, music, singing |

`gtts`, `pyttsx3`, `pipertts`, `silerotts`, `kokorotts` run fine on CPU. `coquitts` and `barktts` run on CPU too but are slow — a CUDA GPU is recommended.

### Install (pip)

```bash
pip install git+https://github.com/wachawo/text-to-speech.git
```

This installs the CLI with lightweight deps only. Neural engines (`pipertts`, `silerotts`, `coquitts`, `barktts`, `kokorotts`) pull `torch`/models on demand via `ttsgen --install <engine>`.

```bash
ttsgen "Hello world"                  # play (default engine: gtts, online)
ttsgen "Hello world" -f out.mp3       # save to a file
ttsgen "Hello world" -e pyttsx3       # fully offline
ttsgen "Hola amigo!"  -l es           # pick language
ttsgen --install coquitts             # add an offline neural engine + models
ttsgen "Hello world" -e coquitts -f out.wav
ttsgen --list                         # engines + installed models
ttsgen "Hello world" --stdout | ttsplay
```

Python:

```python
from libs.api import text_to_speech_file, text_to_speech_bytes

text_to_speech_file("Hello world", engine="gtts")
audio = text_to_speech_bytes("Hello world", engine="pipertts", language="en")
```

### Server (clone)

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech
docker compose up --build -d                          # GPU (CUDA 12.1)
docker compose -f docker-compose-cpu.yml up --build -d # CPU-only
```

Request synthesis over HTTP:

```bash
curl localhost:5000/api/health
curl localhost:5000/api/engines -H "Authorization: Bearer $TTS_TOKEN"
curl "localhost:5000/api/voices?engine=silerotts&language=ru" -H "Authorization: Bearer $TTS_TOKEN"

curl -X POST localhost:5000/api/tts \
  -H "Authorization: Bearer $TTS_TOKEN" -H "Content-Type: application/json" \
  -d '{"text":"Hello world","engine":"gtts"}' -o out.mp3
```

Or use `ttsapi` — same flags as `ttsgen`, but synthesis runs on the server (`TTS_URL` / `TTS_TOKEN` from config):

```bash
ttsapi "Hello world"
ttsapi -i long.txt --output play,file --file out.mp3
```

### Project structure

```
text-to-speech/
├── ttsgen.py / ttsplay.py / ttsrec.py / ttsapi.py   # CLI entry points
├── engines/        # pluggable engines (gtts, piper, silero, coqui, bark, kokoro, …)
├── libs/           # core: api.py, tools.py, playback.py, exceptions.py
├── install/        # `ttsgen --install <engine>` installers
├── ttssrv/         # Flask HTTP server (Docker / python3 ttssrv/app1.py)
├── docker/         # gpu/ and cpu/ builds (Dockerfile + requirements)
├── docs/           # per-engine guides + translations
└── tests/          # pytest suite (engines mocked, no models/GPU needed)
```

### Developer notes

```bash
pip install -e ".[dev]"
pytest                 # tests + coverage
ruff check . && black .
```

Add an engine by dropping `engines/<name>.py` with two functions — it appears in the CLI and API automatically:

```python
def is_available() -> bool: ...                  # deps importable?
def generate(text: str, config: dict) -> bytes:  # return MP3/WAV bytes
    ...
```

Per-engine setup and the full engine guide live in [`docs/`](docs/ENGINES.md).

### License

[MIT](LICENSE)
