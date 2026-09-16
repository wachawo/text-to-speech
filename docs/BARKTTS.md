# Bark TTS (barktts) Installation Guide

## Overview

Bark is a transformer-based text-to-audio model by Suno AI that can generate highly realistic speech with:
- Natural prosody and intonation
- Emotions (laughing, sighing, crying)
- Music and singing
- Background sounds
- Multiple languages

## Features

- Ultra-realistic speech
- Emotions and sound effects
- Music generation
- Non-verbal sounds (laugh, sigh, gasp)
- Speaker voices (100+ presets)
- Multilingual support

## System Requirements

### Minimum Requirements (CPU)
- Python 3.11+ (the Docker images use 3.12)
- 16GB RAM
- 15GB disk space
- CPU: Works but VERY slow (60-180s per sentence)

### Recommended Requirements (GPU)
- Python 3.11+
- 16GB+ RAM
- NVIDIA GPU with 8GB+ VRAM
- 15GB disk space
- NVIDIA driver 525+ (the installer uses the CUDA 12.1 wheel index)

## Installation

### Quick Installation

```bash
ttsgen --install barktts

# Test installation
python -c "from bark import generate_audio; print('Bark TTS installed')"
```

The installer checks free disk space (about 15 GB), installs PyTorch from an
explicit wheel index (`https://download.pytorch.org/whl/cpu` or
`https://download.pytorch.org/whl/cu121`, your choice), installs Bark from
GitHub plus `scipy` and `numpy`, and offers to pre-download the weights. The
default PyPI index ships torch wheels built for a newer CUDA that fail on
NVIDIA drivers below about 580, which is why the installer picks the index.

### Manual install

Only if you cannot run the installer:

```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install git+https://github.com/suno-ai/bark.git scipy numpy
```

## Supported Languages

Bark supports many languages through speaker presets. `engines/barktts.py`
maps these `--language` codes to a preset:
- English (en)
- Spanish (es)
- French (fr)
- German (de)
- Italian (it)
- Portuguese (pt)
- Polish (pl)
- Turkish (tr)
- Russian (ru)
- Chinese (zh)
- Japanese (ja)
- Korean (ko)
- Hindi (hi)

Any other code (for example `nl`, `cs`, `ar`) falls back to the English preset.

## Usage

### Basic Usage

```bash
# English
ttsgen "Hello world" --engine barktts

# With different language
ttsgen "Hola mundo" --engine barktts --language es

# Save to file
ttsgen "Hello" --engine barktts --file output.wav

# German
ttsgen "Hallo Welt" --engine barktts --language de
```

### Special Syntax

Bark supports special annotations in text:

```bash
# Laughter
ttsgen "That's hilarious [laugh]" --engine barktts

# Sighing
ttsgen "I'm so tired [sigh]" --engine barktts

# Music (use ♪ symbols)
ttsgen "♪ La la la ♪" --engine barktts

# Emphasis (CAPS)
ttsgen "This is VERY important" --engine barktts

# Pauses (ellipsis)
ttsgen "Wait... what?" --engine barktts

# Combine effects
ttsgen "Oh no! [gasp] That's TERRIBLE [sigh]" --engine barktts
```

### First Run

The first time you use Bark:
- Models download automatically (10-15 GB)
- Can take 30-60 minutes
- Models cached in: `~/.cache/suno/bark_v0/` (path hard-coded by upstream Bark)
- Subsequent runs use cached models

> **Note on `BARKTTS_MODELS`.** Unlike pipertts/silerotts/coquitts/kokorotts, Bark
> resolves its cache path (`$XDG_CACHE_HOME/suno/bark_v0`) inside the library
> when it is imported, and `ttsgen --install barktts` does not ask where to
> put the models. The engine reads `BARKTTS_MODELS` (default
> `~/.cache/suno/bark_v0`, or `cache/barktts/` in the project root if that
> exists) only to report it and for `ttsgen --list`; it does **not** relocate
> the download. If you need the models on another disk, symlink
> `~/.cache/suno/bark_v0/` to that location before the first run. See
> [ENGINES.md, "Where models live"](ENGINES.md#where-models-live).

### Pre-download Models

`ttsgen --install barktts` offers to pre-download the weights. To do it by hand:

```bash
python << 'EOF'
from bark import preload_models

print("Downloading Bark models (this will take time)...")
print("Text model, coarse model, fine model...")

preload_models()

print("All models downloaded and cached!")
EOF
```

## Configuration

### In Python

```python
from libs.api import text_to_speech_bytes

# Generate with Bark
audio = text_to_speech_bytes(
    text="Hello world!",
    engine="barktts",
    language="en"
)
```

### In .env

```bash
TTS_ENGINE=barktts
TTS_LANGUAGE=en
DEFAULT_OUTPUT_FORMAT=play
```

## Performance

### CPU Mode (Default)
- Speed: Very slow (60-180 seconds per sentence)
- Quality: Excellent (5/5)
- Memory: 8-16GB
- Use for: Testing only

### GPU Mode (Recommended)
- Speed: Moderate (10-30 seconds per sentence)
- Quality: Excellent (5/5)
- Memory: 8GB+ VRAM
- Use for: Production

## Advanced Features

### Voice Selection

Bark ships 100+ speaker presets (`v2/<lang>_speaker_0` to `_9`), but this
engine does not expose them: it picks one fixed preset per `--language`
(`engines/barktts.py:get_speaker_for_language`, for example `v2/en_speaker_6`
for English and `v2/ru_speaker_0` for Russian) and ignores the `voice`
parameter. Voice choice is available in silerotts (speakers), kokorotts
(`KOKOROTTS_VOICE`) and coquitts (reference samples).

### Emotion Control

Use text annotations:
- `[laugh]` - Laughter
- `[sigh]` - Sighing
- `[gasp]` - Surprise
- `[clears throat]` - Throat clearing
- `♪ singing ♪` - Singing/music

### Long Text

For texts longer than one sentence, Bark processes each sentence:
- Automatic sentence splitting
- Consistent voice across sentences
- Natural prosody

## Model Cache Location

- Linux: `~/.cache/suno/bark_v0/`
- macOS: `~/.cache/suno/bark_v0/`
- Windows: `%USERPROFILE%\.cache\suno\bark_v0\`

Models include:
- `text_2.pt` (Text encoder, ~1GB)
- `coarse_2.pt` (Coarse model, ~5GB)
- `fine_2.pt` (Fine model, ~5GB)

## Troubleshooting

### Out of memory

```bash
# Bark requires significant RAM/VRAM
# Solutions:
# 1. Use GPU with more VRAM
# 2. Use different engine (pipertts, silerotts)
# 3. Reduce text length
```

### Very slow generation

```bash
# This is normal on CPU
# Bark is computationally expensive
# Solutions:
# 1. Use GPU (much faster)
# 2. Pre-generate audio files
# 3. Use faster engine (pipertts, silerotts) for real-time
```

### Model download fails

```bash
# Clear cache and retry
rm -rf ~/.cache/suno/bark_v0/

# Or download manually from:
# https://huggingface.co/suno/bark
```

### Import errors

```bash
# Re-run the installer; it installs torch from the right wheel index
ttsgen --install barktts
```

### PyTorch 2.6+ weights_only error

If you see error about "weights_only" or "numpy.core.multiarray.scalar":
```
WeightsUnpickler error: Unsupported global: GLOBAL numpy.core.multiarray.scalar
```

This is already fixed in the engine code. If issue persists:

**Option 1:** Update to latest code (already includes fix)

**Option 2:** Downgrade PyTorch (from the explicit index, see Installation)
```bash
pip install torch==2.5.0 torchaudio==2.5.0 --index-url https://download.pytorch.org/whl/cu121
```

**Option 3:** The engine automatically adds numpy globals to safe list for PyTorch 2.6+

## Comparison

### Bark vs Other Engines

| Feature | Bark | Coqui | Silero | Piper |
|---------|------|-------|--------|-------|
| Quality | 5/5 | 5/5 | 4/5 | 4/5 |
| Speed (CPU) | 0/5 | 1/5 | 5/5 | 5/5 |
| Emotions | Yes | No | No | No |
| Music | Yes | No | No | No |
| Model Size | 10GB | 1-4GB | 60MB | 50MB |
| GPU | Highly Recommended | Recommended | Optional | Not Needed |

### When to Use Bark

**Use Bark when:**
- Need most realistic speech
- Want emotions/laughter
- Need music/singing
- Quality is priority over speed
- Have GPU with 8GB+ VRAM

**Don't use Bark when:**
- Need real-time generation
- Limited memory/disk space
- CPU-only system
- Simple TTS sufficient

## Recommendations

- **For production**: Use GPU, pre-generate audio
- **For development**: Use faster engines (pipertts, silerotts)
- **For emotions**: Bark is unique
- **For speed**: Use pipertts or silerotts instead

## Resources

- GitHub: https://github.com/suno-ai/bark
- HuggingFace: https://huggingface.co/suno/bark
- Demo: https://huggingface.co/spaces/suno/bark
- Paper: https://arxiv.org/abs/2301.12597

## Examples

### Simple Speech
```bash
ttsgen "Hello, how are you?" --engine barktts
```

### With Emotions
```bash
ttsgen "That's hilarious! [laugh]" --engine barktts
ttsgen "Oh no... [sigh]" --engine barktts
```

### Music
```bash
ttsgen "♪ Happy birthday to you ♪" --engine barktts
```

### Emphasis
```bash
ttsgen "This is VERY IMPORTANT!" --engine barktts
```

### Different Languages
```bash
ttsgen "Hola mundo" --engine barktts --language es
ttsgen "Bonjour le monde" --engine barktts --language fr
```

## Notes

- First run downloads 10-15GB of models
- Very slow on CPU (60-180s per sentence)
- GPU highly recommended (10-30s per sentence)
- Excellent quality, most natural sounding
- Supports emotions and non-verbal sounds
- Large memory footprint
- Best for: audiobook narration, character voices, emotional speech
- Not for: real-time applications, low-resource systems

