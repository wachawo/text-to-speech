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

This project uses the **Idiap community fork** (`coqui-tts`), which supports
modern Python and PyTorch - unlike the abandoned upstream `TTS` package.

- Python 3.11+ (the Docker images use 3.12)
- Pinned `transformers>=4.46,<5.0` (the version the fork needs under torch 2.9+)

### Minimum Requirements
- Python 3.11+
- 4GB RAM
- 2GB disk space for models
- CPU: Works but very slow

### Recommended Requirements
- Python 3.11+
- 8GB+ RAM
- NVIDIA GPU with 4GB+ VRAM
- 5GB disk space
- NVIDIA driver 525+ (the installer uses the CUDA 12.1 wheel index)

## License Notice

**IMPORTANT:** Some Coqui TTS models (like xtts_v2) require license acceptance:

- **Non-commercial use**: Free under CPML license (https://coqui.ai/cpml)
- **Commercial use**: Requires commercial license from Coqui (licensing@coqui.ai)

The system will ask you to accept the license on first use of these models.

## Installation

### Installer (CPU or GPU)

```bash
ttsgen --install coquitts

# Test installation
python -c "from TTS.api import TTS; print('Coqui TTS installed successfully')"

# Verify GPU support
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
```

The installer asks where to store the models and the voice sample, installs
PyTorch from an explicit wheel index (`https://download.pytorch.org/whl/cpu`
or `https://download.pytorch.org/whl/cu121`, your choice), then installs
`coqui-tts[codec]` with `transformers>=4.46,<5.0` and offers to pre-download a
model. The default PyPI index ships torch wheels built for a newer CUDA that
fail on NVIDIA drivers below about 580, which is why the installer picks the
index for you.

**Note:** This project pins `transformers>=4.46,<5.0` - the version the Idiap fork needs under torch 2.9+.

**Note:** First run with certain models will prompt for license acceptance.

### Manual install

Only if you cannot run the installer:

```bash
# PyTorch first, from the explicit index (cpu or cu121)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121

# Then the fork with the compatible transformers range
pip install "coqui-tts[codec]" "transformers>=4.46,<5.0"
```

## Models Storage

Environment variable: `COQUITTS_MODELS`. Installer default:
`~/.local/share/tts/` (Coqui's own `TTS_HOME`); the project-local choice is
`cache/coquitts/`. Without the variable the engine falls back to
`cache/coquitts` under the current directory. The three-way prompt and how the
answer is persisted are described in
[ENGINES.md, "Where models live"](ENGINES.md#where-models-live).

To change the directory after installation:

```bash
# Set environment variable
export COQUITTS_MODELS="$HOME/.local/share/tts"

# Or persist to ~/.config/ttsgen.conf
echo "COQUITTS_MODELS=$HOME/.local/share/tts" >> ~/.config/ttsgen.conf
```

`engines/coquitts.py` then tunnels this through to Coqui's own
`TTS_HOME` at runtime - you don't set `TTS_HOME` directly.

Other variables: `COQUITTS_MODEL` (model id, default
`tts_models/multilingual/multi-dataset/xtts_v2`, CLI flag `--coqui-model`),
`COQUITTS_SAMPLE` (reference voice WAV, default `~/.config/ttsgen.wav`, CLI
flag `--coqui-sample`) and `COQUITTS_SAMPLES` (directory of named voice
samples, default `samples`), see [Voice Samples](#voice-samples).

## Available Models

### Multilingual Models (Recommended)

**xtts_v2** - Best quality, supports 17 languages
```bash
Model: tts_models/multilingual/multi-dataset/xtts_v2
Languages: en, es, fr, de, it, pt, pl, tr, ru, nl, cs, ar, zh, ja, hu, ko, hi
```

xtts names Chinese `zh-cn`; the engine sends `zh` (what `--language zh`, the
API and the web UI use) to xtts as `zh-cn`. Any other tag is sent as its
language part (`pt-br` is `pt`).

With `TTS_LANGUAGE_STRICT=true` the server checks the languages of
`COQUITTS_MODEL`: xtts lists its codes plus `zh`, and a single-language model
lists its language (a region model such as `tts_models/zh-CN/baker/...` lists
both `zh-cn` and `zh`). Any other multilingual model, such as `your_tts`, lists
none, so every code passes the check. So does a single-language model whose
language code has three letters (`tts_models/ewe/openbible/vits`): a request
can only carry a 2-character code or a tag, so listing `ewe` would refuse
every request.

### Selecting a model per request

The model id is the Coqui model name, the same spelling as `COQUITTS_MODEL`
(`tts_models/de/thorsten/vits`). `GET /api/engines/coquitts` lists the models
already in the cache (`<COQUITTS_MODELS>/tts/tts_models--*`, shown with `/`)
plus `COQUITTS_MODEL`, which is listed with `installed: false` until its first
download. No other model that is not on disk is listed, so a request never
starts the download of an arbitrary model: pre-download one (see
[Pre-download Models](#pre-download-models)) to make it selectable. Each model
lists its languages as above (xtts its codes plus `zh`, a single-language
model its language, other multilingual models none).

```bash
curl -X POST localhost:5000/api/tts \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hallo Welt","engine":"coquitts","language":"de","model":"tts_models/de/thorsten/vits"}' -o out.wav
```

The `zh` to `zh-cn` mapping follows the model the request loads, so it applies
whenever that model is xtts. Without a model `COQUITTS_MODEL` is used as
before. The voice samples are shared by every model. An id that is not listed
is a 400.

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
ttsgen "Hello world" --engine coquitts

# Spanish
ttsgen "Hola mundo" --engine coquitts --language es

# Save to file
ttsgen "Hello" --engine coquitts --file output.wav

# Play and save
ttsgen "Hello" --engine coquitts --file output.wav --play

# Pick a model or a reference voice for this run
ttsgen "Hello" --engine coquitts --coqui-model tts_models/en/ljspeech/tacotron2-DDC
ttsgen "Hello" --engine coquitts --coqui-sample samples/maria.wav
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

`ttsgen --install coquitts` offers to pre-download a model. To do it by hand:

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

To enable GPU, pick the CUDA build when `ttsgen --install coquitts` asks, or
install it by hand from the same index:
```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
```

## Advanced Features

### Voice Samples

xtts_v2 clones the voice of a reference WAV; this is the only form of voice
selection the engine has. Samples live in the directory named
by `COQUITTS_SAMPLES` (default `samples`, `/opt/samples` in Docker). `COQUITTS_SAMPLE`
picks the default one (`~/.config/ttsgen.wav` unless set); a bare file name is
looked up in that directory. `--coqui-sample PATH` overrides it for one run.

On the server every `*.wav` in the directory is a voice: the `voice` field of a
request is the sample's file name without `.wav`, so `samples/maria.wav` is
`"voice": "maria"`. `GET /api/voices?engine=coquitts` lists them and
`POST /api/voices` uploads a new one.

A good sample is:
- WAV, PCM 16-bit, mono, 22050 Hz
- 5-10 seconds of clean speech from one speaker
- no music, echo or background noise

`ttsrec` records such a sample from the microphone (16-bit mono, 22050 Hz) and
persists the path as `COQUITTS_SAMPLE`, so the recording becomes the default voice:

```bash
ttsrec                          # records to the current COQUITTS_SAMPLE path
ttsrec samples/maria.wav        # records a named voice into the samples directory
```

### Multi-Speaker Models

Some models support multiple speakers/voices. Check model documentation.

## Troubleshooting

### transformers import errors

This project pins `transformers>=4.46,<5.0`. The 5.x line removes symbols the
fork still imports, and very old releases lack others. If you hit a
`cannot import name ...` error from `transformers`, install the pinned range:

```bash
pip install "coqui-tts[codec]" "transformers>=4.46,<5.0"
```

### Installation fails

```bash
# Use the pinned versions from this project (works under torch 2.9+):
pip install "coqui-tts[codec]" "transformers>=4.46,<5.0"

# If you need dependencies separately:
pip install numpy scipy librosa
pip install "coqui-tts[codec]" "transformers>=4.46,<5.0"
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
# 2. Use different engine (pipertts, gtts)
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

- Maintained fork (the `coqui-tts` package this project installs): https://github.com/idiap/coqui-ai-TTS
- Fork documentation: https://coqui-tts.readthedocs.io/
- Model list: `python -c "from TTS.api import TTS; print(TTS().list_models())"`

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

