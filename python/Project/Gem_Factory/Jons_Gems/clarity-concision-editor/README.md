# Clarity & Concision Editor Gem

## Description

Writing-focused gem that rewrites text for board-application tone: direct, confident, and non-flowery. It helps tighten prose, cut length without losing meaning, and remove jargon while preserving your voice and facts.

## Location

- Gem root: `python/Project/Gem_Factory/Jons_Gems/clarity-concision-editor`
- Agent config: `internal/agent/clarity-concision-editor.agent.yaml`
- Instructions: `internal/core/instructions/*.instructions.md`
- Package metadata: `internal/clarity-concision-editor.package.yaml`

## Workflows

- `/tighten` - Improve clarity and concision while preserving meaning
- `/board-tone` - Rewrite for board-application tone (direct, confident, non-fluffy)
- `/cut-20-percent` - Reduce length by ~20% while keeping key points
- `/remove-jargon` - Replace jargon with plain English (keep necessary terms)
- `/help` - View commands and usage guidance

## End-to-End Setup

1. Sync local instruction files to Google Docs using:
   - `python/Project/Gem_Factory/tools/gdocs_sync/README.md`
2. In Gemini web, create or edit this gem.
3. Copy persona/principles from `internal/agent/clarity-concision-editor.agent.yaml` into Gemini Instructions (plain English format is fine).
4. Attach synced Google Docs as Knowledge files.
5. Save the gem and test with `/help`.

## Recommended Operating Workflow

1. Edit instruction files locally in `internal/core/instructions/`.
2. Re-run the sync command to update linked Google Docs.
3. In Gemini, continue using the same attached knowledge files (no re-attach needed if doc IDs stay the same).
4. Test with a short sample prompt:
   - `/board-tone` + pasted paragraph
   - `/cut-20-percent` + same paragraph

## Maintenance Notes

- Keep secrets/tokens/map files in `Sensitive/` only.
- Bump `internal/clarity-concision-editor.package.yaml` and `CHANGELOG.md` when behavior changes materially.
- Re-run sync after any instruction edits so Gemini has latest content.
