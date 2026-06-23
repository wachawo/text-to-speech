## text-to-speech — motores de TTS populares por trás de uma única API

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

Instale motores de TTS online/offline populares (gTTS, espeak, Piper, Silero, Coqui, Bark, Kokoro) e use-os através de uma única CLI, API Python e servidor HTTP.

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | **[Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md)** | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

- **Uma interface, vários motores.** Escolha um motor e chame-o da mesma forma a partir da CLI (`ttsgen`), do Python (`libs.api`) ou via HTTP — alterne entre nuvem e local sem mudar o código.
- **Servidor de API para a sua LAN.** Execute `ttssrv` para que outras máquinas sintetizem por HTTP (`POST /api/tts`); o modelo é carregado uma vez na inicialização e as requisições compartilham um pool.

### Motores

| Motor | Offline | Hardware | Qualidade | Melhor para |
|---|---|---|---|---|
| `gtts` | ❌ online | CPU | ★★★★ | 100+ idiomas, sem configuração |
| `pyttsx3` | ✅ | CPU | ★★ | instalação mínima (espeak / SAPI) |
| `pipertts` | ✅ | CPU | ★★★★ | rápido offline, 50+ idiomas |
| `silerotts` | ✅ | CPU | ★★★★ | rápido offline, russo |
| `kokorotts` | ✅ | CPU | ★★★★ | rápido offline, multilíngue |
| `coquitts` | ✅ | CPU / **GPU** | ★★★★★ | melhor qualidade, clonagem de voz |
| `barktts` | ✅ | CPU / **GPU** | ★★★★★ | emoções, música, canto |

`gtts`, `pyttsx3`, `pipertts`, `silerotts`, `kokorotts` funcionam bem em CPU. `coquitts` e `barktts` também funcionam em CPU, mas são lentos — recomenda-se uma GPU CUDA.

### Instalação (pip)

```bash
pip install git+https://github.com/wachawo/text-to-speech.git
```

Isso instala a CLI apenas com dependências leves. Os motores neurais (`pipertts`, `silerotts`, `coquitts`, `barktts`, `kokorotts`) baixam `torch`/modelos sob demanda via `ttsgen --install <engine>`.

```bash
ttsgen "Hello world"                  # reproduzir (motor padrão: gtts, online)
ttsgen "Hello world" -f out.mp3       # salvar em um arquivo
ttsgen "Hello world" -e pyttsx3       # totalmente offline
ttsgen "Hola amigo!"  -l es           # escolher o idioma
ttsgen --install coquitts             # adicionar um motor neural offline + modelos
ttsgen "Hello world" -e coquitts -f out.wav
ttsgen --list                         # motores + modelos instalados
ttsgen "Hello world" --stdout | ttsplay
```

Python:

```python
from libs.api import text_to_speech_file, text_to_speech_bytes

text_to_speech_file("Hello world", engine="gtts")
audio = text_to_speech_bytes("Hello world", engine="pipertts", language="en")
```

### Servidor (clone)

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech
docker compose up --build -d                          # GPU (CUDA 12.1)
docker compose -f docker-compose-cpu.yml up --build -d # apenas CPU
```

Solicite a síntese por HTTP:

```bash
curl localhost:5000/api/health
curl localhost:5000/api/engines -H "Authorization: Bearer $TTS_TOKEN"
curl "localhost:5000/api/voices?engine=silerotts&language=ru" -H "Authorization: Bearer $TTS_TOKEN"

curl -X POST localhost:5000/api/tts \
  -H "Authorization: Bearer $TTS_TOKEN" -H "Content-Type: application/json" \
  -d '{"text":"Hello world","engine":"gtts"}' -o out.mp3
```

Ou use `ttsapi` — os mesmos parâmetros que `ttsgen`, mas a síntese roda no servidor (`TTS_URL` / `TTS_TOKEN` da configuração):

```bash
ttsapi "Hello world"
ttsapi -i long.txt --output play,file --file out.mp3
```

### Estrutura do projeto

```
text-to-speech/
├── ttsgen.py / ttsplay.py / ttsrec.py / ttsapi.py   # pontos de entrada da CLI
├── engines/        # motores plugáveis (gtts, piper, silero, coqui, bark, kokoro, …)
├── libs/           # núcleo: api.py, tools.py, playback.py, exceptions.py
├── install/        # instaladores `ttsgen --install <engine>`
├── ttssrv/         # servidor HTTP Flask (Docker / python3 ttssrv/app1.py)
├── docker/         # builds gpu/ e cpu/ (Dockerfile + requirements)
├── docs/           # guias por motor + traduções
└── tests/          # suíte pytest (motores mockados, sem necessidade de modelos/GPU)
```

### Notas para desenvolvedores

```bash
pip install -e ".[dev]"
pytest                 # testes + cobertura
ruff check . && black .
```

Adicione um motor colocando `engines/<name>.py` com duas funções — ele aparece na CLI e na API automaticamente:

```python
def is_available() -> bool: ...                  # dependências importáveis?
def generate(text: str, config: dict) -> bytes:  # retorna bytes MP3/WAV
    ...
```

A configuração por motor e o guia completo dos motores ficam em [`docs/`](docs/ENGINES.md).

### Licença

[MIT](LICENSE)
