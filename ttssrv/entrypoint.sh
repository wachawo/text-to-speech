#!/bin/sh
# Entrypoint for ttssrv container.
#
# Single delegation step: hand TTS_ENGINE to install.run(non_interactive=True).
# Same code path as `ttsgen --install <engine>`. It's idempotent:
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

ENGINE="${TTS_ENGINE:-gtts}"

mkdir -p "${PYTHONUSERBASE:-/opt/userbase}" "${PIP_CACHE_DIR:-/opt/pip-cache}"
PY_VER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
mkdir -p "${PYTHONUSERBASE:-/opt/userbase}/lib/python${PY_VER}/site-packages"
export PATH="${PYTHONUSERBASE:-/opt/userbase}/bin:$PATH"
export PIP_USER=1

echo "[entrypoint] TTS_ENGINE=$ENGINE  PYTHONUSERBASE=${PYTHONUSERBASE:-/opt/userbase}"

# Best-effort engine install. A failure here (no network on first boot,
# upstream release moved, etc.) must NOT kill the container — the API server
# can still serve the engines that are already importable. The `if` form
# also disables `set -e` for the python invocation.
if python3 - <<'PY'
import os, sys
# install/, libs/, engines/ are bind-mounted by compose into site-packages,
# so they're already on sys.path — no path tweak needed here.
engine = os.environ.get("TTS_ENGINE", "gtts")
from install import run
sys.exit(run(engine, non_interactive=True))
PY
then
    echo "[entrypoint] engine install OK"
else
    rc=$?
    echo "[entrypoint] engine install failed (exit=$rc) — starting server anyway"
fi

echo "[entrypoint] starting server: $*"
exec "$@"
