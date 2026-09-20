---
thread: harness-hardening
status: done
created: 2026-09-20T05:27Z
supersedes: handoffs/archive/harness-hardening/20260920-0408-harness-hardening.md
private_detail: Sensitive/handoffs/20260920-0527-harness-hardening.md
---

# Harness Hardening (shipped)

## Objective

Close the harness-hardening thread after PR #11 merged so pickup no longer treats it as active.

## Current State

- PR #11 is merged to `main` (`261a41b`, 2026-09-20T05:26Z).
- Skills, CI guardrails, bash script ports, dual branch policy, `Sensitive/` scaffold, and two-tier handoffs are on `main`.
- A follow-up session confirmed every intended repo file from the prior session was in that merge. Private notes from the prior Cloud Agent VM are gone (expected).
- This checkpoint marks the thread `done`.

## Why This Matters

Pickup selects the newest `active` head. The previous note still said PR #11 was awaiting review.

## Key Decisions Already Made

- Skills are keyword-triggered, not slash-only and not always-on.
- Handoffs are two-tier; checkpoint auto-writes the public tier; notes travel on the working branch.
- Pre-existing local notes were not imported.
- CI secret-scan on `handoffs/` was declined during design.

## Open Questions

- Enable branch protection on `main`? Agents cannot set it.
- Add a pytest scaffold, or flip `black`/`pylint` to blocking, later?
- What the next project is (not named yet).

## Constraints and Guardrails

- Never commit under `Sensitive/` except `Sensitive/README.md`.
- Working branches: `feature/[a-z0-9-]{3,40}` locally, `cursor/<name>-<id>` for Cloud Agents.
- Do not run `tools/workflow_guardrails/setup-hooks.sh` on a Cloud Agent VM.

## Files / Artifacts / Sources

- Merged PR: https://github.com/jondubin95/skirt_steak/pull/11
- Public archive: `handoffs/archive/harness-hardening/20260920-0408-harness-hardening.md`
- Private detail for this close-out: `Sensitive/handoffs/20260920-0527-harness-hardening.md`

## Next Best Actions

- Next: enable branch protection on `main` in GitHub Settings (require PRs and the Guardrails checks).
- After that: start the new project on a fresh working branch and a new handoff thread.
- Optional: pytest scaffold; reformat Python and make lint blocking; CI secret-scan on `handoffs/`.

## Known Risks or Failure Modes

- Cloud Agent private notes disappear when the VM is torn down. Copy `Sensitive/handoffs/` locally if that detail needs to survive.
- No CI secret-scan on public `handoffs/`.
- Keyword "checkpoint" can collide with ML model-checkpoint discussion.

## Prompt to Resume

Thread `harness-hardening` is done. Start a new thread for the next project or leftover harness items. Do not reopen PR #11 or the skill-invocation debate. Avoid committing `Sensitive/`, running `setup-hooks` on Cloud Agent VMs, or working on `main`. Validate by reading `handoffs/INDEX.md` and confirming no `active` head unless new work started.

## Postmortem

- Original thesis: absorb repo conventions into Cursor skills and harden the harness before a new project.
- What happened: the work shipped on `main` via PR #11; the first pickup after merge had only the public tier.
- Signal that mattered: keyword triggers and the public/private split, more than extra CI.
- Next time: close the thread as soon as the PR merges, and copy private notes off Cloud VMs if they need to persist.
