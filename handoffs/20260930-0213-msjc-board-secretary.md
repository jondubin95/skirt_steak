---
thread: msjc-board-secretary
status: active
created: 2026-09-30T02:13Z
supersedes: handoffs/archive/msjc-board-secretary/20260925-0139-msjc-board-secretary.md
private_detail: Sensitive/handoffs/20260930-0213-msjc-board-secretary.md
---

# Minutes revision insights

## Objective

Keep a written record of how past minutes drafts were reviewed, so a later pass can update the board-secretary skill. This pass does not edit the skill.

## Current State

- Insights file written. Exports and the manifest are in the sibling repo's gitignored `revisions/` folder. See private detail for doc ids and snapshot ids.
- Four meetings exported. One is degraded (no notes source). One is the skill-written draft and is excluded from rule promotion. The other two are qualifying human meetings, so the two-meeting bar was met.
- Two patterns cleared that bar. One is already required by the skill (`no-op`). One is missing and would be a `change`: the presenter line should name only the person who presented, not everyone who spoke.
- Six other patterns are `insufficient-evidence`. Repeated proper-noun fixes stay meeting-specific.
- Coverage: the August final fails five checklist items the skill already states. Do not relax those rules. Generation score on the September skill snapshot is 3/4, and those defects are `unattributed-to-current-skill` because the working skill hash does not match skirt_steak commit `c10f9fd`.
- No live document still has a Notes tab. Historically tied notes are raw snapshots on the minutes tab. See private detail.
- The 2026-09-25 close-out still holds: no credential rotation, no live Docs write.

## Key Decisions Already Made

- A transformation rule needs quoted, allowed evidence from two human meetings. The skill-written month does not count.
- Coverage findings are a separate schema from promoted rules.
- A reviewer who left a pre-skill defect in place is not overriding the rule.

## Constraints and Guardrails

- Do not edit `SKILL.md` or `template-spec.md` unless the user asks for the presenter-line change.
- Do not commit `revisions/` or anything under `Sensitive/`.
- Do not paste real minutes into the public handoff or into git. See private detail.

## Files / Artifacts / Sources

- Insights: `msjc-board-secretary/.cursor/skills/msjc-board-secretary/revision-insights.md` (sibling repo, not this one).
- Pipeline: `msjc-board-secretary/scripts/revision_insights.py`.
- Write-era skill commit in this repo: `c10f9fd`.
- Private counterpart: `Sensitive/handoffs/20260930-0213-msjc-board-secretary.md`.

## Next Best Actions

- Wait for the user before changing the skill. If they ask, apply only the presenter-line change and leave the topic-label rule as `no-op`.
- Do not promote the six single-meeting patterns.
- Do not write to a live Google Doc.

## Prompt to Resume

Continue from the revision-insights file in the msjc-board-secretary skill folder. Focus on the one missing presenter-line rule, and only if the user asks to edit the skill. Avoid credential files, live Docs writes, and copying real minutes into git. Validate against the two promoted rules and the coverage findings; the skill-written month is not promotion evidence.
