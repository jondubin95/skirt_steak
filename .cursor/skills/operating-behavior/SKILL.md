---
name: operating-behavior
description: skirt_steak coding operating rules from Copilot instructions. Use for implementation, debugging, refactors, summaries, and pull requests in this repo.
---

# Operating Behavior

Canonical source: `.github/copilot-instructions.md`. Git safety rules stay in `AGENTS.md`.

## Defaults

- When scope is unclear, propose a narrow plan before writing code.
- When assumptions look weak, challenge them explicitly before continuing.
- When work is repetitive, prefer a scriptable path over manual repetition.
- Keep responses concise, but include the details needed to make a decision.

## Core rules

### Fix root cause

Trace failures through logic, dependencies, and calling context. If the root cause is uncertain, say so and narrow unknowns first.

### No silent fallbacks

Do not hide bad state or missing data with default values unless the user-facing behavior clearly needs graceful degradation. Prefer visible failures.

### Minimum viable scope

Solve the stated problem first. Do not add flags, abstractions, refactors, or side quests unless they are mechanically required.

### Detailed summaries

Include what changed, why, tradeoffs, risks or edge cases, and validation performed or still missing.

### Pull request bodies

Never leave the raw PR template in place. Replace placeholders with repo-specific content and mark checkboxes to match what actually happened.

### Automation first

Prefer scripts, CLI commands, and repeatable workflows. If an existing repo pattern is already automated, follow it. If it is manual or brittle, automation-first overrides it.

### Reference existing patterns

Search this repo for similar examples before creating a new pattern. If none exists, say so and introduce the simplest workable one.

## Complex work

Gather local context, propose a narrow plan, then execute in small verifiable steps.

## Repo bounds

- Treat `Sensitive/` as out of normal tracked workflows unless the prompt explicitly requires it.
- Do not reference infrastructure, policies, or systems outside this repo unless the prompt scopes them in.
- For substantial work, write a handoff in `handoffs/` using the `handoff-notes` skill.
