## text-to-speech — un'unica interfaccia per i motori TTS

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | **[Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md)** | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

`text-to-speech` ti permette di lavorare con diversi motori di sintesi vocale attraverso un'unica interfaccia. Puoi iniziare con il gTTS online e passare in seguito a Piper, Silero, Coqui, Bark o Kokoro locali — senza riscrivere i comandi della CLI, il codice Python o l'integrazione HTTP.

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

`gtts`, `pyttsx3`, `pipertts`, `silerotts` e `kokorotts` funzionano bene su CPU. `coquitts` e `barktts` possono funzionare anche senza una GPU, ma la sintesi è notevolmente più lenta — per loro è consigliata una scheda grafica compatibile con CUDA.

### Installazione

L'installazione di base configura la CLI e le sue dipendenze leggere:

```bash
pip install git+https://github.com/wachawo/text-to-speech.git
```

Su Linux, il motore offline `pyttsx3` richiede anche il pacchetto di sistema `espeak`:

```bash
sudo apt install espeak espeak-data libespeak1
```

I motori aggiuntivi e i loro modelli si installano separatamente, quando ne hai davvero bisogno:

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

`gtts` è quello predefinito, quindi per il primo avvio basta un solo comando. Per lavorare completamente in locale, scegli un altro motore come `pyttsx3`, `pipertts` o `silerotts`.
La mia scelta: `coquitts` per la qualità e un parlato dal suono naturale, `silerotts` per una generazione veloce.

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

È più semplice eseguire il server con Docker:

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech

docker compose up --build -d                          # GPU / CUDA 12.1
docker compose -f docker-compose-cpu.yml up --build -d # solo CPU
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

Per lavorare con il server e testarlo c'è un client CLI separato, `ttsapi`. Ha gli stessi flag principali di `ttsgen`, ma la sintesi viene eseguita sul server. L'indirizzo del server e il token vengono presi da `TTS_URL` e `TTS_TOKEN`.

```bash
ttsapi "Hello world"
ttsapi -i long.txt --output play,file --file out.mp3
```

### Struttura del progetto

```text
text-to-speech/
├── ttsgen.py / ttsplay.py / ttsrec.py / ttsapi.py   # comandi della CLI
├── engines/        # motori: gTTS, Piper, Silero, Coqui, Bark, Kokoro e altri
├── libs/           # core condiviso: API, strumenti, riproduzione, eccezioni
├── install/        # installatori per ttsgen --install <engine>
├── ttssrv/         # server HTTP Flask
├── docker/         # build Docker per GPU e CPU
├── docs/           # documentazione per motore e traduzioni del README
└── tests/          # test pytest, nessun download di modelli e nessuna GPU
```

### Sviluppo

Per installare le dipendenze di sviluppo:

```bash
pip install -e ".[dev]"
```

Controlli prima del commit:

```bash
pytest
ruff check .
black .
```

Un nuovo motore si collega tramite un file `engines/<name>.py`. Devi solo implementare due funzioni:

```python
def is_available() -> bool:
    ...

def generate(text: str, config: dict) -> bytes:
    ...
```

`is_available()` verifica che le dipendenze siano importabili, e `generate()` prende il testo e la configurazione e restituisce l'audio come byte MP3 o WAV. Dopodiché il motore diventa automaticamente disponibile nella CLI e nell'API.

I parametri dettagliati e le specificità di ciascun motore sono descritti in [`docs/`](ENGINES.md).

### Licenza

[MIT](../LICENSE)
