## text-to-speech — les moteurs TTS populaires derrière une seule API

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

Installez les moteurs TTS en ligne/hors ligne populaires (gTTS, espeak, Piper, Silero, Coqui, Bark, Kokoro) et utilisez-les via une seule CLI, une API Python et un serveur HTTP.

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | **[Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md)** | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

- **Une seule interface, de nombreux moteurs.** Choisissez un moteur et appelez-le de la même manière depuis la CLI (`ttsgen`), Python (`libs.api`) ou HTTP — basculez entre le cloud et le local sans changer de code.
- **Serveur API pour votre réseau local.** Lancez `ttssrv` pour que d'autres machines effectuent la synthèse via HTTP (`POST /api/tts`) ; le modèle se charge une seule fois au démarrage et les requêtes partagent un pool.

### Moteurs

| Moteur | Hors ligne | Matériel | Qualité | Idéal pour |
|---|---|---|---|---|
| `gtts` | ❌ en ligne | CPU | ★★★★ | 100+ langues, aucune configuration |
| `pyttsx3` | ✅ | CPU | ★★ | installation minimale (espeak / SAPI) |
| `pipertts` | ✅ | CPU | ★★★★ | rapide hors ligne, 50+ langues |
| `silerotts` | ✅ | CPU | ★★★★ | rapide hors ligne, russe |
| `kokorotts` | ✅ | CPU | ★★★★ | rapide hors ligne, multilingue |
| `coquitts` | ✅ | CPU / **GPU** | ★★★★★ | meilleure qualité, clonage de voix |
| `barktts` | ✅ | CPU / **GPU** | ★★★★★ | émotions, musique, chant |

`gtts`, `pyttsx3`, `pipertts`, `silerotts`, `kokorotts` fonctionnent très bien sur CPU. `coquitts` et `barktts` fonctionnent aussi sur CPU mais sont lents — un GPU CUDA est recommandé.

### Installation (pip)

```bash
pip install git+https://github.com/wachawo/text-to-speech.git
```

Cela installe la CLI avec seulement des dépendances légères. Les moteurs neuronaux (`pipertts`, `silerotts`, `coquitts`, `barktts`, `kokorotts`) récupèrent `torch`/les modèles à la demande via `ttsgen --install <engine>`.

```bash
ttsgen "Hello world"                  # lecture (moteur par défaut : gtts, en ligne)
ttsgen "Hello world" -f out.mp3       # enregistrer dans un fichier
ttsgen "Hello world" -e pyttsx3       # entièrement hors ligne
ttsgen "Hola amigo!"  -l es           # choisir la langue
ttsgen --install coquitts             # ajouter un moteur neuronal hors ligne + modèles
ttsgen "Hello world" -e coquitts -f out.wav
ttsgen --list                         # moteurs + modèles installés
ttsgen "Hello world" --stdout | ttsplay
```

Python :

```python
from libs.api import text_to_speech_file, text_to_speech_bytes

text_to_speech_file("Hello world", engine="gtts")
audio = text_to_speech_bytes("Hello world", engine="pipertts", language="en")
```

### Serveur (clone)

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech
docker compose up --build -d                          # GPU (CUDA 12.1)
docker compose -f docker-compose-cpu.yml up --build -d # CPU uniquement
```

Demandez une synthèse via HTTP :

```bash
curl localhost:5000/api/health
curl localhost:5000/api/engines -H "Authorization: Bearer $TTS_TOKEN"
curl "localhost:5000/api/voices?engine=silerotts&language=ru" -H "Authorization: Bearer $TTS_TOKEN"

curl -X POST localhost:5000/api/tts \
  -H "Authorization: Bearer $TTS_TOKEN" -H "Content-Type: application/json" \
  -d '{"text":"Hello world","engine":"gtts"}' -o out.mp3
```

Ou utilisez `ttsapi` — les mêmes options que `ttsgen`, mais la synthèse s'exécute sur le serveur (`TTS_URL` / `TTS_TOKEN` depuis la configuration) :

```bash
ttsapi "Hello world"
ttsapi -i long.txt --output play,file --file out.mp3
```

### Structure du projet

```
text-to-speech/
├── ttsgen.py / ttsplay.py / ttsrec.py / ttsapi.py   # points d'entrée CLI
├── engines/        # moteurs enfichables (gtts, piper, silero, coqui, bark, kokoro, …)
├── libs/           # cœur : api.py, tools.py, playback.py, exceptions.py
├── install/        # installateurs `ttsgen --install <engine>`
├── ttssrv/         # serveur HTTP Flask (Docker / python3 ttssrv/app1.py)
├── docker/         # builds gpu/ et cpu/ (Dockerfile + requirements)
├── docs/           # guides par moteur + traductions
└── tests/          # suite pytest (moteurs simulés, aucun modèle/GPU requis)
```

### Notes pour les développeurs

```bash
pip install -e ".[dev]"
pytest                 # tests + couverture
ruff check . && black .
```

Ajoutez un moteur en déposant `engines/<name>.py` avec deux fonctions — il apparaît automatiquement dans la CLI et l'API :

```python
def is_available() -> bool: ...                  # dépendances importables ?
def generate(text: str, config: dict) -> bytes:  # renvoie des octets MP3/WAV
    ...
```

La configuration par moteur et le guide complet des moteurs se trouvent dans [`docs/`](docs/ENGINES.md).

### Licence

[MIT](LICENSE)
