# Silero TTS Installation Guide

## Overview

Silero TTS is a high-quality text-to-speech library with excellent support for multiple languages.
Particularly strong for Russian language. Fast on CPU, no GPU required.

## Features

- High-quality natural voices
- Fast CPU inference
- Small model sizes (50-100MB per language)
- Works completely offline
- Particularly excellent for Russian
- 6+ languages supported
- No external dependencies (just PyTorch)

## System Requirements

### Minimum Requirements
- Python 3.11+ (the Docker images use 3.12)
- 2GB RAM
- 500MB disk space
- CPU: Works well on modern CPUs

### Recommended Requirements
- Python 3.11+
- 4GB+ RAM
- 1GB disk space
- Multi-core CPU

## Installation

### Quick Installation

```bash
ttsgen --install silerotts

# Test installation
python -c "import torch, torchaudio, omegaconf; print('Silero TTS ready')"
```

The installer:
1. Asks where to store the models (see [Models Storage](#models-storage))
2. Installs PyTorch and torchaudio from an explicit wheel index
   (`https://download.pytorch.org/whl/cpu` or `.../whl/cu121`); the default
   PyPI index ships wheels for a newer CUDA that fail on NVIDIA drivers below
   about 580, which is why the installer picks the index for you
3. Installs `omegaconf`
4. Optionally pre-downloads the models

## Models Storage

Environment variable: `SILEROTTS_MODELS`. Installer default:
`~/.cache/torch/hub/` (the torch.hub cache Silero uses on its own); the
project-local choice is `cache/silerotts/`. The three-way prompt and how the
answer is persisted are described in
[ENGINES.md, "Where models live"](ENGINES.md#where-models-live).

To change the directory after installation:

```bash
# Persist in ~/.config/ttsgen.conf
echo "SILEROTTS_MODELS=$HOME/.cache/torch/hub" >> ~/.config/ttsgen.conf

# Or via environment variable
export SILEROTTS_MODELS="$HOME/.cache/torch/hub"
ttsgen "Hello" --engine silerotts
```

## Supported Languages

### Available Models

| Language | Code | Speaker | Quality | Notes |
|----------|------|---------|---------|-------|
| Russian | ru | aidar | 5/5 | Excellent quality |
| English | en | en_0 | 4/5 | Good quality |
| German | de | bernd_ungerer | 4/5 | Good quality |
| Spanish | es | es_0 | 4/5 | Good quality |
| French | fr | fr_0 | 4/5 | Good quality |
| Ukrainian | uk/ua | mykyta | 4/5 | Good quality |

### Selecting a model per request

The model id is the Silero model name from the table below. Without a model
the language picks it, as above (an unknown language gets `v3_en`).

| Model | Languages | Default speaker |
|---|---|---|
| `v3_1_ru` | `ru` | `aidar` |
| `v3_en` | `en` | `en_0` |
| `v3_de` | `de` | `bernd_ungerer` |
| `v3_es` | `es` | `es_0` |
| `v3_fr` | `fr` | `fr_0` |
| `v3_ua` | `ua`, `uk` | `mykyta` |

`GET /api/engines/silerotts` lists these under `models`; `installed` is true
when `<model>.pt` is already under `SILEROTTS_MODELS`, and a model that is not
downloaded yet is fetched from torch.hub on its first request, as the language
defaults are. The listing does not call torch.hub. A request sends the id as
`model` (`/api/tts`, `/api/history`); the model then gives the speaker default
too, so `{"language": "ru", "model": "v3_en"}` speaks with `en_0`.
`GET /api/voices?engine=silerotts&model=v3_en` lists that model's speakers,
which loads the model. An id outside the table is a 400.

### Model Details

All models use:
- Sample rate: 48000 Hz
- Channels: Mono
- Bit depth: 16-bit
- Format: WAV

## Voices

Each Silero language model ships several speakers (voices). The first speaker of
each language is the default; pass `voice` (HTTP `/api/tts`, the `voice`
argument of `libs.api.text_to_speech_bytes`, or `config["voice"]` when calling
the engine directly) to pick another. The `ttsgen` CLI has no voice flag for
this engine. Russian (`v3_1_ru`) includes both male and female voices:

| Language | Default | Speakers |
|----------|---------|----------|
| `ru` | `aidar` (male) | `aidar`, `baya` (female), `kseniya` (female), `xenia` (female), `eugene` (male), `random` |
| `en` | `en_0` | `en_0` to `en_117`, `random` |
| `de` | `bernd_ungerer` | model speakers |
| `es` | `es_0` | `es_0`, ... |
| `fr` | `fr_0` | `fr_0`, ... |
| `ua`, `uk` | `mykyta` | model speakers |

A tag such as `ru-ru` uses the model of its language part; any other language
gets the English model.

The authoritative list comes from the loaded model's `speakers` attribute and is
exposed at runtime:

- `engines.silerotts.list_voices(language)` returns `{"voices": [...], "default": "aidar"}`
- HTTP: `GET /api/voices?engine=silerotts&language=ru`

An unknown voice for the language raises `ValidationError` (HTTP `400`).

```python
from engines.silerotts import generate, list_voices

list_voices("ru")  # {'voices': ['aidar', 'baya', 'kseniya', 'xenia', 'eugene', 'random'], 'default': 'aidar'}
audio = generate("Здравствуйте", {"language": "ru", "voice": "baya"})  # female
```

## Usage

### Basic Usage

```bash
# English
ttsgen "Hello world" --engine silerotts

# Russian (excellent quality)
ttsgen "Привет мир" --engine silerotts --language ru

# Spanish
ttsgen "Hola mundo" --engine silerotts --language es

# Save to file
ttsgen "Hello" --engine silerotts --file output.wav

# Play and save
ttsgen "Hello" --engine silerotts --file output.wav --play
```

### First Run

The first time you use Silero TTS for each language:
- Model downloads automatically from PyTorch Hub
- Download size: 50-100MB per model
- Takes 1-5 minutes depending on connection
- Models cached in the `SILEROTTS_MODELS` directory (see Models Storage)

### Pre-download Models

`ttsgen --install silerotts` offers to pre-download the models. To do it by hand:

```bash
python << 'EOF'
import torch

print("Downloading Russian model...")
model, _ = torch.hub.load(
    repo_or_dir='snakers4/silero-models',
    model='silero_tts',
    language='ru',
    speaker='v3_1_ru',
    verbose=True,
    trust_repo=True
)
print("Russian model downloaded!")

print("Downloading English model...")
model, _ = torch.hub.load(
    repo_or_dir='snakers4/silero-models',
    model='silero_tts',
    language='en',
    speaker='v3_en',
    verbose=True,
    trust_repo=True
)
print("English model downloaded!")
EOF
```

## Configuration

### In Python

```python
from libs.api import text_to_speech_bytes

# Generate with Silero TTS
audio = text_to_speech_bytes(
    text="Hello world",
    engine="silerotts",
    language="en"
)
```

### In .env

```bash
TTS_ENGINE=silerotts
TTS_LANGUAGE=ru
DEFAULT_OUTPUT_FORMAT=play
```

## Performance

### CPU Performance
- Speed: Fast (1-3 seconds per sentence)
- Quality: High (4-5/5)
- Memory: ~300MB per model
- Use for: Production on CPU

### GPU Performance
- Works on GPU automatically if available
- Even faster than CPU
- Recommended for batch processing

## Model Cache Location

Models are cached by PyTorch Hub:
- Linux: `~/.cache/torch/hub/snakers4_silero-models_master/`
- macOS: `~/.cache/torch/hub/snakers4_silero-models_master/`
- Windows: `%USERPROFILE%\.cache\torch\hub\snakers4_silero-models_master\`

## Advanced Usage

### Using in Python

```python
# Direct usage
import torch

model, _ = torch.hub.load(
    repo_or_dir='snakers4/silero-models',
    model='silero_tts',
    language='ru',
    speaker='v3_1_ru'
)

audio = model.apply_tts(
    text="Привет, как дела?",
    speaker='aidar',
    sample_rate=48000
)

# Save to file
import torchaudio
torchaudio.save('output.wav', audio.unsqueeze(0), 48000)
```

### Multiple Speakers

Some models support multiple speakers:

```bash
# Russian model speakers: aidar, baya, kseniya, xenia, eugene
# English model speakers: en_0, en_1, en_2, etc.
```

Pick one with the `voice` parameter, see [Voices](#voices) above.

## Comparison

### Silero vs Piper
- **Quality**: Similar (both 4-5/5)
- **Speed**: Both fast on CPU
- **Setup**: Piper easier (just download .onnx files)
- **Russian**: Silero slightly better
- **English**: Piper slightly better
- **Choice**: Use Silero for Russian, Piper for English

### Silero vs Coqui TTS
- **Quality**: Coqui higher (5/5 vs 4/5)
- **Speed**: Silero much faster on CPU
- **Setup**: Similar complexity
- **GPU**: Coqui requires GPU for practical use
- **Choice**: Use Silero for CPU, Coqui for GPU

### Silero vs gTTS
- **Quality**: Silero higher
- **Speed**: Silero faster
- **Offline**: Silero works offline
- **Setup**: gTTS simpler
- **Choice**: Use Silero for offline, gTTS for quick online

## Troubleshooting

### Installation fails

```bash
# Re-run the installer; it installs torch from the right wheel index
ttsgen --install silerotts
```

### Model download fails

```bash
# Check internet connection
ping raw.githubusercontent.com

# Clear cache and retry
rm -rf ~/.cache/torch/hub/snakers4_silero-models_master/
```

### Audio quality issues

```bash
# Silero generates 48000 Hz audio
# Ensure playback supports this sample rate
# Our playback.py auto-detects and handles this
```

### ImportError: No module named torch

```bash
# Install PyTorch through the installer (prompts for CPU or CUDA build)
ttsgen --install silerotts

# Equivalent by hand, CPU-only build (smaller)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
```

## Resources

- GitHub: https://github.com/snakers4/silero-models
- PyTorch Hub: https://pytorch.org/hub/snakers4_silero-models_tts/
- Colab demo: Available on GitHub

## Recommendations

**Use Silero TTS when:**
- You need high-quality offline TTS
- You want fast CPU inference
- You're working with Russian language
- You don't have GPU
- You want good quality without large downloads

**Don't use Silero TTS when:**
- You only need basic quality (use pyttsx3)
- You want smallest setup (use gtts)
- You need absolute best quality with GPU (use coquitts)

## Quick Start

```bash
# 1. Install
ttsgen --install silerotts

# 2. Use (model downloads automatically on first run)
ttsgen "Hello world" --engine silerotts

# 3. Russian (recommended - best quality)
ttsgen "Привет мир" --engine silerotts --language ru
```

Models download automatically on first use. No manual model management needed!

