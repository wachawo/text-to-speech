## text-to-speech — una única interfaz para motores de TTS

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | **[Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md)** | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

> _Disculpas de antemano: esta traducción se hizo con Claude Code. Si eres hablante nativo y detectas algún error, házmelo saber, por favor._

`text-to-speech` te permite trabajar con varios motores de síntesis de voz a través de una sola interfaz. Puedes empezar con gTTS en línea y más tarde cambiar a Piper, Silero, Coqui, Bark o Kokoro locales, sin reescribir tus comandos de la CLI, tu código Python ni tu integración HTTP.

El proyecto encaja con el uso local, la automatización y la ejecución de tu propio servidor TTS en la red.

* **Una sola forma de trabajar con distintos motores.** Elige el motor que necesites y úsalo a través de la CLI (`ttsgen`), la API de Python (`libs.api`) o la API HTTP.
* **Puedes trabajar totalmente en local.** Piper, Silero, Coqui, Bark, Kokoro y `pyttsx3` se ejecutan todos en tu propia máquina.
* **Se incluye un servidor HTTP listo para usar.** `ttssrv` carga el modelo al iniciarse y atiende las solicitudes de otras máquinas de tu red local.

### Motores

| Motor       | Sin conexión | Hardware      | Calidad | Ideal para                                       |
| ----------- | ------------ | ------------- | ------- | ------------------------------------------------ |
| `gtts`      | ❌      | CPU           | ★★★★    | un inicio rápido y un gran número de idiomas     |
| `pyttsx3`   | ✅      | CPU           | ★★      | voz local sencilla mediante espeak o SAPI        |
| `pipertts`  | ✅      | CPU           | ★★★★    | síntesis offline rápida en muchos idiomas        |
| `silerotts` | ✅      | CPU           | ★★★★    | voz en ruso y una configuración local ligera     |
| `kokorotts` | ✅      | CPU           | ★★★★    | síntesis offline multilingüe                     |
| `coquitts`  | ✅      | CPU / **GPU** | ★★★★★   | voces de alta calidad y clonación de voz         |
| `barktts`   | ✅      | CPU / **GPU** | ★★★★★   | voz expresiva, emociones, música y canto         |

`gtts`, `pyttsx3`, `pipertts`, `silerotts` y `kokorotts` funcionan bien en CPU. `coquitts` y `barktts` también pueden ejecutarse sin GPU, pero la síntesis es notablemente más lenta; para ellos se recomienda una tarjeta gráfica compatible con CUDA.

### Instalación

La instalación base configura la CLI y sus dependencias ligeras:

```bash
pip install git+https://github.com/wachawo/text-to-speech.git
```

En Linux, el motor sin conexión `pyttsx3` también necesita el paquete del sistema `espeak`:

```bash
sudo apt install espeak espeak-data libespeak1
```

Los motores adicionales y sus modelos se instalan por separado, cuando realmente los necesitas:

```bash
ttsgen --install coquitts
```

Ejemplos de uso de la CLI:

```bash
ttsgen "Hello world"                  # pronuncia el texto con gTTS
ttsgen "Hello world" -f out.mp3       # guarda el resultado en un archivo
ttsgen "Hello world" -e pyttsx3       # usa un motor local
ttsgen "Hola amigo!" -l es            # elige un idioma
ttsgen --install coquitts             # instala Coqui TTS y sus modelos
ttsgen "Hello world" -e coquitts -f out.wav
ttsgen --list                         # muestra los motores y modelos disponibles
ttsgen "Hello world" --stdout | ttsplay
```

`gtts` es el motor por defecto, así que un único comando basta para la primera ejecución. Para trabajar de forma totalmente local, elige otro motor como `pyttsx3`, `pipertts` o `silerotts`.
Mi elección: `coquitts` por su calidad y su voz de sonido natural, `silerotts` por su generación rápida.

### API de Python

En Python hay funciones para guardar el resultado en un archivo u obtener el audio como bytes:

```python
from libs.api import text_to_speech_file, text_to_speech_bytes

text_to_speech_file("Hello world", engine="gtts")

audio = text_to_speech_bytes(
    "Hello world",
    engine="pipertts",
    language="en",
)
```

### Servidor HTTP

Es más fácil ejecutar el servidor con Docker:

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech

docker compose up --build -d                          # GPU / CUDA 12.1
docker compose -f docker-compose-cpu.yml up --build -d # solo CPU
```

Una vez en marcha, puedes comprobar el estado del servidor y enviar una solicitud de síntesis:

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

Para trabajar con el servidor y probarlo hay un cliente de CLI aparte, `ttsapi`. Tiene los mismos flags principales que `ttsgen`, pero la síntesis se ejecuta en el servidor. La dirección del servidor y el token se toman de `TTS_URL` y `TTS_TOKEN`.

```bash
ttsapi "Hello world"
ttsapi -i long.txt --output play,file --file out.mp3
```

### Estructura del proyecto

```text
text-to-speech/
├── ttsgen.py / ttsplay.py / ttsrec.py / ttsapi.py   # comandos de la CLI
├── engines/        # motores: gTTS, Piper, Silero, Coqui, Bark, Kokoro y otros
├── libs/           # núcleo compartido: API, herramientas, reproducción, excepciones
├── install/        # instaladores para ttsgen --install <engine>
├── ttssrv/         # servidor HTTP Flask
├── docker/         # compilaciones de Docker para GPU y CPU
├── docs/           # documentación por motor y traducciones del README
└── tests/          # pruebas de pytest, sin descargas de modelos ni GPU
```

### Desarrollo

Para instalar las dependencias de desarrollo:

```bash
pip install -e ".[dev]"
```

Comprobaciones antes de hacer commit:

```bash
pytest
ruff check .
black .
```

Un nuevo motor se integra mediante un archivo `engines/<name>.py`. Solo necesitas implementar dos funciones:

```python
def is_available() -> bool:
    ...

def generate(text: str, config: dict) -> bytes:
    ...
```

`is_available()` comprueba que las dependencias se puedan importar, y `generate()` toma el texto y la configuración y devuelve el audio como bytes MP3 o WAV. Después de eso, el motor queda disponible automáticamente en la CLI y la API.

Los parámetros detallados y las particularidades de cada motor se describen en [`docs/`](ENGINES.md).

### Licencia

[MIT](../LICENSE)
