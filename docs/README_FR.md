## text-to-speech — une interface unique pour les moteurs TTS

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

`text-to-speech` vous permet de travailler avec plusieurs moteurs de synthèse vocale via une seule interface. Vous pouvez commencer avec gTTS en ligne et passer ensuite à Piper, Silero, Coqui, Bark ou Kokoro en local — sans réécrire vos commandes CLI, votre code Python ou votre intégration HTTP.

Le projet convient à un usage local, à l'automatisation et à l'exécution de votre propre serveur TTS sur le réseau.

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | **[Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md)** | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

* **Une seule façon de travailler avec différents moteurs.** Choisissez le moteur dont vous avez besoin et appelez-le via la CLI (`ttsgen`), l'API Python (`libs.api`) ou l'API HTTP.
* **Vous pouvez travailler entièrement en local.** Piper, Silero, Coqui, Bark, Kokoro et `pyttsx3` s'exécutent tous sur votre propre machine.
* **Un serveur HTTP prêt à l'emploi est inclus.** `ttssrv` charge le modèle au démarrage et traite les requêtes provenant d'autres machines de votre réseau local.

### Moteurs

| Moteur      | Hors ligne | Matériel      | Qualité | Adapté à                                        |
| ----------- | ---------- | ------------- | ------- | ----------------------------------------------- |
| `gtts`      | ❌         | CPU           | ★★★★    | un démarrage rapide et un grand nombre de langues |
| `pyttsx3`   | ✅         | CPU           | ★★      | une synthèse vocale locale simple via espeak ou SAPI |
| `pipertts`  | ✅         | CPU           | ★★★★    | une synthèse hors ligne rapide dans de nombreuses langues |
| `silerotts` | ✅         | CPU           | ★★★★    | la parole en russe et une installation locale légère |
| `kokorotts` | ✅         | CPU           | ★★★★    | une synthèse hors ligne multilingue              |
| `coquitts`  | ✅         | CPU / **GPU** | ★★★★★   | des voix de haute qualité et le clonage de voix  |
| `barktts`   | ✅         | CPU / **GPU** | ★★★★★   | une parole expressive, des émotions, de la musique et du chant |

`gtts`, `pyttsx3`, `pipertts`, `silerotts` et `kokorotts` fonctionnent très bien sur CPU. `coquitts` et `barktts` peuvent aussi fonctionner sans GPU, mais la synthèse est nettement plus lente — une carte graphique compatible CUDA est recommandée pour ces moteurs.

### Installation

L'installation de base met en place la CLI et ses dépendances légères :

```bash
pip install git+https://github.com/wachawo/text-to-speech.git
```

Les moteurs supplémentaires et leurs modèles s'installent séparément, lorsque vous en avez réellement besoin :

```bash
ttsgen --install coquitts
```

Exemples d'utilisation de la CLI :

```bash
ttsgen "Hello world"                  # prononce le texte avec gTTS
ttsgen "Hello world" -f out.mp3       # enregistre le résultat dans un fichier
ttsgen "Hello world" -e pyttsx3       # utilise un moteur local
ttsgen "Hola amigo!" -l es            # choisit une langue
ttsgen --install coquitts             # installe Coqui TTS et ses modèles
ttsgen "Hello world" -e coquitts -f out.wav
ttsgen --list                         # affiche les moteurs et modèles disponibles
ttsgen "Hello world" --stdout | ttsplay
```

`gtts` est le moteur par défaut, donc une seule commande suffit pour le premier lancement. Pour un travail entièrement local, choisissez un autre moteur tel que `pyttsx3`, `pipertts` ou `silerotts`.
Mon choix : `coquitts` pour la qualité et le naturel de la parole, `silerotts` pour la rapidité de génération.

### API Python

En Python, il existe des fonctions pour enregistrer le résultat dans un fichier ou récupérer l'audio sous forme d'octets :

```python
from libs.api import text_to_speech_file, text_to_speech_bytes

text_to_speech_file("Hello world", engine="gtts")

audio = text_to_speech_bytes(
    "Hello world",
    engine="pipertts",
    language="en",
)
```

### Serveur HTTP

Il est plus simple de lancer le serveur avec Docker :

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech

docker compose up --build -d                          # GPU / CUDA 12.1
docker compose -f docker-compose-cpu.yml up --build -d # CPU uniquement
```

Une fois lancé, vous pouvez vérifier l'état du serveur et envoyer une requête de synthèse :

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

Pour travailler avec le serveur et le tester, il existe un client CLI distinct, `ttsapi`. Il possède les mêmes principaux indicateurs que `ttsgen`, mais la synthèse s'exécute sur le serveur. L'adresse du serveur et le jeton sont récupérés depuis `TTS_URL` et `TTS_TOKEN`.

```bash
ttsapi "Hello world"
ttsapi -i long.txt --output play,file --file out.mp3
```

### Structure du projet

```text
text-to-speech/
├── ttsgen.py / ttsplay.py / ttsrec.py / ttsapi.py   # commandes CLI
├── engines/        # moteurs : gTTS, Piper, Silero, Coqui, Bark, Kokoro, et autres
├── libs/           # cœur partagé : API, outils, lecture, exceptions
├── install/        # installateurs pour ttsgen --install <engine>
├── ttssrv/         # serveur HTTP Flask
├── docker/         # builds Docker pour GPU et CPU
├── docs/           # docs par moteur et traductions du README
└── tests/          # tests pytest, sans téléchargement de modèles ni GPU
```

### Développement

Pour installer les dépendances de développement :

```bash
pip install -e ".[dev]"
```

Vérifications avant de committer :

```bash
pytest
ruff check .
black .
```

Un nouveau moteur s'intègre via un fichier `engines/<name>.py`. Il vous suffit d'implémenter deux fonctions :

```python
def is_available() -> bool:
    ...

def generate(text: str, config: dict) -> bytes:
    ...
```

`is_available()` vérifie que les dépendances sont importables, et `generate()` prend le texte et la configuration et renvoie l'audio sous forme d'octets MP3 ou WAV. Après cela, le moteur devient automatiquement disponible dans la CLI et l'API.

Les paramètres détaillés et les spécificités de chaque moteur sont décrits dans [`docs/`](docs/ENGINES.md).

### Licence

[MIT](LICENSE)
