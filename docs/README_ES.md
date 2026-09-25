# text-to-speech - una única interfaz para motores de TTS

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | **[Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md)** | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

![La pantalla Studio de la interfaz web](https://raw.githubusercontent.com/wachawo/text-to-speech/main/docs/images/studio.png)

`text-to-speech` te permite trabajar con varios motores de síntesis de voz a través de una sola interfaz. Puedes empezar con gTTS en línea y más tarde cambiar a Piper, Silero, Coqui, Bark o Kokoro locales - sin reescribir tus comandos de la CLI, tu código Python ni tu integración HTTP.

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

`gtts`, `pyttsx3`, `pipertts`, `silerotts` y `kokorotts` funcionan bien en CPU. `coquitts` y `barktts` también pueden ejecutarse sin GPU, pero la síntesis es notablemente más lenta - para ellos se recomienda una tarjeta gráfica compatible con CUDA.

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
cp env.example .env                                   # opcional: tokens, motores, puertos

docker compose up --build -d                          # GPU / CUDA 12.1
docker compose -f docker-compose-cpu.yml up --build -d # solo CPU
```

La variante GPU pasa la tarjeta a través de CDI, así que el host necesita el NVIDIA container toolkit (1.14 o posterior) y una especificación CDI generada, una vez por cada actualización del controlador:

```bash
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
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

Modelos, voces e historial:

```bash
# Modelos instalados y ausentes, la misma tabla que imprime `ttsgen --list`
curl localhost:5000/api/models \
  -H "Authorization: Bearer $TTS_TOKEN"

# Sube una muestra de voz para coquitts (WAV); la voz pasa a llamarse "maria"
curl -X POST localhost:5000/api/voices \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -F file=@voice.wav -F name=maria -F engine=coquitts

curl "localhost:5000/api/voices?engine=coquitts" \
  -H "Authorization: Bearer $TTS_TOKEN"

curl "localhost:5000/api/voices/maria/audio?engine=coquitts&download=1" \
  -H "Authorization: Bearer $TTS_TOKEN" -o maria.wav

# Sintetiza en el historial del servidor en lugar del cuerpo de la respuesta
curl -X POST localhost:5000/api/history \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hola mundo","engine":"coquitts","language":"es","voice":"maria"}'

curl "localhost:5000/api/history?limit=50&offset=0" \
  -H "Authorization: Bearer $TTS_TOKEN"

# Audio de un elemento; sin download=1 se sirve en línea para <audio>
curl "localhost:5000/api/history/<id>/audio?download=1" \
  -H "Authorization: Bearer $TTS_TOKEN" -o tts.wav

curl -X DELETE localhost:5000/api/history/<id> \
  -H "Authorization: Bearer $TTS_TOKEN"
```

#### API compatible con OpenAI

El mismo servidor también responde a la API de audio de OpenAI, así que Open WebUI, SillyTavern, Home Assistant y los SDK oficiales funcionan con `base_url` apuntando a él y el token bearer como clave de API:

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

- `model` es el nombre de un motor, o `tts-1` / `tts-1-hd` / `gpt-4o-mini-tts` para el motor por defecto.
- `voice` es una voz del motor; los nombres de voz de OpenAI (`alloy`, `nova`, ...) seleccionan la voz por defecto del motor.
- `response_format`: `mp3` (por defecto), `wav`, `pcm`, `opus`, `flac`, `aac`. Los motores producen WAV o MP3; todo lo demás se transcodifica con `ffmpeg`, que las imágenes de Docker incluyen. `speed` (de 0.25 a 4.0) se aplica de la misma manera.
- `language` es una extensión: un código de dos letras o una etiqueta como `zh-cn`, por defecto `TTS_LANGUAGE`.
- `GET /v1/models` lista los motores instalados más `tts-1`; `GET /v1/audio/voices?model=<engine>` lista las voces de un motor.

#### Referencia de la API

Toda ruta excepto `/api/health` requiere `Authorization: Bearer <token>` cuando `TTS_TOKENS` está definido. Los errores bajo `/api/` tienen la forma `{"error": "...", "request_id": "..."}`; una respuesta 400 incluye además `message` con el motivo, que nombra los campos que fallan cuando la solicitud no pasa la validación (`language: ...`). Los errores bajo `/v1/` usan el formato de OpenAI.

| Método | Ruta | Propósito |
| --- | --- | --- |
| GET | `/api/health` | Vitalidad, indicador `auth`, motores, tamaños del pool y de la cola. No requiere token. |
| GET | `/api/engines` | Motores soportados, los instalados y el predeterminado. |
| GET | `/api/models` | Modelos instalados y ausentes por motor, la tabla que imprime `ttsgen --list`. |
| GET | `/api/voices?engine=&language=` | Voces de un motor; para `coquitts`, las muestras con tamaño, frecuencia y duración. |
| POST | `/api/voices` | Sube una muestra WAV (`file`, `name`, `engine=coquitts`). |
| GET | `/api/voices/<name>/audio?engine=&download=1` | Reproduce o descarga una muestra. |
| DELETE | `/api/voices/<name>?engine=` | Elimina una muestra. |
| POST, GET | `/api/tts` | Sintetiza `text` con `engine`, `language`, `voice`; `stream=true` transmite los fragmentos a medida que están listos. |
| POST | `/api/history` | Sintetiza en el historial del servidor en lugar del cuerpo de la respuesta. |
| GET | `/api/history?limit=&offset=` | Lista los elementos del historial, los más recientes primero. |
| GET | `/api/history/<id>` | Metadatos de un elemento. |
| GET | `/api/history/<id>/audio?download=1` | El audio del elemento, en línea o como descarga. |
| DELETE | `/api/history/<id>` | Elimina un elemento. |
| POST | `/v1/audio/speech` | Síntesis compatible con OpenAI, ver arriba. |
| GET | `/v1/models` | Lista de modelos compatible con OpenAI. |
| GET | `/v1/audio/voices?model=` | Voces de un motor. |

`language` es un código de dos letras (`en`, `ru`) o una etiqueta con región o escritura (`zh-cn`, `pt_BR`, `en-gb`, `es-419`), que se pasa a minúsculas y se escribe con `-`. Cada motor lleva la etiqueta a lo que tiene: gtts recibe su propia grafía (`zh-CN`; no tiene francés canadiense ni portugués europeo, así que `fr-ca` y `pt-pt` pasan a ser `fr` y `pt`), kokorotts pronuncia `en-gb` con el fonemizador británico, xtts recibe `zh-cn` para el chino y los demás motores usan la parte del idioma (`pt-br` pasa a ser `pt`). Un idioma que el motor no conoce se habla en su idioma por defecto, normalmente inglés (gtts falla en su lugar); con `TTS_LANGUAGE_STRICT=true` es un 400 que enumera los idiomas del motor. La comprobación estricta abarca `/api/tts` sin `stream`, `/api/history` y `/v1/audio/speech`, y todos los motores que enumeran sus idiomas: todos salvo pyttsx3 y coquitts con un modelo multilingüe distinto de xtts.

#### Interfaz web

Ambos archivos compose también inician `ttswww`, un contenedor nginx que sirve la interfaz web y reenvía `/api/` a `ttssrv`:

```bash
docker compose up --build -d
xdg-open http://localhost:8080      # TTS_WWW_PORT; cámbialo si el 8080 está ocupado
xdg-open https://localhost:8443     # TTS_WWW_TLS_PORT; certificado autofirmado, acéptalo una vez
```

- **Studio** - escribe texto, elige motor / idioma / voz, genera, escucha, guarda; cada resultado queda en una lista de historial.
- **Voices** - sube o graba muestras de voz WAV para la clonación de voz de `coquitts`; reprodúcelas, descárgalas y elimínalas.
- **Models** - los motores y los modelos instalados / ausentes, la misma tabla que `ttsgen --list`.

El engranaje de la cabecera abre el diálogo de ajustes: el motor, idioma y voz por defecto del Studio, y si se muestra el ejemplo de curl; las elecciones se guardan en el navegador. El Studio muestra un comando `curl` listo para copiar para la solicitud actual; hace referencia al token como `$TTS_TOKEN` en lugar de imprimirlo. La pantalla Voices también puede grabar una muestra desde el micrófono, algo que los navegadores solo permiten en `https` o `localhost` - en la LAN abre la interfaz a través del puerto https. En el primer arranque se genera un certificado autofirmado en `./data/certs`; monta uno real con los mismos nombres (`tts.crt`, `tts.key`) para sustituirlo.

Cuando `TTS_TOKENS` está definido, la interfaz se abre en una pantalla de inicio de sesión y pide uno de esos tokens; el navegador lo conserva y lo envía con cada solicitud. Sin `TTS_TOKENS` no hay inicio de sesión.

#### Configuración

Cada ajuste es una variable de entorno; `env.example` las documenta todas y el `.env` junto a los archivos compose se lee automáticamente. Las que más probablemente cambiarás:

| Variable | Por defecto | Qué hace |
| --- | --- | --- |
| `TTS_TOKENS` | vacío | Tokens bearer separados por comas. Vacío significa que no hay autenticación en absoluto. |
| `TTS_ENGINES` | vacío | Motores que se instalan y precalientan al inicio, separados por comas (`coquitts,silerotts`). |
| `TTS_ENGINE` | `gtts` | Motor usado cuando una solicitud no indica ninguno. |
| `TTS_LANGUAGE` | `en` | Idioma usado cuando una solicitud no indica ninguno. |
| `TTS_LANGUAGE_STRICT` | `false` | `true` responde 400 a un idioma que el motor no enumera, en lugar de que el motor recurra a su idioma por defecto. |
| `TTS_POOL_SIZE` | `1` | Llamadas de síntesis permitidas a la vez entre todos los motores; `0` elimina el límite y el precalentamiento. |
| `TTS_QUEUE_SIZE` | `8` | Solicitudes de síntesis que pueden esperar un hueco libre; las demás reciben 503 de inmediato. |
| `TTS_HISTORY_MAX` | `200` | Elementos conservados en el historial; los más antiguos se eliminan al guardar uno nuevo. |
| `TTS_MAX_SAMPLE_BYTES` | `16777216` | Tamaño máximo de una muestra de voz subida (16 MiB). |
| `TTS_MAX_SAMPLES` | `100` | Muestras de voz conservadas en el servidor. |
| `TTS_MAX_BODY_BYTES` | `2097152` | Tamaño máximo del cuerpo JSON de una solicitud (2 MiB). |
| `TTS_STREAM_MAX_CHARS` | `200` | Tamaño de fragmento para `stream=true`. |
| `CORS_ORIGINS` | `*` | Orígenes permitidos para `/api/*`. |
| `TTS_PORT` | `5000` | Puerto de `ttssrv`. |
| `TTS_WWW_PORT`, `TTS_WWW_TLS_PORT` | `8080`, `8443` | Puertos http y https de la interfaz web. |
| `COQUITTS_MODEL`, `COQUITTS_SAMPLE` | `xtts_v2`, `default.wav` | Modelo de Coqui y muestra de voz por defecto. |
| `TZ` | `America/New_York` | Zona horaria para las marcas de tiempo en los registros y el historial. |

Fuera de Docker, las CLI y el servidor leen las mismas claves desde, de mayor a menor prioridad: los flags de la CLI, el entorno del shell, `./ttsgen.conf`, `~/.config/ttsgen.conf`, `./.env.local`, `./.env`. Un archivo nunca sobrescribe el shell, y `.env` se lee solo desde el directorio actual.

Un `TTS_POOL_SIZE` mayor que 1 permite que distintos motores sinteticen en paralelo; dentro de un mismo motor las llamadas se serializan, porque los modelos subyacentes no pueden compartirse entre hilos de forma segura.

#### Seguridad

- La autenticación está desactivada hasta que defines `TTS_TOKENS`. A partir de entonces, toda ruta excepto `/api/health` requiere `Authorization: Bearer <token>`, y la interfaz web pide el token en una pantalla de inicio de sesión.
- La API escucha en todas las interfaces y los archivos compose publican `TTS_PORT`, `TTS_WWW_PORT` y `TTS_WWW_TLS_PORT` en el host. En una red compartida define un token, o vincula los puertos a `127.0.0.1` en un archivo de override.
- El listener https usa un certificado autofirmado generado en el primer arranque; está pensado para una LAN. En internet, pon la interfaz detrás de tu propio proxy inverso con un certificado real.
- Las muestras de voz, el historial y los certificados viven bajo `./data`; haz copias de seguridad y mantenlo fuera del contexto de compilación.

Informa de una vulnerabilidad a través de la pestaña Security del repositorio, consulta [SECURITY.md](https://github.com/wachawo/text-to-speech/blob/main/SECURITY.md).

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
├── www/            # interfaz web: Vue 2 sin paso de compilación, servida por nginx
├── nginx/          # configuración principal de nginx y la plantilla conf.d para ttswww
├── docker/         # compilaciones de Docker para GPU, CPU y la interfaz web
├── docs/           # documentación por motor y traducciones del README
└── tests/          # pruebas de pytest, sin descargas de modelos ni GPU
```

### Desarrollo

Las contribuciones son bienvenidas; [CONTRIBUTING.md](https://github.com/wachawo/text-to-speech/blob/main/CONTRIBUTING.md) explica la configuración, las comprobaciones y cómo se añade un motor. Para instalar las dependencias de desarrollo:

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

Los parámetros detallados y las particularidades de cada motor se describen en [`docs/`](https://github.com/wachawo/text-to-speech/blob/main/docs/ENGINES.md).

### Licencia

[MIT](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
