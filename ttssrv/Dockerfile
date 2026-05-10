# GPU image — heavy ML stack (torch+coqui-tts+transformers) is baked in at
# build time via requirements-gpu.txt. Lightweight extra engines (kokorotts,
# pipertts, barktts) install lazily into a shared PYTHONUSERBASE volume on
# container start when their TTS_ENGINE is selected — see entrypoint.sh.
#
# Package code (libs/, engines/, ttssrv/) is NOT pip-installed — it comes from
# bind-mounts in docker-compose.yml. That keeps the running container in sync
# with the local checkout without rebuild or `docker cp`.
#
# Build context is ./ttssrv (this directory) — see docker-compose.yml.
FROM python:3.12-slim

WORKDIR /opt

RUN apt-get update && apt-get install -y --no-install-recommends \
        espeak espeak-data libespeak1 \
        ffmpeg \
        ca-certificates git curl \
    && rm -rf /var/lib/apt/lists/*

# 3rd-party runtime deps. requirements-gpu.txt = requirements.txt + torch (cu121)
# + coqui-tts[codec] + transformers — split on purpose so the CPU image
# (Dockerfile-cpu) can pull cpu wheels from the same source layout.
COPY requirements.txt requirements-gpu.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements-gpu.txt \
    && rm /tmp/requirements*.txt

# Server source — copied so the image runs standalone (`docker run`).
# At runtime the same paths are bind-mounted from ./ttssrv (compose volumes),
# so live code edits don't need a rebuild.
COPY __init__.py app1.py validators.py gu.py entrypoint.sh /opt/ttssrv/
RUN chmod +x /opt/ttssrv/entrypoint.sh

# Lazy-install target for non-default engines (kokoro/piper/bark) added by
# entrypoint.sh on demand. Coqui+torch are already in the image, so most
# users never touch this volume.
ENV PYTHONUSERBASE=/opt/userbase \
    PIP_CACHE_DIR=/opt/pip-cache

EXPOSE 5000
ENTRYPOINT ["sh", "/opt/ttssrv/entrypoint.sh"]
CMD ["python3", "/opt/ttssrv/app1.py"]
