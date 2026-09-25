# text-to-speech - un'unica interfaccia per i motori TTS

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | **[Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md)** | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

![La schermata Studio dell'interfaccia web](https://raw.githubusercontent.com/wachawo/text-to-speech/main/docs/images/studio.png)

`text-to-speech` ti permette di lavorare con diversi motori di sintesi vocale attraverso un'unica interfaccia. Puoi iniziare con il gTTS online e passare in seguito a Piper, Silero, Coqui, Bark o Kokoro locali - senza riscrivere i comandi della CLI, il codice Python o l'integrazione HTTP.

Il progetto è adatto all'uso locale, all'automazione e all'esecuzione di un proprio server TTS sulla rete.

* **Un solo modo di lavorare con motori diversi.** Scegli il motore di cui hai bisogno e richiamalo tramite la CLI (`ttsgen`), l'API Python (`libs.api`) o l'API HTTP.
* **Puoi lavorare completamente in locale.** Piper, Silero, Coqui, Bark, Kokoro e `pyttsx3` funzionano tutti sulla tua macchina.
* **È incluso un server HTTP pronto all'uso.** `ttssrv` carica il modello all'avvio e serve le richieste da altre macchine sulla tua rete locale.

### Motori

| Motore      | Offline | Hardware      | Qualità | Adatto per                                       |
| ----------- | ------- | ------------- | ------- | ------------------------------------------------ |
| `gtts`      | ❌      | CPU           | ★★★★    | un avvio rapido e un gran numero di lingue       |
| `pyttsx3`   | ✅      | CPU           | ★★      | sintesi vocale locale semplice via espeak o SAPI |
| `pipertts`  | ✅      | CPU           | ★★★★    | sintesi offline veloce in molte lingue           |
| `silerotts` | ✅      | CPU           | ★★★★    | sintesi in russo e una configurazione locale leggera |
| `kokorotts` | ✅      | CPU           | ★★★★    | sintesi offline multilingue                      |
| `coquitts`  | ✅      | CPU / **GPU** | ★★★★★   | voci di alta qualità e clonazione vocale         |
| `barktts`   | ✅      | CPU / **GPU** | ★★★★★   | parlato espressivo, emozioni, musica e canto     |

`gtts`, `pyttsx3`, `pipertts`, `silerotts` e `kokorotts` funzionano bene su CPU. `coquitts` e `barktts` possono funzionare anche senza una GPU, ma la sintesi è notevolmente più lenta - per loro è consigliata una scheda grafica compatibile con CUDA.

### Installazione

L'installazione di base configura la CLI e le sue dipendenze leggere:

```bash
pip install git+https://github.com/wachawo/text-to-speech.git
```

Su Linux, il motore offline `pyttsx3` richiede anche il pacchetto di sistema `espeak`:

```bash
sudo apt install espeak espeak-data libespeak1
```

I motori aggiuntivi e i loro modelli si installano separatamente, quando ti servono davvero:

```bash
ttsgen --install coquitts
```

Esempi di utilizzo della CLI:

```bash
ttsgen "Hello world"                  # pronuncia il testo con gTTS
ttsgen "Hello world" -f out.mp3       # salva il risultato in un file
ttsgen "Hello world" -e pyttsx3       # usa un motore locale
ttsgen "Hola amigo!" -l es            # scegli una lingua
ttsgen --install coquitts             # installa Coqui TTS e i suoi modelli
ttsgen "Hello world" -e coquitts -f out.wav
ttsgen --list                         # mostra i motori e i modelli disponibili
ttsgen "Hello world" --stdout | ttsplay
```

`gtts` è il motore predefinito, quindi per la prima esecuzione basta un solo comando. Per lavorare completamente in locale, scegli un altro motore come `pyttsx3`, `pipertts` o `silerotts`.
La mia scelta: `coquitts` per la qualità e il parlato naturale, `silerotts` per la generazione veloce.

### API Python

In Python ci sono funzioni per salvare il risultato in un file o ottenere l'audio come byte:

```python
from libs.api import text_to_speech_file, text_to_speech_bytes

text_to_speech_file("Hello world", engine="gtts")

audio = text_to_speech_bytes(
    "Hello world",
    engine="pipertts",
    language="en",
)
```

### Server HTTP

Il modo più semplice per avviare il server è Docker:

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech
cp env.example .env                                   # opzionale: token, motori, porte

docker compose up --build -d                          # GPU / CUDA 12.1
docker compose -f docker-compose-cpu.yml up --build -d # solo CPU
```

La variante GPU passa la scheda tramite CDI, quindi l'host ha bisogno dell'NVIDIA Container Toolkit (1.14 o successivo) e di una specifica CDI generata, una volta per ogni aggiornamento del driver:

```bash
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
```

Una volta in esecuzione, puoi controllare lo stato del server e inviare una richiesta di sintesi:

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

Modelli, voci e cronologia:

```bash
# Cosa offre un motore: modelli, lingue e voci, letti senza caricare alcun modello
curl localhost:5000/api/engines/pipertts \
  -H "Authorization: Bearer $TTS_TOKEN"

# Sintetizzare con uno dei modelli elencati lì
curl -X POST localhost:5000/api/tts \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world","engine":"pipertts","language":"en-gb","model":"en_GB-alan-low"}' \
  -o out.wav

# Modelli installati e mancanti, la stessa tabella stampata da `ttsgen --list`
curl localhost:5000/api/models \
  -H "Authorization: Bearer $TTS_TOKEN"

# Carica un campione vocale per coquitts (WAV); la voce si chiama poi "maria"
curl -X POST localhost:5000/api/voices \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -F file=@voice.wav -F name=maria -F engine=coquitts

curl "localhost:5000/api/voices?engine=coquitts" \
  -H "Authorization: Bearer $TTS_TOKEN"

curl "localhost:5000/api/voices/maria/audio?engine=coquitts&download=1" \
  -H "Authorization: Bearer $TTS_TOKEN" -o maria.wav

# Sintetizza nella cronologia lato server invece che nel corpo della risposta
curl -X POST localhost:5000/api/history \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hola mundo","engine":"coquitts","language":"es","voice":"maria"}'

curl "localhost:5000/api/history?limit=50&offset=0" \
  -H "Authorization: Bearer $TTS_TOKEN"

# Audio di un elemento; senza download=1 viene servito inline per <audio>
curl "localhost:5000/api/history/<id>/audio?download=1" \
  -H "Authorization: Bearer $TTS_TOKEN" -o tts.wav

curl -X DELETE localhost:5000/api/history/<id> \
  -H "Authorization: Bearer $TTS_TOKEN"
```

#### API compatibile con OpenAI

Lo stesso server risponde anche all'API audio di OpenAI, quindi Open WebUI, SillyTavern, Home Assistant e gli SDK ufficiali funzionano con `base_url` che punta ad esso e il bearer token come chiave API:

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

- `model` è il nome di un motore, oppure `tts-1` / `tts-1-hd` / `gpt-4o-mini-tts` per il motore predefinito. Su `/v1` non si può scegliere un modello all'interno del motore: il motore usa il suo modello predefinito.
- `voice` è una voce del motore; i nomi delle voci OpenAI (`alloy`, `nova`, ...) selezionano quella predefinita del motore.
- `response_format`: `mp3` (predefinito), `wav`, `pcm`, `opus`, `flac`, `aac`. I motori producono WAV o MP3; tutto il resto viene transcodificato con `ffmpeg`, incluso nelle immagini Docker. `speed` (da 0.25 a 4.0) viene applicato allo stesso modo.
- `language` è un'estensione: un codice di due lettere o un tag come `zh-cn`, predefinito `TTS_LANGUAGE`.
- `GET /v1/models` elenca i motori installati più `tts-1`; `GET /v1/audio/voices?model=<engine>` elenca le voci di un motore.

#### Riferimento API

Ogni rotta tranne `/api/health` richiede `Authorization: Bearer <token>` quando `TTS_TOKENS` è impostata. Gli errori sotto `/api/` hanno la forma `{"error": "...", "request_id": "..."}`; una risposta 400 contiene anche `message` con il motivo, che indica i campi non validi quando la richiesta non supera la validazione (`language: ...`). Gli errori sotto `/v1/` usano il formato OpenAI.

| Metodo | Percorso | Scopo |
| --- | --- | --- |
| GET | `/api/health` | Liveness, flag `auth`, motori, dimensioni del pool e della coda. Nessun token necessario. |
| GET | `/api/engines` | Motori supportati, quelli installati e quello predefinito. |
| GET | `/api/engines/<engine>` | Modelli, lingue, elenco delle voci e formato di uscita di un motore, letti senza caricare alcun modello. |
| GET | `/api/models` | Modelli installati e mancanti per motore, la tabella stampata da `ttsgen --list`. |
| GET | `/api/voices?engine=&language=&model=` | Voci di un motore; per `coquitts` i campioni con dimensione, frequenza e durata. Con `model`, le voci di quel modello. |
| POST | `/api/voices` | Carica un campione WAV (`file`, `name`, `engine=coquitts`). |
| GET | `/api/voices/<name>/audio?engine=&download=1` | Riproduci o scarica un campione. |
| DELETE | `/api/voices/<name>?engine=` | Elimina un campione. |
| POST, GET | `/api/tts` | Sintetizza `text` con `engine`, `language`, `voice`, `model`; `stream=true` trasmette i blocchi man mano che sono pronti. |
| POST | `/api/history` | Sintetizza nella cronologia lato server invece che nel corpo della risposta. |
| GET | `/api/history?limit=&offset=` | Elenca gli elementi della cronologia, dal più recente. |
| GET | `/api/history/<id>` | Metadati di un elemento. |
| GET | `/api/history/<id>/audio?download=1` | L'audio dell'elemento, inline o come download. |
| DELETE | `/api/history/<id>` | Elimina un elemento. |
| POST | `/v1/audio/speech` | Sintesi compatibile con OpenAI, vedi sopra. |
| GET | `/v1/models` | Elenco dei modelli compatibile con OpenAI. |
| GET | `/v1/audio/voices?model=` | Voci di un motore. |

`language` è un codice di due lettere (`en`, `ru`) o un tag con regione o sistema di scrittura (`zh-cn`, `pt_BR`, `en-gb`, `es-419`), convertito in minuscolo e scritto con `-`. Ogni motore riconduce il tag a ciò che ha: gtts riceve la propria grafia (`zh-CN`; non ha francese canadese né portoghese europeo, quindi `fr-ca` e `pt-pt` diventano `fr` e `pt`), kokorotts pronuncia `en-gb` con il fonemizzatore britannico, xtts riceve `zh-cn` per il cinese e gli altri motori usano la parte della lingua (`pt-br` diventa `pt`). Una lingua che il motore non conosce viene pronunciata nella sua lingua predefinita, di solito l'inglese (gtts invece fallisce); con `TTS_LANGUAGE_STRICT=true` è un 400 che elenca le lingue del motore. Il controllo rigoroso vale per `/api/tts` senza `stream`, `/api/history` e `/v1/audio/speech`, e per tutti i motori che elencano le proprie lingue: tutti tranne pyttsx3 e coquitts con un modello multilingue diverso da xtts o con un modello il cui codice lingua ha tre lettere (`ewe`).

`model` sceglie un modello all'interno del motore su `/api/tts` e `/api/history`: una voce Piper (`en_GB-alan-low`), un file di modello Kokoro (`kokoro-v1.0.int8.onnx`), un modello Silero (`v3_1_ru`) o il nome di un modello Coqui (`tts_models/de/thorsten/vits`). `GET /api/engines/<engine>` li elenca in `models`, ciascuno con `languages`, `installed` e `default_for` (le lingue che lo usano quando la richiesta non indica un modello), insieme ai `languages` del motore, a `output_format`, a `max_text_length` e all'indicazione se ha un elenco di voci; non carica alcun modello, e un motore sconosciuto dà 404. Senza `model` il motore sceglie come prima; un id che il motore non elenca è un 400 che nomina quelli disponibili, e lo è anche `model` con `stream=true`, perché uno stream usa sempre il modello predefinito del motore. gtts, pyttsx3 e barktts non hanno modelli. Senza modello pipertts sceglie tra le voci installate: un tag con regione (`en-gb`) prende una voce di quella regione, e una lingua fuori dalla sua tabella integrata prende una voce installata di quella lingua invece di quella inglese; il suo elenco di lingue è quello delle voci installate.

#### Interfaccia web

Entrambi i file compose avviano anche `ttswww`, un container nginx che serve l'interfaccia web e inoltra `/api/` a `ttssrv`:

```bash
docker compose up --build -d
xdg-open http://localhost:8080      # TTS_WWW_PORT; cambiala se la 8080 è occupata
xdg-open https://localhost:8443     # TTS_WWW_TLS_PORT; certificato autofirmato, accettalo una volta
```

- **Studio** - digita il testo, scegli motore / lingua / voce, genera, ascolta, salva; ogni risultato finisce in un elenco cronologico.
- **Voices** - carica o registra campioni vocali WAV per la clonazione vocale con `coquitts`; riproducili, scaricali ed eliminali.
- **Models** - i motori e i modelli installati / mancanti, la stessa tabella di `ttsgen --list`.

L'ingranaggio nell'intestazione apre la finestra delle impostazioni: motore, lingua e voce predefiniti per lo Studio, e se mostrare l'esempio curl; le scelte vengono salvate nel browser. Lo Studio mostra un comando `curl` pronto da copiare per la richiesta corrente; fa riferimento al token come `$TTS_TOKEN` invece di stamparlo. La schermata Voices può anche registrare un campione dal microfono, cosa che i browser consentono solo su `https` o `localhost` - sulla LAN apri l'interfaccia tramite la porta https. Al primo avvio viene generato un certificato autofirmato in `./data/certs`; per sostituirlo monta un certificato reale con gli stessi nomi (`tts.crt`, `tts.key`).

Quando `TTS_TOKENS` è impostata, l'interfaccia si apre su una schermata di accesso e chiede uno di quei token; il browser lo conserva e lo invia con ogni richiesta. Senza `TTS_TOKENS` non c'è alcun accesso.

#### Configurazione

Ogni impostazione è una variabile d'ambiente; `env.example` le documenta tutte e `.env` accanto ai file compose viene letto automaticamente. Quelle che più probabilmente cambierai:

| Variabile | Predefinito | Cosa fa |
| --- | --- | --- |
| `TTS_TOKENS` | vuoto | Bearer token separati da virgola. Vuoto significa nessuna autenticazione. |
| `TTS_ENGINES` | vuoto | Motori da installare e preriscaldare all'avvio, separati da virgola (`coquitts,silerotts`). |
| `TTS_ENGINE` | `gtts` | Motore usato quando una richiesta non ne indica uno. |
| `TTS_LANGUAGE` | `en` | Lingua usata quando una richiesta non ne indica una. |
| `TTS_LANGUAGE_STRICT` | `false` | `true` risponde 400 a una lingua che il motore non elenca, invece del ripiego del motore sulla sua lingua predefinita. |
| `TTS_POOL_SIZE` | `1` | Chiamate di sintesi consentite contemporaneamente su tutti i motori; `0` rimuove il limite e il preriscaldamento. |
| `TTS_QUEUE_SIZE` | `8` | Richieste di sintesi che possono attendere uno slot libero; le altre ricevono subito 503. |
| `TTS_HISTORY_MAX` | `200` | Elementi conservati nella cronologia; i più vecchi vengono rimossi quando ne viene salvato uno nuovo. |
| `TTS_MAX_SAMPLE_BYTES` | `16777216` | Dimensione massima del caricamento di un campione vocale (16 MiB). |
| `TTS_MAX_SAMPLES` | `100` | Campioni vocali conservati sul server. |
| `TTS_MAX_BODY_BYTES` | `2097152` | Dimensione massima del corpo JSON della richiesta (2 MiB). |
| `TTS_STREAM_MAX_CHARS` | `200` | Dimensione dei blocchi per `stream=true`. |
| `CORS_ORIGINS` | `*` | Origini consentite per `/api/*`. |
| `TTS_PORT` | `5000` | Porta di `ttssrv`. |
| `TTS_WWW_PORT`, `TTS_WWW_TLS_PORT` | `8080`, `8443` | Porte http e https dell'interfaccia web. |
| `COQUITTS_MODEL`, `COQUITTS_SAMPLE` | `xtts_v2`, `default.wav` | Modello Coqui e campione vocale predefinito. |
| `TZ` | `America/New_York` | Fuso orario per i timestamp nei log e nella cronologia. |

Fuori da Docker le CLI e il server leggono le stesse chiavi da, in ordine di priorità: flag della CLI, ambiente della shell, `./ttsgen.conf`, `~/.config/ttsgen.conf`, `./.env.local`, `./.env`. Un file non sovrascrive mai la shell, e `.env` viene letto solo dalla directory corrente.

`TTS_POOL_SIZE` maggiore di 1 permette a motori diversi di sintetizzare in parallelo; all'interno di un singolo motore le chiamate sono serializzate, perché i modelli sottostanti non possono essere condivisi in sicurezza tra thread.

#### Sicurezza

- L'autenticazione è disattivata finché non imposti `TTS_TOKENS`. Da quel momento ogni rotta tranne `/api/health` richiede `Authorization: Bearer <token>`, e l'interfaccia web chiede il token in una schermata di accesso.
- L'API ascolta su tutte le interfacce e i file compose pubblicano `TTS_PORT`, `TTS_WWW_PORT` e `TTS_WWW_TLS_PORT` sull'host. Su una rete condivisa imposta un token, oppure vincola le porte a `127.0.0.1` in un file di override.
- Il listener https usa un certificato autofirmato creato al primo avvio; è pensato per una LAN. Su Internet metti l'interfaccia dietro il tuo reverse proxy con un certificato reale.
- Campioni vocali, cronologia e certificati risiedono sotto `./data`; fanne il backup e tienila fuori dal contesto di build.

Segnala una vulnerabilità tramite la scheda Security del repository, vedi [SECURITY.md](https://github.com/wachawo/text-to-speech/blob/main/SECURITY.md).

Per lavorare con il server e testarlo esiste un client CLI separato, `ttsapi`. Ha gli stessi flag principali di `ttsgen`, ma la sintesi viene eseguita sul server. L'indirizzo del server e il token vengono letti da `TTS_URL` e `TTS_TOKEN`.

```bash
ttsapi "Hello world"
ttsapi -i long.txt --output play,file --file out.mp3
```

### Struttura del progetto

```text
text-to-speech/
├── ttsgen.py / ttsplay.py / ttsrec.py / ttsapi.py   # comandi CLI
├── engines/        # motori: gTTS, Piper, Silero, Coqui, Bark, Kokoro e altri
├── libs/           # nucleo condiviso: API, strumenti, riproduzione, eccezioni
├── install/        # installatori per ttsgen --install <engine>
├── ttssrv/         # server HTTP Flask
├── www/            # interfaccia web: Vue 2 senza fase di build, servita da nginx
├── nginx/          # configurazione principale di nginx e il template conf.d per ttswww
├── docker/         # build Docker per GPU, CPU e interfaccia web
├── docs/           # documentazione per motore e traduzioni del README
└── tests/          # test pytest, nessun download di modelli e nessuna GPU
```

### Sviluppo

I contributi sono benvenuti; [CONTRIBUTING.md](https://github.com/wachawo/text-to-speech/blob/main/CONTRIBUTING.md) spiega la configurazione, i controlli e come si aggiunge un motore. Per installare le dipendenze di sviluppo:

```bash
pip install -e ".[dev]"
```

Controlli prima del commit:

```bash
pytest
ruff check .
black .
```

Un nuovo motore si collega tramite un file `engines/<name>.py`. Devi implementare solo due funzioni:

```python
def is_available() -> bool:
    ...

def generate(text: str, config: dict) -> bytes:
    ...
```

`is_available()` verifica che le dipendenze siano importabili, e `generate()` prende il testo e la configurazione e restituisce l'audio come byte MP3 o WAV. Dopodiché il motore diventa automaticamente disponibile nella CLI e nell'API.

I parametri dettagliati e le specificità di ciascun motore sono descritti in [`docs/`](https://github.com/wachawo/text-to-speech/blob/main/docs/ENGINES.md).

### Licenza

[MIT](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
