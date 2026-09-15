# Web UI: static Vue 2 files served by nginx, /api/ proxied to ttssrv.
# Build context is the repo root (see docker-compose*.yml).
FROM nginx:1.27-alpine

# openssl for the self-signed certificate the entrypoint script below mints
# when none is mounted; the image ships the library but not the tool.
RUN apk add --no-cache openssl

# Main config replaces the bundled one (error_log level, includes).
COPY nginx/nginx.conf /etc/nginx/nginx.conf

# Runs with the image's other entrypoint scripts, before nginx: a certificate
# for the https listener unless ./data/certs already holds one.
COPY nginx/30-selfsigned-cert.sh /docker-entrypoint.d/30-selfsigned-cert.sh

# The image entrypoint renders /etc/nginx/templates/*.template into
# /etc/nginx/conf.d/ with envsubst at start, filling in TTS_UPSTREAM and
# TTS_WWW_TOKEN from the container environment.
COPY nginx/templates/ /etc/nginx/templates/

# The UI itself; compose bind-mounts ./www over it for edits without a rebuild.
COPY www/ /usr/share/nginx/html/

EXPOSE 80 443
# Entrypoint and CMD stay the image's own: they run the template step, then nginx.
