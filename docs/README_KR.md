## text-to-speech — TTS 엔진을 위한 단일 인터페이스

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

`text-to-speech`를 사용하면 하나의 인터페이스를 통해 여러 음성 합성 엔진을 다룰 수 있습니다. 온라인 gTTS로 시작한 뒤, CLI 명령어, Python 코드, HTTP 연동을 다시 작성하지 않고도 로컬 Piper, Silero, Coqui, Bark, Kokoro로 전환할 수 있습니다.

이 프로젝트는 로컬 사용, 자동화, 그리고 네트워크에서 자체 TTS 서버를 운영하는 데 적합합니다.

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | **[한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)**

* **다양한 엔진을 다루는 하나의 방식.** 필요한 엔진을 선택해 CLI(`ttsgen`), Python API(`libs.api`), 또는 HTTP API를 통해 호출하세요.
* **완전히 로컬에서 작업할 수 있습니다.** Piper, Silero, Coqui, Bark, Kokoro, 그리고 `pyttsx3`는 모두 자신의 컴퓨터에서 실행됩니다.
* **바로 사용할 수 있는 HTTP 서버가 포함되어 있습니다.** `ttssrv`는 시작 시 모델을 로드하고 로컬 네트워크의 다른 컴퓨터에서 오는 요청을 처리합니다.

### 엔진

| 엔진        | 오프라인 | 하드웨어      | 품질    | 적합한 용도                                    |
| ----------- | ------- | ------------- | ------- | ---------------------------------------------- |
| `gtts`      | ❌      | CPU           | ★★★★    | 빠른 시작과 다수의 언어 지원                   |
| `pyttsx3`   | ✅      | CPU           | ★★      | espeak 또는 SAPI를 통한 간단한 로컬 음성       |
| `pipertts`  | ✅      | CPU           | ★★★★    | 여러 언어에서 빠른 오프라인 합성               |
| `silerotts` | ✅      | CPU           | ★★★★    | 러시아어 음성과 가벼운 로컬 구성               |
| `kokorotts` | ✅      | CPU           | ★★★★    | 다국어 오프라인 합성                           |
| `coquitts`  | ✅      | CPU / **GPU** | ★★★★★   | 고품질 음성과 음성 복제                        |
| `barktts`   | ✅      | CPU / **GPU** | ★★★★★   | 표현력 있는 음성, 감정, 음악, 노래             |

`gtts`, `pyttsx3`, `pipertts`, `silerotts`, `kokorotts`는 CPU에서 문제없이 실행됩니다. `coquitts`와 `barktts`도 GPU 없이 실행할 수 있지만 합성이 눈에 띄게 느려지므로, 이들에는 CUDA 지원 그래픽 카드를 권장합니다.

### 설치

기본 설치는 CLI와 그 경량 의존성을 설정합니다:

```bash
pip install git+https://github.com/wachawo/text-to-speech.git
```

Linux에서는 오프라인 `pyttsx3` 엔진에 시스템 `espeak` 패키지도 필요합니다:

```bash
sudo apt install espeak espeak-data libespeak1
```

추가 엔진과 해당 모델은 실제로 필요할 때 별도로 설치합니다:

```bash
ttsgen --install coquitts
```

CLI 사용 예시:

```bash
ttsgen "Hello world"                  # gTTS로 텍스트 읽기
ttsgen "Hello world" -f out.mp3       # 결과를 파일로 저장
ttsgen "Hello world" -e pyttsx3       # 로컬 엔진 사용
ttsgen "Hola amigo!" -l es            # 언어 선택
ttsgen --install coquitts             # Coqui TTS와 모델 설치
ttsgen "Hello world" -e coquitts -f out.wav
ttsgen --list                         # 사용 가능한 엔진과 모델 표시
ttsgen "Hello world" --stdout | ttsplay
```

`gtts`가 기본값이므로 처음 실행할 때는 명령어 하나면 충분합니다. 완전히 로컬에서 작업하려면 `pyttsx3`, `pipertts`, `silerotts` 같은 다른 엔진을 선택하세요.
제가 선택하는 것: 품질과 자연스러운 음성을 위해서는 `coquitts`, 빠른 생성을 위해서는 `silerotts`.

### Python API

Python에서는 결과를 파일로 저장하거나 오디오를 바이트로 받는 함수가 있습니다:

```python
from libs.api import text_to_speech_file, text_to_speech_bytes

text_to_speech_file("Hello world", engine="gtts")

audio = text_to_speech_bytes(
    "Hello world",
    engine="pipertts",
    language="en",
)
```

### HTTP 서버

Docker로 서버를 실행하는 것이 더 쉽습니다:

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech

docker compose up --build -d                          # GPU / CUDA 12.1
docker compose -f docker-compose-cpu.yml up --build -d # CPU only
```

실행되면 서버 상태를 확인하고 합성 요청을 보낼 수 있습니다:

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

서버를 다루고 테스트하기 위한 별도의 CLI 클라이언트 `ttsapi`가 있습니다. `ttsgen`과 동일한 주요 플래그를 가지지만 합성은 서버에서 실행됩니다. 서버 주소와 토큰은 `TTS_URL`과 `TTS_TOKEN`에서 가져옵니다.

```bash
ttsapi "Hello world"
ttsapi -i long.txt --output play,file --file out.mp3
```

### 프로젝트 구조

```text
text-to-speech/
├── ttsgen.py / ttsplay.py / ttsrec.py / ttsapi.py   # CLI 명령어
├── engines/        # 엔진: gTTS, Piper, Silero, Coqui, Bark, Kokoro 등
├── libs/           # 공유 코어: API, 도구, 재생, 예외
├── install/        # ttsgen --install <engine>용 설치 프로그램
├── ttssrv/         # Flask HTTP 서버
├── docker/         # GPU 및 CPU용 Docker 빌드
├── docs/           # 엔진별 문서와 README 번역
└── tests/          # pytest 테스트, 모델 다운로드 및 GPU 불필요
```

### 개발

개발 의존성을 설치하려면:

```bash
pip install -e ".[dev]"
```

커밋 전 점검:

```bash
pytest
ruff check .
black .
```

새 엔진은 `engines/<name>.py` 파일을 통해 연결됩니다. 두 개의 함수만 구현하면 됩니다:

```python
def is_available() -> bool:
    ...

def generate(text: str, config: dict) -> bytes:
    ...
```

`is_available()`는 의존성을 가져올 수 있는지 확인하고, `generate()`는 텍스트와 설정을 받아 오디오를 MP3 또는 WAV 바이트로 반환합니다. 그 후 엔진은 CLI와 API에서 자동으로 사용할 수 있게 됩니다.

각 엔진의 자세한 매개변수와 세부 사항은 [`docs/`](ENGINES.md)에 설명되어 있습니다.

### 라이선스

[MIT](../LICENSE)
