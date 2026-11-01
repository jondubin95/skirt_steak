#!/usr/bin/env bash
# Read-only health check for skirt_steak.
#
# Mirrors the lint job in .github/workflows/guardrails.yml, then runs
# preflight.sh and diagnostics.sh. Does not install packages, change git
# config, stage files, or contact the network. Does not run setup-hooks
# or preflight --dry-run-sync.
#
# Differences from the workflow, so the tree stays untouched and advisory
# tools cannot hide a problem:
# - py_compile writes bytecode to a temp directory instead of __pycache__/
# - pytest adds -p no:cacheprovider
# - pylint omits --exit-zero (still reported as advisory)
#
# Exit 0 only when every check is PASS.
# Exit 1 when any check is FAIL.
# Exit 2 when nothing failed but at least one check did not run.
set -uo pipefail

if [[ $# -gt 0 ]]; then
  echo "health-check.sh takes no arguments and does not modify the repo." >&2
  exit 2
fi

repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "Not inside a git repository." >&2
  exit 2
}
cd "$repo_root"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/skirt-steak-health-pycache-$$"
export NO_COLOR=1

python_bin=""
if command -v python >/dev/null 2>&1; then
  python_bin="$(command -v python)"
elif command -v python3 >/dev/null 2>&1; then
  python_bin="$(command -v python3)"
fi

pass_count=0
fail_count=0
did_not_run_count=0

quote_shell() {
  printf '%q' "$1"
}

record_pass() {
  local role="$1"
  local name="$2"
  local command_display="$3"
  echo "[PASS] ($role) $name"
  echo "  command: $command_display"
  pass_count=$((pass_count + 1))
}

record_fail() {
  local role="$1"
  local name="$2"
  local command_display="$3"
  local exit_code="$4"
  local log_path="$5"
  echo "[FAIL] ($role) $name"
  echo "  command: $command_display"
  echo "  exit: $exit_code"
  if [[ -s "$log_path" ]]; then
    echo "  output:"
    tail -n 40 "$log_path" | sed 's/^/    /'
  fi
  fail_count=$((fail_count + 1))
}

record_did_not_run() {
  local role="$1"
  local name="$2"
  local command_display="$3"
  local reason="$4"
  echo "[DID_NOT_RUN] ($role) $name"
  echo "  command: $command_display"
  echo "  reason: $reason"
  did_not_run_count=$((did_not_run_count + 1))
}

run_shell_command() {
  local role="$1"
  local name="$2"
  local command_display="$3"
  local log_path
  local exit_code
  log_path="$(mktemp)"
  set +e
  bash -c "$command_display" >"$log_path" 2>&1
  exit_code=$?
  if [[ $exit_code -eq 0 ]]; then
    record_pass "$role" "$name" "$command_display"
    if [[ -s "$log_path" ]]; then
      echo "  output:"
      if [[ "$role" == "workflow" ]]; then
        sed 's/^/    /' "$log_path"
      else
        tail -n 20 "$log_path" | sed 's/^/    /'
      fi
    fi
  elif [[ "$role" == "workflow" ]]; then
    echo "[FAIL] ($role) $name"
    echo "  command: $command_display"
    echo "  exit: $exit_code"
    if [[ -s "$log_path" ]]; then
      echo "  output:"
      sed 's/^/    /' "$log_path"
    fi
    fail_count=$((fail_count + 1))
  else
    record_fail "$role" "$name" "$command_display" "$exit_code" "$log_path"
  fi
  rm -f "$log_path"
}

python_module_imports() {
  local module_list="$1"
  "$python_bin" -c "import ${module_list}" >/dev/null 2>&1
}

echo "health-check (read-only)"
echo "repo: $repo_root"
echo "branch: $(git branch --show-current)"
if [[ -n "$python_bin" ]]; then
  echo "python: $python_bin"
else
  echo "python: missing"
fi
echo

tree_before="$(git status --porcelain)"

# CI runs `python -m py_compile` in place, which writes __pycache__. This
# compiles the same files and puts the bytecode in a temp directory.
syntax_program=$(cat <<'PY'
import pathlib
import py_compile
import shutil
import sys
import tempfile

files = sorted(pathlib.Path("python").rglob("*.py"))
if not files:
    sys.exit("no Python files under python/")
temporary = tempfile.mkdtemp(prefix="skirt-steak-py-compile-")
try:
    for source_path in files:
        target = pathlib.Path(temporary) / (str(source_path).replace("/", "_") + ".pyc")
        py_compile.compile(str(source_path), cfile=str(target), doraise=True)
finally:
    shutil.rmtree(temporary, ignore_errors=True)
print("compiled %d files" % len(files))
PY
)

if [[ -z "$python_bin" ]]; then
  record_did_not_run "blocking" "syntax check (py_compile)" "python -c <script>" "python is not on PATH"
else
  syntax_log="$(mktemp)"
  set +e
  "$python_bin" -c "$syntax_program" >"$syntax_log" 2>&1
  syntax_exit=$?
  syntax_display="$python_bin -c <script>"
  if [[ $syntax_exit -eq 0 ]]; then
    record_pass "blocking" "syntax check (py_compile)" "$syntax_display"
  else
    record_fail "blocking" "syntax check (py_compile)" "$syntax_display" "$syntax_exit" "$syntax_log"
  fi
  echo "  script:"
  printf '%s\n' "$syntax_program" | sed 's/^/    /'
  if [[ -s "$syntax_log" && $syntax_exit -eq 0 ]]; then
    echo "  output:"
    tail -n 20 "$syntax_log" | sed 's/^/    /'
  fi
  rm -f "$syntax_log"
fi

board_command="python -m unittest discover -s python/msjc_board_secretary/tests -p 'test_*.py'"
decision_command="python -m unittest discover -s python/decision_log/tests -p 'test_*.py'"
fanfic_command="python -m pytest -q -p no:cacheprovider"
fanfic_cwd="python/fanfic_story_doctor"
ruff_command="python -m ruff check python"
black_command="python -m black --check python"
pylint_command="python -m pylint <python/*.py>  # CI adds --exit-zero and discovers these with find python -maxdepth 1 -name '*.py'"

if [[ -z "$python_bin" ]]; then
  record_did_not_run "blocking" "board secretary unit tests" "$board_command" "python is not on PATH"
  record_did_not_run "blocking" "decision log unit tests" "$decision_command" "python is not on PATH"
  record_did_not_run "blocking" "fanfic story doctor tests" "$fanfic_command (cwd: $fanfic_cwd)" "python is not on PATH"
  record_did_not_run "blocking" "ruff fail-fast and naming" "$ruff_command" "python is not on PATH"
  record_did_not_run "advisory" "black --check" "$black_command" "python is not on PATH"
  record_did_not_run "advisory" "pylint" "$pylint_command" "python is not on PATH"
else
  quoted_python="$(quote_shell "$python_bin")"
  board_command="${quoted_python} -m unittest discover -s python/msjc_board_secretary/tests -p 'test_*.py'"
  run_shell_command "blocking" "board secretary unit tests" "$board_command"

  decision_command="${quoted_python} -m unittest discover -s python/decision_log/tests -p 'test_*.py'"
  if python_module_imports "duckdb"; then
    run_shell_command "blocking" "decision log unit tests" "$decision_command"
  else
    record_did_not_run "blocking" "decision log unit tests" "$decision_command" "duckdb is not importable, so the tests were not started"
  fi

  fanfic_command="cd $(quote_shell "$repo_root/$fanfic_cwd") && ${quoted_python} -m pytest -q -p no:cacheprovider"
  if python_module_imports "pytest, yaml, jsonschema"; then
    run_shell_command "blocking" "fanfic story doctor tests" "$fanfic_command"
  else
    record_did_not_run "blocking" "fanfic story doctor tests" "$fanfic_command" "pytest, PyYAML, or jsonschema is not importable, so the tests were not started"
  fi

  ruff_command="${quoted_python} -m ruff check python"
  if "$python_bin" -m ruff --version >/dev/null 2>&1; then
    run_shell_command "blocking" "ruff fail-fast and naming" "$ruff_command"
  else
    record_did_not_run "blocking" "ruff fail-fast and naming" "$ruff_command" "ruff is not installed for this interpreter"
  fi

  black_command="${quoted_python} -m black --check python"
  if "$python_bin" -m black --version >/dev/null 2>&1; then
    run_shell_command "advisory" "black --check" "$black_command"
  else
    record_did_not_run "advisory" "black --check" "$black_command" "black is not installed for this interpreter"
  fi

  pylint_files=()
  while IFS= read -r pylint_file; do
    pylint_files+=("$pylint_file")
  done < <(find python -maxdepth 1 -name '*.py' | sort)
  if [[ ${#pylint_files[@]} -eq 0 ]]; then
    record_did_not_run "advisory" "pylint" "python -m pylint" "no Python files directly under python/"
  elif "$python_bin" -m pylint --version >/dev/null 2>&1; then
    quoted_pylint_files=""
    for pylint_file in "${pylint_files[@]}"; do
      quoted_pylint_files+=" $(quote_shell "$pylint_file")"
    done
    pylint_command="${quoted_python} -m pylint${quoted_pylint_files}"
    run_shell_command "advisory" "pylint" "$pylint_command"
  else
    record_did_not_run "advisory" "pylint" "${quoted_python} -m pylint python/*.py" "pylint is not installed for this interpreter"
  fi
fi

fanfic_ignore_command=$(cat <<'EOF'
pkg=python/fanfic_story_doctor
for path in drafts/x.txt works/x/ch01.md runs/run.json cache/key.json eval/holdout/set.yaml; do
  git check-ignore -q --no-index "$pkg/$path" || { echo "$pkg/$path is not gitignored"; exit 1; }
done
for path in tests/fixtures/ashfall/ch01.md; do
  if git check-ignore -q --no-index "$pkg/$path"; then echo "$pkg/$path should be tracked"; exit 1; fi
done
echo "fanfic ignore rules ok"
EOF
)
run_shell_command "blocking" "fanfic story doctor private paths are gitignored" "$fanfic_ignore_command"

preflight_command="bash $(quote_shell "$repo_root/tools/workflow_guardrails/preflight.sh")"
run_shell_command "workflow" "workflow preflight" "$preflight_command"

diagnostics_command="bash $(quote_shell "$repo_root/tools/workflow_guardrails/diagnostics.sh")"
run_shell_command "workflow" "workflow diagnostics" "$diagnostics_command"

tree_after="$(git status --porcelain)"
tree_command="git status --porcelain (compared before and after the checks above)"
if [[ "$tree_before" == "$tree_after" ]]; then
  record_pass "guard" "working tree unchanged by this health check" "$tree_command"
else
  tree_log="$(mktemp)"
  {
    echo "before:"
    printf '%s\n' "$tree_before"
    echo "after:"
    printf '%s\n' "$tree_after"
  } >"$tree_log"
  record_fail "guard" "working tree unchanged by this health check" "$tree_command" 1 "$tree_log"
  rm -f "$tree_log"
fi

echo
echo "result: pass=${pass_count} fail=${fail_count} did_not_run=${did_not_run_count}"
if [[ "$fail_count" -eq 0 && "$did_not_run_count" -eq 0 ]]; then
  echo "overall: success"
  exit 0
fi
echo "overall: not success"
if [[ "$fail_count" -gt 0 ]]; then
  exit 1
fi
exit 2
