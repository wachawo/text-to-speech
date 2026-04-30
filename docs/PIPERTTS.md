# Установка Piper TTS

## Быстрая установка (автоматический скрипт)

```bash
# 1. Установите Piper
pip install piper-tts

# 2. Запустите скрипт для скачивания моделей
ttsgen --install pipertts
```

Скрипт автоматически скачает выбранные модели в правильную директорию.

---

## Ручная установка

### 1. Установите Piper в ваш venv

```bash
# Убедитесь что venv активирован
source venv/bin/activate  # или путь к вашему venv

# Установите Piper
pip install piper-tts
```

### 2. Скачайте голосовые модели вручную

```bash
# Создайте директорию для моделей
mkdir -p ~/.local/share/piper/voices

# Английский (en_US-lessac-medium) - качественный женский голос
wget -P ~/.local/share/piper/voices https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx
wget -P ~/.local/share/piper/voices https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json

# Русский (ru_RU-ruslan-medium) - мужской голос
wget -P ~/.local/share/piper/voices https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ru/ru_RU/ruslan/medium/ru_RU-ruslan-medium.onnx
wget -P ~/.local/share/piper/voices https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ru/ru_RU/ruslan/medium/ru_RU-ruslan-medium.onnx.json

# Испанский (es_ES-davefx-medium)
wget -P ~/.local/share/piper/voices https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx
wget -P ~/.local/share/piper/voices https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx.json
```

### 3. Проверьте установку

```bash
# Проверить что Piper установлен
pip list | grep piper

# Проверить что модели скачаны
ls -la ~/.local/share/piper/voices/
```

### 4. Использование

```bash
# Английский
python ttsgen.py "Hello, how are you?" --engine pipertts

# Русский
python ttsgen.py "Привет, как дела?" --engine pipertts --language ru

# С сохранением
python ttsgen.py "Hello world" --engine pipertts --file output.wav
```

## Альтернативный способ (ручная загрузка)

Если команда `piper --download-dir` не работает:

### 1. Скачайте модели вручную

Перейдите на: https://github.com/rhasspy/piper/releases/tag/v1.2.0

Скачайте нужную модель, например:
- `en_US-lessac-medium.onnx`
- `en_US-lessac-medium.onnx.json`

### 2. Создайте директорию

```bash
mkdir -p ~/.local/share/piper/voices
```

### 3. Скопируйте файлы

```bash
# Переместите скачанные файлы
mv ~/Downloads/en_US-lessac-medium.onnx* ~/.local/share/piper/voices/
```

### 4. Проверьте

```bash
ls -la ~/.local/share/piper/voices/
# Должно быть:
# en_US-lessac-medium.onnx
# en_US-lessac-medium.onnx.json
```

## Доступные модели

### Качество голосов
- **low** - быстрые, базовое качество (~10MB)
- **medium** - хорошее качество (~50MB) ⭐ **Рекомендуется**
- **high** - лучшее качество (~150MB)

### Популярные модели

| Язык | Модель | Качество |
|------|--------|----------|
| English (US) | en_US-lessac-medium | ⭐⭐⭐⭐⭐ |
| English (GB) | en_GB-alba-medium | ⭐⭐⭐⭐ |
| Russian | ru_RU-ruslan-medium | ⭐⭐⭐⭐⭐ |
| Spanish (ES) | es_ES-davefx-medium | ⭐⭐⭐⭐ |
| German | de_DE-thorsten-medium | ⭐⭐⭐⭐⭐ |
| French | fr_FR-siwis-medium | ⭐⭐⭐⭐ |
| Italian | it_IT-riccardo-medium | ⭐⭐⭐⭐ |
| Ukrainian | uk_UA-ukrainian_tts-medium | ⭐⭐⭐⭐ |
| Chinese | zh_CN-huayan-medium | ⭐⭐⭐⭐ |

Полный список: https://rhasspy.github.io/piper-samples/

## Проблемы и решения

### Piper не найден после установки

```bash
# Проверьте что venv активирован
which python3
# Должно показать путь внутри venv

# Переустановите
pip uninstall piper-tts
pip install piper-tts
```

### Модель не найдена

```bash
# Проверьте путь
ls -la ~/.local/share/piper/voices/

# Должны быть 2 файла для каждой модели:
# - модель.onnx
# - модель.onnx.json
```

### Низкое качество звука

Используйте модель с `-high` вместо `-medium`:
```bash
piper --download-dir ~/.local/share/piper/voices --model en_US-lessac-high
```

## Пути к моделям

- **Linux**: `~/.local/share/piper/voices/`
- **macOS**: `~/.local/share/piper/voices/`
- **Windows**: `%USERPROFILE%\.local\share\piper\voices\`

Или укажите свой путь в переменной окружения `PIPER_VOICES_DIR`
