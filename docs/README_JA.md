## text-to-speech — TTSエンジンのための単一インターフェース

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

`text-to-speech` を使えば、複数の音声合成エンジンを1つのインターフェースで扱えます。オンラインのgTTSから始めて、後からローカルのPiper、Silero、Coqui、Bark、Kokoroに切り替えることもできます。しかもCLIコマンド、Pythonコード、HTTP連携を書き直す必要はありません。

このプロジェクトは、ローカルでの利用、自動化、そしてネットワーク上で自前のTTSサーバーを運用する用途に適しています。


[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | **[日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md)** | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

* **異なるエンジンを扱う1つの方法。** 必要なエンジンを選び、CLI（`ttsgen`）、Python API（`libs.api`）、またはHTTP API経由で呼び出します。
* **完全にローカルで動作させられます。** Piper、Silero、Coqui、Bark、Kokoro、そして `pyttsx3` はすべて自分のマシン上で動きます。
* **すぐに使えるHTTPサーバーが含まれています。** `ttssrv` は起動時にモデルを読み込み、ローカルネットワーク上の他のマシンからのリクエストに応えます。

### エンジン

| エンジン     | オフライン | ハードウェア  | 品質    | 適した用途                                     |
| ----------- | ------- | ------------- | ------- | ---------------------------------------------- |
| `gtts`      | ❌      | CPU           | ★★★★    | 手早く始めること、そして多数の言語             |
| `pyttsx3`   | ✅      | CPU           | ★★      | espeakやSAPIによるシンプルなローカル音声        |
| `pipertts`  | ✅      | CPU           | ★★★★    | 多言語での高速なオフライン合成                 |
| `silerotts` | ✅      | CPU           | ★★★★    | ロシア語の音声と軽量なローカル構成             |
| `kokorotts` | ✅      | CPU           | ★★★★    | 多言語のオフライン合成                         |
| `coquitts`  | ✅      | CPU / **GPU** | ★★★★★   | 高品質な音声と音声クローン                     |
| `barktts`   | ✅      | CPU / **GPU** | ★★★★★   | 表現豊かな音声、感情、音楽、歌唱               |

`gtts`、`pyttsx3`、`pipertts`、`silerotts`、`kokorotts` はCPUで問題なく動作します。`coquitts` と `barktts` もGPUなしで動かせますが、合成は目に見えて遅くなります。これらにはCUDA対応のグラフィックカードを推奨します。

### インストール

基本インストールでは、CLIとその軽量な依存関係がセットアップされます。

```bash
pip install git+https://github.com/wachawo/text-to-speech.git
```

Linuxでは、オフラインの `pyttsx3` エンジンを使うには、システムの `espeak` パッケージも必要です。

```bash
sudo apt install espeak espeak-data libespeak1
```

追加のエンジンとそのモデルは、実際に必要になったときに別途インストールします。

```bash
ttsgen --install coquitts
```

CLIの使用例:

```bash
ttsgen "Hello world"                  # gTTSでテキストを読み上げる
ttsgen "Hello world" -f out.mp3       # 結果をファイルに保存する
ttsgen "Hello world" -e pyttsx3       # ローカルエンジンを使う
ttsgen "Hola amigo!" -l es            # 言語を選ぶ
ttsgen --install coquitts             # Coqui TTSとそのモデルをインストールする
ttsgen "Hello world" -e coquitts -f out.wav
ttsgen --list                         # 利用可能なエンジンとモデルを表示する
ttsgen "Hello world" --stdout | ttsplay
```

`gtts` がデフォルトなので、最初の実行は1つのコマンドで十分です。完全にローカルで作業するには、`pyttsx3`、`pipertts`、`silerotts` などの別のエンジンを選んでください。
私のおすすめ: 品質と自然な音声には `coquitts`、高速な生成には `silerotts`。

### Python API

Pythonには、結果をファイルに保存する関数や、音声をバイト列として取得する関数があります。

```python
from libs.api import text_to_speech_file, text_to_speech_bytes

text_to_speech_file("Hello world", engine="gtts")

audio = text_to_speech_bytes(
    "Hello world",
    engine="pipertts",
    language="en",
)
```

### HTTPサーバー

サーバーはDockerで実行するのが簡単です。

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech

docker compose up --build -d                          # GPU / CUDA 12.1
docker compose -f docker-compose-cpu.yml up --build -d # CPUのみ
```

起動したら、サーバーの状態を確認したり、合成リクエストを送ったりできます。

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

サーバーを扱ったりテストしたりするために、専用のCLIクライアント `ttsapi` があります。`ttsgen` と同じ主要なフラグを備えていますが、合成はサーバー上で実行されます。サーバーのアドレスとトークンは `TTS_URL` と `TTS_TOKEN` から取得されます。

```bash
ttsapi "Hello world"
ttsapi -i long.txt --output play,file --file out.mp3
```

### プロジェクト構成

```text
text-to-speech/
├── ttsgen.py / ttsplay.py / ttsrec.py / ttsapi.py   # CLIコマンド
├── engines/        # エンジン: gTTS、Piper、Silero、Coqui、Bark、Kokoroなど
├── libs/           # 共有コア: API、ツール、再生、例外
├── install/        # ttsgen --install <engine> 用のインストーラー
├── ttssrv/         # Flask HTTPサーバー
├── docker/         # GPUとCPU向けのDockerビルド
├── docs/           # エンジンごとのドキュメントとREADMEの翻訳
└── tests/          # pytestのテスト、モデルのダウンロードもGPUも不要
```

### 開発

開発用の依存関係をインストールするには:

```bash
pip install -e ".[dev]"
```

コミット前のチェック:

```bash
pytest
ruff check .
black .
```

新しいエンジンは `engines/<name>.py` ファイルを通じて組み込まれます。実装する必要があるのは2つの関数だけです。

```python
def is_available() -> bool:
    ...

def generate(text: str, config: dict) -> bytes:
    ...
```

`is_available()` は依存関係がインポート可能かを確認し、`generate()` はテキストと設定を受け取り、音声をMP3またはWAVのバイト列として返します。その後、エンジンはCLIとAPIで自動的に利用可能になります。

各エンジンの詳細なパラメータと特性は [`docs/`](ENGINES.md) に記載されています。

### ライセンス

[MIT](../LICENSE)
