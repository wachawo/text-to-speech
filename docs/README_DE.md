## text-to-speech — beliebte TTS-Engines hinter einer API

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

Installieren Sie beliebte Online-/Offline-TTS-Engines (gTTS, espeak, Piper, Silero, Coqui, Bark, Kokoro) und nutzen Sie sie über eine einzige CLI, Python-API und einen HTTP-Server.

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | **[Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md)** | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

- **Eine Schnittstelle, viele Engines.** Wählen Sie eine Engine und rufen Sie sie auf dieselbe Weise über die CLI (`ttsgen`), Python (`libs.api`) oder HTTP auf — wechseln Sie zwischen Cloud und lokal, ohne den Code zu ändern.
- **API-Server für Ihr LAN.** Führen Sie `ttssrv` aus, damit andere Rechner über HTTP synthetisieren (`POST /api/tts`); das Modell wird einmal beim Start geladen und die Anfragen teilen sich einen Pool.

### Engines

| Engine | Offline | Hardware | Qualität | Am besten für |
|---|---|---|---|---|
| `gtts` | ❌ online | CPU | ★★★★ | 100+ Sprachen, keine Einrichtung |
| `pyttsx3` | ✅ | CPU | ★★ | minimale Installation (espeak / SAPI) |
| `pipertts` | ✅ | CPU | ★★★★ | schnell offline, 50+ Sprachen |
| `silerotts` | ✅ | CPU | ★★★★ | schnell offline, Russisch |
| `kokorotts` | ✅ | CPU | ★★★★ | schnell offline, mehrsprachig |
| `coquitts` | ✅ | CPU / **GPU** | ★★★★★ | beste Qualität, Stimmenklonen |
| `barktts` | ✅ | CPU / **GPU** | ★★★★★ | Emotionen, Musik, Gesang |

`gtts`, `pyttsx3`, `pipertts`, `silerotts`, `kokorotts` laufen problemlos auf der CPU. `coquitts` und `barktts` laufen ebenfalls auf der CPU, sind aber langsam — eine CUDA-GPU wird empfohlen.

### Installation (pip)

```bash
pip install git+https://github.com/wachawo/text-to-speech.git
```

Dies installiert die CLI nur mit leichtgewichtigen Abhängigkeiten. Neuronale Engines (`pipertts`, `silerotts`, `coquitts`, `barktts`, `kokorotts`) laden `torch`/Modelle bei Bedarf über `ttsgen --install <engine>`.

```bash
ttsgen "Hello world"                  # abspielen (Standard-Engine: gtts, online)
ttsgen "Hello world" -f out.mp3       # in eine Datei speichern
ttsgen "Hello world" -e pyttsx3       # vollständig offline
ttsgen "Hola amigo!"  -l es           # Sprache wählen
ttsgen --install coquitts             # eine neuronale Offline-Engine + Modelle hinzufügen
ttsgen "Hello world" -e coquitts -f out.wav
ttsgen --list                         # Engines + installierte Modelle
ttsgen "Hello world" --stdout | ttsplay
```

Python:

```python
from libs.api import text_to_speech_file, text_to_speech_bytes

text_to_speech_file("Hello world", engine="gtts")
audio = text_to_speech_bytes("Hello world", engine="pipertts", language="en")
```

### Server (klonen)

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech
docker compose up --build -d                          # GPU (CUDA 12.1)
docker compose -f docker-compose-cpu.yml up --build -d # nur CPU
```

Synthese über HTTP anfordern:

```bash
curl localhost:5000/api/health
curl localhost:5000/api/engines -H "Authorization: Bearer $TTS_TOKEN"
curl "localhost:5000/api/voices?engine=silerotts&language=ru" -H "Authorization: Bearer $TTS_TOKEN"

curl -X POST localhost:5000/api/tts \
  -H "Authorization: Bearer $TTS_TOKEN" -H "Content-Type: application/json" \
  -d '{"text":"Hello world","engine":"gtts"}' -o out.mp3
```

Oder verwenden Sie `ttsapi` — dieselben Flags wie `ttsgen`, aber die Synthese läuft auf dem Server (`TTS_URL` / `TTS_TOKEN` aus der Konfiguration):

```bash
ttsapi "Hello world"
ttsapi -i long.txt --output play,file --file out.mp3
```

### Projektstruktur

```
text-to-speech/
├── ttsgen.py / ttsplay.py / ttsrec.py / ttsapi.py   # CLI-Einstiegspunkte
├── engines/        # einsteckbare Engines (gtts, piper, silero, coqui, bark, kokoro, …)
├── libs/           # Kern: api.py, tools.py, playback.py, exceptions.py
├── install/        # `ttsgen --install <engine>` Installer
├── ttssrv/         # Flask-HTTP-Server (Docker / python3 ttssrv/app1.py)
├── docker/         # gpu/- und cpu/-Builds (Dockerfile + requirements)
├── docs/           # Anleitungen pro Engine + Übersetzungen
└── tests/          # pytest-Suite (Engines gemockt, keine Modelle/GPU erforderlich)
```

### Entwicklerhinweise

```bash
pip install -e ".[dev]"
pytest                 # Tests + Coverage
ruff check . && black .
```

Fügen Sie eine Engine hinzu, indem Sie `engines/<name>.py` mit zwei Funktionen ablegen — sie erscheint automatisch in der CLI und der API:

```python
def is_available() -> bool: ...                  # Abhängigkeiten importierbar?
def generate(text: str, config: dict) -> bytes:  # MP3-/WAV-Bytes zurückgeben
    ...
```

Die Einrichtung pro Engine und die vollständige Engine-Anleitung finden Sie in [`docs/`](docs/ENGINES.md).

### Lizenz

[MIT](LICENSE)
