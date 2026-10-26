---
name: Google Doc revision history lookup
description: >-
  When the user asks what an older version of a Google Doc said, whether
  something was removed or edited, or to look through a doc's revision/version
  history. No Drive/Docs connector exposes revisions.
---
# Why this skill exists
The Google Drive/Docs/Gmail connectors only return the current version of a doc, plus comments. They do not expose revision history. The box browser also can't sign in to Google reliably. Do not borrow connector tokens to call the Drive API.

# Steps
1. Get the doc id from the URL (the long string after /d/).
2. Look for old versions already on the user's own computer. Use ListMachines and confirm it is connected. Then run read-only Shell commands with its machineId (each needs the user's approval) to find an existing revision export folder, typically a gitignored `revisions/<docId>/` folder in the user's board-secretary or minutes repo, plus a helper such as `scripts/revision_insights.py` that exports revisions with the user's own saved Google login.
3. If exports exist, read them locally. Search for the keywords the user cares about (names, "motion", "moved", "table", etc.) across every version and report the version number, the exact wording, and what changed between versions. Do not copy the full text off the machine unless asked.
4. If the exports are stale (the doc changed since), ask the user whether to re-run the helper script on their computer. Do it only with their OK, read-only, and never commit or print anything under `revisions/` or `Sensitive/`.
5. If no laptop is connected or no exports or script exist, fall back to the user opening File > Version history > See version history and pasting the old text, or to having a cloud agent write a small read-only `revisions.list` / `revisions.get` export script that the user runs locally.
6. Report findings with the answer first. Say plainly when a version range was not checked.

# Rules
- Read-only. Never edit, comment on, or share the doc.
- In a group chat, don't start sign-ins on the box. Hand sign-in steps to the user's 1:1 chat.
- Only one agent should run commands on the user's computer at a time; use the one that already has the context.
