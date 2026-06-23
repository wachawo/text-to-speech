## text-to-speech — motores TTS populares tras una sola API

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

Instala motores TTS populares en línea/sin conexión (gTTS, espeak, Piper, Silero, Coqui, Bark, Kokoro) y úsalos a través de una sola CLI, API de Python y servidor HTTP.

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | **[Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md)** | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

- **Una interfaz, muchos motores.** Elige un motor y llámalo de la misma forma desde la CLI (`ttsgen`), Python (`libs.api`) o HTTP — cambia entre la nube y lo local sin cambiar el código.
- **Servidor API para tu LAN.** Ejecuta `ttssrv` para que otras máquinas sinteticen por HTTP (`POST /api/tts`); el modelo se carga una sola vez al inicio y las solicitudes comparten un pool.

### Motores

| Motor | Sin conexión | Hardware | Calidad | Ideal para |
|---|---|---|---|---|
| `gtts` | ❌ en línea | CPU | ★★★★ | más de 100 idiomas, sin configuración |
| `pyttsx3` | ✅ | CPU | ★★ | instalación mínima (espeak / SAPI) |
| `pipertts` | ✅ | CPU | ★★★★ | rápido sin conexión, más de 50 idiomas |
| `silerotts` | ✅ | CPU | ★★★★ | rápido sin conexión, ruso |
| `kokorotts` | ✅ | CPU | ★★★★ | rápido sin conexión, multiidioma |
| `coquitts` | ✅ | CPU / **GPU** | ★★★★★ | mejor calidad, clonación de voz |
| `barktts` | ✅ | CPU / **GPU** | ★★★★★ | emociones, música, canto |

`gtts`, `pyttsx3`, `pipertts`, `silerotts`, `kokorotts` funcionan bien en CPU. `coquitts` y `barktts` también funcionan en CPU, pero son lentos — se recomienda una GPU CUDA.

### Instalación (pip)

```bash
pip install git+https://github.com/wachawo/text-to-speech.git
```

Esto instala la CLI solo con dependencias ligeras. Los motores neuronales (`pipertts`, `silerotts`, `coquitts`, `barktts`, `kokorotts`) descargan `torch`/modelos bajo demanda mediante `ttsgen --install <engine>`.

```bash
ttsgen "Hello world"                  # reproducir (motor por defecto: gtts, en línea)
ttsgen "Hello world" -f out.mp3       # guardar en un archivo
ttsgen "Hello world" -e pyttsx3       # totalmente sin conexión
ttsgen "Hola amigo!"  -l es           # elegir idioma
ttsgen --install coquitts             # añadir un motor neuronal sin conexión + modelos
ttsgen "Hello world" -e coquitts -f out.wav
ttsgen --list                         # motores + modelos instalados
ttsgen "Hello world" --stdout | ttsplay
```

Python:

```python
from libs.api import text_to_speech_file, text_to_speech_bytes

text_to_speech_file("Hello world", engine="gtts")
audio = text_to_speech_bytes("Hello world", engine="pipertts", language="en")
```

### Servidor (clonar)

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech
docker compose up --build -d                          # GPU (CUDA 12.1)
docker compose -f docker-compose-cpu.yml up --build -d # solo CPU
```

Solicitar síntesis por HTTP:

```bash
curl localhost:5000/api/health
curl localhost:5000/api/engines -H "Authorization: Bearer $TTS_TOKEN"
curl "localhost:5000/api/voices?engine=silerotts&language=ru" -H "Authorization: Bearer $TTS_TOKEN"

curl -X POST localhost:5000/api/tts \
  -H "Authorization: Bearer $TTS_TOKEN" -H "Content-Type: application/json" \
  -d '{"text":"Hello world","engine":"gtts"}' -o out.mp3
```

O usa `ttsapi` — los mismos parámetros que `ttsgen`, pero la síntesis se ejecuta en el servidor (`TTS_URL` / `TTS_TOKEN` desde la configuración):

```bash
ttsapi "Hello world"
ttsapi -i long.txt --output play,file --file out.mp3
```

### Estructura del proyecto

```
text-to-speech/
├── ttsgen.py / ttsplay.py / ttsrec.py / ttsapi.py   # puntos de entrada de la CLI
├── engines/        # motores conectables (gtts, piper, silero, coqui, bark, kokoro, …)
├── libs/           # núcleo: api.py, tools.py, playback.py, exceptions.py
├── install/        # instaladores de `ttsgen --install <engine>`
├── ttssrv/         # servidor HTTP Flask (Docker / python3 ttssrv/app1.py)
├── docker/         # compilaciones gpu/ y cpu/ (Dockerfile + requirements)
├── docs/           # guías por motor + traducciones
└── tests/          # suite de pytest (motores simulados, sin necesidad de modelos/GPU)
```

### Notas para desarrolladores

```bash
pip install -e ".[dev]"
pytest                 # pruebas + cobertura
ruff check . && black .
```

Añade un motor colocando `engines/<name>.py` con dos funciones — aparece automáticamente en la CLI y la API:

```python
def is_available() -> bool: ...                  # ¿dependencias importables?
def generate(text: str, config: dict) -> bytes:  # devolver bytes MP3/WAV
    ...
```

La configuración por motor y la guía completa de motores están en [`docs/`](docs/ENGINES.md).

### Licencia

[MIT](LICENSE)
