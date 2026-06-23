## text-to-speech — TTS 引擎的统一接口

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | **[中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md)** | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

> _提前致歉：本翻译是借助 Claude Code 完成的。如果你是母语者并发现任何错误，请告诉我。_

`text-to-speech` 让你通过一个统一的接口使用多种语音合成引擎。你可以先从在线的 gTTS 开始，之后再切换到本地的 Piper、Silero、Coqui、Bark 或 Kokoro —— 无需重写你的 CLI 命令、Python 代码或 HTTP 集成。

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

`gtts`、`pyttsx3`、`pipertts`、`silerotts` 和 `kokorotts` 在 CPU 上运行良好。`coquitts` 和 `barktts` 也可以在没有 GPU 的情况下运行，但合成速度会明显变慢 —— 建议为它们配备支持 CUDA 的显卡。

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

docker compose up --build -d                          # GPU / CUDA 12.1
docker compose -f docker-compose-cpu.yml up --build -d # 仅 CPU
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
├── docker/         # 适用于 GPU 和 CPU 的 Docker 构建
├── docs/           # 每个引擎的文档和 README 译文
└── tests/          # pytest 测试，无需下载模型，无需 GPU
```

### 开发

安装开发依赖：

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

每个引擎的详细参数和具体说明请见 [`docs/`](ENGINES.md)。

### 许可证

[MIT](../LICENSE)
