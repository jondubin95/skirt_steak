---
name: handoff-notes
description: Create, read, and resume from skirt_steak AI handoff notes. Trigger only when the user's message contains the word "handoff" or "handoffs" (e.g. "write a handoff", "resume from my handoff", "check the handoffs folder"). Do not apply otherwise.
---

# Handoff Notes

Treat handoffs as continuity artifacts, not transcripts. Keep them short. They are a routing table for the next model.

## Where notes live

- Template (tracked): `handoff-template.md`
- Notes directory (local-only): `handoffs/`
- `handoffs/` is gitignored except `handoffs/README.md`
- Cloud Agents and other remotes cannot see local notes unless the user pastes them or commits them

If `handoffs/` is missing or empty, say so. Do not invent prior context. Ask the user to paste the latest note if work depends on it.

## When to write a handoff

Write or update a note in `handoffs/` for substantial, multi-step, or interrupted work.

Name files with a short topic and timestamp:

```text
handoffs/YYYYMMDD-HHMM-<short-topic>.md
```

Copy the structure from `handoff-template.md`. Fill every section that has real content. Delete sections that do not apply instead of leaving empty prompts.

## Required sections

Use these headings when they have content:

- Objective
- Current State
- Why This Matters
- Key Decisions Already Made (decision / why / tradeoff)
- Open Questions
- Constraints and Guardrails
- Files / Artifacts / Sources
- Decision Playbook Snapshot (one line per field; market work only)
- Next Best Actions
- Known Risks or Failure Modes
- Prompt to Resume (maximum 5 sentences)
- Postmortem (only after an outcome exists)

## Resume prompt rules

The resume prompt is the most important part for the next agent. Maximum 5 sentences. Cover:

- Continue from
- Focus on
- Avoid
- Validate with

## How to absorb a handoff

When the user provides a handoff or `handoffs/` contains notes:

1. Read the newest relevant note first.
2. Follow Next Best Actions and the resume prompt.
3. Do not reopen settled decisions unless new evidence contradicts them.
4. Update the same note or write a successor when state changes.

## Guardrails

- Do not commit files under `handoffs/` except `README.md`.
- Do not dump chat transcripts into a handoff.
- Do not store secrets in handoffs. Credentials stay under `Sensitive/`.
