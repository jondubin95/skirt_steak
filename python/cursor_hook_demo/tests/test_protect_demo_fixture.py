"""Run the demo preToolUse hook as its own program."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK_SCRIPT_PATH = REPO_ROOT / ".cursor" / "hooks" / "protect_demo_fixture.py"
HOOKS_CONFIG_PATH = REPO_ROOT / ".cursor" / "hooks.json"
PROTECTED_REPO_RELATIVE_PATH = (
    "python/cursor_hook_demo/fixtures/hook_demo_protected_file.txt"
)
FORCE_ERROR_ENVIRONMENT_VARIABLE = "CURSOR_HOOK_DEMO_FORCE_ERROR"


def run_protect_demo_fixture_hook(
    standard_input: str,
    environment_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Invoke the hook the way Cursor does: JSON on stdin, JSON on stdout."""
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


def write_tool_payload(target_path: str, tool_name: str = "Write") -> str:
    return json.dumps(
        {
            "tool_name": tool_name,
            "tool_input": {"path": target_path, "contents": "demo"},
            "cwd": str(REPO_ROOT),
        }
    )


class ProtectDemoFixtureHookTests(unittest.TestCase):
    def test_allows_an_edit_to_another_file(self) -> None:
        completed = run_protect_demo_fixture_hook(write_tool_payload("README.md"))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout), {"permission": "allow"})

    def test_blocks_an_edit_that_names_the_demo_fixture(self) -> None:
        fixture_paths = (
            PROTECTED_REPO_RELATIVE_PATH,
            "./" + PROTECTED_REPO_RELATIVE_PATH,
            "/workspace/" + PROTECTED_REPO_RELATIVE_PATH,
            "C:\\workspace\\" + PROTECTED_REPO_RELATIVE_PATH.replace("/", "\\"),
            "python/cursor_hook_demo/fixtures/nested/../hook_demo_protected_file.txt",
        )
        for fixture_path in fixture_paths:
            for tool_name in ("Write", "Delete", "StrReplace"):
                with self.subTest(fixture_path=fixture_path, tool_name=tool_name):
                    completed = run_protect_demo_fixture_hook(
                        write_tool_payload(fixture_path, tool_name=tool_name)
                    )
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    decision = json.loads(completed.stdout)
                    self.assertEqual(decision["permission"], "deny")
                    self.assertIn(
                        PROTECTED_REPO_RELATIVE_PATH, decision["user_message"]
                    )
                    self.assertIn(
                        PROTECTED_REPO_RELATIVE_PATH, decision["agent_message"]
                    )

    def test_blocks_when_the_path_uses_the_file_path_field(self) -> None:
        payload = json.dumps(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": PROTECTED_REPO_RELATIVE_PATH},
            }
        )
        completed = run_protect_demo_fixture_hook(payload)
        self.assertEqual(json.loads(completed.stdout)["permission"], "deny")

    def test_prefers_path_over_file_path(self) -> None:
        payload = json.dumps(
            {
                "tool_name": "Write",
                "tool_input": {
                    "path": "README.md",
                    "file_path": PROTECTED_REPO_RELATIVE_PATH,
                },
            }
        )
        completed = run_protect_demo_fixture_hook(payload)
        self.assertEqual(json.loads(completed.stdout), {"permission": "allow"})

    def test_allows_a_near_name_and_a_non_edit_tool(self) -> None:
        near_name = PROTECTED_REPO_RELATIVE_PATH + ".bak"
        allowed_payloads = (
            write_tool_payload(near_name),
            write_tool_payload("python/cursor_hook_demo/fixtures/other.txt"),
            json.dumps(
                {
                    "tool_name": "Read",
                    "tool_input": {"path": PROTECTED_REPO_RELATIVE_PATH},
                }
            ),
            json.dumps(
                {
                    "tool_name": "Shell",
                    "tool_input": {
                        "command": "echo hi > " + PROTECTED_REPO_RELATIVE_PATH
                    },
                }
            ),
            write_tool_payload(
                "python/cursor_hook_demo/fixtures/hook_demo_protected_file.txt/../other.txt"
            ),
        )
        for payload in allowed_payloads:
            with self.subTest(payload=payload):
                completed = run_protect_demo_fixture_hook(payload)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(json.loads(completed.stdout), {"permission": "allow"})

    def test_malformed_input_is_allowed(self) -> None:
        malformed_inputs = (
            "",
            "   ",
            "not json",
            "[]",
            "null",
            "{}",
            json.dumps({"tool_name": "Write"}),
            json.dumps({"tool_name": "Write", "tool_input": "not-json"}),
            json.dumps({"tool_name": "Write", "tool_input": {"path": ""}}),
            json.dumps({"tool_name": "Write", "tool_input": {"contents": "x"}}),
            json.dumps({"tool_input": {"path": PROTECTED_REPO_RELATIVE_PATH}}),
        )
        for malformed_input in malformed_inputs:
            with self.subTest(malformed_input=malformed_input):
                completed = run_protect_demo_fixture_hook(malformed_input)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(json.loads(completed.stdout), {"permission": "allow"})

    def test_hook_error_exits_nonzero_without_a_deny(self) -> None:
        """Exit 1 is the script's fail-open signal.

        hooks.json sets failClosed to false. Cursor then allows the edit when
        the process exits with a code other than 0 or 2. Exit 0 with invalid
        JSON would still block, so this path prints no JSON.
        """
        completed = run_protect_demo_fixture_hook(
            write_tool_payload(PROTECTED_REPO_RELATIVE_PATH),
            environment_overrides={FORCE_ERROR_ENVIRONMENT_VARIABLE: "1"},
        )
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout, "")
        self.assertNotIn("deny", completed.stdout)
        self.assertIn("fail open", completed.stderr)

    def test_demo_fixture_file_exists(self) -> None:
        fixture_path = REPO_ROOT / PROTECTED_REPO_RELATIVE_PATH
        self.assertTrue(fixture_path.is_file(), fixture_path)

    def test_hooks_config_is_fail_open_and_scoped(self) -> None:
        hooks_config = json.loads(HOOKS_CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(hooks_config["version"], 1)
        hook_definitions = hooks_config["hooks"]["preToolUse"]
        self.assertEqual(len(hook_definitions), 1)
        hook_definition = hook_definitions[0]
        self.assertEqual(
            hook_definition["command"],
            "python3 .cursor/hooks/protect_demo_fixture.py",
        )
        self.assertEqual(hook_definition["matcher"], "Write|Delete|StrReplace")
        self.assertIs(hook_definition["failClosed"], False)
        self.assertEqual(set(hooks_config["hooks"]), {"preToolUse"})
