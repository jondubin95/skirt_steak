# Handoffs

Continuity notes that let work move between sessions and models without a full transcript.

Say **"checkpoint"** to write one. Say **"pickup"** to resume from one. Both are handled by `.cursor/skills/handoff-notes/SKILL.md`.

## Two tiers

This repository is public, so notes are split:

| Tier | Path | Tracked | Contents |
| --- | --- | --- | --- |
| Public | `handoffs/` (here) | Yes | Canonical thread head |
| Private | `Sensitive/handoffs/` | Never | Optional supplement |

A private supplement is optional and holds only what must stay out of git. See `.cursor/skills/handoff-notes/SKILL.md`.

A pushed branch on a public repo is immediately visible. Treat a push as publication.

## Layout

```text
handoffs/
  README.md
  INDEX.md                          # live status; links relative to this directory
  YYYYMMDD-HHMM-<thread>.md         # active heads
  archive/<thread>/...              # superseded heads and done heads
```

Each new note begins with frontmatter recording `thread`, `status` (`active` or `done`), `created`, `pull_request` (a number or `null`), `supersedes`, and `private_detail`. Older notes have no `pull_request` field.

## Threads

A thread is one line of work continued across sessions. Each checkpoint writes a new immutable file and archives only the previous head of that same thread. `pickup` selects the newest `active` head, ordering by the filename timestamp, and states which file it chose before acting.

`INDEX.md` is the live status. On checkpoint and pickup, each `active` head with a `pull_request` number is checked with `gh pr view`. A merged pull request sets that head to `done` and moves it under `archive/<thread>/`. The index link stays relative to this directory. A closed unmerged pull request stays `active`. `pull_request: null` stays `active` until a checkpoint on that thread sets `done` by hand. Age is a reason to run the check. It does not by itself mark a thread done.

A link to another note is relative to the file that contains it. When a head moves, links inside that file are rewritten so they still resolve.

## Template

Structure comes from [`../handoff-template.md`](../handoff-template.md).
