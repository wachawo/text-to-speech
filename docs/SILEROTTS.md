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
- Python 3.8+
- 2GB RAM
- 500MB disk space
- CPU: Works well on modern CPUs

### Recommended Requirements
- Python 3.8+
- 4GB+ RAM
- 1GB disk space
- Multi-core CPU

## Installation

### Quick Installation

```bash
# Install dependencies
pip install torch torchaudio omegaconf

# Test installation
python -c "import torch, torchaudio, omegaconf; print('Silero TTS ready')"
```

### Using Installation Script

```bash
# Run installation script
ttsgen --install silerotts
```

The script will:
1. Install PyTorch and torchaudio
2. Verify installation
3. Optionally pre-download models

## Models Storage

### Default Location

Models are stored in `cache/silerotts/` directory in project root (created automatically during installation).

Example: `/path/to/tts/cache/silerotts/`

### Custom Location

During installation, you can choose from:
1. **Default:** `cache/silerotts/` (in project directory)
2. **Standard:** `~/.cache/torch/hub/` (default Silero location)
3. **Custom:** any directory you specify

To change directory after installation:

```bash
# In .env file
echo "SILEROTTS_MODELS=~/.cache/torch/hub" >> .env

# Or via environment variable
export SILEROTTS_MODELS="~/.cache/torch/hub"
python ttsgen.py "Hello" --engine silerotts
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

### Model Details

All models use:
- Sample rate: 48000 Hz
- Channels: Mono
- Bit depth: 16-bit
- Format: WAV

## Voices

Each Silero language model ships several speakers (voices). The first speaker of
each language is the default; pass `voice` (HTTP `/api/tts`) or `config["voice"]`
to pick another. Russian (`v3_1_ru`) includes both male and female voices:

| Language | Default | Speakers |
|----------|---------|----------|
| `ru` | `aidar` (male) | `aidar`, `baya` (female), `kseniya` (female), `xenia` (female), `eugene` (male), `random` |
| `en` | `en_0` | `en_0` … `en_117`, `random` |
| `de` | `bernd_ungerer` | model speakers |
| `es` | `es_0` | `es_0` … |
| `fr` | `fr_0` | `fr_0` … |
| `ua` | `mykyta` | model speakers |

The authoritative list comes from the loaded model's `speakers` attribute and is
exposed at runtime:

- `engines.silerotts.list_voices(language)` → `{"voices": [...], "default": "aidar"}`
- HTTP: `GET /api/voices?engine=silerotts&language=ru`

An unknown voice for the language raises `ValidationError` (HTTP `400`).

```python
from engines.silerotts import generate, list_voices

list_voices("ru")  # {'voices': ['aidar', 'baya', ...], 'default': 'aidar'}
audio = generate("Здравствуйте", {"language": "ru", "voice": "baya"})  # female
```

## Usage

### Basic Usage

```bash
# English
python ttsgen.py "Hello world" --engine silerotts

# Russian (excellent quality)
python ttsgen.py "Привет мир" --engine silerotts --language ru

# Spanish
python ttsgen.py "Hola mundo" --engine silerotts --language es

# Save to file
python ttsgen.py "Hello" --engine silerotts --file output.wav

# Play and save
python ttsgen.py "Hello" --engine silerotts --file output.wav --play
```

### First Run

The first time you use Silero TTS for each language:
- Model downloads automatically from PyTorch Hub
- Download size: 50-100MB per model
- Takes 1-5 minutes depending on connection
- Models cached in: `~/.cache/torch/hub/`

### Pre-download Models

To download models ahead of time:

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

To use different speaker, modify `engines/silerotts.py` or create custom engine.

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
# Install dependencies separately
pip install numpy
pip install torch torchaudio

# Try specific version
pip install torch==2.0.0 torchaudio==2.0.0
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
# Install PyTorch
pip install torch torchaudio

# Or use CPU-only version (smaller)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
```

## Resources

- GitHub: https://github.com/snakers4/silero-models
- Voice samples: https://oidmtts.site/
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
pip install torch torchaudio

# 2. Use (model downloads automatically on first run)
python ttsgen.py "Hello world" --engine silerotts

# 3. Russian (recommended - best quality)
python ttsgen.py "Привет мир" --engine silerotts --language ru
```

Models download automatically on first use. No manual model management needed!

