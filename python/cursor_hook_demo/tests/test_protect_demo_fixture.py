"""Three checks for the demo hook: deny the fixture, allow another path, fail open."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK_SCRIPT_PATH = REPO_ROOT / ".cursor" / "hooks" / "protect_demo_fixture.py"
PROTECTED_REPO_RELATIVE_PATH = (
    "python/cursor_hook_demo/fixtures/hook_demo_protected_file.txt"
)
FORCE_ERROR_ENVIRONMENT_VARIABLE = "CURSOR_HOOK_DEMO_FORCE_ERROR"


def run_protect_demo_fixture_hook(
    standard_input: str,
    environment_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the hook the way Cursor does: JSON on stdin, JSON on stdout."""
    environment = os.environ.copy()
    environment.pop(FORCE_ERROR_ENVIRONMENT_VARIABLE, None)
    if environment_overrides:
        environment.update(environment_overrides)
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPT_PATH)],
        input=standard_input,
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )


def write_tool_payload(target_path: str) -> str:
    return json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {"path": target_path},
        }
    )


class ProtectDemoFixtureHookTests(unittest.TestCase):
    def test_denies_the_demo_fixture(self) -> None:
        completed = run_protect_demo_fixture_hook(
            write_tool_payload(PROTECTED_REPO_RELATIVE_PATH)
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["permission"], "deny")

    def test_allows_a_different_path(self) -> None:
        completed = run_protect_demo_fixture_hook(write_tool_payload("README.md"))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout), {"permission": "allow"})

    def test_hook_error_exits_nonzero_without_a_deny(self) -> None:
        completed = run_protect_demo_fixture_hook(
            write_tool_payload(PROTECTED_REPO_RELATIVE_PATH),
            environment_overrides={FORCE_ERROR_ENVIRONMENT_VARIABLE: "1"},
        )
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout, "")
