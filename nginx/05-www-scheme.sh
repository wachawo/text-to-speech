#!/bin/sh
# Runs from /docker-entrypoint.d/ before the templates are rendered. The web
# UI listens on TTS_WWW_PORT in the mode TTS_WWW_SCHEME names, and the
# template includes the snippet of that name, so anything but the two modes
# would stop nginx with a missing-file error; stop here with the reason.
set -eu

case "${TTS_WWW_SCHEME:-}" in
    https | http) ;;
    *)
        echo "[www-scheme] TTS_WWW_SCHEME must be https or http, got '${TTS_WWW_SCHEME:-}'" >&2
        exit 1
        ;;
esac
case "${TTS_WWW_PORT:-}" in
    '' | *[!0-9]*)
        echo "[www-scheme] TTS_WWW_PORT must be a port number, got '${TTS_WWW_PORT:-}'" >&2
        exit 1
        ;;
esac
echo "[www-scheme] web UI on ${TTS_WWW_SCHEME} port ${TTS_WWW_PORT}"
