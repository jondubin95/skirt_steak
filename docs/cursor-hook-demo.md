# Cursor hook demonstration

This hook is a demonstration. It is not a security control. It does not protect secrets, and it must not be treated as one.

Cursor's hook reference is [Hooks](https://cursor.com/docs/hooks). Project hooks live in `.cursor/hooks.json`. This repo registers one command hook on `preToolUse`. The command is `python3 .cursor/hooks/protect_demo_fixture.py`. Project hooks run from the repository root, which is why the command uses that path rather than `./hooks/`.

## What it does

Before a `Write`, `Delete`, or `StrReplace` tool call, the script reads one JSON object from stdin. It denies the call only when the tool input names this fixture:

`python/cursor_hook_demo/fixtures/hook_demo_protected_file.txt`

The fixture is dummy text. It holds no secrets. A deny response uses `permission: "deny"` plus `user_message` and `agent_message`, and the process exits 0. Any other file is allowed with `{"permission":"allow"}`.

The published matcher examples name tools such as `Write` and `Delete`. `StrReplace` is also in the matcher because that is the search-and-replace tool name in Cursor's agent tools. The match is unanchored, same as the examples in the hooks reference. The script still allows a call unless `tool_name` is exactly `Write`, `Delete`, or `StrReplace`.

The hooks reference does not list the keys inside `tool_input` for a file edit. The only fully specified `tool_input` example is a shell command (`command`, `working_directory`). This script looks at `path` first, then `file_path`. `path` is the parameter on Cursor's Write, StrReplace, and Delete tools. `file_path` is the field on `beforeReadFile` and `afterFileEdit`. If neither key is a non-empty string, the edit is allowed.

## What it does not cover

- Shell commands. `echo`, `sed`, `git`, and the rest never enter this hook. A shell command can still change the fixture.
- Reads. `beforeReadFile` is a different event. This hook allows a `Read` even when the path is the fixture.
- Human edits in the editor, and any tool whose name is not `Write`, `Delete`, or `StrReplace`.
- A search-and-replace that Cursor reports under some other tool name, or a payload that puts the path in a key other than `path` or `file_path`.
- Case differences. The path check is case-sensitive.
- Other repositories, other filenames, and files that merely sit next to the fixture.

`failClosed` is `false`. A bug in this script must not block ordinary edits.

## Malformed input

If stdin is empty or is not a JSON value the script understands, it still exits 0 and prints `{"permission":"allow"}`. The same allow is used when `tool_name` is missing, when `tool_input` has no path, and when the path is some other file. Blocking an unrecognized payload would stop unrelated work whenever Cursor changed the payload shape.

## When the hook itself errors

The script fails open.

- Set `CURSOR_HOOK_DEMO_FORCE_ERROR=1` and the process writes a line to stderr, writes nothing to stdout, and exits 1. That variable exists so the failure path can be tested. Leave it unset.
- Any other crash exits non-zero (Python's normal behavior) and does not print a permission object.
- `.cursor/hooks.json` sets `failClosed` to `false`. The hooks reference says a crash, a timeout, or an exit code other than 0 or 2 then fails open: Cursor logs the failure and allows the action. Exit code 2 would block. This script does not use exit code 2, so a crash is not reported as a deny.

This is the right failure mode for a demonstration. The fixture is not worth freezing the agent. A security hook could set `failClosed` to `true`. This one must not.

One Cursor rule still blocks even when `failClosed` is false: a permission hook that exits 0 with invalid JSON, or with JSON that does not match the hook schema, blocks the action. The error path avoids that by exiting 1 with an empty stdout. The success path always prints one JSON object with `permission` set to `allow` or `deny`.

## Try the script on its own

From the repository root:

```bash
python -m unittest discover -s python/cursor_hook_demo/tests -p "test_*.py"
```

Or one payload:

```bash
printf '%s' '{"tool_name":"Write","tool_input":{"path":"python/cursor_hook_demo/fixtures/hook_demo_protected_file.txt"}}' \
  | python3 .cursor/hooks/protect_demo_fixture.py
```

That should print a deny object and exit 0. The same command with `"path":"README.md"` should print `{"permission": "allow"}`.

Running the script this way is not the same as Cursor running it during an edit. The tests cover the script. They do not prove that the editor loaded `.cursor/hooks.json`.
