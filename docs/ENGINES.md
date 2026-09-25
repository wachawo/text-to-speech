# TTS Engines - Modular Engine System

## Overview

All TTS engines are stored in the `engines/` directory and loaded dynamically.
Each engine is an optional module that can be installed as needed.

## Engine Comparison

The engine table (offline, hardware, quality, what each engine is good for)
lives in the [README](../README.md#engines); it is not repeated here.

### Best Engines by Language

- **English**: pipertts, kokorotts, coquitts, barktts
- **Russian**: silerotts, pipertts, coquitts, barktts
- **Spanish/French/German**: pipertts, coquitts, barktts, gtts
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
- Install: part of the base `pip install`

**pyttsx3**
- Pros: Offline, fast, small
- Cons: Poor quality (robotic)
- Install: part of the base `pip install` (plus the system `espeak` package on Linux)

**pipertts**
- Pros: Fast on CPU, good quality, small models, no torch dependency
- Cons: One voice per language; the installer ships five languages, more are in the Piper catalogue
- Install: `ttsgen --install pipertts` (installs `piper-tts` and downloads the voices you pick)
- Docs: docs/PIPERTTS.md

**silerotts**
- Pros: Fast on CPU, excellent Russian, several speakers per language
- Cons: Limited languages (6)
- Install: `ttsgen --install silerotts` (torch from the right wheel index, `omegaconf`, optional model pre-download)
- Docs: docs/SILEROTTS.md

**coquitts**
- Pros: Best quality, 100+ languages, voice cloning
- Cons: Slow on CPU (GPU recommended)
- Install: `ttsgen --install coquitts` (installs `coqui-tts[codec]`, the maintained Idiap fork; the upstream `TTS` package is abandoned and breaks under torch 2.9+)
- Docs: docs/COQUITTS.md

**barktts**
- Pros: Most realistic, emotions, music, singing
- Cons: Very slow, large models (10GB), high memory
- Install: `ttsgen --install barktts`
- Docs: docs/BARKTTS.md

**kokorotts**
- Pros: Fast on CPU, ONNX runtime, multi-language voices
- Cons: ~340 MB ONNX model, requires download from upstream release
- Install: `ttsgen --install kokorotts` (kokoro-onnx + onnxruntime + soundfile)
- Docs: docs/KOKOROTTS.md

Engines that depend on PyTorch (silerotts, coquitts, barktts) get it from an
explicit wheel index, `https://download.pytorch.org/whl/cpu` or
`https://download.pytorch.org/whl/cu121`. The default PyPI index ships wheels
built for a newer CUDA that fail on NVIDIA drivers below about 580, which is why
`ttsgen --install <engine>` picks the index for you instead of a plain
`pip install torch`. There are no pip extras for engines; the installer is the
only supported path.

## Where models live

Every engine with model files reads one environment variable, `<ENGINE>_MODELS`:
`PIPERTTS_MODELS`, `SILEROTTS_MODELS`, `COQUITTS_MODELS`, `BARKTTS_MODELS`,
`KOKOROTTS_MODELS`. `ttsgen --install <engine>` asks once where the models
should go (`install/common.py:resolve_models_dir`):

1. **Default** - the system location of that engine, for example
   `~/.local/share/ttsgen/pipertts` or `~/.cache/torch/hub`.
2. **Project-local** - `cache/<engine>/` in the project root.
3. **Custom** - any directory you type.

The answer is written to `~/.config/ttsgen.conf` as `<ENGINE>_MODELS=<path>`,
so synthesis later finds the same directory. When the variable is already set
(shell, `./ttsgen.conf`, `~/.config/ttsgen.conf`, `.env`) the installer uses it
without asking; `--non-interactive` takes the default silently.

At synthesis time an engine resolves its directory in this order:
`<ENGINE>_MODELS` (a relative path is anchored to the project root), then
`cache/<engine>/` if it exists, then the engine's own default. Each engine doc
lists only its variable and that default. Bark is the exception: upstream
hard-codes `~/.cache/suno/bark_v0`, see [docs/BARKTTS.md](BARKTTS.md).

Config precedence for these variables, strongest first: CLI flags > shell
environment > `./ttsgen.conf` > `~/.config/ttsgen.conf` > `./.env.local` >
`./.env`. Files never override the shell, and `.env` is read only from the
current directory.

## Structure

```
engines/
├── __init__.py       # Dynamic engine loader
├── gtts.py           # Google TTS (online)
├── pyttsx3.py        # espeak TTS (offline, basic)
├── pipertts.py       # Piper TTS (offline, high-quality)
├── silerotts.py      # Silero TTS (offline, Russian)
├── coquitts.py       # Coqui TTS (offline, best quality)
├── barktts.py        # Bark TTS (offline, emotions)
└── kokorotts.py      # Kokoro TTS (offline, ONNX, multi-language)
```

Drop a new `engines/<name>.py` to add an engine - see [Creating a Custom Engine](#creating-a-custom-engine) below.

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

### 2. Contract: engines return bytes only

Engines **must not** write files, play audio, or print to stdout. The
return value of `generate()` is the only output. File I/O lives in
`libs/api.py` (`text_to_speech_file`, `text_to_speech_bytesio`); playback
lives in `libs/playback.py`. Adding `to_file()` / `to_bytes()` inside an
engine is a layering violation and will not be picked up by the loader
(`engines/__init__.py` calls `generate()` only).

### 3. Optional language list

```python
def list_languages() -> list[str] | None:
    """Return the language codes the engine serves, or None when not declared."""
```

`engines/__init__.py:get_engine_languages` calls it when it exists. It must
read only constants or metadata (never load a model, never touch the network),
and it works whether or not the engine is available. The server uses it for
`TTS_LANGUAGE_STRICT`: a language that is not listed, neither as a whole nor by
its primary subtag (`en` covers `en-gb`), is refused with a 400. An engine
without the hook, or one that returns None (pyttsx3 has no hook; coquitts
returns None for a multilingual model other than xtts), accepts every code, and
a hook that raises is logged and treated as None.

### 4. Config Parameters

```python
config = {
    'language': 'en',     # Language (required): a 2-character code or a tag
                          # such as 'zh-cn' or 'pt-br', lowercased with '-';
                          # look a tag up by libs.languages.primary_language()
                          # when the engine keys its tables by 2-letter codes
    'rate': 150,          # Speech rate (optional)
    'volume': 0.9,        # Volume (optional)
    'slow': False,        # Slow speech (optional)
    # ... any other parameters
}
```

## Creating a Custom Engine

### Example: engines/custom.py

```python
"""Custom TTS Engine - short description of what this engine does."""

import logging

from libs.exceptions import EngineNotAvailableError, TTSException

logger = logging.getLogger(__name__)

try:
    import your_tts_library  # type: ignore
    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    logger.warning("Custom TTS not available. Install with: pip install your-package")


def is_available() -> bool:
    """True if all deps are importable."""
    return AVAILABLE


def generate(text: str, config: dict) -> bytes:
    """Synthesize and return audio bytes (WAV or MP3).

    Args:
        text: Text to synthesize.
        config: {'language': 'en', 'rate': 150, 'volume': 0.9, ...}.

    Raises:
        EngineNotAvailableError: deps missing.
        TTSException: synthesis failed.
    """
    if not AVAILABLE:
        raise EngineNotAvailableError("Custom TTS not available")

    try:
        language = config.get("language", "en")
        tts = your_tts_library.TTS()
        return tts.synthesize(text, lang=language)
    except Exception as exc:
        raise TTSException(f"Custom TTS generation failed: {type(exc).__name__}: {exc}")
```

### Usage

```bash
# Just specify the filename (without .py)
ttsgen "Hello world" --engine custom

# Save to file
ttsgen "Hello world" --engine custom --file output.wav

# Different language
ttsgen "Hola" --engine custom --language es
```

## Built-in Engines

### gtts.py
- **Description**: Google Text-to-Speech (online)
- **Dependencies**: base install
- **Format**: MP3
- **Languages**: 100+ languages
- **Quality**: 4/5
- **Usage**: `--engine gtts`

### pyttsx3.py
- **Description**: Offline TTS via espeak
- **Dependencies**: base install + `sudo apt install espeak`
- **Format**: WAV
- **Languages**: 50+ languages
- **Quality**: 2/5
- **Usage**: `--engine pyttsx3`

### pipertts.py
- **Description**: High-quality offline TTS
- **Dependencies**: `ttsgen --install pipertts` (package + voice models)
- **Format**: WAV (22050 Hz)
- **Languages**: en, ru, es, de, fr, it, uk, zh are mapped to a voice; other codes fall back to the English voice
- **Quality**: 4/5
- **Usage**: `--engine pipertts`
- **Documentation**: See [docs/PIPERTTS.md](PIPERTTS.md)

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

if is_engine_available('pipertts'):
    print("Piper is available!")
else:
    print("Piper not available - check installation")
```

### Load Engine

```python
from engines import load_engine

pipertts = load_engine('pipertts')
if pipertts:
    audio = pipertts.generate("Hello", {'language': 'en'})
    print(f"Generated {len(audio)} bytes")
```

## List All Available Engines

Run:
```bash
python -c "from engines import get_available_engines; print('\n'.join(get_available_engines().keys()))"
```

## Adding New Engine

1. Create `engines/myengine.py` with `is_available()` and `generate()`; keep the
   optional imports inside `try/except ImportError` so the module loads with
   `AVAILABLE = False` when the dependency is missing. Add `list_voices(language)`
   if the engine has selectable voices (`engines/__init__.py:get_engine_voices`),
   and `list_languages()` if it serves a known set of languages.
2. Do not add the engine's packages to `requirements.txt` or to a pip extra.
   Write `install/myengine.py` with an `install(non_interactive)` function that
   pip-installs the dependency (torch through `install_torch_choice()`), resolves
   the model directory with `resolve_models_dir()` and downloads the models; then
   add the name to `INSTALLERS` in `install/__init__.py`.
3. Add `docs/MYENGINE.md` (env keys, default model directory, usage) and link it
   from this file.
4. Add `tests/test_myengine.py` with the dependency faked in `sys.modules`, as
   `tests/test_kokorotts.py` does, so the suite runs without the package.
5. Use: `ttsgen --install myengine`, then `ttsgen "text" --engine myengine`.

The loader needs no change: `engines/__init__.py` picks up any module in the directory.
