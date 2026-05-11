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
- Zero-shot voice cloning capability

## System Requirements

### Minimum Requirements (CPU)
- Python 3.8-3.11
- 16GB RAM
- 15GB disk space
- CPU: Works but VERY slow (60-180s per sentence)

### Recommended Requirements (GPU)
- Python 3.8-3.11
- 16GB+ RAM
- NVIDIA GPU with 8GB+ VRAM
- 15GB disk space
- CUDA 11.8+

## Installation

### Quick Installation

```bash
# Install Bark from GitHub
pip install git+https://github.com/suno-ai/bark.git

# Install additional dependencies
pip install scipy

# Test installation
python -c "from bark import generate_audio; print('Bark TTS installed')"
```

### Using Installation Script

```bash
# Run installation script
ttsgen --install barktts
```

## Supported Languages

Bark supports many languages through speaker presets:
- English (en)
- Spanish (es)
- French (fr)
- German (de)
- Italian (it)
- Portuguese (pt)
- Polish (pl)
- Turkish (tr)
- Russian (ru)
- Dutch (nl)
- Czech (cs)
- Arabic (ar)
- Chinese (zh)
- Japanese (ja)
- Korean (ko)
- Hindi (hi)

## Usage

### Basic Usage

```bash
# English
python ttsgen.py "Hello world" --engine barktts

# With different language
python ttsgen.py "Hola mundo" --engine barktts --language es

# Save to file
python ttsgen.py "Hello" --engine barktts --file output.wav

# Russian
python ttsgen.py "Привет мир" --engine barktts --language ru
```

### Special Syntax

Bark supports special annotations in text:

```bash
# Laughter
python ttsgen.py "That's hilarious [laugh]" --engine barktts

# Sighing
python ttsgen.py "I'm so tired [sigh]" --engine barktts

# Music (use ♪ symbols)
python ttsgen.py "♪ La la la ♪" --engine barktts

# Emphasis (CAPS)
python ttsgen.py "This is VERY important" --engine barktts

# Pauses (ellipsis)
python ttsgen.py "Wait... what?" --engine barktts

# Combine effects
python ttsgen.py "Oh no! [gasp] That's TERRIBLE [sigh]" --engine barktts
```

### First Run

The first time you use Bark:
- Models download automatically (10-15 GB)
- Can take 30-60 minutes
- Models cached in: `~/.cache/suno/bark_v0/` (path hard-coded by upstream Bark)
- Subsequent runs use cached models

> **Note on `BARKTTS_MODELS`.** Unlike pipertts/silerotts/coquitts/kokorotts, Bark
> hard-codes its model cache path inside the library. Setting
> `BARKTTS_MODELS=<dir>` in `.env` / `~/.config/ttsgen.conf` only affects
> what `ttsgen --list` inspects; it does **not** relocate the actual
> download. If you need the models on another disk, symlink
> `~/.cache/suno/bark_v0/` to that location before the first run.

### Pre-download Models

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

Bark has 100+ speaker presets. To use different voice, modify `engines/barktts.py`:

```python
# Change speaker in get_speaker_for_language()
# Available: v2/en_speaker_0 through v2/en_speaker_9
# And many more variants
```

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
# 1. Use smaller models (modify engines/barktts.py)
# 2. Use GPU with more VRAM
# 3. Use different engine (pipertts, silerotts)
# 4. Reduce text length
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
# Install all dependencies
pip install git+https://github.com/suno-ai/bark.git
pip install scipy numpy
pip install torch torchaudio
```

### PyTorch 2.6+ weights_only error

If you see error about "weights_only" or "numpy.core.multiarray.scalar":
```
WeightsUnpickler error: Unsupported global: GLOBAL numpy.core.multiarray.scalar
```

This is already fixed in the engine code. If issue persists:

**Option 1:** Update to latest code (already includes fix)

**Option 2:** Downgrade PyTorch
```bash
pip install torch==2.5.0 torchaudio==2.5.0
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
python ttsgen.py "Hello, how are you?" --engine barktts
```

### With Emotions
```bash
python ttsgen.py "That's hilarious! [laugh]" --engine barktts
python ttsgen.py "Oh no... [sigh]" --engine barktts
```

### Music
```bash
python ttsgen.py "♪ Happy birthday to you ♪" --engine barktts
```

### Emphasis
```bash
python ttsgen.py "This is VERY IMPORTANT!" --engine barktts
```

### Different Languages
```bash
python ttsgen.py "Привет мир" --engine barktts --language ru
python ttsgen.py "Bonjour le monde" --engine barktts --language fr
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

