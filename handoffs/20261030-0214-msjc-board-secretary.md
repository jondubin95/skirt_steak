---
thread: msjc-board-secretary
status: active
created: 2026-10-30T02:14Z
supersedes: handoffs/archive/msjc-board-secretary/20261030-0016-msjc-board-secretary.md
private_detail: Sensitive/handoffs/20261030-0214-msjc-board-secretary.md
---

# MSJC board secretary

## Objective

Keep this month's full minutes, including the executive session, on the Minutes tab. A redacted copy is a later file, not a rewrite of that tab.

## Current State

- The executive-session notes are folded into the Minutes tab, uncensored, between the enter motion and an italic `Executive session concluded`. see private detail: Sensitive/handoffs/20261030-0214-msjc-board-secretary.md
- One-meeting wording stays in the private minutes JSON. It is not a standing skill rule. The skill points at `Sensitive/msjc/roster.md` for name expansion, and it keeps youth groups versus a WhatsApp group and the executive-session split.
- A paragraph may set `"italic": true`. The close line uses that.
- `reauth.py` replaces the token after sign-in succeeds. It does not print it. If the prompt is closed, the previous token file stays in place.
- Pull request: https://github.com/jondubin95/skirt_steak/pull/19 on `feature/msjc-minutes-skills`. The monthly-setup conflict with `main` is merged. The shorter rules section won. Checks were still running at the checkpoint.
- The redacted copy has not been made. An insert that adds a session block without rewriting the tab has not been built.

## Key Decisions Already Made

- Write the full minutes first. The redacted minutes are that document with the session interior deleted.
- Do not anonymize executive-session notes.
- Do not promote one meeting's sentences into hard rules.

## Constraints and Guardrails

- Do not commit `Sensitive/`. Do not paste minutes into git or the public handoff.
- Do not rebuild the Minutes tab from a Drive markdown export. Start from the private JSON and re-read the live Minutes tab before a full write.
- A one-phrase fix uses `write_tab.py --replace` and requires one match on the output tab.
- The guarded writer is the only Docs write path.

## Next Best Actions

- Wait for the pull request checks, then merge if the user asks.
- Make the redacted copy only when the user asks. Delete the interior between the enter motion and the italic close line.
- Add an insert-after-the-enter-motion operation only when the next meeting needs a fold-in.

## Prompt to Resume

Continue from the full minutes already on the Minutes tab. see private detail: Sensitive/handoffs/20261030-0214-msjc-board-secretary.md Focus on a redacted copy only if asked, or on merging the open pull request if asked. Avoid rebuilding the Minutes tab from Notes or from a markdown export, and avoid anonymizing the executive session. Validate a replace by one match on the Minutes tab, and validate a commit with `git status` so `Sensitive/` stays untracked.
