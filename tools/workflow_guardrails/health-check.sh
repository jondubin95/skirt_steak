#!/usr/bin/env bash
# Calls tools/workflow_guardrails/health_check.py. That file is the check.
set -uo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "Not inside a git repository." >&2
  exit 2
}
cd "$repo_root"

python_bin=""
if command -v python >/dev/null 2>&1; then
  python_bin="$(command -v python)"
elif command -v python3 >/dev/null 2>&1; then
  python_bin="$(command -v python3)"
fi

if [[ -z "$python_bin" ]]; then
  echo "[DID_NOT_RUN] health check"
  echo "  python tools/workflow_guardrails/health_check.py"
  echo "  python is not on PATH"
  echo "pass=0 fail=0 did_not_run=1"
  echo "overall: not success"
  exit 2
fi

exec "$python_bin" "$repo_root/tools/workflow_guardrails/health_check.py" "$@"
