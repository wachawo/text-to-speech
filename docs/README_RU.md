## text-to-speech — популярные TTS-движки за единым API

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

Устанавливайте популярные онлайн/офлайн TTS-движки (gTTS, espeak, Piper, Silero, Coqui, Bark, Kokoro) и используйте их через единый CLI, Python API и HTTP-сервер.

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | **[Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md)** | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

- **Один интерфейс, много движков.** Выберите движок и вызывайте его одинаково из CLI (`ttsgen`), Python (`libs.api`) или HTTP — переключайтесь между облаком и локальной работой без изменения кода.
- **API-сервер для вашей локальной сети.** Запустите `ttssrv`, чтобы другие машины синтезировали речь по HTTP (`POST /api/tts`); модель загружается один раз при старте, а запросы используют общий пул.

### Движки

| Движок | Офлайн | Оборудование | Качество | Лучше всего для |
|---|---|---|---|---|
| `gtts` | ❌ онлайн | CPU | ★★★★ | 100+ языков, без настройки |
| `pyttsx3` | ✅ | CPU | ★★ | минимальная установка (espeak / SAPI) |
| `pipertts` | ✅ | CPU | ★★★★ | быстрый офлайн, 50+ языков |
| `silerotts` | ✅ | CPU | ★★★★ | быстрый офлайн, русский |
| `kokorotts` | ✅ | CPU | ★★★★ | быстрый офлайн, многоязычный |
| `coquitts` | ✅ | CPU / **GPU** | ★★★★★ | лучшее качество, клонирование голоса |
| `barktts` | ✅ | CPU / **GPU** | ★★★★★ | эмоции, музыка, пение |

`gtts`, `pyttsx3`, `pipertts`, `silerotts`, `kokorotts` отлично работают на CPU. `coquitts` и `barktts` тоже работают на CPU, но медленно — рекомендуется CUDA-совместимый GPU.

### Установка (pip)

```bash
pip install git+https://github.com/wachawo/text-to-speech.git
```

Это устанавливает CLI только с лёгкими зависимостями. Нейросетевые движки (`pipertts`, `silerotts`, `coquitts`, `barktts`, `kokorotts`) подтягивают `torch`/модели по требованию через `ttsgen --install <engine>`.

```bash
ttsgen "Hello world"                  # воспроизвести (движок по умолчанию: gtts, онлайн)
ttsgen "Hello world" -f out.mp3       # сохранить в файл
ttsgen "Hello world" -e pyttsx3       # полностью офлайн
ttsgen "Hola amigo!"  -l es           # выбрать язык
ttsgen --install coquitts             # добавить офлайн нейросетевой движок + модели
ttsgen "Hello world" -e coquitts -f out.wav
ttsgen --list                         # движки + установленные модели
ttsgen "Hello world" --stdout | ttsplay
```

Python:

```python
from libs.api import text_to_speech_file, text_to_speech_bytes

text_to_speech_file("Hello world", engine="gtts")
audio = text_to_speech_bytes("Hello world", engine="pipertts", language="en")
```

### Сервер (clone)

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech
docker compose up --build -d                          # GPU (CUDA 12.1)
docker compose -f docker-compose-cpu.yml up --build -d # только CPU
```

Запросить синтез по HTTP:

```bash
curl localhost:5000/api/health
curl localhost:5000/api/engines -H "Authorization: Bearer $TTS_TOKEN"
curl "localhost:5000/api/voices?engine=silerotts&language=ru" -H "Authorization: Bearer $TTS_TOKEN"

curl -X POST localhost:5000/api/tts \
  -H "Authorization: Bearer $TTS_TOKEN" -H "Content-Type: application/json" \
  -d '{"text":"Hello world","engine":"gtts"}' -o out.mp3
```

Или используйте `ttsapi` — те же флаги, что и у `ttsgen`, но синтез выполняется на сервере (`TTS_URL` / `TTS_TOKEN` из конфигурации):

```bash
ttsapi "Hello world"
ttsapi -i long.txt --output play,file --file out.mp3
```

### Структура проекта

```
text-to-speech/
├── ttsgen.py / ttsplay.py / ttsrec.py / ttsapi.py   # точки входа CLI
├── engines/        # подключаемые движки (gtts, piper, silero, coqui, bark, kokoro, …)
├── libs/           # ядро: api.py, tools.py, playback.py, exceptions.py
├── install/        # установщики `ttsgen --install <engine>`
├── ttssrv/         # HTTP-сервер Flask (Docker / python3 ttssrv/app1.py)
├── docker/         # сборки gpu/ и cpu/ (Dockerfile + requirements)
├── docs/           # руководства по каждому движку + переводы
└── tests/          # набор тестов pytest (движки замоканы, модели/GPU не нужны)
```

### Заметки для разработчиков

```bash
pip install -e ".[dev]"
pytest                 # тесты + покрытие
ruff check . && black .
```

Добавьте движок, поместив `engines/<name>.py` с двумя функциями — он автоматически появится в CLI и API:

```python
def is_available() -> bool: ...                  # зависимости импортируются?
def generate(text: str, config: dict) -> bytes:  # вернуть байты MP3/WAV
    ...
```

Настройка каждого движка и полное руководство по движкам находятся в [`docs/`](docs/ENGINES.md).

### Лицензия

[MIT](LICENSE)
