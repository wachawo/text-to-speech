## text-to-speech — 하나의 API로 인기 TTS 엔진 사용하기

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

인기 있는 온라인/오프라인 TTS 엔진(gTTS, espeak, Piper, Silero, Coqui, Bark, Kokoro)을 설치하고, 하나의 CLI, Python API, HTTP 서버를 통해 사용하세요.

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | **[한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)**

- **하나의 인터페이스, 여러 엔진.** 엔진을 선택해 CLI(`ttsgen`), Python(`libs.api`), HTTP에서 동일한 방식으로 호출하세요 — 코드를 바꾸지 않고 클라우드와 로컬 사이를 전환할 수 있습니다.
- **LAN을 위한 API 서버.** `ttssrv`를 실행하면 다른 머신이 HTTP(`POST /api/tts`)로 합성을 수행합니다. 모델은 시작 시 한 번 로드되며 요청은 풀을 공유합니다.

### 엔진

| 엔진 | 오프라인 | 하드웨어 | 품질 | 적합한 용도 |
|---|---|---|---|---|
| `gtts` | ❌ 온라인 | CPU | ★★★★ | 100개 이상의 언어, 설정 불필요 |
| `pyttsx3` | ✅ | CPU | ★★ | 최소 설치(espeak / SAPI) |
| `pipertts` | ✅ | CPU | ★★★★ | 빠른 오프라인, 50개 이상의 언어 |
| `silerotts` | ✅ | CPU | ★★★★ | 빠른 오프라인, 러시아어 |
| `kokorotts` | ✅ | CPU | ★★★★ | 빠른 오프라인, 다국어 |
| `coquitts` | ✅ | CPU / **GPU** | ★★★★★ | 최고 품질, 음성 복제 |
| `barktts` | ✅ | CPU / **GPU** | ★★★★★ | 감정, 음악, 노래 |

`gtts`, `pyttsx3`, `pipertts`, `silerotts`, `kokorotts`는 CPU에서 잘 작동합니다. `coquitts`와 `barktts`는 CPU에서도 작동하지만 느립니다 — CUDA GPU를 권장합니다.

### 설치(pip)

```bash
pip install git+https://github.com/wachawo/text-to-speech.git
```

이렇게 하면 가벼운 의존성만으로 CLI가 설치됩니다. 신경망 엔진(`pipertts`, `silerotts`, `coquitts`, `barktts`, `kokorotts`)은 `ttsgen --install <engine>`을 통해 필요할 때 `torch`/모델을 가져옵니다.

```bash
ttsgen "Hello world"                  # 재생(기본 엔진: gtts, 온라인)
ttsgen "Hello world" -f out.mp3       # 파일로 저장
ttsgen "Hello world" -e pyttsx3       # 완전 오프라인
ttsgen "Hola amigo!"  -l es           # 언어 선택
ttsgen --install coquitts             # 오프라인 신경망 엔진 + 모델 추가
ttsgen "Hello world" -e coquitts -f out.wav
ttsgen --list                         # 엔진 + 설치된 모델
ttsgen "Hello world" --stdout | ttsplay
```

Python:

```python
from libs.api import text_to_speech_file, text_to_speech_bytes

text_to_speech_file("Hello world", engine="gtts")
audio = text_to_speech_bytes("Hello world", engine="pipertts", language="en")
```

### 서버(클론)

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech
docker compose up --build -d                          # GPU (CUDA 12.1)
docker compose -f docker-compose-cpu.yml up --build -d # CPU 전용
```

HTTP로 합성을 요청하세요:

```bash
curl localhost:5000/api/health
curl localhost:5000/api/engines -H "Authorization: Bearer $TTS_TOKEN"
curl "localhost:5000/api/voices?engine=silerotts&language=ru" -H "Authorization: Bearer $TTS_TOKEN"

curl -X POST localhost:5000/api/tts \
  -H "Authorization: Bearer $TTS_TOKEN" -H "Content-Type: application/json" \
  -d '{"text":"Hello world","engine":"gtts"}' -o out.mp3
```

또는 `ttsapi`를 사용하세요 — `ttsgen`과 동일한 플래그를 사용하지만 합성은 서버에서 실행됩니다(`TTS_URL` / `TTS_TOKEN`은 설정에서 가져옴):

```bash
ttsapi "Hello world"
ttsapi -i long.txt --output play,file --file out.mp3
```

### 프로젝트 구조

```
text-to-speech/
├── ttsgen.py / ttsplay.py / ttsrec.py / ttsapi.py   # CLI 진입점
├── engines/        # 플러그형 엔진(gtts, piper, silero, coqui, bark, kokoro, …)
├── libs/           # 코어: api.py, tools.py, playback.py, exceptions.py
├── install/        # `ttsgen --install <engine>` 설치 프로그램
├── ttssrv/         # Flask HTTP 서버(Docker / python3 ttssrv/app1.py)
├── docker/         # gpu/ 및 cpu/ 빌드(Dockerfile + requirements)
├── docs/           # 엔진별 가이드 + 번역
└── tests/          # pytest 스위트(엔진 모킹, 모델/GPU 불필요)
```

### 개발자 노트

```bash
pip install -e ".[dev]"
pytest                 # 테스트 + 커버리지
ruff check . && black .
```

두 개의 함수를 가진 `engines/<name>.py`를 추가하면 엔진이 CLI와 API에 자동으로 나타납니다:

```python
def is_available() -> bool: ...                  # 의존성을 임포트할 수 있는가?
def generate(text: str, config: dict) -> bytes:  # MP3/WAV 바이트 반환
    ...
```

엔진별 설정과 전체 엔진 가이드는 [`docs/`](docs/ENGINES.md)에 있습니다.

### 라이선스

[MIT](LICENSE)
