## text-to-speech — एक ही API के पीछे लोकप्रिय TTS इंजन

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

लोकप्रिय ऑनलाइन/ऑफ़लाइन TTS इंजन (gTTS, espeak, Piper, Silero, Coqui, Bark, Kokoro) इंस्टॉल करें और उन्हें एक ही CLI, Python API, और HTTP सर्वर के ज़रिए उपयोग करें।

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | **[हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md)** | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

- **एक इंटरफ़ेस, कई इंजन।** एक इंजन चुनें और उसे CLI (`ttsgen`), Python (`libs.api`), या HTTP से एक ही तरीके से कॉल करें — कोड बदले बिना क्लाउड और लोकल के बीच स्विच करें।
- **आपके LAN के लिए API सर्वर।** `ttssrv` चलाएँ ताकि अन्य मशीनें HTTP (`POST /api/tts`) पर सिंथेसाइज़ कर सकें; मॉडल स्टार्टअप पर एक बार लोड होता है और अनुरोध एक पूल साझा करते हैं।

### इंजन

| इंजन | ऑफ़लाइन | हार्डवेयर | गुणवत्ता | सर्वोत्तम के लिए |
|---|---|---|---|---|
| `gtts` | ❌ ऑनलाइन | CPU | ★★★★ | 100+ भाषाएँ, शून्य सेटअप |
| `pyttsx3` | ✅ | CPU | ★★ | न्यूनतम इंस्टॉल (espeak / SAPI) |
| `pipertts` | ✅ | CPU | ★★★★ | तेज़ ऑफ़लाइन, 50+ भाषाएँ |
| `silerotts` | ✅ | CPU | ★★★★ | तेज़ ऑफ़लाइन, रूसी |
| `kokorotts` | ✅ | CPU | ★★★★ | तेज़ ऑफ़लाइन, बहु-भाषा |
| `coquitts` | ✅ | CPU / **GPU** | ★★★★★ | सर्वोत्तम गुणवत्ता, वॉइस क्लोनिंग |
| `barktts` | ✅ | CPU / **GPU** | ★★★★★ | भावनाएँ, संगीत, गायन |

`gtts`, `pyttsx3`, `pipertts`, `silerotts`, `kokorotts` CPU पर ठीक चलते हैं। `coquitts` और `barktts` भी CPU पर चलते हैं लेकिन धीमे होते हैं — एक CUDA GPU की अनुशंसा की जाती है।

### इंस्टॉल (pip)

```bash
pip install git+https://github.com/wachawo/text-to-speech.git
```

यह केवल हल्की निर्भरताओं के साथ CLI इंस्टॉल करता है। न्यूरल इंजन (`pipertts`, `silerotts`, `coquitts`, `barktts`, `kokorotts`) `ttsgen --install <engine>` के ज़रिए माँग पर `torch`/मॉडल खींचते हैं।

```bash
ttsgen "Hello world"                  # play (default engine: gtts, online)
ttsgen "Hello world" -f out.mp3       # save to a file
ttsgen "Hello world" -e pyttsx3       # fully offline
ttsgen "Hola amigo!"  -l es           # pick language
ttsgen --install coquitts             # add an offline neural engine + models
ttsgen "Hello world" -e coquitts -f out.wav
ttsgen --list                         # engines + installed models
ttsgen "Hello world" --stdout | ttsplay
```

Python:

```python
from libs.api import text_to_speech_file, text_to_speech_bytes

text_to_speech_file("Hello world", engine="gtts")
audio = text_to_speech_bytes("Hello world", engine="pipertts", language="en")
```

### सर्वर (clone)

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech
docker compose up --build -d                          # GPU (CUDA 12.1)
docker compose -f docker-compose-cpu.yml up --build -d # CPU-only
```

HTTP पर सिंथेसिस का अनुरोध करें:

```bash
curl localhost:5000/api/health
curl localhost:5000/api/engines -H "Authorization: Bearer $TTS_TOKEN"
curl "localhost:5000/api/voices?engine=silerotts&language=ru" -H "Authorization: Bearer $TTS_TOKEN"

curl -X POST localhost:5000/api/tts \
  -H "Authorization: Bearer $TTS_TOKEN" -H "Content-Type: application/json" \
  -d '{"text":"Hello world","engine":"gtts"}' -o out.mp3
```

या `ttsapi` का उपयोग करें — `ttsgen` जैसे ही फ़्लैग, लेकिन सिंथेसिस सर्वर पर चलता है (`TTS_URL` / `TTS_TOKEN` कॉन्फ़िग से):

```bash
ttsapi "Hello world"
ttsapi -i long.txt --output play,file --file out.mp3
```

### प्रोजेक्ट संरचना

```
text-to-speech/
├── ttsgen.py / ttsplay.py / ttsrec.py / ttsapi.py   # CLI entry points
├── engines/        # pluggable engines (gtts, piper, silero, coqui, bark, kokoro, …)
├── libs/           # core: api.py, tools.py, playback.py, exceptions.py
├── install/        # `ttsgen --install <engine>` installers
├── ttssrv/         # Flask HTTP server (Docker / python3 ttssrv/app1.py)
├── docker/         # gpu/ and cpu/ builds (Dockerfile + requirements)
├── docs/           # per-engine guides + translations
└── tests/          # pytest suite (engines mocked, no models/GPU needed)
```

### डेवलपर नोट्स

```bash
pip install -e ".[dev]"
pytest                 # tests + coverage
ruff check . && black .
```

दो फ़ंक्शन के साथ `engines/<name>.py` डालकर एक इंजन जोड़ें — यह CLI और API में अपने-आप दिखाई देता है:

```python
def is_available() -> bool: ...                  # deps importable?
def generate(text: str, config: dict) -> bytes:  # return MP3/WAV bytes
    ...
```

प्रति-इंजन सेटअप और पूर्ण इंजन गाइड [`docs/`](docs/ENGINES.md) में रहते हैं।

### लाइसेंस

[MIT](LICENSE)
