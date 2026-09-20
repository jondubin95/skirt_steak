#!/usr/bin/env bash
# Bash port of diagnostics.ps1 for Linux/macOS/Cloud Agent shells.
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "Not inside a git repository." >&2
  exit 1
}

branch="$(git -C "$repo_root" branch --show-current)"
hooks_path="$(git -C "$repo_root" config --get core.hooksPath || true)"
[ -n "$hooks_path" ] || hooks_path="(not set)"

mapfile -t staged < <(git -C "$repo_root" diff --cached --name-only)

echo "Workflow diagnostics"
echo "Repo root      : $repo_root"
echo "Current branch : $branch"
echo "core.hooksPath : $hooks_path"
echo

if [ "$branch" = "main" ] || [ "$branch" = "master" ]; then
  echo "Branch status  : BLOCKED for commit/push guardrails"
else
  echo "Branch status  : OK (feature/agent branch)"
fi

echo
echo "Staged files:"
if [ "${#staged[@]}" -eq 0 ]; then
  echo "  (none)"
else
  for f in "${staged[@]}"; do echo "  - $f"; done
fi

sensitive_staged=()
for f in "${staged[@]}"; do
  case "$f" in
    Sensitive/*|sensitive/*) sensitive_staged+=("$f") ;;
  esac
done

echo
if [ "${#sensitive_staged[@]}" -gt 0 ]; then
  echo "Sensitive staged files detected (commit will be blocked):"
  for f in "${sensitive_staged[@]}"; do echo "  - $f"; done
else
  echo "Sensitive staged files: none detected."
fi

hook_dir="$repo_root/.githooks"
echo
echo "Hook files:"
if [ ! -d "$hook_dir" ]; then
  echo "  Missing .githooks directory."
else
  for f in "$hook_dir"/*; do
    [ -f "$f" ] && echo "  - $(basename "$f")"
  done
fi
