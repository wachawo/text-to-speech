# Çevrimiçi ve Çevrimdışı Yeteneklere Sahip Evrensel Metin Okuma Sistemi

## Proje Özeti

Bu kütüphane, çeşitli metin okuma (sentezleme) sistemleri için birleşik bir arayüz sağlar. Gereksinimlere ve internet bağlantı durumuna bağlı olarak, çevrimiçi ve çevrimdışı motorlar arasında kesintisiz geçiş yapılmasına olanak tanır.

Temel Özellikler:
- Google TTS aracılığıyla çevrimiçi sentezleme
- espeak ve Piper kullanarak çevrimdışı sentezleme
- Tüm motorlar için tek ve birleşik arayüz
- Çoklu dil desteği
- Birden fazla ses çıkış formatı
- CLI (Komut Satırı Arayüzü) ve Python API desteği

## Kurulum
```bash
# System dependencies (Linux)
sudo apt install espeak espeak-data libespeak1 python3-pip
# Python dependencies
pip install -r requirements.txt
```

## Kullanım

### Basit Örnek

```bash
# Google TTS (online)
python cli.py "Hello world"
# espeak (offline)
python cli.py "Hello world" --engine pyttsx3
# Another languages
python cli.py "Hola amigo!" --language es
# Save with automatic name
python cli.py "Hello world" --file
# Save to specific file
python cli.py "Hello world" --file output.mp3
# Google TTS (best quality)
python cli.py "Hello world" --engine gtts
# espeak (fast, offline)
python cli.py "Hello world" --engine pyttsx3
# Piper (high-quality offline)
python cli.py "Hello world" --engine pipertts
# Read from file
python cli.py -i input.txt
python cli.py -i input.txt --file output.mp3
# BytesIO
python cli.py "Hello world" --stdout | python3 play.py
# Multiple outputs
python cli.py "Hello world" --output play,file 
```

### Python API

```python
from libs.api import text_to_speech_file, text_to_speech_bytes

# Save to file
filename = text_to_speech_file("Hello world!", engine="gtts")
print(f"File created: {filename}")

# Get as bytes (for web apps)
audio_bytes = text_to_speech_bytes("Hello world!", engine="gtts")
```

## Proje Mimarisi

```
text-to-speech/
├── engines/
│   ├── gtts.py
│   ├── pyttsx3.py
│   ├── silerotts.py
│   ├── coquitts.py
│   └── piper.py
├── libs/
│   ├── api.py
│   ├── tools.py
│   ├── playback.py
│   └── exceptions.py
├── bin/
│   ├── install_pipertts.sh
│   ├── install_coquitts.sh
│   └── install_silerotts.sh
├── docs/
│   ├── COQUITTS.md
│   ├── ENGINES.md
│   ├── PIPERTTS.md
│   └── SILEROTTS.md
├── cli.py
├── test_tts.py
├── play.py
└── requirements.txt

```

## Bağımlılıkların Kurulumu

Çalışma zamanı (kullanıcı) bağımlılıklarını yükleyin:

```bash
pip install -r requirements.txt
```

Install developer tools (linters, type checkers, test tools):

```bash
pip install -r requirements-dev.txt
```

## License

MIT License
