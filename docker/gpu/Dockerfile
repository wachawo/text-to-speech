# GPU image — heavy ML stack (torch+coqui-tts+transformers) baked in at build
# time via docker/gpu/requirements.txt on top of ttssrv/requirements.txt (web
# stack). Lightweight extra engines (kokorotts, pipertts, barktts) install
# lazily into PYTHONUSERBASE volume on container start when their TTS_ENGINE
# is selected — see ttssrv/entrypoint.sh.
#
# Package code (libs/, engines/, install/, ttssrv/) is NOT pip-installed —
# it comes from bind-mounts in docker/gpu/docker-compose.yml. Live local
# edits don't need a rebuild.
#
# Build context is the repo root — see compose `build.context: ../..`.
FROM python:3.12-slim

WORKDIR /opt

RUN apt-get update && apt-get install -y --no-install-recommends \
        espeak espeak-data libespeak1 \
        ffmpeg \
        ca-certificates git curl \
    && rm -rf /var/lib/apt/lists/*

# Two requirement files: web stack base + heavy GPU ML stack.
COPY ttssrv/requirements.txt        /tmp/base.txt
COPY docker/gpu/requirements.txt    /tmp/extra.txt
RUN pip install --no-cache-dir -r /tmp/base.txt -r /tmp/extra.txt && rm /tmp/*.txt

# Server source — copied so the image runs standalone (`docker run`).
# At runtime the same files are bind-mounted from ttssrv/ via compose volumes,
# so live edits don't need a rebuild.
COPY ttssrv/__init__.py ttssrv/app1.py ttssrv/validators.py ttssrv/gu.py ttssrv/entrypoint.sh \
     /opt/ttssrv/
RUN chmod +x /opt/ttssrv/entrypoint.sh

# Lazy-install target for non-default engines (kokoro/piper/bark) added by
# entrypoint.sh on demand.
ENV PYTHONUSERBASE=/opt/userbase \
    PIP_CACHE_DIR=/opt/pip-cache

EXPOSE 5000
ENTRYPOINT ["sh", "/opt/ttssrv/entrypoint.sh"]
CMD ["python3", "/opt/ttssrv/app1.py"]
