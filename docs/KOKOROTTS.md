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

# Override voice / speed via env (no CLI flags; the server also takes a voice per request)
KOKOROTTS_VOICE=am_adam     ttsgen "Hi" --engine kokorotts
KOKOROTTS_VOICE=af_heart    ttsgen "Hi" --engine kokorotts
KOKOROTTS_SPEED=1.2         ttsgen "Hi" --engine kokorotts
```

## Voices and mixing

The voice is picked, strongest first, from the request (`voice` of `/api/tts`,
`/api/history` and `/v1/audio/speech`, or the Voice field of the Studio), then
`KOKOROTTS_VOICE`, then the language default (see
[Supported languages](#supported-languages-and-default-voices)). A voice that is
not in the voices file is refused with a 400 that names it.

The voices of one language come from the server:

```bash
curl "localhost:5000/api/voices?engine=kokorotts&language=en" \
  -H "Authorization: Bearer $TTS_TOKEN"
```

English lists the American (`a*`) and the British (`b*`) voices; a `b*` voice
switches the phonemizer from `en-us` to `en-gb`. The reported `default` is
`KOKOROTTS_VOICE` when it is set, else the language default.

The language can also be a tag. `en-gb` selects the British phonemizer with any
English voice; any other tag uses its language part (`pt-br` is `pt`,
`ja-jp` is `ja`), and a language missing from the table below is spoken as
English.

A mix blends up to four voices: `name(weight)+name(weight)`, for example
`af_bella(2)+af_sky(1)`.

- Weights are positive numbers, 1 when left out, and are normalized to sum 1:
  `af_bella(2)+af_sky(1)` is two thirds `af_bella` and one third `af_sky`.
- Each name comes from the voices file and appears once; spaces around names,
  weights and `+` are ignored.
- The first voice decides the English accent: `bf_emma+af_bella` reads as `en-gb`.
- Over HTTP the value is at most 128 characters, the limit of the request
  field. In a query string or a form body write `+` as `%2B`, otherwise it
  arrives as a space; JSON bodies need no escaping.

In the Studio and its settings dialog, the Voice field of this engine takes a
name or a mix typed by hand, with the voices of the language offered as
suggestions.

```bash
# One voice through /api/tts
curl -X POST localhost:5000/api/tts \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world","engine":"kokorotts","language":"en","voice":"bf_emma"}' \
  -o out.wav

# A mix through the OpenAI-compatible route
curl -X POST localhost:5000/v1/audio/speech \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model":"kokorotts","input":"Hello world","voice":"af_bella(2)+af_sky(1)","response_format":"wav"}' \
  -o out.wav

# A mix as the default voice of the CLI (quoted: the shell reads the parentheses)
KOKOROTTS_VOICE="af_bella(2)+af_sky(1)" ttsgen "Hello world" --engine kokorotts
```

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `KOKOROTTS_MODELS` | `~/.local/share/ttsgen/kokorotts` | Directory holding the two model files; `cache/kokorotts/` in the project root is used first when it exists (see [ENGINES.md, "Where models live"](ENGINES.md#where-models-live)) |
| `KOKOROTTS_MODEL` | `kokoro-v1.0.onnx` | Filename inside `KOKOROTTS_MODELS` |
| `KOKOROTTS_VOICES` | `voices-v1.0.bin` | Filename inside `KOKOROTTS_MODELS` |
| `KOKOROTTS_VOICE` | per-language default (`af_sarah`, `ff_siwis`, ...) | A voice ID or a mix (`af_bella(2)+af_sky(1)`); a request `voice` wins over it |
| `KOKOROTTS_SPEED` | `1.0` | Speech speed multiplier |

Config precedence, strongest first: CLI flags > shell environment > `./ttsgen.conf` >
`~/.config/ttsgen.conf` > `./.env.local` > `./.env`. Files never override the
shell; `.env` is read only from the current directory.

## Selecting a model per request

The model id is the name of a `.onnx` file in `KOKOROTTS_MODELS`, such as
`kokoro-v1.0.int8.onnx`. `GET /api/engines/kokorotts` lists every `*.onnx`
there under `models`, plus `KOKOROTTS_MODEL` (with `installed: false` when its
file is missing); the listing reads the directory only and builds no ONNX
session. A request sends the id as `model` (`/api/tts`, `/api/history`):

```bash
curl -X POST localhost:5000/api/tts \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello","engine":"kokorotts","model":"kokoro-v1.0.int8.onnx"}' -o out.wav
```

A named model is paired with the voices file of its release: the release in
its name (`v1.0` in `kokoro-v1.0.int8.onnx`) names `voices-v1.0.bin`, used when
that file is in the same directory; otherwise `KOKOROTTS_VOICES` is used. Without a model `KOKOROTTS_MODEL` and
`KOKOROTTS_VOICES` are used as before. `GET /api/voices?engine=kokorotts&model=`
lists the voices of the paired file. An id that is not listed is a 400; a name
with a path separator is refused by the engine as well, except
`KOKOROTTS_MODEL` itself, which is listed as it is set (`v1/kokoro-v1.0.onnx`)
and paired with the voices file next to it.

Every model a request loads stays in memory, up to `TTS_MODEL_CACHE_SIZE`
models (default `2`, about 300 MB each for the full model); loading one more
first drops the model loaded earliest.

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

Pick male, British or blended voices with the request `voice` or
`KOKOROTTS_VOICE` (see [Voices and mixing](#voices-and-mixing)). The full
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

### British English (`--language en` with a `b*` voice, Kokoro lang `en-gb`; no default, name one)

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
