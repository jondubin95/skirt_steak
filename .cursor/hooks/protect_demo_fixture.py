#!/usr/bin/env python3
"""Demonstration preToolUse hook. Not a security control.

Denies Write, Delete, and StrReplace only for the demo fixture.
Any other input is allowed. A forced error or a crash exits 1 with no JSON
so Cursor can fail open (failClosed is false in hooks.json).
See docs/cursor-hook-demo.md.
"""

from __future__ import annotations

import json
import os
import sys

FORCE_ERROR_ENVIRONMENT_VARIABLE = "CURSOR_HOOK_DEMO_FORCE_ERROR"
PROTECTED_REPO_RELATIVE_PATH = (
    "python/cursor_hook_demo/fixtures/hook_demo_protected_file.txt"
)
EDIT_TOOL_NAMES = frozenset({"Write", "Delete", "StrReplace"})
PATH_FIELD_NAMES = ("path", "file_path")


def main() -> int:
    """Read one hook payload from stdin and write one permission object."""
    if os.environ.get(FORCE_ERROR_ENVIRONMENT_VARIABLE) == "1":
        print(
            "protect_demo_fixture forced an error so the hook can fail open",
            file=sys.stderr,
        )
        return 1

    try:
        raw_input = sys.stdin.read()
    except OSError as read_error:
        print(
            f"protect_demo_fixture could not read stdin: {read_error}", file=sys.stderr
        )
        return 1

    try:
        payload = json.loads(raw_input) if raw_input.strip() else None
    except json.JSONDecodeError:
        print(json.dumps({"permission": "allow"}))
        return 0

    print(json.dumps(decide_pre_tool_use_permission(payload)))
    return 0


def decide_pre_tool_use_permission(payload: object) -> dict[str, str]:
    """Return allow, or deny when this edit names the demo fixture."""
    if not isinstance(payload, dict):
        return {"permission": "allow"}
    if payload.get("tool_name") not in EDIT_TOOL_NAMES:
        return {"permission": "allow"}

    target_path = extract_edit_target_path(payload.get("tool_input"))
    if target_path is None or not path_is_demo_protected_fixture(target_path):
        return {"permission": "allow"}

    return {
        "permission": "deny",
        "user_message": (
            "Demo hook blocked an edit to "
            f"{PROTECTED_REPO_RELATIVE_PATH}. "
            "That file is a fixture for this demonstration, not a protected secret."
        ),
        "agent_message": (
            "preToolUse denied this edit because the path is the demo fixture "
            f"{PROTECTED_REPO_RELATIVE_PATH}. "
            "Leave that file alone and edit a different path. "
            "This hook is not a security control."
        ),
    }


def extract_edit_target_path(tool_input: object) -> str | None:
    """Return the first recognized path string, or None when the shape is unknown."""
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except json.JSONDecodeError:
            return None
    if not isinstance(tool_input, dict):
        return None

    for field_name in PATH_FIELD_NAMES:
        field_value = tool_input.get(field_name)
        if isinstance(field_value, str) and field_value.strip():
            return field_value
    return None


def path_is_demo_protected_fixture(candidate_path: str) -> bool:
    """True when the normalized path is the demo fixture, relative or absolute."""
    normalized_path = normalize_repo_path_text(candidate_path)
    protected_path = normalize_repo_path_text(PROTECTED_REPO_RELATIVE_PATH)
    return normalized_path == protected_path or normalized_path.endswith(
        "/" + protected_path
    )


def normalize_repo_path_text(path_text: str) -> str:
    """Collapse slashes and parent segments without reading the filesystem."""
    path_parts: list[str] = []
    for path_part in path_text.replace("\\", "/").split("/"):
        if path_part in ("", "."):
            continue
        if path_part == "..":
            if path_parts:
                path_parts.pop()
            continue
        path_parts.append(path_part)
    return "/".join(path_parts)


if __name__ == "__main__":
    sys.exit(main())
