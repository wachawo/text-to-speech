# Piper TTS

Offline high-quality TTS via [Piper](https://github.com/rhasspy/piper) -
ONNX models trained per voice/language, about 10x realtime on CPU.

## Quick install

```bash
ttsgen --install pipertts
```

That command:
1. Installs `piper-tts` (CPU-friendly, no torch dependency).
2. Asks where to store the models (see [Models Storage](#models-storage)).
3. Lets you pick the languages to download (English, Russian, Spanish, German,
   French; medium quality) and verifies each file against the upstream checksum.

Use `--non-interactive` to accept defaults - installs all five voices into
`~/.local/share/ttsgen/pipertts/` without prompts.

## Manual install

```bash
# 1. Install the Piper Python package
pip install piper-tts

# 2. Pick a destination (must match what the engine resolves - see Models Storage)
mkdir -p cache/pipertts

# 3. Download voice files (.onnx + .onnx.json) from rhasspy/piper-voices@v1.0.0
BASE=https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0

# English (en_US-lessac-medium) - clear female voice
wget -P cache/pipertts "$BASE/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
wget -P cache/pipertts "$BASE/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"

# Russian (ru_RU-ruslan-medium) - male voice
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
pip list | grep piper                  # piper-tts X.Y.Z
ls -la cache/pipertts/                 # *.onnx + *.onnx.json pairs
ttsgen --list                          # pipertts | installed | <models>
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

Environment variable: `PIPERTTS_MODELS`. Installer default:
`~/.local/share/ttsgen/pipertts/`; the project-local choice is `cache/pipertts/`.
The three-way prompt and how the answer is persisted are described in
[ENGINES.md, "Where models live"](ENGINES.md#where-models-live).

`engines/pipertts.py:get_models_directory()` resolves the directory as
`PIPERTTS_MODELS` (absolute or project-root-relative), then `cache/pipertts/`
in the project root if it exists, then `<project>/.piper/voices` for legacy
installs. When the voice is not in that directory the engine also looks in
`~/.local/share/piper/voices`, `/usr/share/piper/voices` and `./voices`.

Config precedence, strongest first: CLI flags > shell environment >
`./ttsgen.conf` > `~/.config/ttsgen.conf` > `./.env.local` > `./.env`. Files
never override the shell; `.env` is read only from the current directory.

To override after install:

```bash
export PIPERTTS_MODELS="$HOME/my-piper-voices"
# or persist in ~/.config/ttsgen.conf:
echo "PIPERTTS_MODELS=$HOME/my-piper-voices" >> ~/.config/ttsgen.conf
```

## Available Models

### Voice Quality Tiers

- **low** - fast, basic quality (~10 MB).
- **medium** - good quality (~50 MB). Recommended; the installer downloads this tier.
- **high** - best quality (~150 MB).

### Popular Models

| `--language` | Model | Quality | Installer |
|---|---|---|---|
| `en` | `en_US-lessac-medium` | 5/5 | yes |
| `ru` | `ru_RU-ruslan-medium` | 5/5 | yes |
| `es` | `es_ES-davefx-medium` | 4/5 | yes |
| `de` | `de_DE-thorsten-medium` | 5/5 | yes |
| `fr` | `fr_FR-siwis-medium` | 4/5 | yes |
| `it` | `it_IT-riccardo-medium` | 4/5 | manual download |
| `uk` | `uk_UA-ukrainian_tts-medium` | 4/5 | manual download |
| `zh` | `zh_CN-huayan-medium` | 4/5 | manual download |

These are the voices `engines/pipertts.py` maps to a `--language` code; any
other code falls back to the English voice. Other voices from the catalogue
(for example `en_GB-alba-medium`) can be downloaded, but the engine does not
select them by language.

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

Switch to a `-high` voice variant. The installer downloads the medium tier
only, and the engine looks the voice up by its medium file name, so fetch the
high tier manually into a separate directory, store it under the medium names
and point `PIPERTTS_MODELS` at that directory:

```bash
BASE=https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0
mkdir -p ~/piper-high
wget -O ~/piper-high/en_US-lessac-medium.onnx      "$BASE/en/en_US/lessac/high/en_US-lessac-high.onnx"
wget -O ~/piper-high/en_US-lessac-medium.onnx.json "$BASE/en/en_US/lessac/high/en_US-lessac-high.onnx.json"
export PIPERTTS_MODELS=~/piper-high
```
