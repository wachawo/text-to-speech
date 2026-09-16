# text-to-speech - единый интерфейс для TTS-движков

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | **[Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md)** | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

![Экран Studio веб-интерфейса](https://raw.githubusercontent.com/wachawo/text-to-speech/main/docs/images/studio.png)

`text-to-speech` позволяет работать с несколькими движками синтеза речи через один интерфейс. Можно начать с онлайн-gTTS, а затем перейти на локальные Piper, Silero, Coqui, Bark или Kokoro - без переписывания CLI-команд, Python-кода или HTTP-интеграции.

Проект подходит для локального использования, автоматизации и запуска собственного TTS-сервера в сети.

* **Один способ работы с разными движками.** Выберите подходящий движок и вызывайте его через CLI (`ttsgen`), Python API (`libs.api`) или HTTP API.
* **Можно работать полностью локально.** Piper, Silero, Coqui, Bark, Kokoro и `pyttsx3` работают на вашей собственной машине.
* **Есть готовый HTTP-сервер.** `ttssrv` загружает модель при запуске и принимает запросы от других машин в локальной сети.

### Движки

| Движок      | Офлайн | Оборудование  | Качество | Подходит для                                    |
| ----------- | ------ | ------------- | -------- | ----------------------------------------------- |
| `gtts`      | ❌     | CPU           | ★★★★     | быстрого старта и большого числа языков         |
| `pyttsx3`   | ✅     | CPU           | ★★       | простой локальной озвучки через espeak или SAPI |
| `pipertts`  | ✅     | CPU           | ★★★★     | быстрого офлайн-синтеза на многих языках        |
| `silerotts` | ✅     | CPU           | ★★★★     | русской речи и лёгкого локального запуска       |
| `kokorotts` | ✅     | CPU           | ★★★★     | многоязычного офлайн-синтеза                    |
| `coquitts`  | ✅     | CPU / **GPU** | ★★★★★    | качественных голосов и клонирования голоса      |
| `barktts`   | ✅     | CPU / **GPU** | ★★★★★    | выразительной речи, эмоций, музыки и пения      |

`gtts`, `pyttsx3`, `pipertts`, `silerotts` и `kokorotts` нормально работают на CPU. `coquitts` и `barktts` тоже можно запускать без GPU, но синтез будет заметно медленнее - для них рекомендуется CUDA-совместимая видеокарта.

### Установка

Базовая установка ставит CLI и его лёгкие зависимости:

```bash
pip install git+https://github.com/wachawo/text-to-speech.git
```

В Linux офлайн-движку `pyttsx3` дополнительно нужен системный пакет `espeak`:

```bash
sudo apt install espeak espeak-data libespeak1
```

Дополнительные движки и их модели устанавливаются отдельно, когда они действительно нужны:

```bash
ttsgen --install coquitts
```

Примеры использования CLI:

```bash
ttsgen "Hello world"                  # озвучить текст через gTTS
ttsgen "Hello world" -f out.mp3       # сохранить результат в файл
ttsgen "Hello world" -e pyttsx3       # использовать локальный движок
ttsgen "Hola amigo!" -l es            # выбрать язык
ttsgen --install coquitts             # установить Coqui TTS и его модели
ttsgen "Hello world" -e coquitts -f out.wav
ttsgen --list                         # показать доступные движки и модели
ttsgen "Hello world" --stdout | ttsplay
```

`gtts` используется по умолчанию, поэтому для первого запуска достаточно одной команды. Для полностью локальной работы выберите другой движок, например `pyttsx3`, `pipertts` или `silerotts`.
Мой выбор: `coquitts` для качества и естественного звучания, `silerotts` для быстрой генерации.

### Python API

В Python есть функции, чтобы сохранить результат в файл или получить аудио в виде байтов:

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

Проще всего запустить сервер через Docker:

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech
cp env.example .env                                   # необязательно: токены, движки, порты

docker compose up --build -d                          # GPU / CUDA 12.1
docker compose -f docker-compose-cpu.yml up --build -d # только CPU
```

GPU-вариант пробрасывает видеокарту через CDI, поэтому на хосте нужен NVIDIA Container Toolkit (1.14 или новее) и сгенерированная CDI-спецификация, один раз после каждого обновления драйвера:

```bash
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
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

Модели, голоса и история:

```bash
# Установленные и отсутствующие модели, та же таблица, что печатает `ttsgen --list`
curl localhost:5000/api/models \
  -H "Authorization: Bearer $TTS_TOKEN"

# Загрузить образец голоса для coquitts (WAV); после этого голос называется "maria"
curl -X POST localhost:5000/api/voices \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -F file=@voice.wav -F name=maria -F engine=coquitts

curl "localhost:5000/api/voices?engine=coquitts" \
  -H "Authorization: Bearer $TTS_TOKEN"

curl "localhost:5000/api/voices/maria/audio?engine=coquitts&download=1" \
  -H "Authorization: Bearer $TTS_TOKEN" -o maria.wav

# Синтезировать в историю на сервере вместо тела ответа
curl -X POST localhost:5000/api/history \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hola mundo","engine":"coquitts","language":"es","voice":"maria"}'

curl "localhost:5000/api/history?limit=50&offset=0" \
  -H "Authorization: Bearer $TTS_TOKEN"

# Аудио одной записи; без download=1 отдаётся inline для <audio>
curl "localhost:5000/api/history/<id>/audio?download=1" \
  -H "Authorization: Bearer $TTS_TOKEN" -o tts.wav

curl -X DELETE localhost:5000/api/history/<id> \
  -H "Authorization: Bearer $TTS_TOKEN"
```

#### OpenAI-совместимый API

Тот же сервер отвечает и на OpenAI audio API, поэтому Open WebUI, SillyTavern, Home Assistant и официальные SDK работают с ним, если `base_url` указывает на сервер, а bearer-токен передаётся как API-ключ:

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

- `model` - имя движка либо `tts-1` / `tts-1-hd` / `gpt-4o-mini-tts` для движка по умолчанию.
- `voice` - голос движка; имена голосов OpenAI (`alloy`, `nova`, ...) выбирают голос движка по умолчанию.
- `response_format`: `mp3` (по умолчанию), `wav`, `pcm`, `opus`, `flac`, `aac`. Движки выдают WAV или MP3; всё остальное перекодируется через `ffmpeg`, который входит в Docker-образы. `speed` (от 0.25 до 4.0) применяется таким же образом.
- `language` - расширение: двухбуквенный код, по умолчанию `TTS_LANGUAGE`.
- `GET /v1/models` перечисляет установленные движки плюс `tts-1`; `GET /v1/audio/voices?model=<engine>` перечисляет голоса одного движка.

#### Справочник по API

Каждый маршрут, кроме `/api/health`, требует `Authorization: Bearer <token>`, если задан `TTS_TOKENS`. Ошибки под `/api/` имеют вид `{"error": "...", "request_id": "..."}`; ошибки под `/v1/` используют формат OpenAI.

| Метод | Путь | Назначение |
| --- | --- | --- |
| GET | `/api/health` | Liveness, флаг `auth`, движки, размеры пула и очереди. Токен не нужен. |
| GET | `/api/engines` | Поддерживаемые движки, установленные и движок по умолчанию. |
| GET | `/api/models` | Установленные и отсутствующие модели по движкам, та же таблица, что печатает `ttsgen --list`. |
| GET | `/api/voices?engine=&language=` | Голоса движка; для `coquitts` - образцы с размером, частотой и длительностью. |
| POST | `/api/voices` | Загрузить WAV-образец (`file`, `name`, `engine=coquitts`). |
| GET | `/api/voices/<name>/audio?engine=&download=1` | Воспроизвести или скачать образец. |
| DELETE | `/api/voices/<name>?engine=` | Удалить образец. |
| POST, GET | `/api/tts` | Синтезировать `text` с `engine`, `language`, `voice`; `stream=true` отдаёт фрагменты по мере готовности. |
| POST | `/api/history` | Синтезировать в историю на сервере вместо тела ответа. |
| GET | `/api/history?limit=&offset=` | Список записей истории, новые первыми. |
| GET | `/api/history/<id>` | Метаданные одной записи. |
| GET | `/api/history/<id>/audio?download=1` | Аудио записи, inline или как загрузка. |
| DELETE | `/api/history/<id>` | Удалить запись. |
| POST | `/v1/audio/speech` | OpenAI-совместимый синтез, см. выше. |
| GET | `/v1/models` | OpenAI-совместимый список моделей. |
| GET | `/v1/audio/voices?model=` | Голоса одного движка. |

#### Веб-интерфейс

Оба compose-файла также запускают `ttswww` - контейнер nginx, который раздаёт веб-интерфейс и проксирует `/api/` на `ttssrv`:

```bash
docker compose up --build -d
xdg-open http://localhost:8080      # TTS_WWW_PORT; поменяйте, если 8080 занят
xdg-open https://localhost:8443     # TTS_WWW_TLS_PORT; самоподписанный сертификат, примите его один раз
```

- **Studio** - ввести текст, выбрать движок / язык / голос, сгенерировать, прослушать, сохранить; каждый результат попадает в список истории.
- **Voices** - загрузить или записать WAV-образцы голоса для клонирования через `coquitts`; воспроизвести, скачать и удалить их.
- **Models** - движки и установленные / отсутствующие модели, та же таблица, что и `ttsgen --list`.

Шестерёнка в шапке открывает диалог настроек: движок, язык и голос по умолчанию для Studio, а также показывать ли пример curl; выбор хранится в браузере. Studio показывает готовую к копированию команду `curl` для текущего запроса; токен в ней указан как `$TTS_TOKEN`, а не выводится открыто. Экран Voices также умеет записывать образец с микрофона, что браузеры разрешают только на `https` или `localhost` - по локальной сети открывайте интерфейс через https-порт. Самоподписанный сертификат генерируется в `./data/certs` при первом запуске; чтобы заменить его, смонтируйте настоящий под теми же именами (`tts.crt`, `tts.key`).

Если задан `TTS_TOKENS`, интерфейс открывается на экране входа и запрашивает один из этих токенов; браузер сохраняет его и отправляет с каждым запросом. Без `TTS_TOKENS` экрана входа нет.

#### Конфигурация

Каждая настройка - это переменная окружения; `env.example` документирует их все, а `.env` рядом с compose-файлами читается автоматически. Те, что вы скорее всего захотите изменить:

| Переменная | По умолчанию | Что делает |
| --- | --- | --- |
| `TTS_TOKENS` | пусто | Bearer-токены через запятую. Пусто означает полное отсутствие аутентификации. |
| `TTS_ENGINES` | пусто | Движки, которые устанавливаются и прогреваются при старте, через запятую (`coquitts,silerotts`). |
| `TTS_ENGINE` | `gtts` | Движок, используемый, когда запрос его не указывает. |
| `TTS_LANGUAGE` | `en` | Язык, используемый, когда запрос его не указывает. |
| `TTS_POOL_SIZE` | `1` | Сколько вызовов синтеза допускается одновременно по всем движкам; `0` снимает ограничение и прогрев. |
| `TTS_QUEUE_SIZE` | `8` | Сколько запросов на синтез может ждать свободного слота; остальные сразу получают 503. |
| `TTS_HISTORY_MAX` | `200` | Сколько записей хранится в истории; самые старые удаляются при сохранении новой. |
| `TTS_MAX_SAMPLE_BYTES` | `16777216` | Максимальный размер загружаемого образца голоса (16 MiB). |
| `TTS_MAX_SAMPLES` | `100` | Сколько образцов голоса хранится на сервере. |
| `TTS_MAX_BODY_BYTES` | `2097152` | Максимальный размер JSON-тела запроса (2 MiB). |
| `TTS_STREAM_MAX_CHARS` | `200` | Размер фрагмента для `stream=true`. |
| `CORS_ORIGINS` | `*` | Разрешённые origin для `/api/*`. |
| `TTS_PORT` | `5000` | Порт `ttssrv`. |
| `TTS_WWW_PORT`, `TTS_WWW_TLS_PORT` | `8080`, `8443` | http- и https-порты веб-интерфейса. |
| `COQUITTS_MODEL`, `COQUITTS_SAMPLE` | `xtts_v2`, `default.wav` | Модель Coqui и образец голоса по умолчанию. |
| `TZ` | `America/New_York` | Часовой пояс для меток времени в логах и истории. |

Вне Docker CLI и сервер читают те же ключи, от самого приоритетного: флаги CLI, окружение оболочки, `./ttsgen.conf`, `~/.config/ttsgen.conf`, `./.env.local`, `./.env`. Файл никогда не переопределяет оболочку, а `.env` читается только из текущего каталога.

`TTS_POOL_SIZE` больше 1 позволяет разным движкам синтезировать параллельно; внутри одного движка вызовы выполняются последовательно, потому что лежащие в основе модели небезопасно делить между потоками.

#### Безопасность

- Аутентификация выключена, пока не задан `TTS_TOKENS`. После этого каждый маршрут, кроме `/api/health`, требует `Authorization: Bearer <token>`, а веб-интерфейс запрашивает токен на экране входа.
- API слушает на всех интерфейсах, а compose-файлы публикуют `TTS_PORT`, `TTS_WWW_PORT` и `TTS_WWW_TLS_PORT` на хосте. В общей сети задайте токен или привяжите порты к `127.0.0.1` в override-файле.
- https-листенер использует самоподписанный сертификат, созданный при первом запуске; он рассчитан на локальную сеть. В интернете ставьте интерфейс за собственный reverse proxy с настоящим сертификатом.
- Образцы голоса, история и сертификаты лежат в `./data`; делайте резервные копии и не включайте каталог в контекст сборки.

Об уязвимости сообщайте через вкладку Security репозитория, см. [SECURITY.md](https://github.com/wachawo/text-to-speech/blob/main/SECURITY.md).

Для работы с сервером и его тестирования есть отдельный CLI-клиент `ttsapi`. У него те же основные флаги, что и у `ttsgen`, но синтез выполняется на сервере. Адрес сервера и токен берутся из `TTS_URL` и `TTS_TOKEN`.

```bash
ttsapi "Hello world"
ttsapi -i long.txt --output play,file --file out.mp3
```

### Структура проекта

```text
text-to-speech/
├── ttsgen.py / ttsplay.py / ttsrec.py / ttsapi.py   # CLI-команды
├── engines/        # движки: gTTS, Piper, Silero, Coqui, Bark, Kokoro и другие
├── libs/           # общее ядро: API, утилиты, воспроизведение, исключения
├── install/        # установщики для ttsgen --install <engine>
├── ttssrv/         # HTTP-сервер на Flask
├── www/            # веб-интерфейс: Vue 2 без сборки, раздаётся через nginx
├── nginx/          # основной конфиг nginx и шаблон conf.d для ttswww
├── docker/         # Docker-сборки для GPU, CPU и веб-интерфейса
├── docs/           # документация по движкам и переводы README
└── tests/          # pytest-тесты, без загрузки моделей и без GPU
```

### Разработка

Вклад приветствуется; [CONTRIBUTING.md](https://github.com/wachawo/text-to-speech/blob/main/CONTRIBUTING.md) описывает настройку окружения, проверки и то, как добавляется движок. Установка зависимостей для разработки:

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

`is_available()` проверяет, что зависимости импортируются, а `generate()` получает текст и конфигурацию и возвращает аудио в виде байтов MP3 или WAV. После этого движок автоматически становится доступен в CLI и API.

Подробные параметры и особенности каждого движка описаны в [`docs/`](https://github.com/wachawo/text-to-speech/blob/main/docs/ENGINES.md).

### Лицензия

[MIT](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
