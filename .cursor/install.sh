#!/usr/bin/env bash
# Idempotent environment bootstrap for the Skirt Steak workspace.
# Prepares a Python virtual environment with the dependencies needed to run
# the DuckDB starter and the Google Drive / Maps / Docs client scripts.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VENV_DIR="$REPO_ROOT/.venv"
PY="$VENV_DIR/bin/python"

# The default image ships CPython 3.12 but not the venv seed package.
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y --no-install-recommends python3.12-venv
fi

if [ ! -x "$PY" ]; then
  python3 -m venv "$VENV_DIR"
fi

"$PY" -m pip install --upgrade pip

# Baseline analysis + tooling stack (README "Quick Start").
"$PY" -m pip install duckdb pandas black pylint

# Project-specific Google API client dependencies.
"$PY" -m pip install \
  -r python/Project/Google_Maps_Linker/requirements.txt \
  -r python/Project/Gem_Factory/tools/gdocs_sync/requirements.txt \
  -r python/msjc_board_secretary/requirements.txt

echo "Environment ready. Activate with: source .venv/bin/activate"
