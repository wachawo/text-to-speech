# text-to-speech - eine einheitliche Schnittstelle für TTS-Engines

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | **[Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md)** | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

![Der Studio-Bildschirm der Web-Oberfläche](https://raw.githubusercontent.com/wachawo/text-to-speech/main/docs/images/studio.png)

`text-to-speech` ermöglicht es dir, mit mehreren Sprachsynthese-Engines über eine einzige Schnittstelle zu arbeiten. Du kannst mit dem Online-Dienst gTTS beginnen und später zu lokalem Piper, Silero, Coqui, Bark oder Kokoro wechseln - ohne deine CLI-Befehle, deinen Python-Code oder deine HTTP-Integration neu schreiben zu müssen.

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

`gtts`, `pyttsx3`, `pipertts`, `silerotts` und `kokorotts` laufen problemlos auf der CPU. `coquitts` und `barktts` können ebenfalls ohne GPU laufen, aber die Synthese ist spürbar langsamer - für sie wird eine CUDA-fähige Grafikkarte empfohlen.

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

`gtts` ist die Standard-Engine, daher reicht für den ersten Lauf ein einziger Befehl. Für vollständig lokales Arbeiten wähle eine andere Engine wie `pyttsx3`, `pipertts` oder `silerotts`.
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

Am einfachsten startest du den Server mit Docker:

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech
cp env.example .env                                   # optional: Tokens, Engines, Ports

docker compose up --build -d                          # GPU / CUDA 12.1
docker compose -f docker-compose-cpu.yml up --build -d # nur CPU
```

Die GPU-Variante reicht die Grafikkarte über CDI durch, daher braucht der Host das NVIDIA Container Toolkit (1.14 oder neuer) und eine generierte CDI-Spezifikation, einmal pro Treiber-Update:

```bash
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
```

Sobald der Server läuft, kannst du seinen Status prüfen und eine Synthese-Anfrage senden:

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

Modelle, Stimmen und Verlauf:

```bash
# Was eine Engine bietet: Modelle, Sprachen und Stimmen, gelesen ohne ein Modell zu laden
curl localhost:5000/api/engines/pipertts \
  -H "Authorization: Bearer $TTS_TOKEN"

# Mit einem der dort aufgeführten Modelle synthetisieren
curl -X POST localhost:5000/api/tts \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world","engine":"pipertts","language":"en-gb","model":"en_GB-alan-low"}' \
  -o out.wav

# Installierte und fehlende Modelle, dieselbe Tabelle, die `ttsgen --list` ausgibt
curl localhost:5000/api/models \
  -H "Authorization: Bearer $TTS_TOKEN"

# Eine Stimmprobe für coquitts hochladen (WAV); die Stimme heißt danach "maria"
curl -X POST localhost:5000/api/voices \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -F file=@voice.wav -F name=maria -F engine=coquitts

curl "localhost:5000/api/voices?engine=coquitts" \
  -H "Authorization: Bearer $TTS_TOKEN"

curl "localhost:5000/api/voices/maria/audio?engine=coquitts&download=1" \
  -H "Authorization: Bearer $TTS_TOKEN" -o maria.wav

# In den serverseitigen Verlauf synthetisieren statt in den Antwortkörper
curl -X POST localhost:5000/api/history \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hola mundo","engine":"coquitts","language":"es","voice":"maria"}'

curl "localhost:5000/api/history?limit=50&offset=0" \
  -H "Authorization: Bearer $TTS_TOKEN"

# Audio eines Eintrags; ohne download=1 wird es inline für <audio> ausgeliefert
curl "localhost:5000/api/history/<id>/audio?download=1" \
  -H "Authorization: Bearer $TTS_TOKEN" -o tts.wav

curl -X DELETE localhost:5000/api/history/<id> \
  -H "Authorization: Bearer $TTS_TOKEN"
```

#### OpenAI-kompatible API

Derselbe Server beantwortet auch die OpenAI-Audio-API, sodass Open WebUI, SillyTavern, Home Assistant und die offiziellen SDKs funktionieren, wenn `base_url` auf ihn zeigt und das Bearer-Token als API-Schlüssel dient:

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

- `model` ist ein Engine-Name oder `tts-1` / `tts-1-hd` / `gpt-4o-mini-tts` für die Standard-Engine. Auf `/v1` lässt sich kein Modell innerhalb einer Engine wählen: Die Engine verwendet ihr Standardmodell.
- `voice` ist eine Engine-Stimme; die OpenAI-Stimmennamen (`alloy`, `nova`, ...) wählen den Engine-Standard.
- `response_format`: `mp3` (Standard), `wav`, `pcm`, `opus`, `flac`, `aac`. Die Engines erzeugen WAV oder MP3; alles andere wird mit `ffmpeg` transkodiert, das in den Docker-Images enthalten ist. `speed` (0.25 bis 4.0) wird auf dieselbe Weise angewendet.
- `language` ist eine Erweiterung: ein zweibuchstabiger Code oder ein Tag wie `zh-cn`, Standard `TTS_LANGUAGE`.
- `GET /v1/models` listet die installierten Engines plus `tts-1`; `GET /v1/audio/voices?model=<engine>` listet die Stimmen einer Engine.

#### API-Referenz

Jede Route außer `/api/health` erfordert `Authorization: Bearer <token>`, wenn `TTS_TOKENS` gesetzt ist. Fehler unter `/api/` haben die Form `{"error": "...", "request_id": "..."}`; eine 400-Antwort enthält zusätzlich `message` mit dem Grund, der bei einer ungültigen Anfrage die fehlerhaften Felder nennt (`language: ...`). Fehler unter `/v1/` verwenden das OpenAI-Format.

| Methode | Pfad | Zweck |
| --- | --- | --- |
| GET | `/api/health` | Liveness, `auth`-Flag, Engines, Pool- und Warteschlangengrößen. Kein Token nötig. |
| GET | `/api/engines` | Unterstützte Engines, die installierten und die Standard-Engine. |
| GET | `/api/engines/<engine>` | Modelle, Sprachen, Stimmenliste und Ausgabeformat einer Engine, gelesen ohne ein Modell zu laden. |
| GET | `/api/models` | Installierte und fehlende Modelle pro Engine, die Tabelle, die `ttsgen --list` ausgibt. |
| GET | `/api/voices?engine=&language=&model=` | Stimmen einer Engine; für `coquitts` die Proben mit Größe, Abtastrate und Dauer. Mit `model` die Stimmen dieses Modells. |
| POST | `/api/voices` | Eine WAV-Probe hochladen (`file`, `name`, `engine=coquitts`). |
| GET | `/api/voices/<name>/audio?engine=&download=1` | Eine Probe abspielen oder herunterladen. |
| DELETE | `/api/voices/<name>?engine=` | Eine Probe löschen. |
| POST, GET | `/api/tts` | `text` mit `engine`, `language`, `voice`, `model` synthetisieren; `stream=true` streamt die Abschnitte, sobald sie fertig sind. |
| POST | `/api/history` | In den serverseitigen Verlauf synthetisieren statt in den Antwortkörper. |
| GET | `/api/history?limit=&offset=` | Verlaufseinträge auflisten, neueste zuerst. |
| GET | `/api/history/<id>` | Metadaten eines Eintrags. |
| GET | `/api/history/<id>/audio?download=1` | Das Audio des Eintrags, inline oder als Download. |
| DELETE | `/api/history/<id>` | Einen Eintrag löschen. |
| POST | `/v1/audio/speech` | OpenAI-kompatible Synthese, siehe oben. |
| GET | `/v1/models` | OpenAI-kompatible Modellliste. |
| GET | `/v1/audio/voices?model=` | Stimmen einer Engine. |

`language` ist ein zweibuchstabiger Code (`en`, `ru`) oder ein Tag mit Region oder Schrift (`zh-cn`, `pt_BR`, `en-gb`, `es-419`), der in Kleinbuchstaben und mit `-` geschrieben wird. Jede Engine bildet ein Tag auf das ab, was sie hat: gtts bekommt die eigene Schreibweise (`zh-CN`; es hat kein kanadisches Französisch und kein europäisches Portugiesisch, daher werden `fr-ca` und `pt-pt` zu `fr` und `pt`), kokorotts spricht `en-gb` mit dem britischen Phonemizer, xtts bekommt für Chinesisch `zh-cn`, und die übrigen Engines verwenden den Sprachteil (`pt-br` wird zu `pt`). Eine Sprache, die eine Engine nicht kennt, wird in ihrer Standardsprache gesprochen, meist Englisch (gtts schlägt stattdessen fehl); mit `TTS_LANGUAGE_STRICT=true` ist sie ein 400, der die Sprachen der Engine aufzählt. Die strenge Prüfung gilt für `/api/tts` ohne `stream`, `/api/history` und `/v1/audio/speech` und für jede Engine, die ihre Sprachen auflistet: alle außer pyttsx3 und coquitts mit einem mehrsprachigen Modell außer xtts oder einem Modell mit dreibuchstabigem Sprachcode (`ewe`).

`model` wählt auf `/api/tts` und `/api/history` ein Modell innerhalb der Engine: eine Piper-Stimme (`en_GB-alan-low`), eine Kokoro-Modelldatei (`kokoro-v1.0.int8.onnx`), ein Silero-Modell (`v3_1_ru`) oder einen Coqui-Modellnamen (`tts_models/de/thorsten/vits`). `GET /api/engines/<engine>` führt sie unter `models` auf, jedes mit `languages`, `installed` und `default_for` (den Sprachen, die es verwenden, wenn eine Anfrage kein Modell nennt), dazu die `languages` der Engine, `output_format`, `max_text_length` und ob sie eine Stimmenliste hat; dabei wird kein Modell geladen, und eine unbekannte Engine ergibt 404. Ohne `model` wählt die Engine wie bisher; eine ID, die die Engine nicht aufführt, ist ein 400, der die vorhandenen nennt, ebenso `model` mit `stream=true`, weil ein Stream immer das Standardmodell der Engine verwendet. gtts, pyttsx3 und barktts haben keine Modelle. Ohne Modell wählt pipertts unter den installierten Stimmen: Ein Tag mit Region (`en-gb`) nimmt eine Stimme dieser Region, und eine Sprache außerhalb der eingebauten Tabelle nimmt statt der englischen eine installierte Stimme dieser Sprache; seine Sprachliste sind die Sprachen der installierten Stimmen.

#### Web-Oberfläche

Beide Compose-Dateien starten auch `ttswww`, einen nginx-Container, der die Web-Oberfläche ausliefert und `/api/` an `ttssrv` weiterleitet:

```bash
docker compose up --build -d
xdg-open http://localhost:8080      # TTS_WWW_PORT; ändere ihn, falls 8080 belegt ist
xdg-open https://localhost:8443     # TTS_WWW_TLS_PORT; selbstsigniertes Zertifikat, einmal akzeptieren
```

- **Studio** - Text eingeben, Engine / Sprache / Stimme wählen, generieren, anhören, speichern; jedes Ergebnis landet in einer Verlaufsliste.
- **Voices** - WAV-Stimmproben für das Stimmenklonen mit `coquitts` hochladen oder aufnehmen; abspielen, herunterladen und löschen.
- **Models** - die Engines und die installierten / fehlenden Modelle, dieselbe Tabelle wie `ttsgen --list`.

Das Zahnrad in der Kopfzeile öffnet den Einstellungsdialog: Standard-Engine, -Sprache und -Stimme für das Studio sowie ob das curl-Beispiel angezeigt wird; die Auswahl wird im Browser gespeichert. Das Studio zeigt einen kopierfertigen `curl`-Befehl für die aktuelle Anfrage; er referenziert das Token als `$TTS_TOKEN`, statt es auszugeben. Der Voices-Bildschirm kann eine Probe auch über das Mikrofon aufnehmen, was Browser nur über `https` oder `localhost` erlauben - im LAN öffne die Oberfläche über den https-Port. Beim ersten Start wird ein selbstsigniertes Zertifikat nach `./data/certs` erzeugt; um es zu ersetzen, mounte ein echtes unter denselben Namen (`tts.crt`, `tts.key`).

Wenn `TTS_TOKENS` gesetzt ist, öffnet sich die Oberfläche mit einem Anmeldebildschirm und fragt nach einem dieser Tokens; der Browser behält es und sendet es mit jeder Anfrage. Ohne `TTS_TOKENS` gibt es keine Anmeldung.

#### Konfiguration

Jede Einstellung ist eine Umgebungsvariable; `env.example` dokumentiert sie alle, und `.env` neben den Compose-Dateien wird automatisch gelesen. Die, die du am ehesten ändern wirst:

| Variable | Standard | Was sie bewirkt |
| --- | --- | --- |
| `TTS_TOKENS` | leer | Kommagetrennte Bearer-Tokens. Leer bedeutet gar keine Authentifizierung. |
| `TTS_ENGINES` | leer | Engines, die beim Start installiert und vorgewärmt werden, kommagetrennt (`coquitts,silerotts`). |
| `TTS_ENGINE` | `gtts` | Engine, die verwendet wird, wenn eine Anfrage keine nennt. |
| `TTS_LANGUAGE` | `en` | Sprache, die verwendet wird, wenn eine Anfrage keine nennt. |
| `TTS_LANGUAGE_STRICT` | `false` | `true` beantwortet eine Sprache, die die Engine nicht auflistet, mit 400 statt mit dem Rückfall der Engine auf ihre Standardsprache. |
| `TTS_POOL_SIZE` | `1` | Gleichzeitig erlaubte Synthese-Aufrufe über alle Engines hinweg; `0` entfernt das Limit und das Vorwärmen. |
| `TTS_QUEUE_SIZE` | `8` | Synthese-Anfragen, die auf einen freien Platz warten dürfen; weitere erhalten sofort 503. |
| `TTS_HISTORY_MAX` | `200` | Im Verlauf behaltene Einträge; die ältesten werden entfernt, wenn ein neuer gespeichert wird. |
| `TTS_MAX_SAMPLE_BYTES` | `16777216` | Größter Upload einer Stimmprobe (16 MiB). |
| `TTS_MAX_SAMPLES` | `100` | Auf dem Server behaltene Stimmproben. |
| `TTS_MAX_BODY_BYTES` | `2097152` | Größter JSON-Anfragekörper (2 MiB). |
| `TTS_STREAM_MAX_CHARS` | `200` | Abschnittsgröße für `stream=true`. |
| `CORS_ORIGINS` | `*` | Erlaubte Origins für `/api/*`. |
| `TTS_PORT` | `5000` | Port von `ttssrv`. |
| `TTS_WWW_PORT`, `TTS_WWW_TLS_PORT` | `8080`, `8443` | http- und https-Ports der Web-Oberfläche. |
| `COQUITTS_MODEL`, `COQUITTS_SAMPLE` | `xtts_v2`, `default.wav` | Coqui-Modell und die Standard-Stimmprobe. |
| `TZ` | `America/New_York` | Zeitzone für Zeitstempel in Logs und Verlauf. |

Außerhalb von Docker lesen die CLIs und der Server dieselben Schlüssel aus, stärkste zuerst: CLI-Flags, die Shell-Umgebung, `./ttsgen.conf`, `~/.config/ttsgen.conf`, `./.env.local`, `./.env`. Eine Datei überschreibt niemals die Shell, und `.env` wird nur aus dem aktuellen Verzeichnis gelesen.

`TTS_POOL_SIZE` über 1 lässt verschiedene Engines parallel synthetisieren; innerhalb einer Engine werden die Aufrufe serialisiert, weil die zugrunde liegenden Modelle nicht sicher zwischen Threads geteilt werden können.

#### Sicherheit

- Die Authentifizierung ist aus, bis du `TTS_TOKENS` setzt. Danach erfordert jede Route außer `/api/health` `Authorization: Bearer <token>`, und die Web-Oberfläche fragt auf einem Anmeldebildschirm nach dem Token.
- Die API lauscht auf allen Schnittstellen, und die Compose-Dateien veröffentlichen `TTS_PORT`, `TTS_WWW_PORT` und `TTS_WWW_TLS_PORT` auf dem Host. In einem geteilten Netzwerk setze ein Token oder binde die Ports in einer Override-Datei an `127.0.0.1`.
- Der https-Listener verwendet ein beim ersten Start erzeugtes selbstsigniertes Zertifikat; es ist für ein LAN gedacht. Im Internet stelle die Oberfläche hinter deinen eigenen Reverse-Proxy mit einem echten Zertifikat.
- Stimmproben, Verlauf und Zertifikate liegen unter `./data`; sichere das Verzeichnis und halte es aus dem Build-Kontext heraus.

Melde eine Sicherheitslücke über den Security-Tab des Repositorys, siehe [SECURITY.md](https://github.com/wachawo/text-to-speech/blob/main/SECURITY.md).

Für die Arbeit mit dem Server und zum Testen gibt es einen separaten CLI-Client, `ttsapi`. Er hat dieselben wichtigsten Flags wie `ttsgen`, aber die Synthese läuft auf dem Server. Serveradresse und Token werden aus `TTS_URL` und `TTS_TOKEN` gelesen.

```bash
ttsapi "Hello world"
ttsapi -i long.txt --output play,file --file out.mp3
```

### Projektstruktur

```text
text-to-speech/
├── ttsgen.py / ttsplay.py / ttsrec.py / ttsapi.py   # CLI-Befehle
├── engines/        # Engines: gTTS, Piper, Silero, Coqui, Bark, Kokoro und andere
├── libs/           # gemeinsamer Kern: API, Werkzeuge, Wiedergabe, Ausnahmen
├── install/        # Installer für ttsgen --install <engine>
├── ttssrv/         # Flask-HTTP-Server
├── www/            # Web-Oberfläche: Vue 2 ohne Build-Schritt, ausgeliefert von nginx
├── nginx/          # nginx-Hauptkonfiguration und die conf.d-Vorlage für ttswww
├── docker/         # Docker-Builds für GPU, CPU und die Web-Oberfläche
├── docs/           # Dokumentation je Engine und README-Übersetzungen
└── tests/          # pytest-Tests, keine Modell-Downloads und keine GPU
```

### Entwicklung

Beiträge sind willkommen; [CONTRIBUTING.md](https://github.com/wachawo/text-to-speech/blob/main/CONTRIBUTING.md) erklärt das Setup, die Prüfungen und wie eine Engine hinzugefügt wird. So installierst du die Entwicklungsabhängigkeiten:

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

`is_available()` prüft, dass die Abhängigkeiten importierbar sind, und `generate()` nimmt Text und Konfiguration entgegen und gibt das Audio als MP3- oder WAV-Bytes zurück. Danach ist die Engine automatisch in der CLI und in der API verfügbar.

Detaillierte Parameter und Besonderheiten jeder Engine sind in [`docs/`](https://github.com/wachawo/text-to-speech/blob/main/docs/ENGINES.md) beschrieben.

### Lizenz

[MIT](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
