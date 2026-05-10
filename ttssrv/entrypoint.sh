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

python3 - <<'PY'
import os, sys
sys.path.insert(0, "/opt")  # bind-mounted libs/ + engines/ + install/ live here
engine = os.environ.get("TTS_ENGINE", "gtts")
from install import run
sys.exit(run(engine, non_interactive=True))
PY

echo "[entrypoint] starting server: $*"
exec "$@"
