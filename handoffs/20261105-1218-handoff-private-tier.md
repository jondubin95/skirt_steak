---
thread: handoff-private-tier
status: done
created: 2026-11-05T12:18Z
supersedes: handoffs/archive/handoff-private-tier/20261030-1204-handoff-private-tier.md
private_detail: Sensitive/handoffs/20261030-1204-handoff-private-tier.md
---

# Private handoff dictum

## Objective

Make the public handoff the canonical continuity note. A private file is an optional supplement for detail that must stay out of git.

## Current State

- Pull request 20 is merged to main: https://github.com/jondubin95/skirt_steak/pull/20
- The public head is the canonical note. A private file is written only when something must stay out of git.
- Parked private notes stay in the existing supplement. see private detail: Sensitive/handoffs/20261030-1204-handoff-private-tier.md

## Key Decisions Already Made

- The handoff skill is the only normative copy. The three READMEs defer to it.
- No hook, no always-on rule, and no new lint.
- If a checkpoint is unsure whether an item must be withheld, it writes the private supplement.
- Archived public notes keep their old `private_detail` values.

## Next Best Actions

- None.

## Prompt to Resume

This thread is done. Open a new handoff for the next change. Do not add a hook or a lint, and do not edit archived public notes.
