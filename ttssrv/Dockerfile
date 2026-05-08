# GPU image — torch + coqui-tts with CUDA 12.1 wheels.
# Requires nvidia-container-toolkit on host. For pure CPU use Dockerfile-cpu.
#
# Build context is ./ttssrv (this directory) — see docker-compose.yml.
FROM python:3.12-slim

WORKDIR /opt

RUN apt-get update && apt-get install -y --no-install-recommends \
        espeak espeak-data libespeak1 \
        ffmpeg \
        ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# 3rd-party runtime deps (Flask + lightweight engines + torch[cu121] + coqui-tts).
COPY requirements.txt requirements-gpu.txt ./
RUN pip install --no-cache-dir -r requirements-gpu.txt \
    && rm -f requirements*.txt

# Install the text-to-speech package — brings engines/, libs/, and CLIs
# (ttsgen, ttsplay, ttsrec, ttsapi). --no-deps because runtime deps were
# already installed above.
RUN pip install --no-cache-dir --no-deps \
        "text-to-speech @ git+https://github.com/wachawo/text-to-speech.git"

# Server source — copied from this build context (./ttssrv).
COPY __init__.py app1.py validators.py gu.py /opt/ttssrv/

EXPOSE 5000
CMD ["python3", "/opt/ttssrv/app1.py"]
