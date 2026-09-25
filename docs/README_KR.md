# text-to-speech - TTS 엔진을 위한 단일 인터페이스

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | **[한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)**

![웹 UI의 Studio 화면](https://raw.githubusercontent.com/wachawo/text-to-speech/main/docs/images/studio.png)

`text-to-speech`를 사용하면 하나의 인터페이스를 통해 여러 음성 합성 엔진을 다룰 수 있습니다. 온라인 gTTS로 시작한 뒤 로컬 Piper, Silero, Coqui, Bark, Kokoro로 전환할 수 있습니다 - CLI 명령어, Python 코드, HTTP 연동을 다시 작성하지 않고도 말입니다.

이 프로젝트는 로컬 사용, 자동화, 그리고 네트워크에서 자체 TTS 서버를 운영하는 데 적합합니다.

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

`gtts`, `pyttsx3`, `pipertts`, `silerotts`, `kokorotts`는 CPU에서 문제없이 실행됩니다. `coquitts`와 `barktts`도 GPU 없이 실행할 수 있지만 합성이 눈에 띄게 느려집니다 - 이들에는 CUDA 지원 그래픽 카드를 권장합니다.

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
cp env.example .env                                   # 선택 사항: 토큰, 엔진, 포트

docker compose up --build -d                          # GPU / CUDA 12.1
docker compose -f docker-compose-cpu.yml up --build -d # CPU 전용
```

GPU 버전은 CDI를 통해 그래픽 카드를 전달하므로, 호스트에 NVIDIA container toolkit(1.14 이상)과 생성된 CDI spec이 필요합니다. 드라이버를 업데이트할 때마다 한 번 생성합니다:

```bash
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
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

모델, 음성, 히스토리:

```bash
# 엔진 하나가 제공하는 것: 모델, 언어, 음성 (모델을 로드하지 않음)
curl localhost:5000/api/engines/pipertts \
  -H "Authorization: Bearer $TTS_TOKEN"

# 거기에 나온 모델 중 하나로 합성
curl -X POST localhost:5000/api/tts \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world","engine":"pipertts","language":"en-gb","model":"en_GB-alan-low"}' \
  -o out.wav

# 설치된 모델과 누락된 모델, `ttsgen --list`가 출력하는 것과 같은 표
curl localhost:5000/api/models \
  -H "Authorization: Bearer $TTS_TOKEN"

# coquitts용 음성 샘플(WAV) 업로드; 이후 음성 이름은 "maria"
curl -X POST localhost:5000/api/voices \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -F file=@voice.wav -F name=maria -F engine=coquitts

curl "localhost:5000/api/voices?engine=coquitts" \
  -H "Authorization: Bearer $TTS_TOKEN"

curl "localhost:5000/api/voices/maria/audio?engine=coquitts&download=1" \
  -H "Authorization: Bearer $TTS_TOKEN" -o maria.wav

# 응답 본문 대신 서버 측 히스토리로 합성
curl -X POST localhost:5000/api/history \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hola mundo","engine":"coquitts","language":"es","voice":"maria"}'

curl "localhost:5000/api/history?limit=50&offset=0" \
  -H "Authorization: Bearer $TTS_TOKEN"

# 항목 하나의 오디오; download=1이 없으면 <audio>용으로 인라인 제공
curl "localhost:5000/api/history/<id>/audio?download=1" \
  -H "Authorization: Bearer $TTS_TOKEN" -o tts.wav

curl -X DELETE localhost:5000/api/history/<id> \
  -H "Authorization: Bearer $TTS_TOKEN"
```

#### OpenAI 호환 API

같은 서버가 OpenAI 오디오 API에도 응답하므로, Open WebUI, SillyTavern, Home Assistant, 공식 SDK는 `base_url`을 이 서버로 지정하고 bearer 토큰을 API 키로 사용하면 동작합니다:

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

- `model`은 엔진 이름이거나, 기본 엔진을 뜻하는 `tts-1` / `tts-1-hd` / `gpt-4o-mini-tts`입니다. `/v1`에서는 엔진 안의 모델을 고를 수 없으며, 엔진은 기본 모델을 사용합니다.
- `voice`는 엔진의 음성입니다. OpenAI 음성 이름(`alloy`, `nova`, ...)은 엔진 기본값을 선택합니다.
- `response_format`: `mp3`(기본값), `wav`, `pcm`, `opus`, `flac`, `aac`. 엔진은 WAV 또는 MP3를 생성하며, 그 외 형식은 Docker 이미지에 포함된 `ffmpeg`로 트랜스코딩됩니다. `speed`(0.25에서 4.0)도 같은 방식으로 적용됩니다.
- `language`는 확장 항목입니다: 두 글자 코드 또는 `zh-cn` 같은 태그이며 기본값은 `TTS_LANGUAGE`입니다.
- `GET /v1/models`는 설치된 엔진과 `tts-1`을 나열하고, `GET /v1/audio/voices?model=<engine>`는 엔진 하나의 음성을 나열합니다.

#### API 레퍼런스

`TTS_TOKENS`가 설정되어 있으면 `/api/health`를 제외한 모든 경로에 `Authorization: Bearer <token>`이 필요합니다. `/api/` 아래의 오류는 `{"error": "...", "request_id": "..."}` 형태이며, 400 응답에는 이유를 담은 `message`가 추가로 들어 있어 요청이 검증을 통과하지 못하면 문제가 된 필드를 알려 줍니다(`language: ...`). `/v1/` 아래의 오류는 OpenAI 형식을 사용합니다.

| 메서드 | 경로 | 용도 |
| --- | --- | --- |
| GET | `/api/health` | 활성 상태, `auth` 플래그, 엔진, 풀과 큐 크기. 토큰 불필요. |
| GET | `/api/engines` | 지원 엔진, 설치된 엔진, 기본 엔진. |
| GET | `/api/engines/<engine>` | 한 엔진의 모델, 언어, 음성 목록, 출력 형식을 모델을 로드하지 않고 읽음. |
| GET | `/api/models` | 엔진별 설치된 모델과 누락된 모델, `ttsgen --list`가 출력하는 표. |
| GET | `/api/voices?engine=&language=&model=` | 엔진의 음성; `coquitts`의 경우 크기, 샘플링 레이트, 길이를 포함한 샘플. `model`을 주면 그 모델의 음성. |
| POST | `/api/voices` | WAV 샘플 업로드(`file`, `name`, `engine=coquitts`). |
| GET | `/api/voices/<name>/audio?engine=&download=1` | 샘플 재생 또는 다운로드. |
| DELETE | `/api/voices/<name>?engine=` | 샘플 삭제. |
| POST, GET | `/api/tts` | `engine`, `language`, `voice`, `model`로 `text` 합성; `stream=true`는 준비되는 대로 청크를 스트리밍. |
| POST | `/api/history` | 응답 본문 대신 서버 측 히스토리로 합성. |
| GET | `/api/history?limit=&offset=` | 히스토리 항목 목록, 최신순. |
| GET | `/api/history/<id>` | 항목 하나의 메타데이터. |
| GET | `/api/history/<id>/audio?download=1` | 항목의 오디오, 인라인 또는 다운로드. |
| DELETE | `/api/history/<id>` | 항목 삭제. |
| POST | `/v1/audio/speech` | OpenAI 호환 합성, 위 참조. |
| GET | `/v1/models` | OpenAI 호환 모델 목록. |
| GET | `/v1/audio/voices?model=` | 엔진 하나의 음성. |

`language`는 두 글자 코드(`en`, `ru`) 또는 지역이나 문자 체계가 붙은 태그(`zh-cn`, `pt_BR`, `en-gb`, `es-419`)이며, 태그는 소문자로 바뀌고 `-`로 연결됩니다. 각 엔진은 태그를 자신이 가진 언어에 맞춥니다: gtts는 자체 표기(`zh-CN`; 캐나다 프랑스어와 유럽 포르투갈어가 없어 `fr-ca`와 `pt-pt`는 `fr`과 `pt`)를 받고, kokorotts는 `en-gb`를 영국식 음소 변환기로 읽으며, xtts는 중국어에 `zh-cn`을 받고, 나머지 엔진은 언어 부분을 사용합니다(`pt-br`은 `pt`). 엔진이 모르는 언어는 엔진의 기본 언어(보통 영어)로 읽힙니다(gtts는 대신 실패합니다). `TTS_LANGUAGE_STRICT=true`이면 이런 요청은 엔진의 언어 목록을 알려 주는 400이 됩니다. 엄격한 검사는 `stream`이 없는 `/api/tts`, `/api/history`, `/v1/audio/speech`에 적용되며, 언어 목록을 제공하는 모든 엔진, 즉 pyttsx3와, xtts가 아닌 다국어 모델이나 세 글자 언어 코드(`ewe`)의 모델을 쓰는 coquitts를 제외한 모든 엔진이 대상입니다.

`model`은 `/api/tts`와 `/api/history`에서 엔진 안의 모델을 고릅니다: Piper 음성(`en_GB-alan-low`), Kokoro 모델 파일(`kokoro-v1.0.int8.onnx`), Silero 모델(`v3_1_ru`) 또는 Coqui 모델 이름(`tts_models/de/thorsten/vits`). `GET /api/engines/<engine>`은 이를 `models`에 나열하며, 각 모델에는 `languages`, `installed`, `default_for`(요청이 모델을 지정하지 않을 때 그 모델을 쓰는 언어)가 붙고, 엔진의 `languages`, `output_format`, `max_text_length`, 음성 목록 제공 여부도 함께 알려 줍니다. 모델은 로드하지 않으며, 알 수 없는 엔진은 404입니다. `model`이 없으면 엔진은 이전과 같이 고릅니다. 엔진이 나열하지 않은 id는 사용 가능한 id를 알려 주는 400이고, `stream=true`와 함께 쓴 `model`도 400입니다. 스트림은 항상 엔진의 기본 모델을 쓰기 때문입니다. gtts, pyttsx3, barktts에는 모델이 없습니다. 모델이 없으면 pipertts는 설치된 음성 중에서 고릅니다: 지역이 붙은 태그(`en-gb`)는 그 지역의 음성을, 내장 표에 없는 언어는 영어 음성 대신 그 언어의 설치된 음성을 사용합니다. pipertts의 언어 목록은 설치된 음성의 언어입니다.

#### 웹 UI

두 compose 파일 모두 웹 UI를 제공하고 `/api/`를 `ttssrv`로 프록시하는 nginx 컨테이너 `ttswww`도 함께 시작합니다:

```bash
docker compose up --build -d
xdg-open http://localhost:8080      # TTS_WWW_PORT; 8080이 사용 중이면 변경
xdg-open https://localhost:8443     # TTS_WWW_TLS_PORT; 자체 서명 인증서, 한 번만 수락
```

- **Studio** - 텍스트를 입력하고 엔진 / 언어 / 음성을 선택해 생성, 청취, 저장; 모든 결과는 히스토리 목록에 남습니다.
- **Voices** - `coquitts` 음성 복제용 WAV 음성 샘플을 업로드하거나 녹음; 재생, 다운로드, 삭제할 수 있습니다.
- **Models** - 엔진과 설치된 / 누락된 모델, `ttsgen --list`와 같은 표.

헤더의 톱니바퀴는 설정 대화상자를 엽니다: Studio의 기본 엔진, 언어, 음성과 curl 예시 표시 여부이며, 선택은 브라우저에 저장됩니다. Studio는 현재 요청에 대해 바로 복사할 수 있는 `curl` 명령을 보여 주며, 토큰을 그대로 출력하지 않고 `$TTS_TOKEN`으로 참조합니다. Voices 화면에서는 마이크로 샘플을 녹음할 수도 있는데, 브라우저는 이를 `https` 또는 `localhost`에서만 허용합니다 - LAN에서는 https 포트로 UI를 여세요. 첫 시작 시 `./data/certs`에 자체 서명 인증서가 생성되며, 같은 이름(`tts.crt`, `tts.key`)으로 실제 인증서를 마운트하면 교체됩니다.

`TTS_TOKENS`가 설정되어 있으면 UI는 로그인 화면으로 열리고 그 토큰 중 하나를 요구합니다. 브라우저가 토큰을 보관하고 모든 요청에 함께 보냅니다. `TTS_TOKENS`가 없으면 로그인은 없습니다.

#### 설정

모든 설정은 환경 변수입니다. `env.example`에 전부 문서화되어 있으며 compose 파일 옆의 `.env`는 자동으로 읽힙니다. 가장 자주 바꾸게 될 항목:

| 변수 | 기본값 | 역할 |
| --- | --- | --- |
| `TTS_TOKENS` | 비어 있음 | 쉼표로 구분된 bearer 토큰. 비어 있으면 인증이 전혀 없습니다. |
| `TTS_ENGINES` | 비어 있음 | 시작 시 설치하고 워밍업할 엔진, 쉼표로 구분(`coquitts,silerotts`). |
| `TTS_ENGINE` | `gtts` | 요청에 엔진이 지정되지 않았을 때 사용하는 엔진. |
| `TTS_LANGUAGE` | `en` | 요청에 언어가 지정되지 않았을 때 사용하는 언어. |
| `TTS_LANGUAGE_STRICT` | `false` | `true`이면 엔진 목록에 없는 언어에 대해 엔진의 기본 언어로 대체하는 대신 400을 반환. |
| `TTS_MODEL_CACHE_SIZE` | `2` | coquitts와 kokorotts가 동시에 로드해 두는 모델 수; 모델을 하나 더 요청하면 가장 먼저 로드된 모델이 해제됩니다. |
| `TTS_POOL_SIZE` | `1` | 모든 엔진을 통틀어 동시에 허용되는 합성 호출 수; `0`은 제한과 워밍업을 없앱니다. |
| `TTS_QUEUE_SIZE` | `8` | 빈 슬롯을 기다릴 수 있는 합성 요청 수; 초과분은 즉시 503을 받습니다. |
| `TTS_HISTORY_MAX` | `200` | 히스토리에 보관되는 항목 수; 새 항목이 저장되면 가장 오래된 것이 삭제됩니다. |
| `TTS_MAX_SAMPLE_BYTES` | `16777216` | 음성 샘플 업로드 최대 크기(16 MiB). |
| `TTS_MAX_SAMPLES` | `100` | 서버에 보관되는 음성 샘플 수. |
| `TTS_MAX_BODY_BYTES` | `2097152` | JSON 요청 본문 최대 크기(2 MiB). |
| `TTS_STREAM_MAX_CHARS` | `200` | `stream=true`의 청크 크기. |
| `CORS_ORIGINS` | `*` | `/api/*`에 허용되는 오리진. |
| `TTS_PORT` | `5000` | `ttssrv`의 포트. |
| `TTS_WWW_PORT`, `TTS_WWW_TLS_PORT` | `8080`, `8443` | 웹 UI의 http 및 https 포트. |
| `COQUITTS_MODEL`, `COQUITTS_SAMPLE` | `xtts_v2`, `default.wav` | Coqui 모델과 기본 음성 샘플. |
| `TZ` | `America/New_York` | 로그와 히스토리의 타임스탬프에 쓰이는 시간대. |

Docker 밖에서는 CLI와 서버가 같은 키를 다음 순서(우선순위 높은 것부터)로 읽습니다: CLI 플래그, 셸 환경, `./ttsgen.conf`, `~/.config/ttsgen.conf`, `./.env.local`, `./.env`. 파일이 셸을 덮어쓰는 일은 없으며, `.env`는 현재 디렉터리에서만 읽힙니다.

`TTS_POOL_SIZE`가 1보다 크면 서로 다른 엔진이 병렬로 합성할 수 있습니다. 하나의 엔진 안에서는 호출이 직렬화되는데, 기반 모델이 스레드 간 공유에 안전하지 않기 때문입니다.

#### 보안

- `TTS_TOKENS`를 설정하기 전까지 인증은 꺼져 있습니다. 설정하면 `/api/health`를 제외한 모든 경로에 `Authorization: Bearer <token>`이 필요하고, 웹 UI는 로그인 화면에서 토큰을 요구합니다.
- API는 모든 인터페이스에서 수신하며 compose 파일은 `TTS_PORT`, `TTS_WWW_PORT`, `TTS_WWW_TLS_PORT`를 호스트에 공개합니다. 공유 네트워크에서는 토큰을 설정하거나, override 파일에서 포트를 `127.0.0.1`에 바인딩하세요.
- https 리스너는 첫 시작 시 발급된 자체 서명 인증서를 사용하며 LAN용입니다. 인터넷에서는 실제 인증서를 갖춘 자체 리버스 프록시 뒤에 UI를 두세요.
- 음성 샘플, 히스토리, 인증서는 `./data` 아래에 있습니다. 백업하고 빌드 컨텍스트에서 제외하세요.

취약점은 저장소의 Security 탭을 통해 신고하세요. [SECURITY.md](https://github.com/wachawo/text-to-speech/blob/main/SECURITY.md)를 참조하세요.

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
├── www/            # 웹 UI: 빌드 단계 없는 Vue 2, nginx로 제공
├── nginx/          # nginx 메인 설정과 ttswww용 conf.d 템플릿
├── docker/         # GPU, CPU, 웹 UI용 Docker 빌드
├── docs/           # 엔진별 문서와 README 번역
└── tests/          # pytest 테스트, 모델 다운로드 및 GPU 불필요
```

### 개발

기여를 환영합니다. [CONTRIBUTING.md](https://github.com/wachawo/text-to-speech/blob/main/CONTRIBUTING.md)에 환경 설정, 점검 항목, 엔진 추가 방법이 설명되어 있습니다. 개발 의존성을 설치하려면:

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

각 엔진의 자세한 매개변수와 세부 사항은 [`docs/`](https://github.com/wachawo/text-to-speech/blob/main/docs/ENGINES.md)에 설명되어 있습니다.

### 라이선스

[MIT](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
