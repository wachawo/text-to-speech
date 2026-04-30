# Coqui TTS Installation Guide

## Overview

Coqui TTS (formerly Mozilla TTS) is a state-of-the-art text-to-speech library with support for:
- High-quality natural voices
- Voice cloning (XTTS models)
- Multi-speaker models
- Emotional speech synthesis
- 100+ pre-trained models

## System Requirements

### Python Version Compatibility

**IMPORTANT:** Coqui TTS requires Python 3.9 - 3.11

- Python 3.12+ is NOT supported
- Python 3.8 and below not recommended
- **Requires transformers==4.33.0** (newer versions incompatible)

If you have Python 3.12:
- Use other engines (piper, silerotts, gtts)
- Or install Python 3.11 in separate venv

### Minimum Requirements
- Python 3.9-3.11
- 4GB RAM
- 2GB disk space for models
- CPU: Works but very slow

### Recommended Requirements
- Python 3.9-3.11
- 8GB+ RAM
- NVIDIA GPU with 4GB+ VRAM
- 5GB disk space
- CUDA 11.8+ and cuDNN

## License Notice

**IMPORTANT:** Some Coqui TTS models (like xtts_v2) require license acceptance:

- **Non-commercial use**: Free under CPML license (https://coqui.ai/cpml)
- **Commercial use**: Requires commercial license from Coqui (licensing@coqui.ai)

The system will ask you to accept the license on first use of these models.

## Installation

### Basic Installation (CPU only)

```bash
# Install Coqui TTS with compatible transformers version
pip install TTS transformers==4.33.0

# Test installation
python -c "from TTS.api import TTS; print('Coqui TTS installed successfully')"
```

**Important:** Coqui TTS requires `transformers==4.33.0`. Newer versions cause import errors (`cannot import name 'BeamSearchScorer'`).

**Note:** First run with certain models will prompt for license acceptance.

### GPU Installation (Recommended)

```bash
# Install PyTorch with CUDA support first
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Install Coqui TTS with compatible transformers version
pip install TTS transformers==4.33.0

# Verify GPU support
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
```

### Quick Setup Script

```bash
# Run installation script
ttsgen --install coquitts
```

## Models Storage

### Default Location

Models are stored in `.coquitts/` directory in project root (created automatically during installation).

Example: `/path/to/tts/.coquitts/`

### Custom Location

During installation, you can choose from:
1. **Default:** `.coquitts/` (in project directory)
2. **Standard:** `~/.local/share/tts/` (default Coqui location)
3. **Custom:** any directory you specify

To change directory after installation:

```bash
# Set environment variable
export COQUI_TTS_CACHE_DIR="~/.local/share/tts"

# Or add to .env file
echo "COQUI_TTS_CACHE_DIR=~/.local/share/tts" >> .env
```

## Available Models

### Multilingual Models (Recommended)

**xtts_v2** - Best quality, supports 17 languages
```bash
Model: tts_models/multilingual/multi-dataset/xtts_v2
Languages: en, es, fr, de, it, pt, pl, tr, ru, nl, cs, ar, zh, ja, hu, ko, hi
```

### English Models

**LJSpeech Tacotron2** - Fast, good quality
```bash
Model: tts_models/en/ljspeech/tacotron2-DDC
```

**VITS** - High quality
```bash
Model: tts_models/en/ljspeech/vits
```

### Language-Specific Models

```bash
# Spanish
tts_models/es/mai/tacotron2-DDC

# French  
tts_models/fr/mai/tacotron2-DDC

# German
tts_models/de/thorsten/tacotron2-DDC

# Russian (use multilingual xtts_v2)
tts_models/multilingual/multi-dataset/xtts_v2
```

## Usage

### Basic Usage

```bash
# English (will download model on first use)
python ttsgen.py "Hello world" --engine coquitts

# Russian
python ttsgen.py "Привет мир" --engine coquitts --language ru

# Save to file
python ttsgen.py "Hello" --engine coquitts --file output.wav

# Play and save
python ttsgen.py "Hello" --engine coquitts --file output.wav --play
```

### First Run

The first time you use Coqui TTS, it will download the model:
- Download size: 1-4GB depending on model
- Can take 5-30 minutes

**License prompt for xtts models:**
```
> You must confirm the following:
| > "I have purchased a commercial license from Coqui: licensing@coqui.ai"
| > "Otherwise, I agree to the terms of the non-commercial CPML: https://coqui.ai/cpml" - [y/n]
| | > y
```

Type `y` and press Enter to accept the non-commercial license.

### Pre-download Models

To download models ahead of time:

```bash
python << 'EOF'
from TTS.api import TTS

# Download multilingual model
print("Downloading multilingual model...")
ttsgen = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
print("Download complete!")

# Download English model
print("Downloading English model...")
ttsgen = TTS("tts_models/en/ljspeech/tacotron2-DDC")
print("Download complete!")
EOF
```

## Configuration

### In Python

```python
from libs.api import text_to_speech_bytes

# Generate with Coqui TTS
audio = text_to_speech_bytes(
    text="Hello world",
    engine="coquitts",
    language="en"
)
```

### In .env

```bash
TTS_ENGINE=coquitts
TTS_LANGUAGE=en
DEFAULT_OUTPUT_FORMAT=play
```

## Performance

### CPU Mode (Default)
- Speed: Very slow (10-60 seconds per sentence)
- Quality: High
- Use for: Short texts, testing

### GPU Mode (Requires CUDA)
- Speed: Fast (1-3 seconds per sentence)
- Quality: High
- Use for: Production, long texts

To enable GPU, ensure PyTorch with CUDA is installed:
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

## Advanced Features

### Voice Cloning (XTTS)

Coqui TTS supports voice cloning with XTTS models. This requires:
- Reference audio sample (3-10 seconds)
- XTTS model
- More complex API usage

See Coqui TTS documentation for voice cloning details.

### Multi-Speaker Models

Some models support multiple speakers/voices. Check model documentation.

## Troubleshooting

### ImportError: cannot import name 'BeamSearchScorer'

This error occurs with newer versions of `transformers`. Fix:

```bash
# Uninstall incompatible version
pip uninstall transformers -y

# Install compatible version
pip install transformers==4.33.0

# Reinstall Coqui TTS
pip install TTS
```

### Installation fails

```bash
# Try with compatible transformers version
pip install TTS transformers==4.33.0

# Or try specific TTS version
pip install TTS==0.21.0 transformers==4.33.0

# Or install dependencies separately
pip install numpy scipy librosa
pip install TTS transformers==4.33.0
```

### Model download fails

```bash
# Check internet connection
ping huggingface.co

# Try manual download from:
# https://huggingface.co/coqui

# Clear cache and retry
rm -rf ~/.local/share/tts/
```

### CUDA out of memory

```bash
# Use CPU mode (slower but works)
# The engine automatically uses CPU

# Or use smaller model
# tts_models/en/ljspeech/tacotron2-DDC (smaller than xtts_v2)
```

### Very slow generation

```bash
# This is normal on CPU
# Solutions:
# 1. Use GPU (install CUDA + PyTorch with CUDA)
# 2. Use different engine (piper, gtts)
# 3. Use smaller/faster model
```

## Comparison with Other Engines

| Engine | Quality | Speed (CPU) | Size | Offline |
|--------|---------|-------------|------|---------|
| Coqui TTS | 5/5 | 1/5 | 1-4GB | Yes |
| Piper | 4/5 | 5/5 | 50MB | Yes |
| gtts | 4/5 | 5/5 | 0MB | No |
| pyttsx3 | 2/5 | 5/5 | 5MB | Yes |

## Recommendations

- **For production**: Use GPU with Coqui TTS or use Piper (fast on CPU)
- **For best quality**: Coqui TTS with GPU
- **For fast CPU**: Piper
- **For online**: gtts

## Resources

- Official docs: https://github.com/coqui-ai/TTS
- Models: https://github.com/coqui-ai/TTS#released-models
- Voice samples: https://github.com/coqui-ai/TTS#example-demos

## Model List

To see all available models:
```bash
python -c "from TTS.api import TTS; print(TTS().list_models())"
```

## Samples

To generate samples:
```bash
ffmpeg -i input.ogg -ar 48000 -ac 1 -c:a pcm_s16le output_48k.wav
ffmpeg -i input.ogg -ar 22050 -ac 1 -c:a pcm_s16le output_22k.wav
```

## Notes

- First run downloads model (slow)
- Models cached after first download
- GPU highly recommended for practical use
- CPU mode works but very slow
- Excellent for high-quality offline TTS with GPU
- Consider Piper for fast CPU inference

