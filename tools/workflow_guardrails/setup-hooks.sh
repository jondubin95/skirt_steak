#!/usr/bin/env bash
# Bash port of setup-hooks.ps1 for Linux/macOS/Cloud Agent shells.
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "Not inside a git repository." >&2
  exit 1
}

hooks_dir="$repo_root/.githooks"
if [ ! -d "$hooks_dir" ]; then
  echo "Missing hooks directory: $hooks_dir" >&2
  exit 1
fi

git -C "$repo_root" config core.hooksPath .githooks

configured="$(git -C "$repo_root" config --get core.hooksPath || true)"
if [ -z "$configured" ]; then
  echo "Failed to read core.hooksPath after setup. Check repository permissions." >&2
  exit 1
fi

echo "Hooks configured."
echo "Repository: $repo_root"
echo "core.hooksPath: $configured"
echo "Active hooks:"
for f in "$hooks_dir"/*; do
  [ -f "$f" ] && echo "  - $(basename "$f")"
done
