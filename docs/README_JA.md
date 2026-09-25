# text-to-speech - TTSエンジンのための単一インターフェース

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | **[日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md)** | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

![Web UIのStudio画面](https://raw.githubusercontent.com/wachawo/text-to-speech/main/docs/images/studio.png)

`text-to-speech` を使えば、複数の音声合成エンジンを1つのインターフェースで扱えます。オンラインのgTTSから始めて、後からローカルのPiper、Silero、Coqui、Bark、Kokoroに切り替えることもできます - CLIコマンド、Pythonコード、HTTP連携を書き直す必要はありません。

このプロジェクトは、ローカルでの利用、自動化、そしてネットワーク上で自前のTTSサーバーを運用する用途に適しています。

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

`gtts`、`pyttsx3`、`pipertts`、`silerotts`、`kokorotts` はCPUで問題なく動作します。`coquitts` と `barktts` もGPUなしで動かせますが、合成は目に見えて遅くなります - これらにはCUDA対応のグラフィックカードを推奨します。

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
cp env.example .env                                   # 任意: トークン、エンジン、ポート

docker compose up --build -d                          # GPU / CUDA 12.1
docker compose -f docker-compose-cpu.yml up --build -d # CPUのみ
```

GPU版はCDI経由でグラフィックカードをコンテナに渡すため、ホストにはNVIDIA container toolkit（1.14以降）と、生成済みのCDI仕様が必要です。CDI仕様はドライバーを更新するたびに1回生成します。

```bash
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
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

モデル、音声、履歴:

```bash
# インストール済みと未インストールのモデル。`ttsgen --list` が表示するのと同じ表
curl localhost:5000/api/models \
  -H "Authorization: Bearer $TTS_TOKEN"

# coquitts用の音声サンプル（WAV）をアップロードする。以後この音声は "maria" になる
curl -X POST localhost:5000/api/voices \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -F file=@voice.wav -F name=maria -F engine=coquitts

curl "localhost:5000/api/voices?engine=coquitts" \
  -H "Authorization: Bearer $TTS_TOKEN"

curl "localhost:5000/api/voices/maria/audio?engine=coquitts&download=1" \
  -H "Authorization: Bearer $TTS_TOKEN" -o maria.wav

# レスポンス本文ではなく、サーバー側の履歴に合成する
curl -X POST localhost:5000/api/history \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hola mundo","engine":"coquitts","language":"es","voice":"maria"}'

curl "localhost:5000/api/history?limit=50&offset=0" \
  -H "Authorization: Bearer $TTS_TOKEN"

# 1件の音声。download=1 なしなら <audio> 向けにインラインで配信される
curl "localhost:5000/api/history/<id>/audio?download=1" \
  -H "Authorization: Bearer $TTS_TOKEN" -o tts.wav

curl -X DELETE localhost:5000/api/history/<id> \
  -H "Authorization: Bearer $TTS_TOKEN"
```

#### OpenAI互換API

同じサーバーはOpenAIのオーディオAPIにも応答します。そのため、`base_url` をこのサーバーに向け、bearerトークンをAPIキーとして渡せば、Open WebUI、SillyTavern、Home Assistant、公式SDKがそのまま使えます。

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

- `model` はエンジン名、またはデフォルトエンジンを指す `tts-1` / `tts-1-hd` / `gpt-4o-mini-tts` です。
- `voice` はエンジンの音声です。OpenAIの音声名（`alloy`、`nova` など）はエンジンのデフォルト音声を選びます。
- `response_format`: `mp3`（デフォルト）、`wav`、`pcm`、`opus`、`flac`、`aac`。エンジンはWAVまたはMP3を生成し、それ以外の形式は `ffmpeg` でトランスコードされます（Dockerイメージに同梱）。`speed`（0.25から4.0）も同じ方法で適用されます。
- `language` は拡張パラメータです。2文字の言語コード、または `zh-cn` のようなタグで、デフォルトは `TTS_LANGUAGE` です。
- `GET /v1/models` はインストール済みのエンジンと `tts-1` を一覧し、`GET /v1/audio/voices?model=<engine>` は1つのエンジンの音声を一覧します。

#### APIリファレンス

`TTS_TOKENS` が設定されている場合、`/api/health` を除くすべてのルートで `Authorization: Bearer <token>` が必要です。`/api/` 配下のエラーは `{"error": "...", "request_id": "..."}` の形式で、400 にはさらに理由を示す `message` が付きます。リクエストが検証に通らなかった場合は、問題のあるフィールドが示されます（`language: ...`）。`/v1/` 配下のエラーはOpenAIの形式です。

| メソッド | パス | 用途 |
| --- | --- | --- |
| GET | `/api/health` | 死活状態、`auth` フラグ、エンジン、プールとキューのサイズ。トークン不要。 |
| GET | `/api/engines` | 対応エンジン、インストール済みのエンジン、デフォルトのエンジン。 |
| GET | `/api/models` | エンジンごとのインストール済みと未インストールのモデル。`ttsgen --list` が表示する表。 |
| GET | `/api/voices?engine=&language=` | エンジンの音声。`coquitts` ではサイズ、サンプルレート、長さ付きのサンプル。 |
| POST | `/api/voices` | WAVサンプルをアップロードする（`file`、`name`、`engine=coquitts`）。 |
| GET | `/api/voices/<name>/audio?engine=&download=1` | サンプルを再生またはダウンロードする。 |
| DELETE | `/api/voices/<name>?engine=` | サンプルを削除する。 |
| POST, GET | `/api/tts` | `engine`、`language`、`voice` で `text` を合成する。`stream=true` なら準備でき次第チャンクをストリーミングする。 |
| POST | `/api/history` | レスポンス本文ではなく、サーバー側の履歴に合成する。 |
| GET | `/api/history?limit=&offset=` | 履歴の一覧。新しいものが先頭。 |
| GET | `/api/history/<id>` | 1件のメタデータ。 |
| GET | `/api/history/<id>/audio?download=1` | その項目の音声。インラインまたはダウンロード。 |
| DELETE | `/api/history/<id>` | 項目を削除する。 |
| POST | `/v1/audio/speech` | OpenAI互換の合成。上記を参照。 |
| GET | `/v1/models` | OpenAI互換のモデル一覧。 |
| GET | `/v1/audio/voices?model=` | 1つのエンジンの音声。 |

`language` は2文字のコード（`en`、`ru`）、または地域や文字体系を含むタグ（`zh-cn`、`pt_BR`、`en-gb`、`es-419`）です。タグは小文字にされ、`-` でつながれます。各エンジンはタグを自分の持つ言語に対応づけます。gtts は独自の表記（`zh-CN`。カナダのフランス語とヨーロッパのポルトガル語はないため、`fr-ca` と `pt-pt` は `fr` と `pt` になります）を受け取り、kokorotts は `en-gb` を英国式の音素変換器で読み上げ、xtts は中国語に `zh-cn` を受け取り、その他のエンジンは言語部分を使います（`pt-br` は `pt`）。エンジンが知らない言語は、そのエンジンのデフォルト言語（通常は英語）で読み上げられます（gtts は失敗します）。`TTS_LANGUAGE_STRICT=true` にすると、そのようなリクエストはエンジンの対応言語を列挙した 400 になります。厳格チェックの対象は `stream` なしの `/api/tts`、`/api/history`、`/v1/audio/speech` で、言語を列挙するすべてのエンジン、つまり pyttsx3 と、xtts 以外の多言語モデルまたは3文字の言語コード（`ewe`）のモデルを使う coquitts を除くすべてのエンジンです。

#### Web UI

どちらのcomposeファイルも `ttswww` を起動します。これはWeb UIを配信し、`/api/` を `ttssrv` にプロキシするnginxコンテナです。

```bash
docker compose up --build -d
xdg-open http://localhost:8080      # TTS_WWW_PORT。8080が使用中なら変更する
xdg-open https://localhost:8443     # TTS_WWW_TLS_PORT。自己署名証明書なので、一度だけ受け入れる
```

- **Studio** - テキストを入力し、エンジン / 言語 / 音声を選んで、生成、再生、保存します。すべての結果は履歴リストに入ります。
- **Voices** - `coquitts` の音声クローン用にWAVの音声サンプルをアップロードまたは録音し、再生、ダウンロード、削除します。
- **Models** - エンジンと、インストール済み / 未インストールのモデル。`ttsgen --list` と同じ表です。

ヘッダーの歯車アイコンは設定ダイアログを開きます。Studioのデフォルトのエンジン、言語、音声と、curlの例を表示するかどうかを設定でき、選択内容はブラウザに保存されます。Studioは現在のリクエストに対応する、そのままコピーできる `curl` コマンドを表示します。トークンは印字せず `$TTS_TOKEN` として参照されます。Voices画面ではマイクからサンプルを録音することもできますが、ブラウザがこれを許可するのは `https` または `localhost` 上だけです - LAN越しではhttpsポートでUIを開いてください。初回起動時に自己署名証明書が `./data/certs` に生成されます。同じ名前（`tts.crt`、`tts.key`）で本物の証明書をマウントすれば置き換えられます。

`TTS_TOKENS` が設定されていると、UIはサインイン画面で開き、そのトークンのいずれかを求めます。ブラウザはそれを保持し、すべてのリクエストと一緒に送信します。`TTS_TOKENS` がなければサインインはありません。

#### 設定

すべての設定は環境変数です。`env.example` にすべて記載されており、composeファイルの隣にある `.env` は自動的に読み込まれます。変更する可能性が高いもの:

| 変数 | デフォルト | 役割 |
| --- | --- | --- |
| `TTS_TOKENS` | 空 | カンマ区切りのbearerトークン。空なら認証はまったく行われない。 |
| `TTS_ENGINES` | 空 | 起動時にインストールしてウォームアップするエンジン。カンマ区切り（`coquitts,silerotts`）。 |
| `TTS_ENGINE` | `gtts` | リクエストでエンジンが指定されなかったときに使うエンジン。 |
| `TTS_LANGUAGE` | `en` | リクエストで言語が指定されなかったときに使う言語。 |
| `TTS_LANGUAGE_STRICT` | `false` | `true` にすると、エンジンが列挙していない言語に対して、デフォルト言語へのフォールバックではなく 400 を返す。 |
| `TTS_POOL_SIZE` | `1` | 全エンジン合計で同時に許可する合成呼び出しの数。`0` で上限とウォームアップを無効にする。 |
| `TTS_QUEUE_SIZE` | `8` | 空きスロットを待てる合成リクエストの数。それを超えると即座に503になる。 |
| `TTS_HISTORY_MAX` | `200` | 履歴に保持する件数。新しい項目が保存されると最も古いものが削除される。 |
| `TTS_MAX_SAMPLE_BYTES` | `16777216` | 音声サンプルのアップロード上限（16 MiB）。 |
| `TTS_MAX_SAMPLES` | `100` | サーバーに保持する音声サンプルの数。 |
| `TTS_MAX_BODY_BYTES` | `2097152` | JSONリクエスト本文の上限（2 MiB）。 |
| `TTS_STREAM_MAX_CHARS` | `200` | `stream=true` のチャンクサイズ。 |
| `CORS_ORIGINS` | `*` | `/api/*` で許可するオリジン。 |
| `TTS_PORT` | `5000` | `ttssrv` のポート。 |
| `TTS_WWW_PORT`, `TTS_WWW_TLS_PORT` | `8080`, `8443` | Web UIのhttpとhttpsのポート。 |
| `COQUITTS_MODEL`, `COQUITTS_SAMPLE` | `xtts_v2`, `default.wav` | Coquiのモデルとデフォルトの音声サンプル。 |
| `TZ` | `America/New_York` | ログと履歴のタイムスタンプのタイムゾーン。 |

Docker以外では、CLIとサーバーは同じキーを次の優先順位（強い順）で読み込みます: CLIフラグ、シェル環境、`./ttsgen.conf`、`~/.config/ttsgen.conf`、`./.env.local`、`./.env`。ファイルがシェルを上書きすることはなく、`.env` はカレントディレクトリからのみ読み込まれます。

`TTS_POOL_SIZE` を1より大きくすると、異なるエンジンが並列に合成できます。1つのエンジンの中では呼び出しは直列化されます。基盤となるモデルはスレッド間で安全に共有できないためです。

#### セキュリティ

- `TTS_TOKENS` を設定するまで認証はオフです。設定すると、`/api/health` を除くすべてのルートで `Authorization: Bearer <token>` が必要になり、Web UIはサインイン画面でトークンを求めます。
- APIはすべてのインターフェースで待ち受け、composeファイルは `TTS_PORT`、`TTS_WWW_PORT`、`TTS_WWW_TLS_PORT` をホストに公開します。共有ネットワークではトークンを設定するか、オーバーライドファイルでポートを `127.0.0.1` にバインドしてください。
- httpsリスナーは初回起動時に発行された自己署名証明書を使います。これはLAN向けです。インターネット上では、本物の証明書を持つ自前のリバースプロキシの背後にUIを置いてください。
- 音声サンプル、履歴、証明書は `./data` の下にあります。バックアップを取り、ビルドコンテキストから除外してください。

脆弱性はリポジトリのSecurityタブから報告してください。[SECURITY.md](https://github.com/wachawo/text-to-speech/blob/main/SECURITY.md) を参照。

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
├── www/            # Web UI: ビルド不要のVue 2、nginxで配信
├── nginx/          # nginxのメイン設定とttswww用のconf.dテンプレート
├── docker/         # GPU、CPU、Web UI向けのDockerビルド
├── docs/           # エンジンごとのドキュメントとREADMEの翻訳
└── tests/          # pytestのテスト、モデルのダウンロードもGPUも不要
```

### 開発

コントリビューションを歓迎します。[CONTRIBUTING.md](https://github.com/wachawo/text-to-speech/blob/main/CONTRIBUTING.md) にセットアップ、チェック、エンジンの追加方法が説明されています。開発用の依存関係をインストールするには:

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

各エンジンの詳細なパラメータと特性は [`docs/`](https://github.com/wachawo/text-to-speech/blob/main/docs/ENGINES.md) に記載されています。

### ライセンス

[MIT](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
