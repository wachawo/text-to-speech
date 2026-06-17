#!/bin/sh
# Entrypoint for ttssrv container.
#
# Installs every engine listed in TTS_ENGINES (comma-separated; falls back to
# the single TTS_ENGINE) via install.run(non_interactive=True) — same code path
# as `ttsgen --install <engine>`. It's idempotent:
#   - pip "already satisfied" for engines baked into the image
#   - download_file()/predownload_model() skip when files exist in the mounted
#     cache directory (cache/<engine>/)
# So the heavy work happens once on the first start of each engine; all
# subsequent restarts come up in seconds.
#
# PIP_USER=1 forces every pip install spawned inside install/ to land in
# PYTHONUSERBASE (a mounted volume). That's how non-default engines (kokorotts,
# pipertts, barktts) survive container recreate without rebuilding the image.

set -eu

ENGINES="${TTS_ENGINES:-${TTS_ENGINE:-gtts}}"

mkdir -p "${PYTHONUSERBASE:-/opt/userbase}" "${PIP_CACHE_DIR:-/opt/pip-cache}"
PY_VER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
mkdir -p "${PYTHONUSERBASE:-/opt/userbase}/lib/python${PY_VER}/site-packages"
export PATH="${PYTHONUSERBASE:-/opt/userbase}/bin:$PATH"
export PIP_USER=1

echo "[entrypoint] TTS_ENGINES=$ENGINES  PYTHONUSERBASE=${PYTHONUSERBASE:-/opt/userbase}"

# Best-effort engine install, one engine at a time. A failure here (no network
# on first boot, upstream release moved, etc.) must NOT kill the container — the
# API server can still serve the engines that are already importable, and the
# remaining engines in the list still get their turn. The `if` form disables
# `set -e` for the python invocation.
OLDIFS=$IFS
IFS=','
for ENGINE in $ENGINES; do
    ENGINE=$(echo "$ENGINE" | tr -d ' ')
    [ -z "$ENGINE" ] && continue
    # install/, libs/, engines/ are bind-mounted by compose into site-packages,
    # so they're already on sys.path — no path tweak needed here.
    if python3 - "$ENGINE" <<'PY'
import sys
from install import run
sys.exit(run(sys.argv[1], non_interactive=True))
PY
    then
        echo "[entrypoint] $ENGINE install OK"
    else
        rc=$?
        echo "[entrypoint] $ENGINE install failed (exit=$rc) — continuing"
    fi
done
IFS=$OLDIFS

echo "[entrypoint] starting server: $*"
exec "$@"
