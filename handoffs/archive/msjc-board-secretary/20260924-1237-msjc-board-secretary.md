---
thread: msjc-board-secretary
status: active
created: 2026-09-24T12:37Z
supersedes: null
private_detail: Sensitive/handoffs/20260924-1237-msjc-board-secretary.md
---

# MSJC Board Secretary PR

## Objective

Ship the board-secretary skill and a guarded Google Docs tab writer on `feature/msjc-board-secretary`, then open a PR after offline tests.

## Current State

- Branch exists from `main`. No commits yet.
- On disk: `python/msjc_board_secretary/{__init__,schema,builder}.py`.
- Still missing: CLI writer, read-only MCP server, skill + template spec, sample JSON, tests, CI hook, install.sh, package README, index rows.
- Two unrelated untracked files already exist under `handoffs/`. Leave them out of this branch.
- Credential rotation and a live smoke write are gated on the user. See private detail.

## Key Decisions Already Made

- Keep the four existing skills. Keyword triggers stay narrow so they do not collide with `board tone`.
- Public examples use a fictional roster only. The writer is the only write path; MCP is read-only.
- Semantic JSON schema v1; no agent-supplied offsets. Attendance supports categorized groups.
- Dry-run default; explicit `--write`, expected title, distinct tabs, revision lock on every batch.
- Token/cred defaults follow the existing `Sensitive/` layout. Do not commit `mcp.json`.
- Do not edit the immutable `harness-hardening` public head in this PR.

## Constraints and Guardrails

- Stage explicit paths only. Never `git add .`.
- Do not copy sandbox secrets, the September transcript builder, or a real attendance roster into git.
- PR body must not contain the raw template phrases `What changed?` or `Why was this needed?`.

## Files / Artifacts / Sources

- Implementation plan (do not edit): the attached board-secretary plan.
- Written: `python/msjc_board_secretary/schema.py`, `builder.py`.
- Remaining file list is in that plan’s “Files on the branch” section.
- Private counterpart: `Sensitive/handoffs/20260924-1237-msjc-board-secretary.md`.

## Next Best Actions

- Next: finish the remaining planned files and run the zero-dependency unit tests plus `py_compile`.
- After that: offline request-parity check, content/secret scan, explicit-path commit, push, PR.
- Live smoke only after the user rotates credentials and approves a disposable Test-tab write. Without that, label the PR as an offline-validated migration.

## Known Risks or Failure Modes

- Importing Google client libraries at module import time will break hermetic CI tests.
- A failed pass after the first `batchUpdate` leaves a half-written tab; re-run the same `--write` command to rebuild.
- Skills under `skirt_steak/.cursor/skills/` are discovered when that repo is the Cursor workspace root.

## Prompt to Resume

Continue from `feature/msjc-board-secretary` with `schema.py` and `builder.py` already written. Focus on the guarded CLI, read-only MCP server, fictional skill/spec, tests, and CI. Avoid committing secrets, real meeting content, leftover unrelated `handoffs/` files, or editing the harness-hardening head. Validate with `python -m unittest discover -s python/msjc_board_secretary/tests -p "test_*.py"` and a pre-push name/secret scan.
