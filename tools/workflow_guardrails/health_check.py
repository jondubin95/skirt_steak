#!/usr/bin/env python3
"""Read-only health check for skirt_steak.

health-check.sh and health-check.ps1 call this file. It runs the lint-job
commands from .github/workflows/guardrails.yml, then preflight. It does not
install packages, sync, or edit the tree.

Handoff notes are not read. The fanfic paths below are the dummy paths from
that workflow's gitignore step, not handoff files.

Exit 0 only when every check is PASS. Exit 1 when any check is FAIL.
Exit 2 when nothing failed and at least one check did not run.
"""

from __future__ import annotations

import os
import py_compile
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable

FANFIC_PACKAGE = "python/fanfic_story_doctor"
FANFIC_PRIVATE_PATHS = (
    "drafts/x.txt",
    "works/x/ch01.md",
    "runs/run.json",
    "cache/key.json",
    "eval/holdout/set.yaml",
)
FANFIC_TRACKED_PATH = "tests/fixtures/ashfall/ch01.md"


@dataclass
class CheckResult:
    name: str
    status: str
    command: str
    detail: str = ""

    def render(self) -> str:
        lines = [f"[{self.status}] {self.name}", f"  {self.command}"]
        if self.detail:
            lines.extend(f"  {line}" for line in self.detail.splitlines())
        return "\n".join(lines)


ANSI_COLOR = re.compile(r"\x1b\[[0-9;]*m")


def tail_lines(text: str, limit: int) -> str:
    plain = ANSI_COLOR.sub("", text)
    lines = [line for line in plain.splitlines() if line.strip()]
    return "\n".join(lines[-limit:])


def run_command(name: str, command: list[str], cwd: Path | None = None) -> CheckResult:
    display = " ".join(command)
    if cwd is not None:
        display = f"cd {cwd} && {display}"
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        missing = error.filename or command[0]
        return CheckResult(name, "DID_NOT_RUN", display, f"{missing} is not on PATH")
    output = f"{completed.stdout}{completed.stderr}"
    if completed.returncode == 0:
        return CheckResult(name, "PASS", display, tail_lines(output, 2))
    detail = f"exit {completed.returncode}"
    excerpt = tail_lines(output, 12)
    if excerpt:
        detail = f"{detail}\n{excerpt}"
    return CheckResult(name, "FAIL", display, detail)


def imports_ok(modules: list[str]) -> bool:
    statement = "import " + ", ".join(modules)
    completed = subprocess.run(
        [PYTHON, "-c", statement],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return completed.returncode == 0


def tool_runs(module: str) -> bool:
    completed = subprocess.run(
        [PYTHON, "-m", module, "--version"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return completed.returncode == 0


def check_syntax() -> CheckResult:
    command = "py_compile.compile on each python/**/*.py, bytecode in a temp directory"
    source_files = sorted(Path("python").rglob("*.py"))
    if not source_files:
        return CheckResult("syntax check", "DID_NOT_RUN", command, "no Python files under python/")
    try:
        with tempfile.TemporaryDirectory(prefix="skirt-steak-py-compile-") as temporary:
            temporary_path = Path(temporary)
            for source_path in source_files:
                flattened_name = str(source_path).replace("/", "_").replace("\\", "_") + ".pyc"
                py_compile.compile(
                    str(source_path),
                    cfile=str(temporary_path / flattened_name),
                    doraise=True,
                )
    except py_compile.PyCompileError as error:
        return CheckResult("syntax check", "FAIL", command, str(error))
    return CheckResult("syntax check", "PASS", command, f"compiled {len(source_files)} files")


def check_when_importable(
    name: str,
    modules: list[str],
    command: list[str],
    missing_reason: str,
    cwd: Path | None = None,
) -> CheckResult:
    display = " ".join(command)
    if cwd is not None:
        display = f"cd {cwd} && {display}"
    if not imports_ok(modules):
        return CheckResult(name, "DID_NOT_RUN", display, missing_reason)
    return run_command(name, command, cwd=cwd)


def check_when_tool_runs(name: str, module: str, command: list[str]) -> CheckResult:
    display = " ".join(command)
    if not tool_runs(module):
        return CheckResult(name, "DID_NOT_RUN", display, f"{module} is not installed for this interpreter")
    return run_command(name, command)


def check_fanfic_gitignore() -> CheckResult:
    command = "git check-ignore -q --no-index (fanfic paths in .github/workflows/guardrails.yml)"
    problems: list[str] = []
    for relative_path in FANFIC_PRIVATE_PATHS:
        target = f"{FANFIC_PACKAGE}/{relative_path}"
        completed = subprocess.run(
            ["git", "check-ignore", "-q", "--no-index", target],
            check=False,
        )
        if completed.returncode != 0:
            problems.append(f"{target} is not gitignored")
    tracked = f"{FANFIC_PACKAGE}/{FANFIC_TRACKED_PATH}"
    tracked_result = subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", tracked],
        check=False,
    )
    if tracked_result.returncode == 0:
        problems.append(f"{tracked} should be tracked")
    if problems:
        return CheckResult("fanfic private paths are gitignored", "FAIL", command, "\n".join(problems))
    return CheckResult("fanfic private paths are gitignored", "PASS", command)


def preflight_excerpt(text: str) -> str:
    lines = text.splitlines()
    start = next((index for index, line in enumerate(lines) if "Preflight failed:" in line), None)
    if start is None:
        return tail_lines(text, 12)
    kept: list[str] = []
    for line in lines[start:]:
        if line.startswith("Standard sync"):
            break
        if line.strip() == "" and kept:
            break
        kept.append(line)
    return "\n".join(kept)


def check_preflight() -> CheckResult:
    if os.name == "nt":
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(REPO_ROOT / "tools/workflow_guardrails/preflight.ps1"),
        ]
    else:
        command = ["bash", str(REPO_ROOT / "tools/workflow_guardrails/preflight.sh")]
    display = " ".join(command)
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
    except FileNotFoundError as error:
        missing = error.filename or command[0]
        return CheckResult("preflight", "DID_NOT_RUN", display, f"{missing} is not on PATH")
    output = f"{completed.stdout}{completed.stderr}"
    if completed.returncode == 0:
        return CheckResult("preflight", "PASS", display)
    return CheckResult("preflight", "FAIL", display, f"exit {completed.returncode}\n{preflight_excerpt(output)}")


def check_pylint() -> CheckResult:
    targets = sorted(str(path) for path in Path("python").glob("*.py"))
    command = [PYTHON, "-m", "pylint", *targets]
    display = " ".join(command) if targets else f"{PYTHON} -m pylint"
    if not targets:
        return CheckResult("pylint", "DID_NOT_RUN", display, "no Python files directly under python/")
    if not tool_runs("pylint"):
        return CheckResult("pylint", "DID_NOT_RUN", display, "pylint is not installed for this interpreter")
    return run_command("pylint", command)


def collect_checks() -> list[CheckResult]:
    fanfic_cwd = REPO_ROOT / FANFIC_PACKAGE
    return [
        check_syntax(),
        run_command(
            "cursor demo hook unit tests",
            [PYTHON, "-m", "unittest", "discover", "-s", "python/cursor_hook_demo/tests", "-p", "test_*.py"],
        ),
        run_command(
            "board secretary unit tests",
            [PYTHON, "-m", "unittest", "discover", "-s", "python/msjc_board_secretary/tests", "-p", "test_*.py"],
        ),
        check_when_importable(
            "decision log unit tests",
            ["duckdb"],
            [PYTHON, "-m", "unittest", "discover", "-s", "python/decision_log/tests", "-p", "test_*.py"],
            "duckdb is not importable, so the tests were not started",
        ),
        check_when_importable(
            "fanfic story doctor tests",
            ["pytest", "yaml", "jsonschema"],
            [PYTHON, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
            "pytest, PyYAML, or jsonschema is not importable, so the tests were not started",
            cwd=fanfic_cwd,
        ),
        check_fanfic_gitignore(),
        check_when_tool_runs("ruff", "ruff", [PYTHON, "-m", "ruff", "check", "python"]),
        check_when_tool_runs("black --check", "black", [PYTHON, "-m", "black", "--check", "python"]),
        check_pylint(),
        check_preflight(),
    ]


def main() -> int:
    if len(sys.argv) > 1:
        print("health check takes no arguments and does not install or sync.", file=sys.stderr)
        return 2
    os.chdir(REPO_ROOT)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["NO_COLOR"] = "1"
    os.environ.pop("FORCE_COLOR", None)
    os.environ["PYTHONPYCACHEPREFIX"] = tempfile.mkdtemp(prefix="skirt-steak-health-pycache-")

    checks = collect_checks()
    pass_count = sum(1 for check in checks if check.status == "PASS")
    fail_count = sum(1 for check in checks if check.status == "FAIL")
    did_not_run_count = sum(1 for check in checks if check.status == "DID_NOT_RUN")
    print("\n".join(check.render() for check in checks))
    print()
    print(f"pass={pass_count} fail={fail_count} did_not_run={did_not_run_count}")
    if fail_count == 0 and did_not_run_count == 0:
        print("overall: success")
        return 0
    print("overall: not success")
    if fail_count > 0:
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
