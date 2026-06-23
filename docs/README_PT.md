## text-to-speech — uma única interface para motores de TTS

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | **[Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md)** | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

> _Desculpe desde já: esta tradução foi feita com o Claude Code. Se você for falante nativo e notar algum erro, por favor me avise._

`text-to-speech` permite trabalhar com vários motores de síntese de fala através de uma única interface. Você pode começar com o gTTS online e depois mudar para Piper, Silero, Coqui, Bark ou Kokoro locais — sem reescrever seus comandos de CLI, seu código Python ou sua integração HTTP.

O projeto serve para uso local, automação e para executar seu próprio servidor de TTS na rede.

* **Uma única forma de trabalhar com diferentes motores.** Escolha o motor de que precisa e use-o através da CLI (`ttsgen`), da API Python (`libs.api`) ou da API HTTP.
* **Você pode trabalhar totalmente de forma local.** Piper, Silero, Coqui, Bark, Kokoro e `pyttsx3` rodam todos na sua própria máquina.
* **Está incluído um servidor HTTP pronto para usar.** O `ttssrv` carrega o modelo na inicialização e atende às solicitações de outras máquinas na sua rede local.

### Motores

| Motor       | Offline | Hardware      | Qualidade | Bom para                                        |
| ----------- | ------- | ------------- | --------- | ----------------------------------------------- |
| `gtts`      | ❌      | CPU           | ★★★★    | um início rápido e um grande número de idiomas  |
| `pyttsx3`   | ✅      | CPU           | ★★      | fala local simples via espeak ou SAPI           |
| `pipertts`  | ✅      | CPU           | ★★★★    | síntese offline rápida em muitos idiomas        |
| `silerotts` | ✅      | CPU           | ★★★★    | fala em russo e uma configuração local leve     |
| `kokorotts` | ✅      | CPU           | ★★★★    | síntese offline multilíngue                     |
| `coquitts`  | ✅      | CPU / **GPU** | ★★★★★   | vozes de alta qualidade e clonagem de voz       |
| `barktts`   | ✅      | CPU / **GPU** | ★★★★★   | fala expressiva, emoções, música e canto        |

`gtts`, `pyttsx3`, `pipertts`, `silerotts` e `kokorotts` funcionam bem em CPU. `coquitts` e `barktts` também podem rodar sem GPU, mas a síntese é notavelmente mais lenta — para eles é recomendada uma placa de vídeo compatível com CUDA.

### Instalação

A instalação base configura a CLI e suas dependências leves:

```bash
pip install git+https://github.com/wachawo/text-to-speech.git
```

Motores extras e seus modelos são instalados separadamente, quando você realmente precisa deles:

```bash
ttsgen --install coquitts
```

Exemplos de uso da CLI:

```bash
ttsgen "Hello world"                  # fala o texto com o gTTS
ttsgen "Hello world" -f out.mp3       # salva o resultado em um arquivo
ttsgen "Hello world" -e pyttsx3       # usa um motor local
ttsgen "Hola amigo!" -l es            # escolhe um idioma
ttsgen --install coquitts             # instala o Coqui TTS e seus modelos
ttsgen "Hello world" -e coquitts -f out.wav
ttsgen --list                         # mostra os motores e modelos disponíveis
ttsgen "Hello world" --stdout | ttsplay
```

`gtts` é o padrão, então um único comando é suficiente para a primeira execução. Para um trabalho totalmente local, escolha outro motor como `pyttsx3`, `pipertts` ou `silerotts`.
Minha escolha: `coquitts` pela qualidade e pela fala com som natural, `silerotts` pela geração rápida.

### API Python

Em Python, há funções para salvar o resultado em um arquivo ou obter o áudio como bytes:

```python
from libs.api import text_to_speech_file, text_to_speech_bytes

text_to_speech_file("Hello world", engine="gtts")

audio = text_to_speech_bytes(
    "Hello world",
    engine="pipertts",
    language="en",
)
```

### Servidor HTTP

É mais fácil executar o servidor com o Docker:

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech

docker compose up --build -d                          # GPU / CUDA 12.1
docker compose -f docker-compose-cpu.yml up --build -d # apenas CPU
```

Uma vez em execução, você pode verificar o status do servidor e enviar uma solicitação de síntese:

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

Para trabalhar com o servidor e testá-lo, há um cliente de CLI separado, o `ttsapi`. Ele tem as mesmas flags principais que o `ttsgen`, mas a síntese é executada no servidor. O endereço do servidor e o token são obtidos de `TTS_URL` e `TTS_TOKEN`.

```bash
ttsapi "Hello world"
ttsapi -i long.txt --output play,file --file out.mp3
```

### Estrutura do projeto

```text
text-to-speech/
├── ttsgen.py / ttsplay.py / ttsrec.py / ttsapi.py   # comandos da CLI
├── engines/        # motores: gTTS, Piper, Silero, Coqui, Bark, Kokoro e outros
├── libs/           # núcleo compartilhado: API, ferramentas, reprodução, exceções
├── install/        # instaladores para ttsgen --install <engine>
├── ttssrv/         # servidor HTTP Flask
├── docker/         # builds do Docker para GPU e CPU
├── docs/           # documentação por motor e traduções do README
└── tests/          # testes pytest, sem downloads de modelos e sem GPU
```

### Desenvolvimento

Para instalar as dependências de desenvolvimento:

```bash
pip install -e ".[dev]"
```

Verificações antes de fazer commit:

```bash
pytest
ruff check .
black .
```

Um novo motor é conectado através de um arquivo `engines/<name>.py`. Você só precisa implementar duas funções:

```python
def is_available() -> bool:
    ...

def generate(text: str, config: dict) -> bytes:
    ...
```

`is_available()` verifica se as dependências podem ser importadas, e `generate()` recebe o texto e a configuração e retorna o áudio como bytes MP3 ou WAV. Depois disso, o motor fica disponível na CLI e na API automaticamente.

Parâmetros detalhados e particularidades de cada motor estão descritos em [`docs/`](docs/ENGINES.md).

### Licença

[MIT](LICENSE)
