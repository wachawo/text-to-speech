## text-to-speech — i motori TTS più diffusi dietro un'unica API

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

Installa i più diffusi motori TTS online/offline (gTTS, espeak, Piper, Silero, Coqui, Bark, Kokoro) e usali tramite una sola CLI, API Python e server HTTP.

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | **[Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md)** | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

- **Un'unica interfaccia, molti motori.** Scegli un motore e chiamalo allo stesso modo dalla CLI (`ttsgen`), da Python (`libs.api`) o via HTTP — passa dal cloud al locale senza modificare il codice.
- **Server API per la tua LAN.** Avvia `ttssrv` così altre macchine sintetizzano via HTTP (`POST /api/tts`); il modello si carica una sola volta all'avvio e le richieste condividono un pool.

### Motori

| Motore | Offline | Hardware | Qualità | Ideale per |
|---|---|---|---|---|
| `gtts` | ❌ online | CPU | ★★★★ | 100+ lingue, zero configurazione |
| `pyttsx3` | ✅ | CPU | ★★ | installazione minima (espeak / SAPI) |
| `pipertts` | ✅ | CPU | ★★★★ | veloce offline, 50+ lingue |
| `silerotts` | ✅ | CPU | ★★★★ | veloce offline, russo |
| `kokorotts` | ✅ | CPU | ★★★★ | veloce offline, multilingua |
| `coquitts` | ✅ | CPU / **GPU** | ★★★★★ | qualità migliore, clonazione vocale |
| `barktts` | ✅ | CPU / **GPU** | ★★★★★ | emozioni, musica, canto |

`gtts`, `pyttsx3`, `pipertts`, `silerotts`, `kokorotts` funzionano bene su CPU. `coquitts` e `barktts` funzionano anche su CPU ma sono lenti — si consiglia una GPU CUDA.

### Installazione (pip)

```bash
pip install git+https://github.com/wachawo/text-to-speech.git
```

Questo installa la CLI con sole dipendenze leggere. I motori neurali (`pipertts`, `silerotts`, `coquitts`, `barktts`, `kokorotts`) scaricano `torch`/modelli su richiesta tramite `ttsgen --install <engine>`.

```bash
ttsgen "Hello world"                  # riproduci (motore predefinito: gtts, online)
ttsgen "Hello world" -f out.mp3       # salva su un file
ttsgen "Hello world" -e pyttsx3       # completamente offline
ttsgen "Hola amigo!"  -l es           # scegli la lingua
ttsgen --install coquitts             # aggiungi un motore neurale offline + modelli
ttsgen "Hello world" -e coquitts -f out.wav
ttsgen --list                         # motori + modelli installati
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
docker compose -f docker-compose-cpu.yml up --build -d # solo CPU
```

Richiedi la sintesi via HTTP:

```bash
curl localhost:5000/api/health
curl localhost:5000/api/engines -H "Authorization: Bearer $TTS_TOKEN"
curl "localhost:5000/api/voices?engine=silerotts&language=ru" -H "Authorization: Bearer $TTS_TOKEN"

curl -X POST localhost:5000/api/tts \
  -H "Authorization: Bearer $TTS_TOKEN" -H "Content-Type: application/json" \
  -d '{"text":"Hello world","engine":"gtts"}' -o out.mp3
```

Oppure usa `ttsapi` — stessi flag di `ttsgen`, ma la sintesi viene eseguita sul server (`TTS_URL` / `TTS_TOKEN` dalla configurazione):

```bash
ttsapi "Hello world"
ttsapi -i long.txt --output play,file --file out.mp3
```

### Struttura del progetto

```
text-to-speech/
├── ttsgen.py / ttsplay.py / ttsrec.py / ttsapi.py   # punti di ingresso CLI
├── engines/        # motori plugin (gtts, piper, silero, coqui, bark, kokoro, …)
├── libs/           # core: api.py, tools.py, playback.py, exceptions.py
├── install/        # installer `ttsgen --install <engine>`
├── ttssrv/         # server HTTP Flask (Docker / python3 ttssrv/app1.py)
├── docker/         # build gpu/ e cpu/ (Dockerfile + requirements)
├── docs/           # guide per motore + traduzioni
└── tests/          # suite pytest (motori mockati, nessun modello/GPU richiesto)
```

### Note per gli sviluppatori

```bash
pip install -e ".[dev]"
pytest                 # test + copertura
ruff check . && black .
```

Aggiungi un motore inserendo `engines/<name>.py` con due funzioni — appare automaticamente nella CLI e nell'API:

```python
def is_available() -> bool: ...                  # dipendenze importabili?
def generate(text: str, config: dict) -> bytes:  # restituisci byte MP3/WAV
    ...
```

La configurazione per ogni motore e la guida completa dei motori si trovano in [`docs/`](docs/ENGINES.md).

### Licenza

[MIT](LICENSE)
