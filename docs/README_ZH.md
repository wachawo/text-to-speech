## text-to-speech — 一个 API 背后的主流 TTS 引擎

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

安装主流的在线/离线 TTS 引擎（gTTS、espeak、Piper、Silero、Coqui、Bark、Kokoro），并通过统一的 CLI、Python API 和 HTTP 服务器使用它们。

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | **[中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md)** | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

- **一个接口，多种引擎。** 选择一个引擎，并以相同的方式从 CLI（`ttsgen`）、Python（`libs.api`）或 HTTP 调用它——无需修改代码即可在云端和本地之间切换。
- **面向局域网的 API 服务器。** 运行 `ttssrv`，让其他机器通过 HTTP 进行合成（`POST /api/tts`）；模型在启动时加载一次，请求共享一个池。

### 引擎

| 引擎 | 离线 | 硬件 | 质量 | 最适合 |
|---|---|---|---|---|
| `gtts` | ❌ 在线 | CPU | ★★★★ | 100+ 种语言，零配置 |
| `pyttsx3` | ✅ | CPU | ★★ | 最小化安装（espeak / SAPI） |
| `pipertts` | ✅ | CPU | ★★★★ | 快速离线，50+ 种语言 |
| `silerotts` | ✅ | CPU | ★★★★ | 快速离线，俄语 |
| `kokorotts` | ✅ | CPU | ★★★★ | 快速离线，多语言 |
| `coquitts` | ✅ | CPU / **GPU** | ★★★★★ | 最佳质量，语音克隆 |
| `barktts` | ✅ | CPU / **GPU** | ★★★★★ | 情感、音乐、歌唱 |

`gtts`、`pyttsx3`、`pipertts`、`silerotts`、`kokorotts` 在 CPU 上运行良好。`coquitts` 和 `barktts` 也可以在 CPU 上运行，但速度较慢——建议使用支持 CUDA 的 GPU。

### 安装（pip）

```bash
pip install git+https://github.com/wachawo/text-to-speech.git
```

这只会安装带有轻量级依赖的 CLI。神经网络引擎（`pipertts`、`silerotts`、`coquitts`、`barktts`、`kokorotts`）会通过 `ttsgen --install <engine>` 按需拉取 `torch`/模型。

```bash
ttsgen "Hello world"                  # 播放（默认引擎：gtts，在线）
ttsgen "Hello world" -f out.mp3       # 保存到文件
ttsgen "Hello world" -e pyttsx3       # 完全离线
ttsgen "Hola amigo!"  -l es           # 选择语言
ttsgen --install coquitts             # 添加离线神经网络引擎 + 模型
ttsgen "Hello world" -e coquitts -f out.wav
ttsgen --list                         # 引擎 + 已安装的模型
ttsgen "Hello world" --stdout | ttsplay
```

Python：

```python
from libs.api import text_to_speech_file, text_to_speech_bytes

text_to_speech_file("Hello world", engine="gtts")
audio = text_to_speech_bytes("Hello world", engine="pipertts", language="en")
```

### 服务器（克隆）

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech
docker compose up --build -d                          # GPU（CUDA 12.1）
docker compose -f docker-compose-cpu.yml up --build -d # 仅 CPU
```

通过 HTTP 请求合成：

```bash
curl localhost:5000/api/health
curl localhost:5000/api/engines -H "Authorization: Bearer $TTS_TOKEN"
curl "localhost:5000/api/voices?engine=silerotts&language=ru" -H "Authorization: Bearer $TTS_TOKEN"

curl -X POST localhost:5000/api/tts \
  -H "Authorization: Bearer $TTS_TOKEN" -H "Content-Type: application/json" \
  -d '{"text":"Hello world","engine":"gtts"}' -o out.mp3
```

或者使用 `ttsapi`——与 `ttsgen` 的参数相同，但合成在服务器上运行（`TTS_URL` / `TTS_TOKEN` 来自配置）：

```bash
ttsapi "Hello world"
ttsapi -i long.txt --output play,file --file out.mp3
```

### 项目结构

```
text-to-speech/
├── ttsgen.py / ttsplay.py / ttsrec.py / ttsapi.py   # CLI 入口点
├── engines/        # 可插拔引擎（gtts、piper、silero、coqui、bark、kokoro 等）
├── libs/           # 核心：api.py、tools.py、playback.py、exceptions.py
├── install/        # `ttsgen --install <engine>` 安装器
├── ttssrv/         # Flask HTTP 服务器（Docker / python3 ttssrv/app1.py）
├── docker/         # gpu/ 和 cpu/ 构建（Dockerfile + requirements）
├── docs/           # 各引擎指南 + 翻译
└── tests/          # pytest 测试套件（引擎被 mock，无需模型/GPU）
```

### 开发者须知

```bash
pip install -e ".[dev]"
pytest                 # 测试 + 覆盖率
ruff check . && black .
```

通过放入带有两个函数的 `engines/<name>.py` 来添加引擎——它会自动出现在 CLI 和 API 中：

```python
def is_available() -> bool: ...                  # 依赖可导入？
def generate(text: str, config: dict) -> bytes:  # 返回 MP3/WAV 字节
    ...
```

各引擎的设置和完整的引擎指南位于 [`docs/`](docs/ENGINES.md)。

### 许可证

[MIT](LICENSE)
