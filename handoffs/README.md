# Handoffs

Continuity notes that let work move between sessions and models without a full transcript.

Say **"checkpoint"** to write one. Say **"pickup"** to resume from one. Both are handled by `.cursor/skills/handoff-notes/SKILL.md`.

## Two tiers

This repository is public, so notes are split:

| Tier | Path | Tracked | Contents |
| --- | --- | --- | --- |
| Private | `Sensitive/handoffs/` | Never | Full-fidelity note |
| Public | `handoffs/` (here) | Yes | Sanitized thread head |

Public heads carry objective, current state, decisions, next actions, and a resume prompt. Anything sensitive is replaced by a pointer to the private counterpart, which never leaves the local machine.

A pushed branch on a public repo is immediately visible. Treat a push as publication.

## Layout

```text
handoffs/
  README.md
  INDEX.md                          # thread -> current head
  YYYYMMDD-HHMM-<thread>.md         # live heads
  archive/<thread>/...              # superseded heads
```

Each note begins with frontmatter recording `thread`, `status` (`active` or `done`), `created`, `supersedes`, and `private_detail`.

## Threads

A thread is one line of work continued across sessions. Each checkpoint writes a new immutable file and supersedes the previous head for that thread. `pickup` selects the newest `active` head, ordering by the filename timestamp, and states which file it chose before acting.

Mark a thread `status: done` when the work ships so `pickup` stops selecting it.

## Template

Structure comes from [`../handoff-template.md`](../handoff-template.md).
