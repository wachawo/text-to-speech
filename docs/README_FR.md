# text-to-speech - une interface unique pour les moteurs TTS

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | **[Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md)** | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

![L'écran Studio de l'interface web](https://raw.githubusercontent.com/wachawo/text-to-speech/main/docs/images/studio.png)

`text-to-speech` vous permet de travailler avec plusieurs moteurs de synthèse vocale via une seule interface. Vous pouvez commencer avec gTTS en ligne et passer ensuite à Piper, Silero, Coqui, Bark ou Kokoro en local - sans réécrire vos commandes CLI, votre code Python ou votre intégration HTTP.

Le projet convient à un usage local, à l'automatisation et à l'exécution de votre propre serveur TTS sur le réseau.

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

`gtts`, `pyttsx3`, `pipertts`, `silerotts` et `kokorotts` fonctionnent très bien sur CPU. `coquitts` et `barktts` peuvent aussi fonctionner sans GPU, mais la synthèse est nettement plus lente - une carte graphique compatible CUDA est recommandée pour ces moteurs.

### Installation

L'installation de base met en place la CLI et ses dépendances légères :

```bash
pip install git+https://github.com/wachawo/text-to-speech.git
```

Sous Linux, le moteur hors ligne `pyttsx3` nécessite également le paquet système `espeak` :

```bash
sudo apt install espeak espeak-data libespeak1
```

Les moteurs supplémentaires et leurs modèles s'installent séparément, quand vous en avez réellement besoin :

```bash
ttsgen --install coquitts
```

Exemples d'utilisation de la CLI :

```bash
ttsgen "Hello world"                  # lit le texte avec gTTS
ttsgen "Hello world" -f out.mp3       # enregistre le résultat dans un fichier
ttsgen "Hello world" -e pyttsx3       # utilise un moteur local
ttsgen "Hola amigo!" -l es            # choisit une langue
ttsgen --install coquitts             # installe Coqui TTS et ses modèles
ttsgen "Hello world" -e coquitts -f out.wav
ttsgen --list                         # affiche les moteurs et modèles disponibles
ttsgen "Hello world" --stdout | ttsplay
```

`gtts` est le moteur par défaut, une seule commande suffit donc pour le premier essai. Pour travailler entièrement en local, choisissez un autre moteur comme `pyttsx3`, `pipertts` ou `silerotts`.
Mon choix : `coquitts` pour la qualité et le naturel de la voix, `silerotts` pour la rapidité de génération.

### API Python

En Python, des fonctions permettent d'enregistrer le résultat dans un fichier ou d'obtenir l'audio sous forme d'octets :

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
cp env.example .env                                   # facultatif : jetons, moteurs, ports

docker compose up --build -d                          # GPU / CUDA 12.1
docker compose -f docker-compose-cpu.yml up --build -d # CPU uniquement
```

La variante GPU transmet la carte via CDI, l'hôte a donc besoin du NVIDIA container toolkit (1.14 ou plus récent) et d'une spécification CDI générée, une fois à chaque mise à jour du pilote :

```bash
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
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

Modèles, voix et historique :

```bash
# Ce qu'offre un moteur : modèles, langues et voix, lus sans charger de modèle
curl localhost:5000/api/engines/pipertts \
  -H "Authorization: Bearer $TTS_TOKEN"

# Synthétiser avec l'un des modèles listés
curl -X POST localhost:5000/api/tts \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world","engine":"pipertts","language":"en-gb","model":"en_GB-alan-low"}' \
  -o out.wav

# Modèles installés et manquants, le même tableau que celui affiché par `ttsgen --list`
curl localhost:5000/api/models \
  -H "Authorization: Bearer $TTS_TOKEN"

# Téléverse un échantillon de voix pour coquitts (WAV) ; la voix s'appelle alors "maria"
curl -X POST localhost:5000/api/voices \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -F file=@voice.wav -F name=maria -F engine=coquitts

curl "localhost:5000/api/voices?engine=coquitts" \
  -H "Authorization: Bearer $TTS_TOKEN"

curl "localhost:5000/api/voices/maria/audio?engine=coquitts&download=1" \
  -H "Authorization: Bearer $TTS_TOKEN" -o maria.wav

# Synthétise dans l'historique côté serveur au lieu du corps de la réponse
curl -X POST localhost:5000/api/history \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hola mundo","engine":"coquitts","language":"es","voice":"maria"}'

curl "localhost:5000/api/history?limit=50&offset=0" \
  -H "Authorization: Bearer $TTS_TOKEN"

# Audio d'un élément ; sans download=1 il est servi en ligne pour <audio>
curl "localhost:5000/api/history/<id>/audio?download=1" \
  -H "Authorization: Bearer $TTS_TOKEN" -o tts.wav

curl -X DELETE localhost:5000/api/history/<id> \
  -H "Authorization: Bearer $TTS_TOKEN"
```

#### API compatible OpenAI

Le même serveur répond aussi à l'API audio d'OpenAI, de sorte qu'Open WebUI, SillyTavern, Home Assistant et les SDK officiels fonctionnent avec `base_url` pointant vers lui et le jeton bearer comme clé d'API :

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

- `model` est le nom d'un moteur, ou `tts-1` / `tts-1-hd` / `gpt-4o-mini-tts` pour le moteur par défaut. `/v1` ne permet pas de choisir un modèle à l'intérieur d'un moteur : le moteur utilise son modèle par défaut.
- `voice` est une voix du moteur ; les noms de voix OpenAI (`alloy`, `nova`, ...) sélectionnent la voix par défaut du moteur.
- `response_format` : `mp3` (par défaut), `wav`, `pcm`, `opus`, `flac`, `aac`. Les moteurs produisent du WAV ou du MP3 ; tout autre format est transcodé avec `ffmpeg`, inclus dans les images Docker. `speed` (de 0.25 à 4.0) est appliqué de la même manière.
- `language` est une extension : un code à deux lettres ou une étiquette comme `zh-cn`, par défaut `TTS_LANGUAGE`.
- `GET /v1/models` liste les moteurs installés plus `tts-1` ; `GET /v1/audio/voices?model=<engine>` liste les voix d'un moteur.

#### Référence de l'API

Toute route sauf `/api/health` exige `Authorization: Bearer <token>` lorsque `TTS_TOKENS` est défini. Les erreurs sous `/api/` ont la forme `{"error": "...", "request_id": "..."}` ; une réponse 400 contient aussi `message` avec la raison, qui nomme les champs en échec quand la requête ne passe pas la validation (`language: ...`). Les erreurs sous `/v1/` utilisent le format OpenAI.

| Méthode | Chemin | Rôle |
| --- | --- | --- |
| GET | `/api/health` | Vivacité, indicateur `auth`, moteurs, tailles du pool et de la file. Aucun jeton requis. |
| GET | `/api/engines` | Moteurs pris en charge, ceux installés et celui par défaut. |
| GET | `/api/engines/<engine>` | Modèles, langues, liste de voix et format de sortie d'un moteur, lus sans charger de modèle. |
| GET | `/api/models` | Modèles installés et manquants par moteur, le tableau affiché par `ttsgen --list`. |
| GET | `/api/voices?engine=&language=&model=` | Voix d'un moteur ; pour `coquitts`, les échantillons avec taille, fréquence et durée. Avec `model`, les voix de ce modèle. |
| POST | `/api/voices` | Téléverse un échantillon WAV (`file`, `name`, `engine=coquitts`). |
| GET | `/api/voices/<name>/audio?engine=&download=1` | Lit ou télécharge un échantillon. |
| DELETE | `/api/voices/<name>?engine=` | Supprime un échantillon. |
| POST, GET | `/api/tts` | Synthétise `text` avec `engine`, `language`, `voice`, `model` ; `stream=true` diffuse les morceaux dès qu'ils sont prêts. |
| POST | `/api/history` | Synthétise dans l'historique côté serveur au lieu du corps de la réponse. |
| GET | `/api/history?limit=&offset=` | Liste les éléments de l'historique, les plus récents en premier. |
| GET | `/api/history/<id>` | Métadonnées d'un élément. |
| GET | `/api/history/<id>/audio?download=1` | L'audio de l'élément, en ligne ou en téléchargement. |
| DELETE | `/api/history/<id>` | Supprime un élément. |
| POST | `/v1/audio/speech` | Synthèse compatible OpenAI, voir ci-dessus. |
| GET | `/v1/models` | Liste de modèles compatible OpenAI. |
| GET | `/v1/audio/voices?model=` | Voix d'un moteur. |

`language` est un code à deux lettres (`en`, `ru`) ou une étiquette avec région ou écriture (`zh-cn`, `pt_BR`, `en-gb`, `es-419`), mise en minuscules et écrite avec `-`. Chaque moteur ramène l'étiquette à ce qu'il possède : gtts reçoit sa propre graphie (`zh-CN` ; il n'a ni français canadien ni portugais européen, donc `fr-ca` et `pt-pt` deviennent `fr` et `pt`), kokorotts prononce `en-gb` avec le phonémiseur britannique, xtts reçoit `zh-cn` pour le chinois, et les autres moteurs utilisent la partie langue (`pt-br` devient `pt`). Une langue que le moteur ne connaît pas est prononcée dans sa langue par défaut, généralement l'anglais (gtts échoue à la place) ; avec `TTS_LANGUAGE_STRICT=true`, c'est une erreur 400 qui liste les langues du moteur. La vérification stricte couvre `/api/tts` sans `stream`, `/api/history` et `/v1/audio/speech`, et tous les moteurs qui listent leurs langues : tous sauf pyttsx3, pipertts sans voix installée et coquitts avec un modèle multilingue autre que xtts ou un modèle dont le code de langue a trois lettres (`ewe`).

`model` choisit un modèle à l'intérieur du moteur sur `/api/tts` et `/api/history` : une voix Piper (`en_GB-alan-low`), un fichier de modèle Kokoro (`kokoro-v1.0.int8.onnx`), un modèle Silero (`v3_1_ru`) ou un nom de modèle Coqui (`tts_models/de/thorsten/vits`). `GET /api/engines/<engine>` les liste sous `models`, chacun avec ses `languages`, `installed` et `default_for` (les langues qui l'utilisent quand la requête ne nomme aucun modèle), à côté des `languages` du moteur, de `output_format`, de `max_text_length` et de la présence d'une liste de voix ; aucun modèle n'est chargé, et un moteur inconnu donne une erreur 404. Sans `model`, le moteur choisit comme avant ; un identifiant que le moteur ne liste pas est une erreur 400 qui nomme ceux qu'il possède, tout comme `model` avec `stream=true`, car un flux utilise toujours le modèle par défaut du moteur. gtts, pyttsx3 et barktts n'ont pas de modèles. Sans modèle, pipertts choisit parmi ses voix installées : une étiquette avec région (`en-gb`) prend une voix de cette région, et une langue absente de sa table intégrée prend une voix installée de cette langue au lieu de la voix anglaise ; sa liste de langues est celle des voix installées.

#### Interface web

Les deux fichiers compose démarrent aussi `ttswww`, un conteneur nginx qui sert l'interface web et relaie `/api/` vers `ttssrv` :

```bash
docker compose up --build -d
xdg-open http://localhost:8080      # TTS_WWW_PORT ; changez-le si le 8080 est déjà pris
xdg-open https://localhost:8443     # TTS_WWW_TLS_PORT ; certificat auto-signé, acceptez-le une fois
```

- **Studio** - saisissez un texte, choisissez moteur / langue / voix, générez, écoutez, enregistrez ; chaque résultat arrive dans une liste d'historique.
- **Voices** - téléversez ou enregistrez des échantillons de voix WAV pour le clonage de voix de `coquitts` ; lisez-les, téléchargez-les et supprimez-les.
- **Models** - les moteurs et les modèles installés / manquants, le même tableau que `ttsgen --list`.

L'engrenage dans l'en-tête ouvre la boîte de dialogue des paramètres : le moteur, la langue et la voix par défaut du Studio, et l'affichage ou non de l'exemple curl ; les choix sont stockés dans le navigateur. Le Studio affiche une commande `curl` prête à copier pour la requête en cours ; elle référence le jeton sous la forme `$TTS_TOKEN` au lieu de l'afficher. L'écran Voices peut aussi enregistrer un échantillon depuis le microphone, ce que les navigateurs n'autorisent qu'en `https` ou sur `localhost` - sur le réseau local, ouvrez l'interface via le port https. Un certificat auto-signé est généré dans `./data/certs` au premier démarrage ; montez un vrai certificat sous les mêmes noms (`tts.crt`, `tts.key`) pour le remplacer.

Lorsque `TTS_TOKENS` est défini, l'interface s'ouvre sur un écran de connexion et demande l'un de ces jetons ; le navigateur le conserve et l'envoie avec chaque requête. Sans `TTS_TOKENS`, il n'y a pas de connexion.

#### Configuration

Chaque réglage est une variable d'environnement ; `env.example` les documente toutes et le `.env` à côté des fichiers compose est lu automatiquement. Celles que vous êtes le plus susceptible de modifier :

| Variable | Par défaut | Rôle |
| --- | --- | --- |
| `TTS_TOKENS` | vide | Jetons bearer séparés par des virgules. Vide signifie aucune authentification. |
| `TTS_ENGINES` | vide | Moteurs à installer et à préchauffer au démarrage, séparés par des virgules (`coquitts,silerotts`). |
| `TTS_ENGINE` | `gtts` | Moteur utilisé quand une requête n'en indique aucun. |
| `TTS_LANGUAGE` | `en` | Langue utilisée quand une requête n'en indique aucune. |
| `TTS_LANGUAGE_STRICT` | `false` | `true` répond 400 à une langue que le moteur ne liste pas, au lieu du repli du moteur sur sa langue par défaut. |
| `TTS_MODEL_CACHE_SIZE` | `2` | Modèles que coquitts et kokorotts gardent chargés en même temps ; une requête pour un modèle de plus retire le premier chargé. |
| `TTS_POOL_SIZE` | `1` | Appels de synthèse autorisés simultanément tous moteurs confondus ; `0` supprime la limite et le préchauffage. |
| `TTS_QUEUE_SIZE` | `8` | Requêtes de synthèse autorisées à attendre une place libre ; au-delà, 503 immédiat. |
| `TTS_HISTORY_MAX` | `200` | Éléments conservés dans l'historique ; les plus anciens sont supprimés à l'enregistrement d'un nouveau. |
| `TTS_MAX_SAMPLE_BYTES` | `16777216` | Taille maximale d'un échantillon de voix téléversé (16 Mio). |
| `TTS_MAX_SAMPLES` | `100` | Échantillons de voix conservés sur le serveur. |
| `TTS_MAX_BODY_BYTES` | `2097152` | Taille maximale du corps JSON d'une requête (2 Mio). |
| `TTS_STREAM_MAX_CHARS` | `200` | Taille des morceaux pour `stream=true`. |
| `CORS_ORIGINS` | `*` | Origines autorisées pour `/api/*`. |
| `TTS_PORT` | `5000` | Port de `ttssrv`. |
| `TTS_WWW_PORT`, `TTS_WWW_TLS_PORT` | `8080`, `8443` | Ports http et https de l'interface web. |
| `COQUITTS_MODEL`, `COQUITTS_SAMPLE` | `xtts_v2`, `default.wav` | Modèle Coqui et échantillon de voix par défaut. |
| `TZ` | `America/New_York` | Fuseau horaire des horodatages dans les journaux et l'historique. |

Hors Docker, les CLI et le serveur lisent les mêmes clés depuis, par ordre de priorité décroissante : les options de la CLI, l'environnement du shell, `./ttsgen.conf`, `~/.config/ttsgen.conf`, `./.env.local`, `./.env`. Un fichier ne remplace jamais le shell, et `.env` n'est lu que depuis le répertoire courant.

Un `TTS_POOL_SIZE` supérieur à 1 permet à différents moteurs de synthétiser en parallèle ; au sein d'un même moteur, les appels sont sérialisés, car les modèles sous-jacents ne peuvent pas être partagés entre threads en toute sécurité.

#### Sécurité

- L'authentification est désactivée tant que vous n'avez pas défini `TTS_TOKENS`. Ensuite, toute route sauf `/api/health` exige `Authorization: Bearer <token>`, et l'interface web demande le jeton sur un écran de connexion.
- L'API écoute sur toutes les interfaces et les fichiers compose publient `TTS_PORT`, `TTS_WWW_PORT` et `TTS_WWW_TLS_PORT` sur l'hôte. Sur un réseau partagé, définissez un jeton ou liez les ports à `127.0.0.1` dans un fichier d'override.
- L'écouteur https utilise un certificat auto-signé créé au premier démarrage ; il est prévu pour un réseau local. Sur Internet, placez l'interface derrière votre propre reverse proxy avec un vrai certificat.
- Les échantillons de voix, l'historique et les certificats se trouvent sous `./data` ; sauvegardez-le et gardez-le hors du contexte de build.

Signalez une vulnérabilité via l'onglet Security du dépôt, voir [SECURITY.md](https://github.com/wachawo/text-to-speech/blob/main/SECURITY.md).

Pour travailler avec le serveur et le tester, il existe un client CLI distinct, `ttsapi`. Il possède les mêmes options principales que `ttsgen`, mais la synthèse s'exécute sur le serveur. L'adresse du serveur et le jeton sont récupérés depuis `TTS_URL` et `TTS_TOKEN`.

```bash
ttsapi "Hello world"
ttsapi -i long.txt --output play,file --file out.mp3
```

### Structure du projet

```text
text-to-speech/
├── ttsgen.py / ttsplay.py / ttsrec.py / ttsapi.py   # commandes CLI
├── engines/        # moteurs : gTTS, Piper, Silero, Coqui, Bark, Kokoro et autres
├── libs/           # noyau partagé : API, outils, lecture, exceptions
├── install/        # installateurs pour ttsgen --install <engine>
├── ttssrv/         # serveur HTTP Flask
├── www/            # interface web : Vue 2 sans étape de build, servie par nginx
├── nginx/          # configuration principale de nginx et le gabarit conf.d pour ttswww
├── docker/         # builds Docker pour GPU, CPU et l'interface web
├── docs/           # documentation par moteur et traductions du README
└── tests/          # tests pytest, sans téléchargement de modèles ni GPU
```

### Développement

Les contributions sont les bienvenues ; [CONTRIBUTING.md](https://github.com/wachawo/text-to-speech/blob/main/CONTRIBUTING.md) explique la mise en place, les vérifications et la façon d'ajouter un moteur. Pour installer les dépendances de développement :

```bash
pip install -e ".[dev]"
```

Vérifications avant de committer :

```bash
pytest
ruff check .
black .
```

Un nouveau moteur se branche via un fichier `engines/<name>.py`. Il suffit d'implémenter deux fonctions :

```python
def is_available() -> bool:
    ...

def generate(text: str, config: dict) -> bytes:
    ...
```

`is_available()` vérifie que les dépendances sont importables, et `generate()` prend le texte et la configuration et renvoie l'audio sous forme d'octets MP3 ou WAV. Le moteur devient ensuite automatiquement disponible dans la CLI et l'API.

Les paramètres détaillés et les particularités de chaque moteur sont décrits dans [`docs/`](https://github.com/wachawo/text-to-speech/blob/main/docs/ENGINES.md).

### Licence

[MIT](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
