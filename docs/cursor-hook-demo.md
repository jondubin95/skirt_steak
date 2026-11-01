# Cursor hook demonstration

This is a demonstration, not a security control.

`.cursor/hooks.json` runs `python3 .cursor/hooks/protect_demo_fixture.py` before a `Write`, `Delete`, or `StrReplace`. The script denies the call only when the path is `python/cursor_hook_demo/fixtures/hook_demo_protected_file.txt`. Any other path is allowed. `failClosed` is false.

Malformed input exits 0 with `{"permission":"allow"}`. If the script crashes, or `CURSOR_HOOK_DEMO_FORCE_ERROR=1` is set, it exits 1 and prints no JSON. Cursor then allows the edit. Exit 0 with invalid JSON would still block, so the error path prints nothing.

Shell commands, reads, and human edits are not covered. A path stored under a key other than `path` or `file_path` is allowed.

The unit tests run the script. They do not prove that Cursor loaded `.cursor/hooks.json`. In a new agent session on this branch, ask it to edit the fixture. A loaded hook denies that edit. An edit that is saved means the hook did not run.
