# Kokoro TTS

Offline ONNX-based TTS using [Kokoro 82M](https://huggingface.co/hexgrad/Kokoro-82M)
through the Python bindings [`kokoro-onnx`](https://github.com/thewh1teagle/kokoro-onnx).
This engine wraps the same model used by the [`nazdridoy/kokoro-tts`](https://github.com/nazdridoy/kokoro-tts) CLI.

## Quick install

```bash
ttsgen --install kokorotts
```

That command:
1. Asks where to store the models (see [Configuration](#configuration)).
2. Picks `onnxruntime` (CPU) or `onnxruntime-gpu` (CUDA) - interactive prompt.
3. Installs `kokoro-onnx` and `soundfile`.
4. Downloads `kokoro-v1.0.onnx` (~310 MB) and `voices-v1.0.bin` (~25 MB) from
   [`nazdridoy/kokoro-tts` v1.0.0 release](https://github.com/nazdridoy/kokoro-tts/releases/tag/v1.0.0).

Use `--non-interactive` to accept defaults (CPU runtime, model directory
`~/.local/share/ttsgen/kokorotts`). Kokoro needs no PyTorch; `kokoro-onnx`
supports Python 3.10 to 3.12, and the project itself requires 3.11+.

## Manual install

```bash
pip install kokoro-onnx soundfile onnxruntime
mkdir -p ~/.local/share/ttsgen/kokorotts
cd ~/.local/share/ttsgen/kokorotts
wget https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/kokoro-v1.0.onnx
wget https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/voices-v1.0.bin
```

Set `KOKOROTTS_MODELS` if you want models in another directory.

## Usage

```bash
# English (default voice af_sarah)
ttsgen "Hello world" --engine kokorotts

# Other languages - 2-char code maps to Kokoro lang internally
ttsgen "Bonjour"     --engine kokorotts --language fr   # fr-fr / ff_siwis
ttsgen "Ciao mondo"  --engine kokorotts --language it   # it    / if_sara
ttsgen "你好世界"     --engine kokorotts --language zh   # cmn   / zf_xiaobei
ttsgen "こんにちは"    --engine kokorotts --language ja   # ja    / jf_alpha
ttsgen "Hola mundo"  --engine kokorotts --language es   # es    / ef_dora

# Override voice / speed via env (no CLI flags; the `voice` request field is ignored by this engine)
KOKOROTTS_VOICE=am_adam     ttsgen "Hi" --engine kokorotts
KOKOROTTS_VOICE=af_heart    ttsgen "Hi" --engine kokorotts
KOKOROTTS_SPEED=1.2         ttsgen "Hi" --engine kokorotts
```

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `KOKOROTTS_MODELS` | `~/.local/share/ttsgen/kokorotts` | Directory holding the two model files; `cache/kokorotts/` in the project root is used first when it exists (see [ENGINES.md, "Where models live"](ENGINES.md#where-models-live)) |
| `KOKOROTTS_MODEL` | `kokoro-v1.0.onnx` | Filename inside `KOKOROTTS_MODELS` |
| `KOKOROTTS_VOICES` | `voices-v1.0.bin` | Filename inside `KOKOROTTS_MODELS` |
| `KOKOROTTS_VOICE` | per-language default (`af_sarah`, `ff_siwis`, ...) | Any voice ID supported by the model |
| `KOKOROTTS_SPEED` | `1.0` | Speech speed multiplier |

Config precedence, strongest first: CLI flags > shell environment > `./ttsgen.conf` >
`~/.config/ttsgen.conf` > `./.env.local` > `./.env`. Files never override the
shell; `.env` is read only from the current directory.

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

Override `KOKOROTTS_VOICE` to pick male / British / blended voices. The full
catalog (mirrored from <https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md>)
is below. Grades come from upstream subjective evaluation (A best to F worst);
ungraded voices are listed without one.

## Full voice list

Voice ID prefix encodes language + gender:
`af_*`/`am_*` American Female/Male, `bf_*`/`bm_*` British, `jf_*`/`jm_*`
Japanese, `zf_*`/`zm_*` Mandarin, `ef_*`/`em_*` Spanish, `ff_*` French,
`hf_*`/`hm_*` Hindi, `if_*`/`im_*` Italian, `pf_*`/`pm_*` Brazilian Portuguese.

### American English (`--language en`, Kokoro lang `en-us`)

| Voice ID | Gender | Grade |
|---|---|---|
| `af_heart` | Female | A |
| `af_bella` | Female | A- |
| `af_nicole` | Female | B- |
| `af_aoede` | Female | C+ |
| `af_kore` | Female | C+ |
| `af_sarah` *(default)* | Female | C+ |
| `af_alloy` | Female | C |
| `af_nova` | Female | C |
| `af_sky` | Female | C- |
| `af_jessica` | Female | D |
| `af_river` | Female | D |
| `am_fenrir` | Male | C+ |
| `am_michael` | Male | C+ |
| `am_puck` | Male | C+ |
| `am_echo` | Male | D |
| `am_eric` | Male | D |
| `am_liam` | Male | D |
| `am_onyx` | Male | D |
| `am_santa` | Male | D- |
| `am_adam` | Male | F+ |

### British English (no default - set `KOKOROTTS_VOICE` and use `--language en`)

| Voice ID | Gender | Grade |
|---|---|---|
| `bf_emma` | Female | B- |
| `bf_isabella` | Female | C |
| `bf_alice` | Female | D |
| `bf_lily` | Female | D |
| `bm_fable` | Male | C |
| `bm_george` | Male | C |
| `bm_lewis` | Male | D+ |
| `bm_daniel` | Male | D |

### Japanese (`--language ja`, Kokoro lang `ja`)

| Voice ID | Gender | Grade |
|---|---|---|
| `jf_alpha` *(default)* | Female | C+ |
| `jf_gongitsune` | Female | C |
| `jf_tebukuro` | Female | C |
| `jf_nezumi` | Female | C- |
| `jm_kumo` | Male | C- |

### Mandarin Chinese (`--language zh`, Kokoro lang `cmn`)

| Voice ID | Gender | Grade |
|---|---|---|
| `zf_xiaobei` *(default)* | Female | D |
| `zf_xiaoni` | Female | D |
| `zf_xiaoxiao` | Female | D |
| `zf_xiaoyi` | Female | D |
| `zm_yunjian` | Male | D |
| `zm_yunxi` | Male | D |
| `zm_yunxia` | Male | D |
| `zm_yunyang` | Male | D |

### Spanish (`--language es`, Kokoro lang `es`)

| Voice ID | Gender | Grade |
|---|---|---|
| `ef_dora` *(default)* | Female | ungraded |
| `em_alex` | Male | ungraded |
| `em_santa` | Male | ungraded |

### French (`--language fr`, Kokoro lang `fr-fr`)

| Voice ID | Gender | Grade |
|---|---|---|
| `ff_siwis` *(default)* | Female | B- |

### Hindi (`--language hi`, Kokoro lang `hi`)

| Voice ID | Gender | Grade |
|---|---|---|
| `hf_alpha` *(default)* | Female | C |
| `hf_beta` | Female | C |
| `hm_omega` | Male | C |
| `hm_psi` | Male | C |

### Italian (`--language it`, Kokoro lang `it`)

| Voice ID | Gender | Grade |
|---|---|---|
| `if_sara` *(default)* | Female | C |
| `im_nicola` | Male | C |

### Brazilian Portuguese (`--language pt`, Kokoro lang `pt-br`)

| Voice ID | Gender | Grade |
|---|---|---|
| `pf_dora` *(default)* | Female | ungraded |
| `pm_alex` | Male | ungraded |
| `pm_santa` | Male | ungraded |

## Output format

WAV, 16-bit PCM, mono, 24000 Hz (Kokoro native). The CLI's chunking pipeline
concatenates chunks via `wave` from the standard library - no re-encoding.

## Troubleshooting

**`Kokoro TTS model files not found`**
Run `ttsgen --install kokorotts`, or check that `KOKOROTTS_MODELS` points to a
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
