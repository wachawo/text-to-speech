# text-to-speech - TTS इंजनों के लिए एक एकल इंटरफ़ेस

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | **[हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md)** | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

![वेब UI की Studio स्क्रीन](https://raw.githubusercontent.com/wachawo/text-to-speech/main/docs/images/studio.png)

`text-to-speech` आपको एक ही इंटरफ़ेस के माध्यम से कई स्पीच-सिंथेसिस इंजनों के साथ काम करने देता है। आप ऑनलाइन gTTS से शुरुआत कर सकते हैं और बाद में स्थानीय Piper, Silero, Coqui, Bark, या Kokoro पर स्विच कर सकते हैं - अपने CLI कमांड, Python कोड, या HTTP इंटीग्रेशन को फिर से लिखे बिना।

यह प्रोजेक्ट स्थानीय उपयोग, ऑटोमेशन, और नेटवर्क पर अपना खुद का TTS सर्वर चलाने के लिए उपयुक्त है।

* **विभिन्न इंजनों के साथ काम करने का एक ही तरीका।** आपको जिस इंजन की ज़रूरत है उसे चुनें और उसे CLI (`ttsgen`), Python API (`libs.api`), या HTTP API के माध्यम से कॉल करें।
* **आप पूरी तरह स्थानीय रूप से काम कर सकते हैं।** Piper, Silero, Coqui, Bark, Kokoro, और `pyttsx3` सभी आपकी अपनी मशीन पर चलते हैं।
* **एक उपयोग के लिए तैयार HTTP सर्वर शामिल है।** `ttssrv` स्टार्टअप पर मॉडल लोड करता है और आपके स्थानीय नेटवर्क की अन्य मशीनों से आने वाले अनुरोधों को संभालता है।

### इंजन

| इंजन        | ऑफ़लाइन | हार्डवेयर     | गुणवत्ता | किसके लिए अच्छा                                  |
| ----------- | ------- | ------------- | ------- | ---------------------------------------------- |
| `gtts`      | ❌      | CPU           | ★★★★    | त्वरित शुरुआत और बड़ी संख्या में भाषाएँ            |
| `pyttsx3`   | ✅      | CPU           | ★★      | espeak या SAPI के माध्यम से सरल स्थानीय स्पीच       |
| `pipertts`  | ✅      | CPU           | ★★★★    | कई भाषाओं में तेज़ ऑफ़लाइन सिंथेसिस                 |
| `silerotts` | ✅      | CPU           | ★★★★    | रूसी स्पीच और एक हल्का स्थानीय सेटअप               |
| `kokorotts` | ✅      | CPU           | ★★★★    | बहुभाषी ऑफ़लाइन सिंथेसिस                          |
| `coquitts`  | ✅      | CPU / **GPU** | ★★★★★   | उच्च-गुणवत्ता वाली आवाज़ें और वॉइस क्लोनिंग         |
| `barktts`   | ✅      | CPU / **GPU** | ★★★★★   | अभिव्यंजक स्पीच, भावनाएँ, संगीत, और गायन          |

`gtts`, `pyttsx3`, `pipertts`, `silerotts`, और `kokorotts` CPU पर ठीक से चलते हैं। `coquitts` और `barktts` बिना GPU के भी चल सकते हैं, लेकिन सिंथेसिस काफ़ी धीमा होता है - उनके लिए एक CUDA-सक्षम ग्राफ़िक्स कार्ड की अनुशंसा की जाती है।

### इंस्टॉलेशन

बेस इंस्टॉल CLI और इसकी हल्की निर्भरताओं को सेट करता है:

```bash
pip install git+https://github.com/wachawo/text-to-speech.git
```

Linux पर, ऑफ़लाइन `pyttsx3` इंजन को सिस्टम `espeak` पैकेज की भी ज़रूरत होती है:

```bash
sudo apt install espeak espeak-data libespeak1
```

अतिरिक्त इंजन और उनके मॉडल अलग से इंस्टॉल किए जाते हैं, जब आपको वास्तव में उनकी ज़रूरत होती है:

```bash
ttsgen --install coquitts
```

CLI उपयोग के उदाहरण:

```bash
ttsgen "Hello world"                  # gTTS के साथ टेक्स्ट बोलें
ttsgen "Hello world" -f out.mp3       # परिणाम को एक फ़ाइल में सहेजें
ttsgen "Hello world" -e pyttsx3       # एक स्थानीय इंजन का उपयोग करें
ttsgen "Hola amigo!" -l es            # एक भाषा चुनें
ttsgen --install coquitts             # Coqui TTS और इसके मॉडल इंस्टॉल करें
ttsgen "Hello world" -e coquitts -f out.wav
ttsgen --list                         # उपलब्ध इंजन और मॉडल दिखाएँ
ttsgen "Hello world" --stdout | ttsplay
```

`gtts` डिफ़ॉल्ट है, इसलिए पहली बार चलाने के लिए एक ही कमांड पर्याप्त है। पूरी तरह स्थानीय काम के लिए, `pyttsx3`, `pipertts`, या `silerotts` जैसा कोई अन्य इंजन चुनें।
मेरी पसंद: गुणवत्ता और स्वाभाविक-सुनाई देने वाली स्पीच के लिए `coquitts`, तेज़ जनरेशन के लिए `silerotts`।

### Python API

Python में, परिणाम को एक फ़ाइल में सहेजने या ऑडियो को बाइट्स के रूप में प्राप्त करने के लिए फ़ंक्शन हैं:

```python
from libs.api import text_to_speech_file, text_to_speech_bytes

text_to_speech_file("Hello world", engine="gtts")

audio = text_to_speech_bytes(
    "Hello world",
    engine="pipertts",
    language="en",
)
```

### HTTP सर्वर

सर्वर को Docker के साथ चलाना आसान है:

```bash
git clone https://github.com/wachawo/text-to-speech.git
cd text-to-speech
cp env.example .env                                   # वैकल्पिक: टोकन, इंजन, पोर्ट

docker compose up --build -d                          # GPU / CUDA 12.1
docker compose -f docker-compose-cpu.yml up --build -d # केवल CPU
```

GPU वैरिएंट कार्ड को CDI के माध्यम से पास करता है, इसलिए होस्ट पर NVIDIA container toolkit (1.14 या नया) और एक जनरेट किया गया CDI spec चाहिए, हर ड्राइवर अपडेट के बाद एक बार:

```bash
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
```

एक बार चलने के बाद, आप सर्वर की स्थिति जाँच सकते हैं और एक सिंथेसिस अनुरोध भेज सकते हैं:

```bash
curl localhost:5000/api/health

curl localhost:5000/api/engines \
  -H "Authorization: Bearer $TTS_TOKEN"

curl "localhost:5000/api/voices?engine=silerotts&language=ru" \
  -H "Authorization: Bearer $TTS_TOKEN"

curl -X POST localhost:5000/api/tts \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world","engine":"gtts"}' \
  -o out.mp3
```

मॉडल, आवाज़ें और इतिहास:

```bash
# इंस्टॉल किए गए और अनुपस्थित मॉडल, वही तालिका जो `ttsgen --list` प्रिंट करता है
curl localhost:5000/api/models \
  -H "Authorization: Bearer $TTS_TOKEN"

# coquitts के लिए एक वॉइस सैंपल अपलोड करें (WAV); इसके बाद आवाज़ "maria" कहलाती है
curl -X POST localhost:5000/api/voices \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -F file=@voice.wav -F name=maria -F engine=coquitts

curl "localhost:5000/api/voices?engine=coquitts" \
  -H "Authorization: Bearer $TTS_TOKEN"

curl "localhost:5000/api/voices/maria/audio?engine=coquitts&download=1" \
  -H "Authorization: Bearer $TTS_TOKEN" -o maria.wav

# प्रतिक्रिया बॉडी के बजाय सर्वर-साइड इतिहास में सिंथेसाइज़ करें
curl -X POST localhost:5000/api/history \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hola mundo","engine":"coquitts","language":"es","voice":"maria"}'

curl "localhost:5000/api/history?limit=50&offset=0" \
  -H "Authorization: Bearer $TTS_TOKEN"

# एक आइटम का ऑडियो; download=1 के बिना यह <audio> के लिए इनलाइन परोसा जाता है
curl "localhost:5000/api/history/<id>/audio?download=1" \
  -H "Authorization: Bearer $TTS_TOKEN" -o tts.wav

curl -X DELETE localhost:5000/api/history/<id> \
  -H "Authorization: Bearer $TTS_TOKEN"
```

#### OpenAI-संगत API

वही सर्वर OpenAI ऑडियो API का भी उत्तर देता है, इसलिए Open WebUI, SillyTavern, Home Assistant और आधिकारिक SDK इसकी ओर इंगित करते `base_url` और API कुंजी के रूप में bearer टोकन के साथ काम करते हैं:

```bash
curl -X POST localhost:5000/v1/audio/speech \
  -H "Authorization: Bearer $TTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model":"tts-1","input":"Hello world","voice":"alloy","response_format":"mp3"}' \
  -o out.mp3
```

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:5000/v1", api_key="<one of TTS_TOKENS>")
audio = client.audio.speech.create(model="coquitts", voice="maria", input="Hola mundo")
audio.write_to_file("hola.mp3")
```

- `model` एक इंजन का नाम है, या डिफ़ॉल्ट इंजन के लिए `tts-1` / `tts-1-hd` / `gpt-4o-mini-tts`।
- `voice` इंजन की एक आवाज़ है; OpenAI आवाज़ नाम (`alloy`, `nova`, ...) इंजन का डिफ़ॉल्ट चुनते हैं।
- `response_format`: `mp3` (डिफ़ॉल्ट), `wav`, `pcm`, `opus`, `flac`, `aac`। इंजन WAV या MP3 बनाते हैं; बाकी सब कुछ `ffmpeg` से ट्रांसकोड किया जाता है, जो Docker इमेज में शामिल है। `speed` (0.25 से 4.0) उसी तरह लागू होता है।
- `language` एक एक्सटेंशन है: दो-अक्षर का कोड या `zh-cn` जैसा टैग, डिफ़ॉल्ट `TTS_LANGUAGE`।
- `GET /v1/models` इंस्टॉल किए गए इंजनों के साथ `tts-1` सूचीबद्ध करता है; `GET /v1/audio/voices?model=<engine>` एक इंजन की आवाज़ें सूचीबद्ध करता है।

#### API संदर्भ

जब `TTS_TOKENS` सेट हो, तो `/api/health` को छोड़कर हर रूट को `Authorization: Bearer <token>` की ज़रूरत होती है। `/api/` के अंतर्गत त्रुटियाँ `{"error": "...", "request_id": "..."}` होती हैं; 400 उत्तर में कारण के साथ `message` भी होता है, और अनुरोध सत्यापन में विफल होने पर यह गलत फ़ील्ड का नाम बताता है (`language: ...`)। `/v1/` के अंतर्गत त्रुटियाँ OpenAI के प्रारूप का उपयोग करती हैं।

| मेथड | पाथ | उद्देश्य |
| --- | --- | --- |
| GET | `/api/health` | लाइवनेस, `auth` फ़्लैग, इंजन, पूल और कतार के आकार। टोकन की ज़रूरत नहीं। |
| GET | `/api/engines` | समर्थित इंजन, इंस्टॉल किए गए इंजन और डिफ़ॉल्ट। |
| GET | `/api/models` | प्रति इंजन इंस्टॉल किए गए और अनुपस्थित मॉडल, वही तालिका जो `ttsgen --list` प्रिंट करता है। |
| GET | `/api/voices?engine=&language=` | एक इंजन की आवाज़ें; `coquitts` के लिए आकार, रेट और अवधि सहित सैंपल। |
| POST | `/api/voices` | एक WAV सैंपल अपलोड करें (`file`, `name`, `engine=coquitts`)। |
| GET | `/api/voices/<name>/audio?engine=&download=1` | एक सैंपल चलाएँ या डाउनलोड करें। |
| DELETE | `/api/voices/<name>?engine=` | एक सैंपल हटाएँ। |
| POST, GET | `/api/tts` | `engine`, `language`, `voice` के साथ `text` सिंथेसाइज़ करें; `stream=true` तैयार होते ही चंक स्ट्रीम करता है। |
| POST | `/api/history` | प्रतिक्रिया बॉडी के बजाय सर्वर-साइड इतिहास में सिंथेसाइज़ करें। |
| GET | `/api/history?limit=&offset=` | इतिहास आइटम सूचीबद्ध करें, सबसे नए पहले। |
| GET | `/api/history/<id>` | एक आइटम का मेटाडेटा। |
| GET | `/api/history/<id>/audio?download=1` | आइटम का ऑडियो, इनलाइन या डाउनलोड के रूप में। |
| DELETE | `/api/history/<id>` | एक आइटम हटाएँ। |
| POST | `/v1/audio/speech` | OpenAI-संगत सिंथेसिस, ऊपर देखें। |
| GET | `/v1/models` | OpenAI-संगत मॉडल सूची। |
| GET | `/v1/audio/voices?model=` | एक इंजन की आवाज़ें। |

`language` दो-अक्षर का कोड (`en`, `ru`) या क्षेत्र या लिपि वाला टैग (`zh-cn`, `pt_BR`, `en-gb`, `es-419`) होता है; टैग को छोटे अक्षरों में बदला जाता है और `-` से जोड़ा जाता है। हर इंजन टैग को अपनी उपलब्ध भाषा से मिलाता है: gtts को उसकी अपनी वर्तनी (`zh-CN`; इसमें कनाडाई फ़्रेंच और यूरोपीय पुर्तगाली नहीं हैं, इसलिए `fr-ca` और `pt-pt` का अर्थ `fr` और `pt`) मिलती है, kokorotts `en-gb` को ब्रिटिश फ़ोनेमाइज़र से बोलता है, xtts को चीनी के लिए `zh-cn` मिलता है, और बाकी इंजन भाषा वाला हिस्सा लेते हैं (`pt-br` का अर्थ `pt`)। जो भाषा इंजन नहीं जानता, वह इंजन की डिफ़ॉल्ट भाषा में बोली जाती है, आम तौर पर अंग्रेज़ी (gtts इसके बजाय विफल होता है); `TTS_LANGUAGE_STRICT=true` होने पर ऐसा अनुरोध 400 पाता है, जिसमें इंजन की भाषाओं की सूची होती है। सख़्त जाँच `stream` के बिना `/api/tts`, `/api/history` और `/v1/audio/speech` पर, और उन सभी इंजनों पर लागू होती है जो अपनी भाषाओं की सूची देते हैं: pyttsx3 और xtts के अलावा किसी बहुभाषी मॉडल वाले coquitts को छोड़कर सभी।

#### वेब UI

दोनों compose फ़ाइलें `ttswww` भी शुरू करती हैं, एक nginx कंटेनर जो वेब UI परोसता है और `/api/` को `ttssrv` की ओर प्रॉक्सी करता है:

```bash
docker compose up --build -d
xdg-open http://localhost:8080      # TTS_WWW_PORT; यदि 8080 व्यस्त है तो इसे बदलें
xdg-open https://localhost:8443     # TTS_WWW_TLS_PORT; स्व-हस्ताक्षरित प्रमाणपत्र, इसे एक बार स्वीकार करें
```

- **Studio** - टेक्स्ट टाइप करें, इंजन / भाषा / आवाज़ चुनें, जनरेट करें, सुनें, सहेजें; हर परिणाम एक इतिहास सूची में जाता है।
- **Voices** - `coquitts` वॉइस क्लोनिंग के लिए WAV वॉइस सैंपल अपलोड या रिकॉर्ड करें; उन्हें चलाएँ, डाउनलोड करें और हटाएँ।
- **Models** - इंजन और इंस्टॉल किए गए / अनुपस्थित मॉडल, वही तालिका जो `ttsgen --list` दिखाता है।

हेडर में गियर सेटिंग्स डायलॉग खोलता है: Studio के लिए डिफ़ॉल्ट इंजन, भाषा और आवाज़, और क्या curl उदाहरण दिखाया जाए; विकल्प ब्राउज़र में संग्रहीत होते हैं। Studio वर्तमान अनुरोध के लिए कॉपी करने के लिए तैयार `curl` कमांड दिखाता है; यह टोकन को प्रिंट करने के बजाय `$TTS_TOKEN` के रूप में संदर्भित करता है। Voices स्क्रीन माइक्रोफ़ोन से सैंपल रिकॉर्ड भी कर सकती है, जिसकी अनुमति ब्राउज़र केवल `https` या `localhost` पर देते हैं - LAN पर UI को https पोर्ट के माध्यम से खोलें। पहली बार शुरू होने पर `./data/certs` में एक स्व-हस्ताक्षरित प्रमाणपत्र जनरेट किया जाता है; इसे बदलने के लिए उन्हीं नामों (`tts.crt`, `tts.key`) के साथ एक असली प्रमाणपत्र माउंट करें।

जब `TTS_TOKENS` सेट होता है, तो UI एक साइन-इन स्क्रीन पर खुलता है और उन टोकनों में से एक माँगता है; ब्राउज़र इसे रखता है और हर अनुरोध के साथ भेजता है। `TTS_TOKENS` के बिना कोई साइन-इन नहीं होता।

#### कॉन्फ़िगरेशन

हर सेटिंग एक एनवायरनमेंट वेरिएबल है; `env.example` उन सभी का दस्तावेज़ीकरण करता है और compose फ़ाइलों के बगल में रखी `.env` अपने आप पढ़ी जाती है। जिन्हें आप सबसे अधिक संभावना से बदलेंगे:

| वेरिएबल | डिफ़ॉल्ट | यह क्या करता है |
| --- | --- | --- |
| `TTS_TOKENS` | खाली | अल्पविराम से अलग किए गए bearer टोकन। खाली का अर्थ है कोई प्रमाणीकरण नहीं। |
| `TTS_ENGINES` | खाली | शुरू में इंस्टॉल और वार्म अप किए जाने वाले इंजन, अल्पविराम से अलग (`coquitts,silerotts`)। |
| `TTS_ENGINE` | `gtts` | वह इंजन जो तब उपयोग होता है जब अनुरोध किसी का नाम नहीं लेता। |
| `TTS_LANGUAGE` | `en` | वह भाषा जो तब उपयोग होती है जब अनुरोध किसी का नाम नहीं लेता। |
| `TTS_LANGUAGE_STRICT` | `false` | `true` होने पर, इंजन की सूची में न होने वाली भाषा के लिए इंजन की डिफ़ॉल्ट भाषा पर लौटने के बजाय 400 लौटाता है। |
| `TTS_POOL_SIZE` | `1` | सभी इंजनों में एक साथ अनुमत सिंथेसिस कॉल; `0` सीमा और वार्मअप हटा देता है। |
| `TTS_QUEUE_SIZE` | `8` | खाली स्लॉट की प्रतीक्षा कर सकने वाले सिंथेसिस अनुरोध; इससे अधिक को तुरंत 503 मिलता है। |
| `TTS_HISTORY_MAX` | `200` | इतिहास में रखे गए आइटम; नया सहेजे जाने पर सबसे पुराने हटा दिए जाते हैं। |
| `TTS_MAX_SAMPLE_BYTES` | `16777216` | सबसे बड़ा वॉइस सैंपल अपलोड (16 MiB)। |
| `TTS_MAX_SAMPLES` | `100` | सर्वर पर रखे गए वॉइस सैंपल। |
| `TTS_MAX_BODY_BYTES` | `2097152` | सबसे बड़ी JSON अनुरोध बॉडी (2 MiB)। |
| `TTS_STREAM_MAX_CHARS` | `200` | `stream=true` के लिए चंक का आकार। |
| `CORS_ORIGINS` | `*` | `/api/*` के लिए अनुमत ऑरिजिन। |
| `TTS_PORT` | `5000` | `ttssrv` का पोर्ट। |
| `TTS_WWW_PORT`, `TTS_WWW_TLS_PORT` | `8080`, `8443` | वेब UI के http और https पोर्ट। |
| `COQUITTS_MODEL`, `COQUITTS_SAMPLE` | `xtts_v2`, `default.wav` | Coqui मॉडल और डिफ़ॉल्ट वॉइस सैंपल। |
| `TZ` | `America/New_York` | लॉग और इतिहास में टाइमस्टैम्प के लिए समय क्षेत्र। |

Docker के बाहर CLI और सर्वर वही कुंजियाँ इन स्रोतों से पढ़ते हैं, सबसे मज़बूत पहले: CLI फ़्लैग, शेल एनवायरनमेंट, `./ttsgen.conf`, `~/.config/ttsgen.conf`, `./.env.local`, `./.env`। कोई फ़ाइल कभी शेल को ओवरराइड नहीं करती, और `.env` केवल वर्तमान डायरेक्टरी से पढ़ी जाती है।

1 से अधिक `TTS_POOL_SIZE` अलग-अलग इंजनों को समानांतर में सिंथेसाइज़ करने देता है; एक इंजन के भीतर कॉल क्रमबद्ध की जाती हैं, क्योंकि अंतर्निहित मॉडल थ्रेड्स के बीच साझा करने के लिए सुरक्षित नहीं हैं।

#### सुरक्षा

- जब तक आप `TTS_TOKENS` सेट नहीं करते, प्रमाणीकरण बंद रहता है। फिर `/api/health` को छोड़कर हर रूट को `Authorization: Bearer <token>` की ज़रूरत होती है, और वेब UI साइन-इन स्क्रीन पर टोकन माँगता है।
- API सभी इंटरफ़ेस पर सुनता है और compose फ़ाइलें होस्ट पर `TTS_PORT`, `TTS_WWW_PORT` और `TTS_WWW_TLS_PORT` प्रकाशित करती हैं। साझा नेटवर्क पर एक टोकन सेट करें, या एक override फ़ाइल में पोर्ट को `127.0.0.1` से बाँधें।
- https लिसनर पहली बार शुरू होने पर बनाए गए स्व-हस्ताक्षरित प्रमाणपत्र का उपयोग करता है; यह LAN के लिए है। इंटरनेट पर UI को असली प्रमाणपत्र वाले अपने रिवर्स प्रॉक्सी के पीछे रखें।
- वॉइस सैंपल, इतिहास और प्रमाणपत्र `./data` के अंतर्गत रहते हैं; इसका बैकअप लें और इसे बिल्ड कॉन्टेक्स्ट से बाहर रखें।

रिपॉज़िटरी के Security टैब के माध्यम से किसी भेद्यता की रिपोर्ट करें, देखें [SECURITY.md](https://github.com/wachawo/text-to-speech/blob/main/SECURITY.md)।

सर्वर के साथ काम करने और उसका परीक्षण करने के लिए एक अलग CLI क्लाइंट है, `ttsapi`। इसमें `ttsgen` जैसे ही मुख्य फ़्लैग हैं, लेकिन सिंथेसिस सर्वर पर चलता है। सर्वर का पता और टोकन `TTS_URL` और `TTS_TOKEN` से लिए जाते हैं।

```bash
ttsapi "Hello world"
ttsapi -i long.txt --output play,file --file out.mp3
```

### प्रोजेक्ट संरचना

```text
text-to-speech/
├── ttsgen.py / ttsplay.py / ttsrec.py / ttsapi.py   # CLI कमांड
├── engines/        # इंजन: gTTS, Piper, Silero, Coqui, Bark, Kokoro, और अन्य
├── libs/           # साझा कोर: API, टूल्स, प्लेबैक, अपवाद
├── install/        # ttsgen --install <engine> के लिए इंस्टॉलर
├── ttssrv/         # Flask HTTP सर्वर
├── www/            # वेब UI: बिना बिल्ड स्टेप के Vue 2, nginx द्वारा परोसा गया
├── nginx/          # nginx मुख्य कॉन्फ़िग और ttswww के लिए conf.d टेम्पलेट
├── docker/         # GPU, CPU और वेब UI के लिए Docker बिल्ड
├── docs/           # प्रति-इंजन दस्तावेज़ और README अनुवाद
└── tests/          # pytest टेस्ट, कोई मॉडल डाउनलोड नहीं और कोई GPU नहीं
```

### विकास

योगदान का स्वागत है; [CONTRIBUTING.md](https://github.com/wachawo/text-to-speech/blob/main/CONTRIBUTING.md) सेटअप, जाँचों और इंजन जोड़ने के तरीके की व्याख्या करता है। विकास निर्भरताओं को इंस्टॉल करने के लिए:

```bash
pip install -e ".[dev]"
```

कमिट करने से पहले जाँचें:

```bash
pytest
ruff check .
black .
```

एक नया इंजन `engines/<name>.py` फ़ाइल के माध्यम से जोड़ा जाता है। आपको केवल दो फ़ंक्शन लागू करने की ज़रूरत है:

```python
def is_available() -> bool:
    ...

def generate(text: str, config: dict) -> bytes:
    ...
```

`is_available()` जाँचता है कि निर्भरताएँ इम्पोर्ट करने योग्य हैं, और `generate()` टेक्स्ट और कॉन्फ़िग लेता है और ऑडियो को MP3 या WAV बाइट्स के रूप में लौटाता है। उसके बाद इंजन CLI और API में अपने आप उपलब्ध हो जाता है।

प्रत्येक इंजन के विस्तृत पैरामीटर और विशेषताएँ [`docs/`](https://github.com/wachawo/text-to-speech/blob/main/docs/ENGINES.md) में वर्णित हैं।

### लाइसेंस

[MIT](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
