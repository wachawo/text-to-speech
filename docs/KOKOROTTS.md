# Kokoro TTS

Offline ONNX-based TTS using [Kokoro 82M](https://huggingface.co/hexgrad/Kokoro-82M)
through the Python bindings [`kokoro-onnx`](https://github.com/thewh1teagle/kokoro-onnx).
This engine wraps the same model used by the [`nazdridoy/kokoro-tts`](https://github.com/nazdridoy/kokoro-tts) CLI.

## Quick install

```bash
ttsgen --install kokorotts
```

That command:
1. Picks `onnxruntime` (CPU) or `onnxruntime-gpu` (CUDA) — interactive prompt.
2. Installs `kokoro-onnx` and `soundfile`.
3. Downloads `kokoro-v1.0.onnx` (~310 MB) and `voices-v1.0.bin` (~25 MB) from
   [`nazdridoy/kokoro-tts` v1.0.0 release](https://github.com/nazdridoy/kokoro-tts/releases/tag/v1.0.0).

Use `--non-interactive` to accept defaults (CPU runtime, default model dir).

## Manual install

```bash
pip install kokoro-onnx soundfile onnxruntime
mkdir -p ~/.local/share/ttsgen/kokorotts
cd ~/.local/share/ttsgen/kokorotts
wget https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/kokoro-v1.0.onnx
wget https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/voices-v1.0.bin
```

Set `KOKOROTTS_PATH` if you want models in another directory.

## Usage

```bash
# English (default voice af_sarah)
ttsgen "Hello world" --engine kokorotts

# Other languages — 2-char code maps to Kokoro lang internally
ttsgen "Bonjour"     --engine kokorotts --language fr   # → fr-fr / ff_siwis
ttsgen "Ciao mondo"  --engine kokorotts --language it   # → it    / if_sara
ttsgen "你好世界"     --engine kokorotts --language zh   # → cmn   / zf_xiaobei
ttsgen "こんにちは"    --engine kokorotts --language ja   # → ja    / jf_alpha
ttsgen "Hola mundo"  --engine kokorotts --language es   # → es    / ef_dora

# Override voice / speed via env (no CLI flags yet)
KOKOROTTS_VOICE=am_adam     ttsgen "Hi" --engine kokorotts
KOKOROTTS_VOICE=af_heart    ttsgen "Hi" --engine kokorotts
KOKOROTTS_SPEED=1.2         ttsgen "Hi" --engine kokorotts
```

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `KOKOROTTS_PATH` | `~/.local/share/ttsgen/kokorotts` | Directory holding the two model files |
| `KOKOROTTS_MODEL` | `kokoro-v1.0.onnx` | Filename inside `KOKOROTTS_PATH` |
| `KOKOROTTS_VOICES` | `voices-v1.0.bin` | Filename inside `KOKOROTTS_PATH` |
| `KOKOROTTS_VOICE` | per-language default (`af_sarah`, `ff_siwis`, …) | Any voice ID supported by the model |
| `KOKOROTTS_SPEED` | `1.0` | Speech speed multiplier |

Standard config-file priority applies: process env > `./ttsgen.conf` > `~/.config/ttsgen.conf` > `.env`.

## Supported languages and default voices

| `--language` | Kokoro lang | Default voice | Notes |
|---|---|---|---|
| `en` | `en-us` | `af_sarah` | American English (female) |
| `fr` | `fr-fr` | `ff_siwis` | French |
| `it` | `it`    | `if_sara`  | Italian |
| `ja` | `ja`    | `jf_alpha` | Japanese |
| `zh` | `cmn`   | `zf_xiaobei` | Mandarin Chinese |
| `es` | `es`    | `ef_dora`  | Spanish |
| `hi` | `hi`    | `hf_alpha` | Hindi |
| `pt` | `pt-br` | `pf_dora`  | Brazilian Portuguese |

Full voice catalog: <https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md>.
Override `KOKOROTTS_VOICE` to pick male / British / blended voices.

## Output format

WAV, 16-bit PCM, mono, 24000 Hz (Kokoro native). The CLI's chunking pipeline
concatenates chunks via `wave` from the standard library — no re-encoding.

## Troubleshooting

**`Kokoro TTS model files not found`**
Run `ttsgen --install kokorotts`, or check that `KOKOROTTS_PATH` points to a
directory containing both `kokoro-v1.0.onnx` and `voices-v1.0.bin`.

**`onnxruntime` import error**
Reinstall a matching runtime: `pip install onnxruntime` (CPU) or
`pip install onnxruntime-gpu` (NVIDIA CUDA).

**`soundfile` cannot find `libsndfile`**
On Debian/Ubuntu: `sudo apt install libsndfile1`. The Python `soundfile`
package needs the system library to encode WAV.

**Voice IDs**
Each voice ID encodes language + gender (`af_*` = American Female, `am_*` =
American Male, `bf_*` = British Female, `ff_*` = French Female, etc.). See
the upstream VOICES.md for the full list.
