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
# Build:
#   docker compose -f docker/gpu/docker-compose.yml build
#   # or with a different base image (advanced — must already include python3.12):
#   docker build -f docker/gpu/Dockerfile \
#     --build-arg BASE_IMAGE=nvcr.io/nvidia/cuda \
#     --build-arg BASE_IMAGE_TAG=12.4.1-cudnn-runtime-ubuntu22.04 ...
#
# Build context is the repo root — see compose `build.context: ../..`.
ARG BASE_IMAGE=python
ARG BASE_IMAGE_TAG=3.12-slim
FROM ${BASE_IMAGE}:${BASE_IMAGE_TAG} AS base

# uv (https://github.com/astral-sh/uv) — drop-in pip replacement, ~5–10x faster
# resolver+installer with parallel wheel downloads. Pin to a tag once you've
# validated; `latest` is fine for first try.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /opt

RUN apt-get update && apt-get install -y --no-install-recommends \
        espeak espeak-data libespeak1 \
        ffmpeg \
        ca-certificates git curl \
    && rm -rf /var/lib/apt/lists/*

# Two requirement files: web-stack base + heavy GPU ML stack. uv installs
# system-wide (--system) into the same /usr/local/lib/python3.12/site-packages
# pip would, so the bind-mounts and PYTHONUSERBASE behavior are unchanged.
#
# --index-strategy=unsafe-best-match makes uv consider all indices for each
# package (matching pip's behavior). Without it uv defaults to first-index,
# which would pick CPU torch from PyPI over cu121 wheels from the extra index.
#
# --mount=type=cache keeps uv's wheel cache across builds without baking it
# into the image (requires BuildKit, which is the docker compose default).
COPY ttssrv/requirements.txt        /tmp/base.txt
COPY docker/gpu/requirements.txt    /tmp/extra.txt
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --index-strategy=unsafe-best-match \
        -r /tmp/base.txt -r /tmp/extra.txt \
 && rm /tmp/*.txt

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
