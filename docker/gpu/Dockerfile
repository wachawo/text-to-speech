ARG BASE_IMAGE=python
ARG BASE_IMAGE_TAG=3.12-slim
FROM ${BASE_IMAGE}:${BASE_IMAGE_TAG} AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /opt

RUN apt-get update && apt-get install -y --no-install-recommends \
        espeak espeak-data libespeak1 \
        ffmpeg \
        build-essential \
        ca-certificates git curl \
    && rm -rf /var/lib/apt/lists/*

COPY ttssrv/requirements.txt        /tmp/base.txt
COPY docker/gpu/requirements.txt    /tmp/extra.txt
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --index-strategy=unsafe-best-match \
        -r /tmp/base.txt -r /tmp/extra.txt \
 && rm /tmp/*.txt

# Copy the package, not a hand-written file list: the enumeration used to omit
# ttssrv/streaming.py, which app1.py imports unconditionally.
COPY ttssrv/ /opt/ttssrv/
RUN chmod +x /opt/ttssrv/entrypoint.sh

ENV PYTHONUSERBASE=/opt/data/userbase \
    PIP_CACHE_DIR=/opt/data/pip-cache \
    PYTHONPATH=/opt

EXPOSE 5000
ENTRYPOINT ["sh", "/opt/ttssrv/entrypoint.sh"]
CMD ["python3", "/opt/ttssrv/app1.py"]
