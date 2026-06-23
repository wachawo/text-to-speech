## text-to-speech — a single interface for TTS engines

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

`text-to-speech` lets you work with several speech-synthesis engines through one interface. You can start with online gTTS and later switch to local Piper, Silero, Coqui, Bark, or Kokoro — without rewriting your CLI commands, Python code, or HTTP integration.

The project fits local use, automation, and running your own TTS server on the network.

**[English](https://github.com/wachawo/text-to-speech/blob/main/README.md)** | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

* **One way to work with different engines.** Pick the engine you need and call it through the CLI (`ttsgen`), the Python API (`libs.api`), or the HTTP API.
* **You can work fully locally.** Piper, Silero, Coqui, Bark, Kokoro, and `pyttsx3` all run on your own machine.
* **A ready-to-use HTTP server is included.** `ttssrv` loads the model at startup and serves requests from other machines on your local network.

### Engines

| Engine      | Offline | Hardware      | Quality | Good for                                       |
| ----------- | ------- | ------------- | ------- | ---------------------------------------------- |
| `gtts`      | ❌      | CPU           | ★★★★    | a quick start and a large number of languages  |
| `pyttsx3`   | ✅      | CPU           | ★★      | simple local speech via espeak or SAPI         |
| `pipertts`  | ✅      | CPU           | ★★★★    | fast offline synthesis in many languages       |
| `silerotts` | ✅      | CPU           | ★★★★    | Russian speech and a lightweight local setup   |
| `kokorotts` | ✅      | CPU           | ★★★★    | multilingual offline synthesis                 |
| `coquitts`  | ✅      | CPU / **GPU** | ★★★★★   | high-quality voices and voice cloning          |
| `barktts`   | ✅      | CPU / **GPU** | ★★★★★   | expressive speech, emotions, music, and singing |

`gtts`, `pyttsx3`, `pipertts`, `silerotts`, and `kokorotts` run fine on CPU. `coquitts` and `barktts` can also run without a GPU, but synthesis is noticeably slower — a CUDA-capable graphics card is recommended for them.

### Installation

The base install sets up the CLI and its lightweight dependencies:

```bash
pip install git+https://github.com/wachawo/text-to-speech.git
```

On Linux, the offline `pyttsx3` engine also needs the system `espeak` package:

```bash
sudo apt install espeak espeak-data libespeak1
```

Extra engines and their models are installed separately, when you actually need them:

```bash
ttsgen --install coquitts
```

CLI usage examples:

```bash
ttsgen "Hello world"                  # speak the text with gTTS
ttsgen "Hello world" -f out.mp3       # save the result to a file
ttsgen "Hello world" -e pyttsx3       # use a local engine
ttsgen "Hola amigo!" -l es            # pick a language
ttsgen --install coquitts             # install Coqui TTS and its models
ttsgen "Hello world" -e coquitts -f out.wav
ttsgen --list                         # show available engines and models
ttsgen "Hello world" --stdout | ttsplay
```

`gtts` is the default, so a single command is enough for the first run. For fully local work, pick another engine such as `pyttsx3`, `pipertts`, or `silerotts`.
My pick: `coquitts` for quality and natural-sounding speech, `silerotts` for fast generation.

### Python API

In Python, there are functions to save the result to a file or get the audio as bytes:

```python
from libs.api import text_to_speech_file, text_to_speech_bytes

text_to_speech_file("Hello world", engine="gtts")

audio = text_to_speech_bytes(
    "Hello world",
    engine="pipertts",
    language="en",
)
```

### HTTP server

It is easier to run the server with Docker:

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech

docker compose up --build -d                          # GPU / CUDA 12.1
docker compose -f docker-compose-cpu.yml up --build -d # CPU only
```

Once it is running, you can check the server status and send a synthesis request:

```bash
curl localhost:5000/api/health

curl localhost:5000/api/engines \
  -H "Authorization: Bearer $TTS_TOKEN"

curl "localhost:5000/api/voices?engine=silerotts&language=ru" \
  -H "Authorization: Bearer $TTS_TOKEN"

curl -X POST localhost:5000/api/tts \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world","engine":"gtts"}' \
  -o out.mp3
```

For working with and testing the server there is a separate CLI client, `ttsapi`. It has the same main flags as `ttsgen`, but synthesis runs on the server. The server address and token are taken from `TTS_URL` and `TTS_TOKEN`.

```bash
ttsapi "Hello world"
ttsapi -i long.txt --output play,file --file out.mp3
```

### Project structure

```text
text-to-speech/
├── ttsgen.py / ttsplay.py / ttsrec.py / ttsapi.py   # CLI commands
├── engines/        # engines: gTTS, Piper, Silero, Coqui, Bark, Kokoro, and others
├── libs/           # shared core: API, tools, playback, exceptions
├── install/        # installers for ttsgen --install <engine>
├── ttssrv/         # Flask HTTP server
├── docker/         # Docker builds for GPU and CPU
├── docs/           # per-engine docs and README translations
└── tests/          # pytest tests, no model downloads and no GPU
```

### Development

To install the development dependencies:

```bash
pip install -e ".[dev]"
```

Checks before committing:

```bash
pytest
ruff check .
black .
```

A new engine is plugged in through an `engines/<name>.py` file. You only need to implement two functions:

```python
def is_available() -> bool:
    ...

def generate(text: str, config: dict) -> bytes:
    ...
```

`is_available()` checks that the dependencies are importable, and `generate()` takes the text and config and returns the audio as MP3 or WAV bytes. After that the engine becomes available in the CLI and API automatically.

Detailed parameters and specifics of each engine are described in [`docs/`](docs/ENGINES.md).

### License

[MIT](LICENSE)
