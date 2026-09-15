#!/bin/sh
# Runs from /docker-entrypoint.d/ before nginx starts. Browsers hand the
# microphone only to a secure page, so the UI has to be reachable over https
# for the Voices screen's REC button; a self-signed certificate is enough for
# that, and this script mints one on the first start when the certs directory
# (bind-mounted from ./data/certs) holds none. The pair is kept, so the
# exception a browser stores for it survives restarts. Mount a real
# certificate under the same two names to replace it.
set -eu

CERT_DIR=/etc/nginx/certs
CERT="$CERT_DIR/tts.crt"
KEY="$CERT_DIR/tts.key"

if [ -s "$CERT" ] && [ -s "$KEY" ]; then
    exit 0
fi

mkdir -p "$CERT_DIR"
openssl req -x509 -nodes -newkey rsa:2048 -days 3650 \
    -subj "/CN=ttswww" \
    -addext "subjectAltName=DNS:ttswww,DNS:localhost,IP:127.0.0.1" \
    -keyout "$KEY" -out "$CERT" >/dev/null 2>&1
echo "[selfsigned-cert] generated $CERT"
