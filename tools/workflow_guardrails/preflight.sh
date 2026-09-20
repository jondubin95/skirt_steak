#!/usr/bin/env bash
# Bash port of preflight.ps1 for Linux/macOS/Cloud Agent shells.
#
# Usage:
#   tools/workflow_guardrails/preflight.sh
#   tools/workflow_guardrails/preflight.sh --dry-run-sync
#
# Optional overrides (env vars):
#   SYNC_SOURCE, CLIENT_SECRETS, TOKEN_PATH, MAP_PATH
set -euo pipefail

dry_run_sync=0
for arg in "$@"; do
  case "$arg" in
    --dry-run-sync) dry_run_sync=1 ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 1
      ;;
  esac
done

repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "Not inside a git repository." >&2
  exit 1
}

branch="$(git -C "$repo_root" branch --show-current)"
cwd="$(pwd)"

sync_source="${SYNC_SOURCE:-python/Project/Gem_Factory/Jons_Gems/clarity-concision-editor/internal/core/instructions}"
client_secrets="${CLIENT_SECRETS:-Sensitive/credentials.json}"
token_path="${TOKEN_PATH:-Sensitive/google/gdocs_token.json}"
map_path="${MAP_PATH:-Sensitive/google/clarity-concision-editor.gdocs-map.json}"

resolve() {
  local value="$1"
  if [[ "$value" = /* ]]; then
    echo "$value"
  else
    echo "$repo_root/$value"
  fi
}

sync_script_rel="python/Project/Gem_Factory/tools/gdocs_sync/sync_gem_folder_to_gdocs.py"
sync_script_abs="$repo_root/$sync_script_rel"

source_abs="$(resolve "$sync_source")"
client_secrets_abs="$(resolve "$client_secrets")"
token_abs="$(resolve "$token_path")"
map_abs="$(resolve "$map_path")"

errors=()
warnings=()

if [ "$branch" = "main" ] || [ "$branch" = "master" ]; then
  errors+=("Current branch is '$branch'. Use a feature branch before sync/commit.")
fi

[ -f "$sync_script_abs" ] || errors+=("Sync script not found: $sync_script_abs")
[ -e "$source_abs" ] || errors+=("Sync source path not found: $source_abs")
[ -f "$client_secrets_abs" ] || errors+=("Client secrets file not found: $client_secrets_abs")

token_parent="$(dirname "$token_abs")"
map_parent="$(dirname "$map_abs")"
[ -d "$token_parent" ] || errors+=("Token parent directory is missing: $token_parent (create with: mkdir -p \"$token_parent\")")
[ -d "$map_parent" ] || errors+=("Map parent directory is missing: $map_parent (create with: mkdir -p \"$map_parent\")")

cwd_variant_a="$cwd/tools/gdocs_sync/sync_gem_folder_to_gdocs.py"
cwd_variant_b="$cwd/python/Project/Gem_Factory/tools/gdocs_sync/sync_gem_folder_to_gdocs.py"
if [ ! -f "$cwd_variant_a" ] && [ ! -f "$cwd_variant_b" ]; then
  warnings+=("Current directory does not match the two standard command layouts.")
fi

root_command=$(cat <<'EOF'
.venv/bin/python python/Project/Gem_Factory/tools/gdocs_sync/sync_gem_folder_to_gdocs.py \
  --src python/Project/Gem_Factory/Jons_Gems/clarity-concision-editor/internal/core/instructions \
  --title-prefix "Polish - " \
  --client-secrets Sensitive/credentials.json \
  --token Sensitive/google/gdocs_token.json \
  --map Sensitive/google/clarity-concision-editor.gdocs-map.json
EOF
)

gem_factory_command=$(cat <<'EOF'
../../../.venv/bin/python tools/gdocs_sync/sync_gem_folder_to_gdocs.py \
  --src Jons_Gems/clarity-concision-editor/internal/core/instructions \
  --title-prefix "Polish - " \
  --client-secrets ../../../Sensitive/credentials.json \
  --token ../../../Sensitive/google/gdocs_token.json \
  --map ../../../Sensitive/google/clarity-concision-editor.gdocs-map.json
EOF
)

echo "Workflow preflight"
echo "Repo root : $repo_root"
echo "Branch    : $branch"
echo "CWD       : $cwd"
echo "Sync src  : $source_abs"
echo

if [ "${#warnings[@]}" -gt 0 ]; then
  echo "Warnings:"
  for w in "${warnings[@]}"; do echo "  - $w"; done
  echo
fi

if [ "${#errors[@]}" -gt 0 ]; then
  echo "Preflight failed:"
  for e in "${errors[@]}"; do echo "  - $e"; done
  echo
  echo "Standard sync command from repo root:"
  echo "$root_command"
  echo
  echo "Standard sync command from python/Project/Gem_Factory:"
  echo "$gem_factory_command"
  exit 1
fi

echo "Preflight checks passed."
echo
echo "Standard sync command from repo root:"
echo "$root_command"
echo
echo "Standard sync command from python/Project/Gem_Factory:"
echo "$gem_factory_command"

if [ "$dry_run_sync" -eq 1 ]; then
  echo
  echo "Running dry-run sync..."
  python_exe="$repo_root/.venv/bin/python"
  [ -x "$python_exe" ] || python_exe="python3"

  "$python_exe" "$sync_script_abs" \
    --src "$source_abs" \
    --title-prefix "Polish - " \
    --client-secrets "$client_secrets_abs" \
    --token "$token_abs" \
    --map "$map_abs" \
    --dry-run
fi
