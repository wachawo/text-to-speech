# TTS Engines - Modular Engine System

## Overview

All TTS engines are stored in the `engines/` directory and loaded dynamically.
Each engine is an optional module that can be installed as needed.

## Engine Comparison

### Quick Comparison Table

| Engine | Quality | CPU Speed | Size | Offline | Best For |
|--------|---------|-----------|------|---------|----------|
| gtts | 4/5 | Fast | 0MB | No | Online, simple setup |
| pyttsx3 | 2/5 | Fast | 5MB | Yes | Basic offline |
| pipertts | 4/5 | Very Fast | 50MB | Yes | Fast offline, English |
| silerotts | 4/5 | Very Fast | 60MB | Yes | Fast offline, Russian |
| coquitts | 5/5 | Slow* | 1-4GB | Yes | Best quality + GPU |
| barktts | 5/5 | Very Slow* | 10GB | Yes | Emotions + music |

*Fast with GPU

### Best Engines by Language

- **English**: pipertts, coquitts, barktts
- **Russian**: silerotts, coquitts, barktts
- **Spanish/French/German**: coquitts, barktts, gtts
- **100+ languages**: gtts (online), coquitts (offline)

### Recommendations

- **Fast offline + good quality**: pipertts or silerotts
- **Best quality with GPU**: coquitts or barktts
- **Emotions/music**: barktts (only option)
- **Russian language**: silerotts
- **Simple online**: gtts
- **Minimal setup**: pyttsx3

### Engine Details

**gtts**
- Pros: Simple, online, 100+ languages
- Cons: Requires internet
- Install: `pip install gtts`

**pyttsx3**
- Pros: Offline, fast, small
- Cons: Poor quality (robotic)
- Install: `pip install pyttsx3`

**pipertts**
- Pros: Fast on CPU, good quality, small models
- Cons: Manual model download
- Install: `pip install piper-tts` + models
- Docs: docs/PIPERTTS.md

**silerotts**
- Pros: Fast on CPU, excellent Russian, auto-download
- Cons: Limited languages (6)
- Install: `pip install torch torchaudio omegaconf`
- Docs: docs/SILEROTTS.md

**coquitts**
- Pros: Best quality, 100+ languages, voice cloning
- Cons: Slow on CPU, Python 3.9-3.11 only
- Install: `pip install TTS`
- Docs: docs/COQUITTS.md

**barktts**
- Pros: Most realistic, emotions, music, singing
- Cons: Very slow, large models (10GB), high memory
- Install: `pip install git+https://github.com/suno-ai/bark.git scipy`
- Docs: docs/BARKTTS.md

## Structure

```
engines/
├── __init__.py       # Dynamic engine loader
├── gtts.py      # Google TTS (online)
├── pyttsx3.py        # espeak TTS (offline, basic)
├── pipertts.py       # Piper TTS (offline, high-quality)
├── silerotts.py      # Silero TTS (offline, Russian)
├── coquitts.py       # Coqui TTS (offline, best quality)
├── barktts.py        # Bark TTS (offline, emotions)
└── custom.py         # Your custom engines
```

## Engine Interface

Each engine must implement:

### 1. Required Functions

```python
def is_available() -> bool:
    """Check if engine is available (dependencies installed)."""
    return True  # or False

def generate(text: str, config: dict) -> bytes:
    """Generate audio and return as bytes."""
    # Your implementation
    return audio_bytes
```

### 2. Optional Functions

```python
def to_file(text: str, filename: str, config: dict) -> str:
    """Generate and save to file."""
    # If not implemented, will be auto-generated from generate()
    pass

def to_bytes(text: str, config: dict) -> bytes:
    """Generate and return bytes."""
    # If not implemented, will use generate()
    pass
```

### 3. Config Parameters

```python
config = {
    'language': 'en',     # Language (required)
    'rate': 150,          # Speech rate (optional)
    'volume': 0.9,        # Volume (optional)
    'slow': False,        # Slow speech (optional)
    # ... any other parameters
}
```

## Creating a Custom Engine

### Example: engines/custom.py

```python
"""
Custom TTS Engine

Description of your custom engine.
"""

import logging
import sys
from pathlib import Path as PathLib
sys.path.insert(0, str(PathLib(__file__).parent.parent / 'libs'))
from exceptions import EngineNotAvailableError, TTSException

logger = logging.getLogger(__name__)

# Try to import your dependencies
try:
    import your_tts_library
    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    logger.warning("Custom TTS not available. Install with: pip install your-package")


def is_available() -> bool:
    """Check if engine is available."""
    return AVAILABLE


def generate(text: str, config: dict) -> bytes:
    """
    Generate audio and return as bytes.
    
    Args:
        text: Text to synthesize
        config: Configuration dict with 'language', etc.
    
    Returns:
        Audio bytes (WAV or MP3)
    """
    if not AVAILABLE:
        raise EngineNotAvailableError("Custom TTS not available")
    
    try:
        # Your implementation
        language = config.get('language', 'en')
        
        # Use your library
        tts = your_tts_library.TTS()
        audio_bytes = tts.synthesize(text, lang=language)
        
        return audio_bytes
        
    except Exception as e:
        raise TTSException(f"Custom TTS generation failed: {e}")
```

### Usage

```bash
# Just specify the filename (without .py)
python tts.py "Hello world" --engine custom

# Save to file
python tts.py "Hello world" --engine custom --file output.wav

# Different language
python tts.py "Hola" --engine custom --language es
```

## Built-in Engines

### gtts.py
- **Description**: Google Text-to-Speech (online)
- **Dependencies**: `pip install gtts`
- **Format**: MP3
- **Languages**: 100+ languages
- **Quality**: 4/5
- **Usage**: `--engine gtts`

### pyttsx3.py
- **Description**: Offline TTS via espeak
- **Dependencies**: `pip install pyttsx3` + `sudo apt install espeak`
- **Format**: WAV
- **Languages**: 50+ languages
- **Quality**: 2/5
- **Usage**: `--engine pyttsx3`

### piper.py
- **Description**: High-quality offline TTS
- **Dependencies**: `pip install piper-tts` + download models
- **Format**: WAV (22050 Hz)
- **Languages**: 50+ languages
- **Quality**: 5/5
- **Usage**: `--engine piper`
- **Documentation**: See docs/PIPER.md

## Benefits of Modular System

- **Optional** - Install only needed engines
- **Extensible** - Easy to add new engines
- **Auto-detection** - System automatically detects availability
- **Graceful degradation** - Informative errors if engine unavailable
- **No coupling** - Engines are independent

## Debugging

### Check Available Engines

```python
from engines import get_available_engines

engines = get_available_engines()
print(f"Available engines: {list(engines.keys())}")
```

### Check Specific Engine

```python
from engines import is_engine_available

if is_engine_available('piper'):
    print("Piper is available!")
else:
    print("Piper not available - check installation")
```

### Load Engine

```python
from engines import load_engine

piper = load_engine('piper')
if piper:
    audio = piper.generate("Hello", {'language': 'en'})
    print(f"Generated {len(audio)} bytes")
```

## List All Available Engines

Run:
```bash
python -c "from engines import get_available_engines; print('\n'.join(get_available_engines().keys()))"
```

## Adding New Engine

1. Create `engines/myengine.py`
2. Implement `is_available()` and `generate()`
3. Add dependencies to `requirements.txt` (optional)
4. Use: `python tts.py "text" --engine myengine`

Done! No changes to core code required.
