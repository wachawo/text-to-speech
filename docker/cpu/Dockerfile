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
COPY docker/cpu/requirements.txt    /tmp/extra.txt
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --index-strategy=unsafe-best-match \
        -r /tmp/base.txt -r /tmp/extra.txt \
 && rm /tmp/*.txt

COPY ttssrv/__init__.py ttssrv/app1.py ttssrv/validators.py ttssrv/gu.py ttssrv/entrypoint.sh \
     /opt/ttssrv/
RUN chmod +x /opt/ttssrv/entrypoint.sh

ENV PYTHONUSERBASE=/opt/data/userbase \
    PIP_CACHE_DIR=/opt/data/pip-cache \
    PYTHONPATH=/opt

EXPOSE 5000
ENTRYPOINT ["sh", "/opt/ttssrv/entrypoint.sh"]
CMD ["python3", "/opt/ttssrv/app1.py"]
