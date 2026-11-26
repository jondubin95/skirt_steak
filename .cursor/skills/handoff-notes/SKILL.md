---
name: handoff-notes
description: >-
  Two-tier handoff notes for skirt_steak. Trigger when the user says
  "checkpoint" (write a handoff), "pickup" (resume from one), or mentions
  "handoff"/"handoffs". Do not apply otherwise. Note: "checkpoint" here means
  a session handoff, not an ML model checkpoint.
---

# Handoff Notes

## Purpose

Handoffs are continuity artifacts, not transcripts. Keep them short. They are a routing table for the next model.

The public head is the canonical note. The private file is an optional supplement for material that must not be in git. It is not a second copy of the public head.

## Inputs

The word "checkpoint" or "pickup", or a named file. Otherwise pickup reads `handoffs/INDEX.md`. Checkpoint uses `handoff-template.md`.

## Steps

### Two tiers

This repository is **public**.

| Tier | Path | Tracked in git | Contents |
| --- | --- | --- | --- |
| Public | `handoffs/` | Yes | Canonical thread head. Objective, state, decisions, constraints, next actions, resume prompt, and safe references. |
| Private | `Sensitive/handoffs/` | Never | Optional supplement. Only the withheld items. |

`Sensitive/` is protected by `.gitignore`, the pre-commit hook, and CI. Only `Sensitive/README.md` is tracked.

`private_detail` is either `null` or a path under `Sensitive/handoffs/`. A public line of the form `see private detail: Sensitive/handoffs/<file>` may name that same path. Other body text does not add `Sensitive/` paths.

A Cloud Agent sees only the public tier. `null` means nothing was withheld. A path the agent cannot read is unavailable. Do not guess the contents.

Existing private files stay as historical artifacts. Do not rewrite them into supplements, and do not publish their contents because a new checkpoint would not have created them.

### Naming and threads

A thread is one line of work, continued across sessions. Each checkpoint writes a **new immutable public file**; the thread is the chain.

```text
handoffs/YYYYMMDD-HHMM-<thread-slug>.md
Sensitive/handoffs/YYYYMMDD-HHMM-<thread-slug>.md   # only when something is withheld
```

Every public note starts with frontmatter. `pull_request` and `private_detail` are always present.

```yaml
---
thread: harness-hardening
status: active        # active | done
created: 2026-09-20T04:08Z
pull_request: null    # pull request number, or null
supersedes: handoffs/archive/harness-hardening/20260919-2210-harness-hardening.md   # or null
private_detail: null  # or Sensitive/handoffs/YYYYMMDD-HHMM-<thread-slug>.md
---
```

`handoffs/INDEX.md` is the live status for each thread. The top of `handoffs/` holds active heads, `INDEX.md`, `README.md`, and the two fanfic spec files. Superseded heads and `done` heads live in `handoffs/archive/<thread-slug>/`. The index points at that archived path. Do not add a `branch` field. `gh pr view` returns the branch.

A link to another note is relative to the file that contains it. GitHub resolves a markdown link from that file's directory. `INDEX.md` links stay relative to `handoffs/`, including `archive/<thread>/<file>.md` after a move. When a head is archived, rewrite links inside that file so they still resolve from `archive/<thread>/`. After that move, do not edit the file again. Do not scan older files in `archive/` for this.

### Reconcile active heads

Run this at the start of checkpoint and pickup. It does not archive a thread because another thread moved, and it does not archive by age.

For each `active` row in `handoffs/INDEX.md`, open that head and read `pull_request`.

- A number: run `gh pr view <number> --json state`. `MERGED` sets `status: done`, moves the file to `handoffs/archive/<thread>/`, rewrites links in that file so they resolve from the archive directory, and points the index at `archive/<thread>/<file>.md` with status `done`. A line in the note that says not to merge does not keep the thread active after that merge. `OPEN` or `CLOSED` without a merge stays `active`. If `created` is old, say how old the head is.
- `null`: stays `active` until a checkpoint on that thread sets `status: done` by hand. Say how old the head is when `created` is old. A hand-marked `done` head moves to `archive/<thread>/` the same way.
- A head with no `pull_request` field is an older note. Leave it. Do not invent a number.

### On "checkpoint"

Do not ask for confirmation first. Reconcile active heads, then draft the public head before deciding whether a private supplement exists.

1. Determine the thread. Continuing existing work reuses that thread slug; new work starts a new one. A new checkpoint archives only the previous head of that same thread.
2. Draft the public head completely. Use the structure in `handoff-template.md`. Fill sections that have real content and delete the rest. The resume prompt is the most important part: maximum 5 sentences, covering continue from / focus on / avoid / validate with. Half-formed reasoning that is not confidential stays here. Do not open a private note just to think out loud.
3. Walk the withhold list below. Any hit: write `Sensitive/handoffs/<timestamp>-<thread>.md` containing only those items, and set `private_detail` to that path. No hit: set `private_detail: null`. If unsure whether an item must be withheld, treat it as a hit.
4. Write the public head to `handoffs/<timestamp>-<thread>.md`.
5. Set `supersedes` to the previous head's path under `handoffs/archive/<thread>/`, then move that previous public note there. Rewrite links in the moved file so they still resolve.
6. Update `handoffs/INDEX.md`. `pull_request` stays in the head, not in an index column.
7. Report the public path. If a supplement was written, report its path and the kind of detail withheld. If not, say nothing was withheld. Do not repeat the withheld values.
8. If the current branch matches `feature/*` or `cursor/*`, commit only the handoff files from this checkpoint and push. Do not open a pull request. Do not stage unrelated files. If the branch is `main` or `master`, leave the files uncommitted and say so.

### What stays out of the public head

- Credentials, tokens, or other authentication material
- Financial account detail, unpublished position information, or a live market thesis with entry and exit levels while the position is open
- Non-public identifying personal information
- Ids or URLs that open a private document
- Local paths to private files or personal directories
- Confidential third-party or unpublished work product

A public name, a path inside this repo, and a non-sensitive technical finding the next session needs all stay in the public head.

### On "pickup"

1. Reconcile active heads.
2. If the user named a file, use that file.
3. Otherwise read `handoffs/INDEX.md` and select the newest note with `status: active`, ordering by the filename timestamp rather than file mtime.
4. If more than one thread is active, list them and ask which one instead of guessing.
5. **State which file was chosen and summarize it before acting.**
6. Read `private_detail`:
   - `null`: nothing was withheld. Do not say the detail is missing.
   - A path that can be read: load that supplement. It may be an older file than the public head. In the reply, name the kind of detail in one sentence. Do not repeat the withheld values.
   - A path that cannot be read: say the referenced private detail is unavailable in this environment, then continue. Do not infer it.
7. Re-check the repo before doing what the note says. Run `git status --short`, `git branch --show-current`, and `git diff --stat`. Open the files and paths the note names. If the branch, pull-request state, or those files do not match the note, say what differs and follow the repo. The note is a starting point, not a live status.
8. Treat every approval in the note as expired. A recorded yes for a merge, a file delete, an external write, a publish, or a weaker check does not carry into this session. Do that only after the owner confirms it again in this conversation.
9. Follow the Next Best Actions and the resume prompt that still match the re-check. Do not reopen settled decisions without new evidence.

If `handoffs/` is empty, say so. Never invent prior context.

## Limits

### Guardrails

- Never commit anything under `Sensitive/`.
- Public notes are visible as soon as the branch is pushed, not just when a PR merges. Treat a push as publication.
- Do not dump chat transcripts into either tier.
- A merged `pull_request` marks the thread `done`. `pull_request: null` stays `active` until a checkpoint on that thread sets `done` by hand. Pickup skips `done`.
