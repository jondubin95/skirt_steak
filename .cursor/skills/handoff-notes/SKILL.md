---
name: handoff-notes
description: Two-tier handoff notes for skirt_steak. Trigger when the user says "checkpoint" (write a handoff), "pickup" (resume from one), or mentions "handoff"/"handoffs". Do not apply otherwise. Note: "checkpoint" here means a session handoff, not an ML model checkpoint.
---

# Handoff Notes

Handoffs are continuity artifacts, not transcripts. Keep them short. They are a routing table for the next model.

The public head is the canonical note. The private file is an optional supplement for material that must not be in git. It is not a second copy of the public head.

## Two tiers

This repository is **public**.

| Tier | Path | Tracked in git | Contents |
| --- | --- | --- | --- |
| Public | `handoffs/` | Yes | Canonical thread head. Objective, state, decisions, constraints, next actions, resume prompt, and safe references. |
| Private | `Sensitive/handoffs/` | Never | Optional supplement. Only the withheld items. |

`Sensitive/` is protected by `.gitignore`, the pre-commit hook, and CI. Only `Sensitive/README.md` is tracked.

`private_detail` is either `null` or a path under `Sensitive/handoffs/`. A public line of the form `see private detail: Sensitive/handoffs/<file>` may name that same path. Other body text does not add `Sensitive/` paths.

A Cloud Agent sees only the public tier. `null` means nothing was withheld. A path the agent cannot read is unavailable. Do not guess the contents.

Existing private files stay as historical artifacts. Do not rewrite them into supplements, and do not publish their contents because a new checkpoint would not have created them.

## Naming and threads

A thread is one line of work, continued across sessions. Each checkpoint writes a **new immutable public file**; the thread is the chain.

```text
handoffs/YYYYMMDD-HHMM-<thread-slug>.md
Sensitive/handoffs/YYYYMMDD-HHMM-<thread-slug>.md   # only when something is withheld
```

Every public note starts with frontmatter. `private_detail` is always present.

```yaml
---
thread: harness-hardening
status: active        # active | done
created: 2026-09-20T04:08Z
supersedes: handoffs/20260919-2210-harness-hardening.md   # or null
private_detail: null  # or Sensitive/handoffs/YYYYMMDD-HHMM-<thread-slug>.md
---
```

`handoffs/INDEX.md` maps each thread to its current head. Superseded public notes move to `handoffs/archive/<thread-slug>/` so the top level holds only live heads.

## On "checkpoint"

Do not ask for confirmation first. Draft the public head before deciding whether a private supplement exists.

1. Determine the thread. Continuing existing work reuses that thread slug; new work starts a new one.
2. Draft the public head completely. Use the structure in `handoff-template.md`. Fill sections that have real content and delete the rest. The resume prompt is the most important part: maximum 5 sentences, covering continue from / focus on / avoid / validate with. Half-formed reasoning that is not confidential stays here. Do not open a private note just to think out loud.
3. Walk the withhold list below. Any hit: write `Sensitive/handoffs/<timestamp>-<thread>.md` containing only those items, and set `private_detail` to that path. No hit: set `private_detail: null`. If unsure whether an item must be withheld, treat it as a hit.
4. Write the public head to `handoffs/<timestamp>-<thread>.md`.
5. Set `supersedes` to the previous head, then move that previous public note into `handoffs/archive/<thread>/`.
6. Update `handoffs/INDEX.md`.
7. Report the public path. If a supplement was written, report its path and the kind of detail withheld. If not, say nothing was withheld. Do not repeat the withheld values.

## What stays out of the public head

- Credentials, tokens, or other authentication material
- Financial account detail, unpublished position information, or a live market thesis with entry and exit levels while the position is open
- Non-public identifying personal information
- Ids or URLs that open a private document
- Local paths to private files or personal directories
- Confidential third-party or unpublished work product

A public name, a path inside this repo, and a non-sensitive technical finding the next session needs all stay in the public head.

## On "pickup"

1. If the user named a file, use that file.
2. Otherwise read `handoffs/INDEX.md` and select the newest note with `status: active`, ordering by the filename timestamp rather than file mtime.
3. If more than one thread is active, list them and ask which one instead of guessing.
4. **State which file was chosen and summarize it before acting.**
5. Read `private_detail`:
   - `null`: nothing was withheld. Do not say the detail is missing.
   - A path that can be read: load that supplement. It may be an older file than the public head. In the reply, name the kind of detail in one sentence. Do not repeat the withheld values.
   - A path that cannot be read: say the referenced private detail is unavailable in this environment, then continue. Do not infer it.
6. Follow Next Best Actions and the resume prompt. Do not reopen settled decisions without new evidence.

If `handoffs/` is empty, say so. Never invent prior context.

## Guardrails

- Never commit anything under `Sensitive/`.
- Public notes are visible as soon as the branch is pushed, not just when a PR merges. Treat a push as publication.
- Do not dump chat transcripts into either tier.
- Mark a thread `status: done` when the work ships, so pickup stops selecting it.
