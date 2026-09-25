# text-to-speech - TTS 引擎的统一接口

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | **[中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md)** | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

![Web UI 的 Studio 界面](https://raw.githubusercontent.com/wachawo/text-to-speech/main/docs/images/studio.png)

`text-to-speech` 让你通过一个统一的接口使用多种语音合成引擎。你可以先从在线的 gTTS 开始，之后再切换到本地的 Piper、Silero、Coqui、Bark 或 Kokoro - 无需重写你的 CLI 命令、Python 代码或 HTTP 集成。

本项目适合本地使用、自动化以及在网络上运行你自己的 TTS 服务器。

* **以同一种方式使用不同的引擎。** 选择你需要的引擎，并通过 CLI（`ttsgen`）、Python API（`libs.api`）或 HTTP API 调用它。
* **可以完全在本地运行。** Piper、Silero、Coqui、Bark、Kokoro 和 `pyttsx3` 都能在你自己的机器上运行。
* **内置了开箱即用的 HTTP 服务器。** `ttssrv` 在启动时加载模型，并为本地网络上的其他机器提供请求服务。

### 引擎

| 引擎        | 离线    | 硬件          | 质量    | 适用场景                                       |
| ----------- | ------- | ------------- | ------- | ---------------------------------------------- |
| `gtts`      | ❌      | CPU           | ★★★★    | 快速上手以及支持大量语言                       |
| `pyttsx3`   | ✅      | CPU           | ★★      | 通过 espeak 或 SAPI 实现简单的本地语音         |
| `pipertts`  | ✅      | CPU           | ★★★★    | 多语言的快速离线合成                           |
| `silerotts` | ✅      | CPU           | ★★★★    | 俄语语音以及轻量的本地配置                     |
| `kokorotts` | ✅      | CPU           | ★★★★    | 多语言离线合成                                 |
| `coquitts`  | ✅      | CPU / **GPU** | ★★★★★   | 高质量声音和声音克隆                           |
| `barktts`   | ✅      | CPU / **GPU** | ★★★★★   | 富有表现力的语音、情感、音乐和歌唱             |

`gtts`、`pyttsx3`、`pipertts`、`silerotts` 和 `kokorotts` 在 CPU 上运行良好。`coquitts` 和 `barktts` 也可以在没有 GPU 的情况下运行，但合成速度会明显变慢 - 建议为它们配备支持 CUDA 的显卡。

### 安装

基础安装会配置 CLI 及其轻量依赖：

```bash
pip install git+https://github.com/wachawo/text-to-speech.git
```

在 Linux 上，离线的 `pyttsx3` 引擎还需要系统的 `espeak` 软件包：

```bash
sudo apt install espeak espeak-data libespeak1
```

额外的引擎及其模型会在你真正需要时单独安装：

```bash
ttsgen --install coquitts
```

CLI 用法示例：

```bash
ttsgen "Hello world"                  # 用 gTTS 朗读文本
ttsgen "Hello world" -f out.mp3       # 将结果保存到文件
ttsgen "Hello world" -e pyttsx3       # 使用本地引擎
ttsgen "Hola amigo!" -l es            # 选择语言
ttsgen --install coquitts             # 安装 Coqui TTS 及其模型
ttsgen "Hello world" -e coquitts -f out.wav
ttsgen --list                         # 显示可用的引擎和模型
ttsgen "Hello world" --stdout | ttsplay
```

`gtts` 是默认引擎，因此首次运行只需一条命令即可。如需完全本地化的工作，请选择其他引擎，例如 `pyttsx3`、`pipertts` 或 `silerotts`。
我的选择：追求质量和自然的语音用 `coquitts`，追求快速生成用 `silerotts`。

### Python API

在 Python 中，提供了将结果保存到文件或以字节形式获取音频的函数：

```python
from libs.api import text_to_speech_file, text_to_speech_bytes

text_to_speech_file("Hello world", engine="gtts")

audio = text_to_speech_bytes(
    "Hello world",
    engine="pipertts",
    language="en",
)
```

### HTTP 服务器

使用 Docker 运行服务器更为简便：

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech
cp env.example .env                                   # 可选：令牌、引擎、端口

docker compose up --build -d                          # GPU / CUDA 12.1
docker compose -f docker-compose-cpu.yml up --build -d # 仅 CPU
```

GPU 版本通过 CDI 将显卡传递给容器，因此主机需要 NVIDIA container toolkit（1.14 或更新版本）以及生成好的 CDI 规范，每次更新驱动后生成一次：

```bash
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
```

启动后，你可以检查服务器状态并发送合成请求：

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

模型、声音和历史记录：

```bash
# 已安装和缺失的模型，与 `ttsgen --list` 打印的表格相同
curl localhost:5000/api/models \
  -H "Authorization: Bearer $TTS_TOKEN"

# 为 coquitts 上传声音样本（WAV）；此后该声音名为 "maria"
curl -X POST localhost:5000/api/voices \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -F file=@voice.wav -F name=maria -F engine=coquitts

curl "localhost:5000/api/voices?engine=coquitts" \
  -H "Authorization: Bearer $TTS_TOKEN"

curl "localhost:5000/api/voices/maria/audio?engine=coquitts&download=1" \
  -H "Authorization: Bearer $TTS_TOKEN" -o maria.wav

# 合成到服务器端的历史记录中，而不是返回到响应体
curl -X POST localhost:5000/api/history \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hola mundo","engine":"coquitts","language":"es","voice":"maria"}'

curl "localhost:5000/api/history?limit=50&offset=0" \
  -H "Authorization: Bearer $TTS_TOKEN"

# 单个条目的音频；不带 download=1 时以内联方式提供，可直接用于 <audio>
curl "localhost:5000/api/history/<id>/audio?download=1" \
  -H "Authorization: Bearer $TTS_TOKEN" -o tts.wav

curl -X DELETE localhost:5000/api/history/<id> \
  -H "Authorization: Bearer $TTS_TOKEN"
```

#### 兼容 OpenAI 的 API

同一个服务器还响应 OpenAI 音频 API，因此只要把 `base_url` 指向它并将 bearer 令牌用作 API key，Open WebUI、SillyTavern、Home Assistant 和官方 SDK 都可以直接使用：

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

- `model` 是引擎名称，或者用 `tts-1` / `tts-1-hd` / `gpt-4o-mini-tts` 表示默认引擎。
- `voice` 是引擎的声音；OpenAI 的声音名称（`alloy`、`nova` 等）会选择引擎的默认声音。
- `response_format`：`mp3`（默认）、`wav`、`pcm`、`opus`、`flac`、`aac`。引擎生成 WAV 或 MP3；其他格式通过 `ffmpeg` 转码，Docker 镜像中已包含它。`speed`（0.25 到 4.0）以同样的方式应用。
- `language` 是一个扩展参数：两位字母的语言代码或 `zh-cn` 这样的标签，默认为 `TTS_LANGUAGE`。
- `GET /v1/models` 列出已安装的引擎以及 `tts-1`；`GET /v1/audio/voices?model=<engine>` 列出某个引擎的声音。

#### API 参考

设置了 `TTS_TOKENS` 时，除 `/api/health` 之外的每个路由都需要 `Authorization: Bearer <token>`。`/api/` 下的错误格式为 `{"error": "...", "request_id": "..."}`；400 响应还带有说明原因的 `message`，请求未通过校验时它会列出出错的字段（`language: ...`）。`/v1/` 下的错误使用 OpenAI 的格式。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/health` | 存活状态、`auth` 标志、引擎、池和队列大小。无需令牌。 |
| GET | `/api/engines` | 支持的引擎、已安装的引擎以及默认引擎。 |
| GET | `/api/models` | 每个引擎已安装和缺失的模型，即 `ttsgen --list` 打印的表格。 |
| GET | `/api/voices?engine=&language=` | 某个引擎的声音；对于 `coquitts` 则是带大小、采样率和时长的样本。 |
| POST | `/api/voices` | 上传 WAV 样本（`file`、`name`、`engine=coquitts`）。 |
| GET | `/api/voices/<name>/audio?engine=&download=1` | 播放或下载样本。 |
| DELETE | `/api/voices/<name>?engine=` | 删除样本。 |
| POST, GET | `/api/tts` | 用 `engine`、`language`、`voice` 合成 `text`；`stream=true` 会在分块就绪时流式返回。 |
| POST | `/api/history` | 合成到服务器端的历史记录中，而不是返回到响应体。 |
| GET | `/api/history?limit=&offset=` | 列出历史条目，最新的在前。 |
| GET | `/api/history/<id>` | 单个条目的元数据。 |
| GET | `/api/history/<id>/audio?download=1` | 该条目的音频，内联或作为下载。 |
| DELETE | `/api/history/<id>` | 删除条目。 |
| POST | `/v1/audio/speech` | 兼容 OpenAI 的合成，见上文。 |
| GET | `/v1/models` | 兼容 OpenAI 的模型列表。 |
| GET | `/v1/audio/voices?model=` | 某个引擎的声音。 |

`language` 是两位字母的代码（`en`、`ru`），或带地区或书写系统的标签（`zh-cn`、`pt_BR`、`en-gb`、`es-419`），标签会转为小写并用 `-` 连接。每个引擎会把标签映射到自己支持的语言：gtts 使用它自己的写法（`zh-CN`；它没有加拿大法语和欧洲葡萄牙语，所以 `fr-ca` 和 `pt-pt` 即 `fr` 和 `pt`），kokorotts 用英式音素转换器朗读 `en-gb`，xtts 对中文使用 `zh-cn`，其他引擎使用语言部分（`pt-br` 即 `pt`）。`stream=true` 时，请求中的 `language` 与以前一样只接受两位字母的代码；不带 `language` 的请求按设置原样使用 `TTS_LANGUAGE`，即使它是标签。引擎不认识的语言会用该引擎的默认语言朗读，通常是英语（gtts 则会直接失败）；设置 `TTS_LANGUAGE_STRICT=true` 后，这类请求返回 400，并列出该引擎支持的语言。严格检查适用于不带 `stream` 的 `/api/tts`、`/api/history` 和 `/v1/audio/speech`，以及所有列出自身语言的引擎，即除 pyttsx3 和使用 xtts 以外多语言模型的 coquitts 之外的所有引擎。

#### Web UI

两个 compose 文件还会启动 `ttswww`，这是一个 nginx 容器，负责提供 Web UI 并将 `/api/` 代理到 `ttssrv`：

```bash
docker compose up --build -d
xdg-open http://localhost:8080      # TTS_WWW_PORT；如果 8080 被占用请修改
xdg-open https://localhost:8443     # TTS_WWW_TLS_PORT；自签名证书，接受一次即可
```

- **Studio** - 输入文本，选择引擎 / 语言 / 声音，生成、试听、保存；每个结果都会进入历史列表。
- **Voices** - 为 `coquitts` 声音克隆上传或录制 WAV 声音样本；可播放、下载和删除。
- **Models** - 引擎以及已安装 / 缺失的模型，与 `ttsgen --list` 相同的表格。

页眉中的齿轮图标会打开设置对话框：Studio 的默认引擎、语言和声音，以及是否显示 curl 示例；这些选择保存在浏览器中。Studio 会为当前请求显示一条可直接复制的 `curl` 命令；其中令牌以 `$TTS_TOKEN` 的形式引用，而不会直接打印出来。Voices 界面还可以从麦克风录制样本，浏览器只允许在 `https` 或 `localhost` 下这样做 - 在局域网中请通过 https 端口打开 UI。首次启动时会在 `./data/certs` 中生成自签名证书；以相同的文件名（`tts.crt`、`tts.key`）挂载真实证书即可替换它。

设置了 `TTS_TOKENS` 时，UI 会打开登录界面并要求输入其中一个令牌；浏览器会保存它并随每个请求发送。没有 `TTS_TOKENS` 时则没有登录界面。

#### 配置

所有设置都是环境变量；`env.example` 记录了全部变量，compose 文件旁边的 `.env` 会被自动读取。你最有可能修改的几个：

| 变量 | 默认值 | 作用 |
| --- | --- | --- |
| `TTS_TOKENS` | 空 | 逗号分隔的 bearer 令牌。为空表示完全不做认证。 |
| `TTS_ENGINES` | 空 | 启动时要安装并预热的引擎，逗号分隔（`coquitts,silerotts`）。 |
| `TTS_ENGINE` | `gtts` | 请求未指定引擎时使用的引擎。 |
| `TTS_LANGUAGE` | `en` | 请求未指定语言时使用的语言。 |
| `TTS_LANGUAGE_STRICT` | `false` | 为 `true` 时，对引擎未列出的语言返回 400，而不是让引擎回退到默认语言。 |
| `TTS_POOL_SIZE` | `1` | 所有引擎合计允许同时进行的合成调用数；`0` 取消上限和预热。 |
| `TTS_QUEUE_SIZE` | `8` | 允许等待空闲槽位的合成请求数；超出的请求会立即收到 503。 |
| `TTS_HISTORY_MAX` | `200` | 历史记录中保留的条目数；保存新条目时会删除最旧的。 |
| `TTS_MAX_SAMPLE_BYTES` | `16777216` | 声音样本上传的最大大小（16 MiB）。 |
| `TTS_MAX_SAMPLES` | `100` | 服务器上保留的声音样本数。 |
| `TTS_MAX_BODY_BYTES` | `2097152` | JSON 请求体的最大大小（2 MiB）。 |
| `TTS_STREAM_MAX_CHARS` | `200` | `stream=true` 时的分块大小。 |
| `CORS_ORIGINS` | `*` | `/api/*` 允许的来源。 |
| `TTS_PORT` | `5000` | `ttssrv` 的端口。 |
| `TTS_WWW_PORT`, `TTS_WWW_TLS_PORT` | `8080`, `8443` | Web UI 的 http 和 https 端口。 |
| `COQUITTS_MODEL`, `COQUITTS_SAMPLE` | `xtts_v2`, `default.wav` | Coqui 模型和默认声音样本。 |
| `TZ` | `America/New_York` | 日志和历史记录中时间戳的时区。 |

在 Docker 之外，CLI 和服务器按以下优先级（从高到低）读取相同的键：CLI 标志、shell 环境、`./ttsgen.conf`、`~/.config/ttsgen.conf`、`./.env.local`、`./.env`。文件永远不会覆盖 shell，而且 `.env` 只从当前目录读取。

`TTS_POOL_SIZE` 大于 1 时允许不同引擎并行合成；同一引擎内部的调用是串行的，因为底层模型无法安全地在线程之间共享。

#### 安全

- 在设置 `TTS_TOKENS` 之前，认证是关闭的。设置之后，除 `/api/health` 之外的每个路由都需要 `Authorization: Bearer <token>`，Web UI 也会在登录界面要求输入令牌。
- API 监听所有网络接口，compose 文件会在主机上发布 `TTS_PORT`、`TTS_WWW_PORT` 和 `TTS_WWW_TLS_PORT`。在共享网络中请设置令牌，或在 override 文件中将端口绑定到 `127.0.0.1`。
- https 监听器使用首次启动时生成的自签名证书；它面向局域网。在互联网上，请把 UI 放在你自己的、带真实证书的反向代理之后。
- 声音样本、历史记录和证书位于 `./data` 下；请备份它，并将其排除在构建上下文之外。

请通过仓库的 Security 标签页报告漏洞，见 [SECURITY.md](https://github.com/wachawo/text-to-speech/blob/main/SECURITY.md)。

为了使用和测试服务器，有一个独立的 CLI 客户端 `ttsapi`。它的主要标志与 `ttsgen` 相同，但合成在服务器上运行。服务器地址和令牌取自 `TTS_URL` 和 `TTS_TOKEN`。

```bash
ttsapi "Hello world"
ttsapi -i long.txt --output play,file --file out.mp3
```

### 项目结构

```text
text-to-speech/
├── ttsgen.py / ttsplay.py / ttsrec.py / ttsapi.py   # CLI 命令
├── engines/        # 引擎：gTTS、Piper、Silero、Coqui、Bark、Kokoro 等
├── libs/           # 共享核心：API、工具、播放、异常
├── install/        # ttsgen --install <engine> 的安装器
├── ttssrv/         # Flask HTTP 服务器
├── www/            # Web UI：无需构建步骤的 Vue 2，由 nginx 提供
├── nginx/          # nginx 主配置以及 ttswww 的 conf.d 模板
├── docker/         # 适用于 GPU、CPU 和 Web UI 的 Docker 构建
├── docs/           # 每个引擎的文档和 README 译文
└── tests/          # pytest 测试，无需下载模型，无需 GPU
```

### 开发

欢迎贡献；[CONTRIBUTING.md](https://github.com/wachawo/text-to-speech/blob/main/CONTRIBUTING.md) 说明了环境搭建、检查项以及如何添加引擎。安装开发依赖：

```bash
pip install -e ".[dev]"
```

提交前的检查：

```bash
pytest
ruff check .
black .
```

新引擎通过一个 `engines/<name>.py` 文件接入。你只需要实现两个函数：

```python
def is_available() -> bool:
    ...

def generate(text: str, config: dict) -> bytes:
    ...
```

`is_available()` 检查依赖是否可导入，`generate()` 接收文本和配置并以 MP3 或 WAV 字节的形式返回音频。之后该引擎会自动在 CLI 和 API 中可用。

每个引擎的详细参数和具体说明请见 [`docs/`](https://github.com/wachawo/text-to-speech/blob/main/docs/ENGINES.md)。

### 许可证

[MIT](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
