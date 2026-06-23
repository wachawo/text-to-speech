## text-to-speech — единый интерфейс для TTS-движков

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

`text-to-speech` позволяет работать с несколькими движками синтеза речи через один интерфейс. Можно начать с онлайн-gTTS, а затем перейти на локальные Piper, Silero, Coqui, Bark или Kokoro — без переписывания CLI-команд, Python-кода или HTTP-интеграции.

Проект подходит для локального использования, автоматизации и запуска собственного TTS-сервера в сети.

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | **[Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md)** | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

* **Один способ работы с разными движками.** Выберите подходящий движок и вызывайте его через CLI (`ttsgen`), Python API (`libs.api`) или HTTP API.
* **Можно работать полностью локально.** Для этого подойдут Piper, Silero, Coqui, Bark, Kokoro и `pyttsx3`.
* **Есть готовый HTTP-сервер.** `ttssrv` загружает модель при запуске и принимает запросы от других машин в локальной сети.

### Движки

| Движок      | Офлайн | Оборудование  | Качество | Подходит для                                    |
| ----------- |-------| ------------- | -------- | ----------------------------------------------- |
| `gtts`      | ❌ | CPU           | ★★★★     | быстрого старта и большого числа языков         |
| `pyttsx3`   | ✅ | CPU           | ★★       | простой локальной озвучки через espeak или SAPI |
| `pipertts`  | ✅ | CPU           | ★★★★     | быстрого офлайн-синтеза на разных языках        |
| `silerotts` | ✅ | CPU           | ★★★★     | русской речи и лёгкого локального запуска       |
| `kokorotts` | ✅ | CPU           | ★★★★     | многоязычного офлайн-синтеза                    |
| `coquitts`  | ✅ | CPU / **GPU** | ★★★★★    | качественных голосов и клонирования голоса      |
| `barktts`   | ✅ | CPU / **GPU** | ★★★★★    | выразительной речи, эмоций, музыки и пения      |

`gtts`, `pyttsx3`, `pipertts`, `silerotts` и `kokorotts` нормально работают на CPU. `coquitts` и `barktts` также можно запускать без GPU, но синтез будет заметно медленнее. Для них желательно использовать CUDA-совместимую видеокарту.

### Установка

Базовая установка ставит CLI и лёгкие зависимости:

```bash
pip install git+https://github.com/wachawo/text-to-speech.git
```

Дополнительные движки и их модели устанавливаются отдельно, когда они действительно нужны:

```bash
ttsgen --install coquitts
```

Примеров использования CLI:

```bash
ttsgen "Hello world"                  # озвучить текст через gTTS
ttsgen "Hello world" -f out.mp3       # сохранить результат в файл
ttsgen "Hello world" -e pyttsx3       # использовать локальный движок
ttsgen "Hola amigo!" -l es            # выбрать язык
ttsgen --install coquitts             # установить Coqui TTS и модели
ttsgen "Hello world" -e coquitts -f out.wav
ttsgen --list                         # показать доступные движки и модели
ttsgen "Hello world" --stdout | ttsplay
```

По умолчанию используется `gtts`, поэтому для первого запуска достаточно одной команды. Для полностью локальной работы укажите другой движок, например `pyttsx3`, `pipertts` или `silerotts`.
Мой выбор coquitts если требуется качество и естественность речи, silerotts если нужна скорость генерации. 

### Python API

В Python доступны функции для сохранения результата в файл или получения аудио в виде байтов:

```python
from libs.api import text_to_speech_file, text_to_speech_bytes

text_to_speech_file("Hello world", engine="gtts")

audio = text_to_speech_bytes(
    "Hello world",
    engine="pipertts",
    language="en",
)
```

### HTTP-сервер

Для запуска сервера удобнее использовать Docker:

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech

docker compose up --build -d                          # GPU / CUDA 12.1
docker compose -f docker-compose-cpu.yml up --build -d # только CPU
```

После запуска можно проверить состояние сервера и отправить запрос на синтез:

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

Для работы и тестирования сервера есть отдельный CLI-клиент `ttsapi`. У него те же основные флаги, что и у `ttsgen`, но синтез выполняется на сервере. Адрес сервера и токен берутся из `TTS_URL` и `TTS_TOKEN`.

```bash
ttsapi "Hello world"
ttsapi -i long.txt --output play,file --file out.mp3
```

### Структура проекта

```text
text-to-speech/
├── ttsgen.py / ttsplay.py / ttsrec.py / ttsapi.py   # CLI-команды
├── engines/        # движки: gTTS, Piper, Silero, Coqui, Bark, Kokoro и другие
├── libs/           # общее ядро: API, инструменты, воспроизведение, исключения
├── install/        # установщики для ttsgen --install <engine>
├── ttssrv/         # HTTP-сервер Flask
├── docker/         # Docker-сборки для GPU и CPU
├── docs/           # документация по движкам и переводы README
└── tests/          # pytest-тесты без загрузки моделей и без GPU
```

### Разработка

Для установки зависимостей разработки:

```bash
pip install -e ".[dev]"
```

Проверки перед коммитом:

```bash
pytest
ruff check .
black .
```

Новый движок подключается через файл `engines/<name>.py`. Достаточно реализовать две функции:

```python
def is_available() -> bool:
    ...

def generate(text: str, config: dict) -> bytes:
    ...
```

`is_available()` проверяет доступность зависимостей, а `generate()` получает текст и настройки, после чего возвращает аудиофайл в виде байтов MP3 или WAV. После этого движок автоматически становится доступен в CLI и API.

Подробные параметры и особенности каждого движка описаны в [`docs/`](docs/ENGINES.md).

### Лицензия

[MIT](LICENSE)
