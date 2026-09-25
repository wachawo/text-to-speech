# text-to-speech - a single interface for TTS engines

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

**[English](https://github.com/wachawo/text-to-speech/blob/main/README.md)** | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

![The Studio screen of the web UI](https://raw.githubusercontent.com/wachawo/text-to-speech/main/docs/images/studio.png)

`text-to-speech` lets you work with several speech-synthesis engines through one interface. You can start with online gTTS and later switch to local Piper, Silero, Coqui, Bark, or Kokoro - without rewriting your CLI commands, Python code, or HTTP integration.

The project fits local use, automation, and running your own TTS server on the network.

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

`gtts`, `pyttsx3`, `pipertts`, `silerotts`, and `kokorotts` run fine on CPU. `coquitts` and `barktts` can also run without a GPU, but synthesis is noticeably slower - a CUDA-capable graphics card is recommended for them.

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
cp env.example .env                                   # optional: tokens, engines, ports

docker compose up --build -d                          # GPU / CUDA 12.1
docker compose -f docker-compose-cpu.yml up --build -d # CPU only
```

The GPU variant passes the card through CDI, so the host needs the NVIDIA container toolkit (1.14 or newer) and a generated CDI spec, once per driver update:

```bash
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
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

Models, voices and history:

```bash
# What one engine offers: models, languages and voices, read without loading a model
curl localhost:5000/api/engines/pipertts \
  -H "Authorization: Bearer $TTS_TOKEN"

# Synthesize with one of the models listed there
curl -X POST localhost:5000/api/tts \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world","engine":"pipertts","language":"en-gb","model":"en_GB-alan-low"}' \
  -o out.wav

# Installed and missing models, the same table `ttsgen --list` prints
curl localhost:5000/api/models \
  -H "Authorization: Bearer $TTS_TOKEN"

# Upload a voice sample for coquitts (WAV); the voice is then "maria"
curl -X POST localhost:5000/api/voices \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -F file=@voice.wav -F name=maria -F engine=coquitts

curl "localhost:5000/api/voices?engine=coquitts" \
  -H "Authorization: Bearer $TTS_TOKEN"

curl "localhost:5000/api/voices/maria/audio?engine=coquitts&download=1" \
  -H "Authorization: Bearer $TTS_TOKEN" -o maria.wav

# Synthesize into the server-side history instead of the response body
curl -X POST localhost:5000/api/history \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hola mundo","engine":"coquitts","language":"es","voice":"maria"}'

curl "localhost:5000/api/history?limit=50&offset=0" \
  -H "Authorization: Bearer $TTS_TOKEN"

# Audio of one item; without download=1 it is served inline for <audio>
curl "localhost:5000/api/history/<id>/audio?download=1" \
  -H "Authorization: Bearer $TTS_TOKEN" -o tts.wav

curl -X DELETE localhost:5000/api/history/<id> \
  -H "Authorization: Bearer $TTS_TOKEN"
```

#### OpenAI-compatible API

The same server also answers the OpenAI audio API, so Open WebUI, SillyTavern, Home Assistant and the official SDKs work with `base_url` pointing at it and the bearer token as the API key:

```bash
curl -X POST localhost:5000/v1/audio/speech \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model":"tts-1","input":"Hello world","voice":"alloy","response_format":"mp3"}' \
  -o out.mp3
```

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:5000/v1", api_key="<one of TTS_TOKENS>")
audio = client.audio.speech.create(model="coquitts", voice="maria", input="Hola mundo")
audio.write_to_file("hola.mp3")
```

- `model` is an engine name, or `tts-1` / `tts-1-hd` / `gpt-4o-mini-tts` for the default engine. There is no model choice inside an engine on `/v1`: the engine uses its default model.
- `voice` is an engine voice; the OpenAI voice names (`alloy`, `nova`, ...) select the engine default.
- `response_format`: `mp3` (default), `wav`, `pcm`, `opus`, `flac`, `aac`. Engines produce WAV or MP3; anything else is transcoded with `ffmpeg`, which the Docker images include. `speed` (0.25 to 4.0) is applied the same way.
- `language` is an extension: a two-letter code or a tag such as `zh-cn`, default `TTS_LANGUAGE`.
- `GET /v1/models` lists the installed engines plus `tts-1`; `GET /v1/audio/voices?model=<engine>` lists the voices of one engine.

#### API reference

Every route except `/api/health` requires `Authorization: Bearer <token>` when `TTS_TOKENS` is set. Errors under `/api/` are `{"error": "...", "request_id": "..."}`; a 400 also carries `message` with the reason, which names the failing fields when the request does not pass validation (`language: ...`). Errors under `/v1/` use the OpenAI shape.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Liveness, `auth` flag, engines, pool and queue sizes. No token needed. |
| GET | `/api/engines` | Supported engines, the installed ones and the default. |
| GET | `/api/engines/<engine>` | Models, languages, voice list and output format of one engine, read without loading a model. |
| GET | `/api/models` | Installed and missing models per engine, the table `ttsgen --list` prints. |
| GET | `/api/voices?engine=&language=&model=` | Voices of an engine; for `coquitts` the samples with size, rate and duration. With `model`, the voices of that model. |
| POST | `/api/voices` | Upload a WAV sample (`file`, `name`, `engine=coquitts`). |
| GET | `/api/voices/<name>/audio?engine=&download=1` | Play or download a sample. |
| DELETE | `/api/voices/<name>?engine=` | Delete a sample. |
| POST, GET | `/api/tts` | Synthesize `text` with `engine`, `language`, `voice`, `model`; `stream=true` streams chunks as they are ready. |
| POST | `/api/history` | Synthesize into the server-side history instead of the response body. |
| GET | `/api/history?limit=&offset=` | List history items, newest first. |
| GET | `/api/history/<id>` | One item's metadata. |
| GET | `/api/history/<id>/audio?download=1` | The item's audio, inline or as a download. |
| DELETE | `/api/history/<id>` | Delete an item. |
| POST | `/v1/audio/speech` | OpenAI-compatible synthesis, see above. |
| GET | `/v1/models` | OpenAI-compatible model list. |
| GET | `/v1/audio/voices?model=` | Voices of one engine. |
| GET | `/api/metrics` | Uptime, pool occupancy and per-engine calls, failures and latency percentiles as JSON. |
| GET | `/metrics` | The same in the Prometheus text format. |

`language` is a two-letter code (`en`, `ru`) or a tag with a region or script (`zh-cn`, `pt_BR`, `en-gb`, `es-419`), which is lowercased and written with `-`. Each engine maps a tag to what it has: gtts gets its own spelling (`zh-CN`; it has no Canadian French or European Portuguese, so `fr-ca` and `pt-pt` are `fr` and `pt`), kokorotts speaks `en-gb` with the British phonemizer, xtts gets `zh-cn` for Chinese, and the other engines use the language part (`pt-br` is `pt`). A language an engine does not know is spoken in its default language, usually English (gtts fails instead); with `TTS_LANGUAGE_STRICT=true` it is a 400 that lists the languages the engine has. The strict check covers `/api/tts` without `stream`, `/api/history` and `/v1/audio/speech`, and every engine that lists its languages: all but pyttsx3, and coquitts with a multilingual model other than xtts or a model whose language code has three letters (`ewe`).

`model` picks a model inside the engine on `/api/tts` and `/api/history`: a Piper voice (`en_GB-alan-low`), a Kokoro model file (`kokoro-v1.0.int8.onnx`), a Silero model (`v3_1_ru`) or a Coqui model name (`tts_models/de/thorsten/vits`). `GET /api/engines/<engine>` lists them under `models`, each with its `languages`, `installed` and `default_for` (the languages that use it when a request names no model), next to the engine's `languages`, `output_format`, `max_text_length` and whether it has a voice list; it loads no model, and an unknown engine is a 404. Without `model` the engine picks as before; an id the engine does not list is a 400 that names the ones it has, and so is `model` with `stream=true`, because a stream always uses the engine default model. gtts, pyttsx3 and barktts have no models. Without a model pipertts picks among its installed voices: a region tag (`en-gb`) takes a voice of that region, and a language outside its built-in table takes an installed voice of that language instead of the English one; its language list is the languages of the installed voices.

#### Web UI

Both compose files also start `ttswww`, an nginx container that serves the web UI and proxies `/api/` to `ttssrv`:

```bash
docker compose up --build -d
xdg-open http://localhost:8080      # TTS_WWW_PORT; change it if 8080 is taken
xdg-open https://localhost:8443     # TTS_WWW_TLS_PORT; self-signed certificate, accept it once
```

- **Studio** - type text, pick engine / language / voice, generate, listen, save; every result lands in a history list.
- **Voices** - upload or record WAV voice samples for `coquitts` voice cloning; play, download and delete them.
- **Models** - the engines and the installed / missing models, the same table as `ttsgen --list`.

The gear in the header opens the settings dialog: the default engine, language and voice for the Studio, and whether the curl example is shown; the choices are stored in the browser. The Studio shows a ready-to-copy `curl` command for the current request; it references the token as `$TTS_TOKEN` rather than printing it. The Voices screen can also record a sample from the microphone, which browsers allow only on `https` or `localhost` - over the LAN open the UI through the https port. A self-signed certificate is generated into `./data/certs` on the first start; mount a real one under the same names (`tts.crt`, `tts.key`) to replace it.

When `TTS_TOKENS` is set, the UI opens on a sign-in screen and asks for one of those tokens; the browser keeps it and sends it with every request. Without `TTS_TOKENS` there is no sign-in.

#### Configuration

Every setting is an environment variable; `env.example` documents them all and `.env` next to the compose files is read automatically. The ones you are most likely to change:

| Variable | Default | What it does |
| --- | --- | --- |
| `TTS_TOKENS` | empty | Comma-separated bearer tokens. Empty means no authentication at all. |
| `TTS_ENGINES` | empty | Engines to install and warm up at start, comma-separated (`coquitts,silerotts`). |
| `TTS_ENGINE` | `gtts` | Engine used when a request does not name one. |
| `TTS_LANGUAGE` | `en` | Language used when a request does not name one. |
| `TTS_LANGUAGE_STRICT` | `false` | `true` answers 400 to a language the engine does not list, instead of the engine's fallback to its default language. |
| `TTS_POOL_SIZE` | `1` | Synthesis calls allowed at the same time across all engines; `0` removes the cap and the warmup. |
| `TTS_QUEUE_SIZE` | `8` | Synthesis requests allowed to wait for a free slot; any more get 503 at once. |
| `TTS_HISTORY_MAX` | `200` | Items kept in the history; the oldest are removed when a new one is saved. |
| `TTS_MAX_SAMPLE_BYTES` | `16777216` | Largest voice sample upload (16 MiB). |
| `TTS_MAX_SAMPLES` | `100` | Voice samples kept on the server. |
| `TTS_MAX_BODY_BYTES` | `2097152` | Largest JSON request body (2 MiB). |
| `TTS_STREAM_MAX_CHARS` | `200` | Chunk size for `stream=true`. |
| `TTS_LOG_FORMAT` | `text` | Log format of the server: `text`, or `json` for one JSON object per line with `request_id` and the synthesis fields. |
| `CORS_ORIGINS` | `*` | Allowed origins for `/api/*`. |
| `TTS_PORT` | `5000` | Port of `ttssrv`. |
| `TTS_WWW_PORT`, `TTS_WWW_TLS_PORT` | `8080`, `8443` | http and https ports of the web UI. |
| `COQUITTS_MODEL`, `COQUITTS_SAMPLE` | `xtts_v2`, `default.wav` | Coqui model and the default voice sample. |
| `TZ` | `America/New_York` | Time zone for timestamps in logs and history. |

Outside Docker the CLIs and the server read the same keys from, strongest first: CLI flags, the shell environment, `./ttsgen.conf`, `~/.config/ttsgen.conf`, `./.env.local`, `./.env`. A file never overrides the shell, and `.env` is read only from the current directory.

`TTS_POOL_SIZE` above 1 lets different engines synthesize in parallel; inside one engine the calls are serialized, because the underlying models are not safe to share between threads.

#### Observability

- Every response carries an `X-Request-Id` header; a well-formed one sent by the client (`[A-Za-z0-9._-]`, up to 64 characters) is kept, so a request can be followed through nginx, the server log and the error body.
- Each engine call writes one `Synthesis` log line with the engine, the text length and the engine time, one per chunk of a streamed response, so a slow engine can be told apart from a request that waited for a pool slot.
- `TTS_LOG_FORMAT=json` writes every log line as one JSON object with the request id and those fields as keys.
- `GET /api/metrics` returns the uptime, the pool occupancy and per-engine counters and latency percentiles as JSON; `GET /metrics` exposes the same numbers for Prometheus. Both take the bearer token when `TTS_TOKENS` is set:

```bash
curl localhost:5000/metrics -H "Authorization: Bearer $TTS_TOKEN"
```

#### Security

- Authentication is off until you set `TTS_TOKENS`. Every route except `/api/health` then requires `Authorization: Bearer <token>`, and the web UI asks for the token on a sign-in screen.
- The API listens on all interfaces and the compose files publish `TTS_PORT`, `TTS_WWW_PORT` and `TTS_WWW_TLS_PORT` on the host. On a shared network set a token, or bind the ports to `127.0.0.1` in an override file.
- The https listener uses a self-signed certificate minted on the first start; it is meant for a LAN. On the internet put the UI behind your own reverse proxy with a real certificate.
- Voice samples, history and certificates live under `./data`; back it up and keep it out of the build context.

Report a vulnerability through the repository's Security tab, see [SECURITY.md](SECURITY.md).

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
├── www/            # web UI: Vue 2 without a build step, served by nginx
├── nginx/          # nginx main config and the conf.d template for ttswww
├── docker/         # Docker builds for GPU, CPU and the web UI
├── docs/           # per-engine docs and README translations
└── tests/          # pytest tests, no model downloads and no GPU
```

### Development

Contributions are welcome; [CONTRIBUTING.md](CONTRIBUTING.md) explains the setup, the checks and how an engine is added. To install the development dependencies:

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
