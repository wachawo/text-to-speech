# text-to-speech - uma única interface para motores de TTS

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | **[Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md)** | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

![A tela Studio da interface web](https://raw.githubusercontent.com/wachawo/text-to-speech/main/docs/images/studio.png)

`text-to-speech` permite trabalhar com vários motores de síntese de fala através de uma única interface. Você pode começar com o gTTS online e depois mudar para Piper, Silero, Coqui, Bark ou Kokoro locais - sem reescrever seus comandos de CLI, seu código Python ou sua integração HTTP.

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

`gtts`, `pyttsx3`, `pipertts`, `silerotts` e `kokorotts` funcionam bem em CPU. `coquitts` e `barktts` também podem rodar sem GPU, mas a síntese é notavelmente mais lenta - para eles é recomendada uma placa de vídeo compatível com CUDA.

### Instalação

A instalação base configura a CLI e suas dependências leves:

```bash
pip install git+https://github.com/wachawo/text-to-speech.git
```

No Linux, o motor offline `pyttsx3` também precisa do pacote de sistema `espeak`:

```bash
sudo apt install espeak espeak-data libespeak1
```

Os motores extras e seus modelos são instalados separadamente, quando você realmente precisa deles:

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

`gtts` é o padrão, então um único comando basta para a primeira execução. Para trabalhar totalmente de forma local, escolha outro motor como `pyttsx3`, `pipertts` ou `silerotts`.
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
cp env.example .env                                   # opcional: tokens, motores, portas

docker compose up --build -d                          # GPU / CUDA 12.1
docker compose -f docker-compose-cpu.yml up --build -d # apenas CPU
```

A variante GPU passa a placa pelo CDI, então o host precisa do NVIDIA container toolkit (1.14 ou mais recente) e de uma especificação CDI gerada, uma vez a cada atualização do driver:

```bash
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
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

Modelos, vozes e histórico:

```bash
# O que um motor oferece: modelos, idiomas e vozes, lidos sem carregar nenhum modelo
curl localhost:5000/api/engines/pipertts \
  -H "Authorization: Bearer $TTS_TOKEN"

# Sintetizar com um dos modelos listados ali
curl -X POST localhost:5000/api/tts \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world","engine":"pipertts","language":"en-gb","model":"en_GB-alan-low"}' \
  -o out.wav

# Modelos instalados e ausentes, a mesma tabela que `ttsgen --list` imprime
curl localhost:5000/api/models \
  -H "Authorization: Bearer $TTS_TOKEN"

# Envia uma amostra de voz para o coquitts (WAV); a voz passa a se chamar "maria"
curl -X POST localhost:5000/api/voices \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -F file=@voice.wav -F name=maria -F engine=coquitts

curl "localhost:5000/api/voices?engine=coquitts" \
  -H "Authorization: Bearer $TTS_TOKEN"

curl "localhost:5000/api/voices/maria/audio?engine=coquitts&download=1" \
  -H "Authorization: Bearer $TTS_TOKEN" -o maria.wav

# Sintetiza para o histórico do servidor em vez do corpo da resposta
curl -X POST localhost:5000/api/history \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hola mundo","engine":"coquitts","language":"es","voice":"maria"}'

curl "localhost:5000/api/history?limit=50&offset=0" \
  -H "Authorization: Bearer $TTS_TOKEN"

# Áudio de um item; sem download=1 ele é servido inline para <audio>
curl "localhost:5000/api/history/<id>/audio?download=1" \
  -H "Authorization: Bearer $TTS_TOKEN" -o tts.wav

curl -X DELETE localhost:5000/api/history/<id> \
  -H "Authorization: Bearer $TTS_TOKEN"
```

#### API compatível com OpenAI

O mesmo servidor também responde à API de áudio da OpenAI, então Open WebUI, SillyTavern, Home Assistant e os SDKs oficiais funcionam com `base_url` apontando para ele e o token bearer como chave de API:

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

- `model` é o nome de um motor, ou `tts-1` / `tts-1-hd` / `gpt-4o-mini-tts` para o motor padrão. Em `/v1` não há escolha de modelo dentro do motor: o motor usa o seu modelo padrão.
- `voice` é uma voz do motor; os nomes de voz da OpenAI (`alloy`, `nova`, ...) selecionam a voz padrão do motor.
- `response_format`: `mp3` (padrão), `wav`, `pcm`, `opus`, `flac`, `aac`. Os motores produzem WAV ou MP3; qualquer outro formato é transcodificado com `ffmpeg`, que as imagens Docker incluem. `speed` (de 0.25 a 4.0) é aplicado da mesma forma.
- `language` é uma extensão: um código de duas letras ou uma tag como `zh-cn`, padrão `TTS_LANGUAGE`.
- `GET /v1/models` lista os motores instalados mais `tts-1`; `GET /v1/audio/voices?model=<engine>` lista as vozes de um motor.

#### Referência da API

Toda rota exceto `/api/health` exige `Authorization: Bearer <token>` quando `TTS_TOKENS` está definido. Os erros em `/api/` têm a forma `{"error": "...", "request_id": "..."}`; uma resposta 400 traz também `message` com o motivo, que nomeia os campos com falha quando a solicitação não passa na validação (`language: ...`). Os erros em `/v1/` usam o formato da OpenAI.

| Método | Caminho | Propósito |
| --- | --- | --- |
| GET | `/api/health` | Liveness, flag `auth`, motores, tamanhos do pool e da fila. Não precisa de token. |
| GET | `/api/engines` | Motores suportados, os instalados e o padrão. |
| GET | `/api/engines/<engine>` | Modelos, idiomas, lista de vozes e formato de saída de um motor, lidos sem carregar nenhum modelo. |
| GET | `/api/models` | Modelos instalados e ausentes por motor, a tabela que `ttsgen --list` imprime. |
| GET | `/api/voices?engine=&language=&model=` | Vozes de um motor; para `coquitts`, as amostras com tamanho, taxa e duração. Com `model`, as vozes desse modelo. |
| POST | `/api/voices` | Envia uma amostra WAV (`file`, `name`, `engine=coquitts`). |
| GET | `/api/voices/<name>/audio?engine=&download=1` | Reproduz ou baixa uma amostra. |
| DELETE | `/api/voices/<name>?engine=` | Exclui uma amostra. |
| POST, GET | `/api/tts` | Sintetiza `text` com `engine`, `language`, `voice`, `model`; `stream=true` transmite os trechos conforme ficam prontos. |
| POST | `/api/history` | Sintetiza para o histórico do servidor em vez do corpo da resposta. |
| GET | `/api/history?limit=&offset=` | Lista os itens do histórico, os mais recentes primeiro. |
| GET | `/api/history/<id>` | Metadados de um item. |
| GET | `/api/history/<id>/audio?download=1` | O áudio do item, inline ou como download. |
| DELETE | `/api/history/<id>` | Exclui um item. |
| POST | `/v1/audio/speech` | Síntese compatível com OpenAI, veja acima. |
| GET | `/v1/models` | Lista de modelos compatível com OpenAI. |
| GET | `/v1/audio/voices?model=` | Vozes de um motor. |

`language` é um código de duas letras (`en`, `ru`) ou uma tag com região ou escrita (`zh-cn`, `pt_BR`, `en-gb`, `es-419`), convertida para minúsculas e escrita com `-`. Cada motor converte a tag no que tem: o gtts recebe a própria grafia (`zh-CN`; ele não tem francês canadense nem português europeu, então `fr-ca` e `pt-pt` viram `fr` e `pt`), o kokorotts fala `en-gb` com o fonemizador britânico, o xtts recebe `zh-cn` para chinês e os demais motores usam a parte do idioma (`pt-br` vira `pt`). Um idioma que o motor não conhece é falado no idioma padrão dele, normalmente inglês (o gtts falha em vez disso); com `TTS_LANGUAGE_STRICT=true` é um 400 que lista os idiomas do motor. A verificação estrita vale para `/api/tts` sem `stream`, `/api/history` e `/v1/audio/speech`, e para todos os motores que listam seus idiomas: todos exceto o pyttsx3, o pipertts sem nenhuma voz instalada e o coquitts com um modelo multilíngue que não seja o xtts ou com um modelo cujo código de idioma tem três letras (`ewe`).

`model` escolhe um modelo dentro do motor em `/api/tts` e `/api/history`: uma voz do Piper (`en_GB-alan-low`), um arquivo de modelo do Kokoro (`kokoro-v1.0.int8.onnx`), um modelo do Silero (`v3_1_ru`) ou o nome de um modelo do Coqui (`tts_models/de/thorsten/vits`). `GET /api/engines/<engine>` os lista em `models`, cada um com seus `languages`, `installed` e `default_for` (os idiomas que o usam quando a requisição não indica modelo), junto com os `languages` do motor, `output_format`, `max_text_length` e se ele tem lista de vozes; nenhum modelo é carregado, e um motor desconhecido dá 404. Sem `model` o motor escolhe como antes; um id que o motor não lista é um 400 que nomeia os que ele tem, assim como `model` com `stream=true`, porque um stream sempre usa o modelo padrão do motor. O gtts, o pyttsx3 e o barktts não têm modelos. Sem modelo, o pipertts escolhe entre as vozes instaladas: uma tag com região (`en-gb`) pega uma voz dessa região, e um idioma fora da tabela embutida pega uma voz instalada desse idioma em vez da inglesa; a lista de idiomas dele são os idiomas das vozes instaladas.

#### Interface web

Ambos os arquivos compose também iniciam o `ttswww`, um contêiner nginx que serve a interface web e encaminha `/api/` para o `ttssrv`:

```bash
docker compose up --build -d
xdg-open http://localhost:8080      # TTS_WWW_PORT; altere se a 8080 estiver ocupada
xdg-open https://localhost:8443     # TTS_WWW_TLS_PORT; certificado autoassinado, aceite-o uma vez
```

- **Studio** - digite o texto, escolha motor / idioma / voz, gere, ouça, salve; cada resultado vai para uma lista de histórico.
- **Voices** - envie ou grave amostras de voz WAV para a clonagem de voz do `coquitts`; reproduza, baixe e exclua.
- **Models** - os motores e os modelos instalados / ausentes, a mesma tabela que `ttsgen --list`.

A engrenagem no cabeçalho abre o diálogo de configurações: motor, idioma e voz padrão do Studio, e se o exemplo de curl é exibido; as escolhas ficam armazenadas no navegador. O Studio mostra um comando `curl` pronto para copiar para a solicitação atual; ele referencia o token como `$TTS_TOKEN` em vez de imprimi-lo. A tela Voices também pode gravar uma amostra pelo microfone, o que os navegadores permitem apenas em `https` ou `localhost` - na LAN, abra a interface pela porta https. Um certificado autoassinado é gerado em `./data/certs` na primeira inicialização; monte um certificado real com os mesmos nomes (`tts.crt`, `tts.key`) para substituí-lo.

Quando `TTS_TOKENS` está definido, a interface abre em uma tela de login e pede um desses tokens; o navegador o guarda e o envia com cada solicitação. Sem `TTS_TOKENS` não há login.

#### Configuração

Toda configuração é uma variável de ambiente; `env.example` documenta todas elas e o `.env` ao lado dos arquivos compose é lido automaticamente. As que você provavelmente vai alterar:

| Variável | Padrão | O que faz |
| --- | --- | --- |
| `TTS_TOKENS` | vazio | Tokens bearer separados por vírgula. Vazio significa nenhuma autenticação. |
| `TTS_ENGINES` | vazio | Motores a instalar e aquecer na inicialização, separados por vírgula (`coquitts,silerotts`). |
| `TTS_ENGINE` | `gtts` | Motor usado quando a solicitação não indica nenhum. |
| `TTS_LANGUAGE` | `en` | Idioma usado quando a solicitação não indica nenhum. |
| `TTS_LANGUAGE_STRICT` | `false` | `true` responde 400 a um idioma que o motor não lista, em vez de o motor recorrer ao idioma padrão. |
| `TTS_MODEL_CACHE_SIZE` | `2` | Modelos que coquitts e kokorotts mantêm carregados ao mesmo tempo; uma solicitação de mais um descarta o carregado primeiro. |
| `TTS_POOL_SIZE` | `1` | Chamadas de síntese permitidas ao mesmo tempo entre todos os motores; `0` remove o limite e o aquecimento. |
| `TTS_QUEUE_SIZE` | `8` | Solicitações de síntese que podem esperar por uma vaga livre; as demais recebem 503 imediatamente. |
| `TTS_HISTORY_MAX` | `200` | Itens mantidos no histórico; os mais antigos são removidos quando um novo é salvo. |
| `TTS_MAX_SAMPLE_BYTES` | `16777216` | Maior envio de amostra de voz (16 MiB). |
| `TTS_MAX_SAMPLES` | `100` | Amostras de voz mantidas no servidor. |
| `TTS_MAX_BODY_BYTES` | `2097152` | Maior corpo JSON de solicitação (2 MiB). |
| `TTS_STREAM_MAX_CHARS` | `200` | Tamanho do trecho para `stream=true`. |
| `CORS_ORIGINS` | `*` | Origens permitidas para `/api/*`. |
| `TTS_PORT` | `5000` | Porta do `ttssrv`. |
| `TTS_WWW_PORT`, `TTS_WWW_TLS_PORT` | `8080`, `8443` | Portas http e https da interface web. |
| `COQUITTS_MODEL`, `COQUITTS_SAMPLE` | `xtts_v2`, `default.wav` | Modelo do Coqui e amostra de voz padrão. |
| `TZ` | `America/New_York` | Fuso horário para os carimbos de tempo nos logs e no histórico. |

Fora do Docker, as CLIs e o servidor leem as mesmas chaves de, da maior para a menor prioridade: flags da CLI, o ambiente do shell, `./ttsgen.conf`, `~/.config/ttsgen.conf`, `./.env.local`, `./.env`. Um arquivo nunca sobrescreve o shell, e o `.env` é lido apenas do diretório atual.

Um `TTS_POOL_SIZE` acima de 1 permite que motores diferentes sintetizem em paralelo; dentro de um mesmo motor as chamadas são serializadas, porque os modelos subjacentes não podem ser compartilhados entre threads com segurança.

#### Segurança

- A autenticação fica desligada até você definir `TTS_TOKENS`. A partir daí, toda rota exceto `/api/health` exige `Authorization: Bearer <token>`, e a interface web pede o token em uma tela de login.
- A API escuta em todas as interfaces e os arquivos compose publicam `TTS_PORT`, `TTS_WWW_PORT` e `TTS_WWW_TLS_PORT` no host. Em uma rede compartilhada, defina um token ou vincule as portas a `127.0.0.1` em um arquivo de override.
- O listener https usa um certificado autoassinado gerado na primeira inicialização; ele é destinado a uma LAN. Na internet, coloque a interface atrás do seu próprio proxy reverso com um certificado real.
- Amostras de voz, histórico e certificados ficam em `./data`; faça backup e mantenha-o fora do contexto de build.

Relate uma vulnerabilidade pela aba Security do repositório, veja [SECURITY.md](https://github.com/wachawo/text-to-speech/blob/main/SECURITY.md).

Para trabalhar com o servidor e testá-lo há um cliente de CLI separado, o `ttsapi`. Ele tem as mesmas flags principais do `ttsgen`, mas a síntese roda no servidor. O endereço do servidor e o token são lidos de `TTS_URL` e `TTS_TOKEN`.

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
├── www/            # interface web: Vue 2 sem etapa de build, servida pelo nginx
├── nginx/          # configuração principal do nginx e o template conf.d para o ttswww
├── docker/         # builds Docker para GPU, CPU e a interface web
├── docs/           # documentação por motor e traduções do README
└── tests/          # testes pytest, sem download de modelos e sem GPU
```

### Desenvolvimento

Contribuições são bem-vindas; [CONTRIBUTING.md](https://github.com/wachawo/text-to-speech/blob/main/CONTRIBUTING.md) explica a configuração, as verificações e como um motor é adicionado. Para instalar as dependências de desenvolvimento:

```bash
pip install -e ".[dev]"
```

Verificações antes do commit:

```bash
pytest
ruff check .
black .
```

Um novo motor é integrado por meio de um arquivo `engines/<name>.py`. Você só precisa implementar duas funções:

```python
def is_available() -> bool:
    ...

def generate(text: str, config: dict) -> bytes:
    ...
```

`is_available()` verifica se as dependências podem ser importadas, e `generate()` recebe o texto e a configuração e retorna o áudio como bytes MP3 ou WAV. Depois disso, o motor fica disponível automaticamente na CLI e na API.

Os parâmetros detalhados e as particularidades de cada motor estão descritos em [`docs/`](https://github.com/wachawo/text-to-speech/blob/main/docs/ENGINES.md).

### Licença

[MIT](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
