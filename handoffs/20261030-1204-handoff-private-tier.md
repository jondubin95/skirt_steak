---
thread: handoff-private-tier
status: active
created: 2026-10-30T12:04Z
supersedes: null
private_detail: Sensitive/handoffs/20261030-1204-handoff-private-tier.md
---

# Private handoff dictum

## Objective

Make the public handoff the canonical continuity note. A private file is an optional supplement for detail that must stay out of git.

## Current State

- Branch `feature/handoff-private-tier`. Pull request: https://github.com/jondubin95/skirt_steak/pull/20. It is open and not merged.
- Two commits. `7d3880c` marks `msjc-board-secretary` done. `79bcc48` rewrites the handoff skill and retargets the live heads.
- The harness and market done heads use `private_detail: null`. The fanfic done head points at `Sensitive/handoffs/20261018-1817-fanfic-story-doctor.md`. The October done head points at `Sensitive/handoffs/20261030-0214-msjc-board-secretary.md`.
- Redundant private notes were parked locally. One private fanfic note was left in place because it still holds a name mapping the kept trial notes do not. see private detail: Sensitive/handoffs/20261030-1204-handoff-private-tier.md
- The DuckDB foreign-key note stays on disk as a historical file. It is not a template for new checkpoints.

## Key Decisions Already Made

- The handoff skill is the only normative copy. The three READMEs defer to it.
- No hook, no always-on rule, and no new lint. Hooks and CI cannot see gitignored files.
- If a checkpoint is unsure whether an item must be withheld, it writes the private supplement.
- Archived public notes keep their old `private_detail` values.

## Next Best Actions

- Merge pull request 20 only if the user asks.
- After it merges, switch to `main`. Do not commit on `main`.

## Prompt to Resume

Continue from pull request 20 on `feature/handoff-private-tier`. Focus on review comments, or merge only if the user asks. Avoid a hook, a lint, and edits to archived public notes. Validate with `git status` so nothing under `Sensitive/` is staged, and with `handoffs/INDEX.md` so `msjc-board-secretary` stays `done`.
