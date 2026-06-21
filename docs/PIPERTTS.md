# Piper TTS

Offline high-quality TTS via [Piper](https://github.com/rhasspy/piper) —
ONNX models trained per voice/language, ~10× realtime on CPU.

## Quick install

```bash
ttsgen --install pipertts
```

That command:
1. Installs `piper-tts` (CPU-friendly, no torch dependency).
2. Lets you pick the voices to download.
3. Stores models under `cache/pipertts/` in the project root (or another
   directory if you choose «Standard»/«Custom» at the prompt).

Use `--non-interactive` to accept defaults — installs `en_US-lessac-medium`
into `cache/pipertts/` without prompts.

## Manual install

```bash
# 1. Install the Piper Python package
pip install piper-tts

# 2. Pick a destination (must match what the engine resolves — see Models Storage)
mkdir -p cache/pipertts

# 3. Download voice files (.onnx + .onnx.json) from rhasspy/piper-voices@v1.0.0
BASE=https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0

# English (en_US-lessac-medium) — clear female voice
wget -P cache/pipertts "$BASE/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
wget -P cache/pipertts "$BASE/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"

# Russian (ru_RU-ruslan-medium) — male voice
wget -P cache/pipertts "$BASE/ru/ru_RU/ruslan/medium/ru_RU-ruslan-medium.onnx"
wget -P cache/pipertts "$BASE/ru/ru_RU/ruslan/medium/ru_RU-ruslan-medium.onnx.json"

# Spanish (es_ES-davefx-medium)
wget -P cache/pipertts "$BASE/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx"
wget -P cache/pipertts "$BASE/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx.json"
```

Each voice ships as **two files** (`.onnx` model + `.onnx.json` config).
Both must live in the same directory.

## Verify the install

```bash
pip list | grep piper                  # → piper-tts X.Y.Z
ls -la cache/pipertts/                 # → *.onnx + *.onnx.json pairs
ttsgen --list                          # → pipertts | installed | <models>
```

## Usage

```bash
# English (default voice resolved by --language en)
ttsgen "Hello, how are you?" --engine pipertts

# Spanish
ttsgen "Hola mundo" --engine pipertts --language es

# Save to file
ttsgen "Hello world" --engine pipertts --file output.wav
```

## Models Storage

### Default Location

Models live in `cache/pipertts/` in the project root (auto-created by the
installer). Example: `/path/to/text-to-speech/cache/pipertts/`.

### Path Resolution Priority

`engines/pipertts.py:get_models_directory()` resolves the model directory
in this order:

1. **`PIPERTTS_MODELS` env var** (set in process env, `.env`,
   `./ttsgen.conf`, or `~/.config/ttsgen.conf`). Absolute or
   project-root-relative.
2. **`cache/pipertts/`** in the project root — used if it exists on disk.
3. **`<project>/.piper/voices`** — fallback for legacy installs.

### Custom Location

`ttsgen --install pipertts` interactive mode offers three options:

1. **Default:** `cache/pipertts/` (project-local — recommended for clones).
2. **Standard:** `~/.local/share/ttsgen/pipertts/` (user-wide — survives
   moving the project clone).
3. **Custom:** any directory you specify.

The choice persists to `~/.config/ttsgen.conf` as
`PIPERTTS_MODELS=<chosen-path>`.

To override after install:

```bash
export PIPERTTS_MODELS="$HOME/my-piper-voices"
# or persist in ~/.config/ttsgen.conf:
echo "PIPERTTS_MODELS=$HOME/my-piper-voices" >> ~/.config/ttsgen.conf
```

## Available Models

### Voice Quality Tiers

- **low** — fast, basic quality (~10 MB).
- **medium** — good quality (~50 MB). ⭐ Recommended.
- **high** — best quality (~150 MB).

### Popular Models

| Language | Model | Quality |
|---|---|---|
| English (US) | `en_US-lessac-medium` | ⭐⭐⭐⭐⭐ |
| English (GB) | `en_GB-alba-medium` | ⭐⭐⭐⭐ |
| Russian | `ru_RU-ruslan-medium` | ⭐⭐⭐⭐⭐ |
| Spanish (ES) | `es_ES-davefx-medium` | ⭐⭐⭐⭐ |
| German | `de_DE-thorsten-medium` | ⭐⭐⭐⭐⭐ |
| French | `fr_FR-siwis-medium` | ⭐⭐⭐⭐ |
| Italian | `it_IT-riccardo-medium` | ⭐⭐⭐⭐ |
| Ukrainian | `uk_UA-ukrainian_tts-medium` | ⭐⭐⭐⭐ |
| Chinese | `zh_CN-huayan-medium` | ⭐⭐⭐⭐ |

Full catalogue: <https://rhasspy.github.io/piper-samples/>.

## Troubleshooting

### `piper` not found after install

```bash
# Verify the venv is the one ttsgen sees:
which python3                          # must point inside your venv
pip uninstall piper-tts && pip install piper-tts
```

### Model not found

```bash
ls -la cache/pipertts/
# Each voice needs BOTH files:
#   <name>.onnx
#   <name>.onnx.json
```

If you placed models in another directory, set `PIPERTTS_MODELS` to point
to that directory.

### Low audio quality

Switch to a `-high` voice variant — re-run the installer and pick the
`high` quality tier, or download manually:

```bash
BASE=https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0
wget -P cache/pipertts "$BASE/en/en_US/lessac/high/en_US-lessac-high.onnx"
wget -P cache/pipertts "$BASE/en/en_US/lessac/high/en_US-lessac-high.onnx.json"
```
