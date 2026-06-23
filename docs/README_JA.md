## text-to-speech — 人気の TTS エンジンを 1 つの API で

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

人気のオンライン/オフライン TTS エンジン（gTTS、espeak、Piper、Silero、Coqui、Bark、Kokoro）をインストールし、1 つの CLI、Python API、HTTP サーバーから利用できます。

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | **[日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md)** | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

- **1 つのインターフェース、多数のエンジン。** エンジンを選び、CLI（`ttsgen`）、Python（`libs.api`）、HTTP のいずれからも同じ方法で呼び出せます。コードを変更せずにクラウドとローカルを切り替えられます。
- **LAN 向け API サーバー。** `ttssrv` を実行すれば、他のマシンが HTTP（`POST /api/tts`）経由で音声合成できます。モデルは起動時に一度だけ読み込まれ、リクエストはプールを共有します。

### エンジン

| エンジン | オフライン | ハードウェア | 品質 | 最適な用途 |
|---|---|---|---|---|
| `gtts` | ❌ オンライン | CPU | ★★★★ | 100 以上の言語、セットアップ不要 |
| `pyttsx3` | ✅ | CPU | ★★ | 最小インストール（espeak / SAPI） |
| `pipertts` | ✅ | CPU | ★★★★ | 高速オフライン、50 以上の言語 |
| `silerotts` | ✅ | CPU | ★★★★ | 高速オフライン、ロシア語 |
| `kokorotts` | ✅ | CPU | ★★★★ | 高速オフライン、多言語 |
| `coquitts` | ✅ | CPU / **GPU** | ★★★★★ | 最高品質、音声クローニング |
| `barktts` | ✅ | CPU / **GPU** | ★★★★★ | 感情、音楽、歌唱 |

`gtts`、`pyttsx3`、`pipertts`、`silerotts`、`kokorotts` は CPU で問題なく動作します。`coquitts` と `barktts` も CPU で動作しますが低速です。CUDA GPU の使用を推奨します。

### インストール（pip）

```bash
pip install git+https://github.com/wachawo/text-to-speech.git
```

これにより軽量な依存関係のみで CLI がインストールされます。ニューラルエンジン（`pipertts`、`silerotts`、`coquitts`、`barktts`、`kokorotts`）は、`ttsgen --install <engine>` を介して必要に応じて `torch`/モデルを取得します。

```bash
ttsgen "Hello world"                  # 再生（デフォルトエンジン: gtts、オンライン）
ttsgen "Hello world" -f out.mp3       # ファイルに保存
ttsgen "Hello world" -e pyttsx3       # 完全オフライン
ttsgen "Hola amigo!"  -l es           # 言語を選択
ttsgen --install coquitts             # オフラインのニューラルエンジン + モデルを追加
ttsgen "Hello world" -e coquitts -f out.wav
ttsgen --list                         # エンジン + インストール済みモデル
ttsgen "Hello world" --stdout | ttsplay
```

Python:

```python
from libs.api import text_to_speech_file, text_to_speech_bytes

text_to_speech_file("Hello world", engine="gtts")
audio = text_to_speech_bytes("Hello world", engine="pipertts", language="en")
```

### サーバー（clone）

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech
docker compose up --build -d                          # GPU (CUDA 12.1)
docker compose -f docker-compose-cpu.yml up --build -d # CPU のみ
```

HTTP 経由で音声合成をリクエスト:

```bash
curl localhost:5000/api/health
curl localhost:5000/api/engines -H "Authorization: Bearer $TTS_TOKEN"
curl "localhost:5000/api/voices?engine=silerotts&language=ru" -H "Authorization: Bearer $TTS_TOKEN"

curl -X POST localhost:5000/api/tts \
  -H "Authorization: Bearer $TTS_TOKEN" -H "Content-Type: application/json" \
  -d '{"text":"Hello world","engine":"gtts"}' -o out.mp3
```

または `ttsapi` を使用します。`ttsgen` と同じフラグですが、音声合成はサーバー上で実行されます（`TTS_URL` / `TTS_TOKEN` は設定から取得）:

```bash
ttsapi "Hello world"
ttsapi -i long.txt --output play,file --file out.mp3
```

### プロジェクト構成

```
text-to-speech/
├── ttsgen.py / ttsplay.py / ttsrec.py / ttsapi.py   # CLI エントリーポイント
├── engines/        # プラグイン可能なエンジン (gtts, piper, silero, coqui, bark, kokoro, …)
├── libs/           # コア: api.py, tools.py, playback.py, exceptions.py
├── install/        # `ttsgen --install <engine>` インストーラー
├── ttssrv/         # Flask HTTP サーバー (Docker / python3 ttssrv/app1.py)
├── docker/         # gpu/ と cpu/ のビルド (Dockerfile + requirements)
├── docs/           # エンジンごとのガイド + 翻訳
└── tests/          # pytest スイート (エンジンはモック、モデル/GPU 不要)
```

### 開発者向けノート

```bash
pip install -e ".[dev]"
pytest                 # テスト + カバレッジ
ruff check . && black .
```

2 つの関数を持つ `engines/<name>.py` を配置するだけでエンジンを追加できます。CLI と API に自動的に表示されます:

```python
def is_available() -> bool: ...                  # 依存関係をインポート可能か?
def generate(text: str, config: dict) -> bytes:  # MP3/WAV バイトを返す
    ...
```

エンジンごとのセットアップと完全なエンジンガイドは [`docs/`](docs/ENGINES.md) にあります。

### ライセンス

[MIT](LICENSE)
