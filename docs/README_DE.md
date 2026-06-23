## text-to-speech — eine einheitliche Schnittstelle für TTS-Engines

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | **[Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md)** | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

`text-to-speech` ermöglicht es dir, mit mehreren Sprachsynthese-Engines über eine einzige Schnittstelle zu arbeiten. Du kannst mit dem Online-Dienst gTTS beginnen und später zu lokalem Piper, Silero, Coqui, Bark oder Kokoro wechseln — ohne deine CLI-Befehle, deinen Python-Code oder deine HTTP-Integration neu schreiben zu müssen.

Das Projekt eignet sich für die lokale Nutzung, für die Automatisierung und für den Betrieb eines eigenen TTS-Servers im Netzwerk.

* **Ein einheitlicher Weg, mit verschiedenen Engines zu arbeiten.** Wähle die benötigte Engine und rufe sie über die CLI (`ttsgen`), die Python-API (`libs.api`) oder die HTTP-API auf.
* **Du kannst vollständig lokal arbeiten.** Piper, Silero, Coqui, Bark, Kokoro und `pyttsx3` laufen alle auf deinem eigenen Rechner.
* **Ein einsatzbereiter HTTP-Server ist enthalten.** `ttssrv` lädt das Modell beim Start und beantwortet Anfragen von anderen Rechnern in deinem lokalen Netzwerk.

### Engines

| Engine      | Offline | Hardware      | Qualität | Gut für                                        |
| ----------- | ------- | ------------- | -------- | ---------------------------------------------- |
| `gtts`      | ❌      | CPU           | ★★★★    | einen schnellen Einstieg und eine große Anzahl an Sprachen |
| `pyttsx3`   | ✅      | CPU           | ★★      | einfache lokale Sprachausgabe über espeak oder SAPI |
| `pipertts`  | ✅      | CPU           | ★★★★    | schnelle Offline-Synthese in vielen Sprachen   |
| `silerotts` | ✅      | CPU           | ★★★★    | russische Sprache und ein leichtgewichtiges lokales Setup |
| `kokorotts` | ✅      | CPU           | ★★★★    | mehrsprachige Offline-Synthese                 |
| `coquitts`  | ✅      | CPU / **GPU** | ★★★★★   | hochwertige Stimmen und Stimmenklonen          |
| `barktts`   | ✅      | CPU / **GPU** | ★★★★★   | ausdrucksstarke Sprache, Emotionen, Musik und Gesang |

`gtts`, `pyttsx3`, `pipertts`, `silerotts` und `kokorotts` laufen problemlos auf der CPU. `coquitts` und `barktts` können ebenfalls ohne GPU laufen, aber die Synthese ist spürbar langsamer — für sie wird eine CUDA-fähige Grafikkarte empfohlen.

### Installation

Die Basisinstallation richtet die CLI und ihre leichtgewichtigen Abhängigkeiten ein:

```bash
pip install git+https://github.com/wachawo/text-to-speech.git
```

Unter Linux benötigt die Offline-Engine `pyttsx3` außerdem das System-Paket `espeak`:

```bash
sudo apt install espeak espeak-data libespeak1
```

Zusätzliche Engines und ihre Modelle werden separat installiert, wenn du sie tatsächlich brauchst:

```bash
ttsgen --install coquitts
```

Beispiele für die CLI-Nutzung:

```bash
ttsgen "Hello world"                  # den Text mit gTTS sprechen
ttsgen "Hello world" -f out.mp3       # das Ergebnis in einer Datei speichern
ttsgen "Hello world" -e pyttsx3       # eine lokale Engine verwenden
ttsgen "Hola amigo!" -l es            # eine Sprache wählen
ttsgen --install coquitts             # Coqui TTS und seine Modelle installieren
ttsgen "Hello world" -e coquitts -f out.wav
ttsgen --list                         # verfügbare Engines und Modelle anzeigen
ttsgen "Hello world" --stdout | ttsplay
```

`gtts` ist die Standardeinstellung, daher genügt ein einziger Befehl für den ersten Start. Für vollständig lokales Arbeiten wähle eine andere Engine wie `pyttsx3`, `pipertts` oder `silerotts`.
Meine Wahl: `coquitts` für Qualität und natürlich klingende Sprache, `silerotts` für schnelle Generierung.

### Python-API

In Python gibt es Funktionen, um das Ergebnis in einer Datei zu speichern oder das Audio als Bytes zu erhalten:

```python
from libs.api import text_to_speech_file, text_to_speech_bytes

text_to_speech_file("Hello world", engine="gtts")

audio = text_to_speech_bytes(
    "Hello world",
    engine="pipertts",
    language="en",
)
```

### HTTP-Server

Am einfachsten lässt sich der Server mit Docker betreiben:

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech

docker compose up --build -d                          # GPU / CUDA 12.1
docker compose -f docker-compose-cpu.yml up --build -d # nur CPU
```

Sobald er läuft, kannst du den Serverstatus prüfen und eine Synthese-Anfrage senden:

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

Für die Arbeit mit dem Server und zum Testen gibt es einen separaten CLI-Client, `ttsapi`. Er hat dieselben wichtigsten Flags wie `ttsgen`, aber die Synthese läuft auf dem Server. Die Serveradresse und das Token werden aus `TTS_URL` und `TTS_TOKEN` übernommen.

```bash
ttsapi "Hello world"
ttsapi -i long.txt --output play,file --file out.mp3
```

### Projektstruktur

```text
text-to-speech/
├── ttsgen.py / ttsplay.py / ttsrec.py / ttsapi.py   # CLI-Befehle
├── engines/        # Engines: gTTS, Piper, Silero, Coqui, Bark, Kokoro und andere
├── libs/           # gemeinsamer Kern: API, Tools, Wiedergabe, Ausnahmen
├── install/        # Installer für ttsgen --install <engine>
├── ttssrv/         # Flask-HTTP-Server
├── docker/         # Docker-Builds für GPU und CPU
├── docs/           # Doku pro Engine und README-Übersetzungen
└── tests/          # pytest-Tests, ohne Modell-Downloads und ohne GPU
```

### Entwicklung

So installierst du die Entwicklungsabhängigkeiten:

```bash
pip install -e ".[dev]"
```

Prüfungen vor dem Commit:

```bash
pytest
ruff check .
black .
```

Eine neue Engine wird über eine Datei `engines/<name>.py` eingebunden. Du musst nur zwei Funktionen implementieren:

```python
def is_available() -> bool:
    ...

def generate(text: str, config: dict) -> bytes:
    ...
```

`is_available()` prüft, ob die Abhängigkeiten importierbar sind, und `generate()` nimmt den Text und die Konfiguration entgegen und gibt das Audio als MP3- oder WAV-Bytes zurück. Danach wird die Engine in der CLI und der API automatisch verfügbar.

Ausführliche Parameter und Besonderheiten jeder Engine sind in [`docs/`](ENGINES.md) beschrieben.

### Lizenz

[MIT](../LICENSE)
