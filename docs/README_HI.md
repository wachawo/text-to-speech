## text-to-speech — TTS इंजनों के लिए एक एकल इंटरफ़ेस

[![CI](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/text-to-speech/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/text-to-speech/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

`text-to-speech` आपको एक ही इंटरफ़ेस के माध्यम से कई स्पीच-सिंथेसिस इंजनों के साथ काम करने देता है। आप ऑनलाइन gTTS से शुरुआत कर सकते हैं और बाद में स्थानीय Piper, Silero, Coqui, Bark, या Kokoro पर स्विच कर सकते हैं — अपने CLI कमांड, Python कोड, या HTTP इंटीग्रेशन को फिर से लिखे बिना।

यह प्रोजेक्ट स्थानीय उपयोग, ऑटोमेशन, और नेटवर्क पर अपना खुद का TTS सर्वर चलाने के लिए उपयुक्त है।

[English](https://github.com/wachawo/text-to-speech/blob/main/README.md) | [Español](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/text-to-speech/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/text-to-speech/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/text-to-speech/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/text-to-speech/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/text-to-speech/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/text-to-speech/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/text-to-speech/blob/main/docs/README_JA.md) | **[हिन्दी](https://github.com/wachawo/text-to-speech/blob/main/docs/README_HI.md)** | [한국어](https://github.com/wachawo/text-to-speech/blob/main/docs/README_KR.md)

* **विभिन्न इंजनों के साथ काम करने का एक ही तरीका।** आपको जिस इंजन की ज़रूरत है उसे चुनें और उसे CLI (`ttsgen`), Python API (`libs.api`), या HTTP API के माध्यम से कॉल करें।
* **आप पूरी तरह स्थानीय रूप से काम कर सकते हैं।** Piper, Silero, Coqui, Bark, Kokoro, और `pyttsx3` सभी आपकी अपनी मशीन पर चलते हैं।
* **एक उपयोग के लिए तैयार HTTP सर्वर शामिल है।** `ttssrv` स्टार्टअप पर मॉडल लोड करता है और आपके स्थानीय नेटवर्क की अन्य मशीनों से आने वाले अनुरोधों को संभालता है।

### इंजन

| Engine      | ऑफ़लाइन | हार्डवेयर     | गुणवत्ता | किसके लिए अच्छा                                  |
| ----------- | ------- | ------------- | ------- | ---------------------------------------------- |
| `gtts`      | ❌      | CPU           | ★★★★    | त्वरित शुरुआत और बड़ी संख्या में भाषाएँ            |
| `pyttsx3`   | ✅      | CPU           | ★★      | espeak या SAPI के माध्यम से सरल स्थानीय स्पीच       |
| `pipertts`  | ✅      | CPU           | ★★★★    | कई भाषाओं में तेज़ ऑफ़लाइन सिंथेसिस                 |
| `silerotts` | ✅      | CPU           | ★★★★    | रूसी स्पीच और एक हल्का स्थानीय सेटअप               |
| `kokorotts` | ✅      | CPU           | ★★★★    | बहुभाषी ऑफ़लाइन सिंथेसिस                          |
| `coquitts`  | ✅      | CPU / **GPU** | ★★★★★   | उच्च-गुणवत्ता वाली आवाज़ें और वॉइस क्लोनिंग         |
| `barktts`   | ✅      | CPU / **GPU** | ★★★★★   | अभिव्यंजक स्पीच, भावनाएँ, संगीत, और गायन          |

`gtts`, `pyttsx3`, `pipertts`, `silerotts`, और `kokorotts` CPU पर ठीक से चलते हैं। `coquitts` और `barktts` बिना GPU के भी चल सकते हैं, लेकिन सिंथेसिस काफ़ी धीमा होता है — उनके लिए एक CUDA-सक्षम ग्राफ़िक्स कार्ड की अनुशंसा की जाती है।

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

docker compose up --build -d                          # GPU / CUDA 12.1
docker compose -f docker-compose-cpu.yml up --build -d # केवल CPU
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
├── docker/         # GPU और CPU के लिए Docker बिल्ड
├── docs/           # प्रति-इंजन दस्तावेज़ और README अनुवाद
└── tests/          # pytest टेस्ट, कोई मॉडल डाउनलोड नहीं और कोई GPU नहीं
```

### विकास

विकास निर्भरताओं को इंस्टॉल करने के लिए:

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

प्रत्येक इंजन के विस्तृत पैरामीटर और विशेषताएँ [`docs/`](ENGINES.md) में वर्णित हैं।

### लाइसेंस

[MIT](../LICENSE)
