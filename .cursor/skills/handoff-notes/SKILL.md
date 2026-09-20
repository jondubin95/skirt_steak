---
name: handoff-notes
description: Two-tier handoff notes for skirt_steak. Trigger when the user says "checkpoint" (write a handoff), "pickup" (resume from one), or mentions "handoff"/"handoffs". Do not apply otherwise. Note: "checkpoint" here means a session handoff, not an ML model checkpoint.
---

# Handoff Notes

Handoffs are continuity artifacts, not transcripts. Keep them short. They are a routing table for the next model.

## Two tiers

This repository is **public**. Handoffs are split so candid detail never becomes public history.

| Tier | Path | Tracked in git | Contents |
| --- | --- | --- | --- |
| Private | `Sensitive/handoffs/` | Never | Full-fidelity note. Candid reasoning, position sizing, account details, client/personal specifics. |
| Public | `handoffs/` | Yes | Sanitized thread head. Objective, state, next actions, resume prompt, file references. |

`Sensitive/` is protected by `.gitignore`, the pre-commit hook, and CI. Only `Sensitive/README.md` is tracked.

A public note points at its private counterpart by path without revealing content. Locally you have both. A Cloud Agent sees only the public tier and should say so rather than guessing at the missing detail.

## Naming and threads

A thread is one line of work, continued across sessions. Each checkpoint writes a **new immutable file**; the thread is the chain.

```text
handoffs/YYYYMMDD-HHMM-<thread-slug>.md
Sensitive/handoffs/YYYYMMDD-HHMM-<thread-slug>.md
```

Every note starts with frontmatter:

```yaml
---
thread: harness-hardening
status: active        # active | done
created: 2026-09-20T04:08Z
supersedes: handoffs/20260919-2210-harness-hardening.md   # or null
private_detail: Sensitive/handoffs/20260920-0408-harness-hardening.md
---
```

`handoffs/INDEX.md` maps each thread to its current head. Superseded public notes move to `handoffs/archive/<thread-slug>/` so the top level holds only live heads.

## On "checkpoint"

Write both tiers automatically. Do not ask for confirmation first.

1. Determine the thread. Continuing existing work reuses that thread slug; new work starts a new one.
2. Write the full note to `Sensitive/handoffs/<timestamp>-<thread>.md`.
3. Write the sanitized head to `handoffs/<timestamp>-<thread>.md`, applying the sanitization rules below.
4. Set `supersedes` to the previous head, then move that previous public note into `handoffs/archive/<thread>/`.
5. Update `handoffs/INDEX.md`.
6. Report both paths and state plainly what was withheld from the public tier.

Use the structure in `handoff-template.md`. Fill sections that have real content and delete the rest rather than leaving empty prompts. The resume prompt is the most important part: maximum 5 sentences, covering continue from / focus on / avoid / validate with.

## Sanitization rules for the public tier

Never put these in `handoffs/`:

- Credentials, tokens, keys, OAuth client ids, or file paths that contain them
- Account numbers, broker details, bankroll amounts, position sizes, or dollar P&L
- Live market theses with entry/exit levels while the position is open
- Personal or third-party identifying detail beyond what the repo already publishes
- Long verbatim pastes of private documents

Replace each with a pointer: `see private detail: Sensitive/handoffs/<file>`. Keep the public head structurally useful — objective, state, decisions, next actions — so a remote agent knows what to do and what it is missing.

## On "pickup"

1. If the user named a file, use that file.
2. Otherwise read `handoffs/INDEX.md` and select the newest note with `status: active`, ordering by the filename timestamp rather than file mtime.
3. If more than one thread is active, list them and ask which one instead of guessing.
4. **State which file was chosen and summarize it before acting.**
5. Load the private counterpart from `private_detail` when that file exists locally. When it does not, say the detail is unavailable in this environment.
6. Follow Next Best Actions and the resume prompt. Do not reopen settled decisions without new evidence.

If `handoffs/` is empty, say so. Never invent prior context.

## Guardrails

- Never commit anything under `Sensitive/`.
- Public notes are visible as soon as the branch is pushed, not just when a PR merges. Treat a push as publication.
- Do not dump chat transcripts into either tier.
- Mark a thread `status: done` when the work ships, so pickup stops selecting it.
