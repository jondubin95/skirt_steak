# Sensitive/

Local-only credentials, tokens, and map files. Do not commit anything in this directory except this README.

Cloud Agents and other remotes cannot see files that exist only on your machine. Put secrets here locally; pass them into a remote session only when that session actually needs them.

## Expected layout

```text
Sensitive/
  README.md                          # tracked (this file)
  credentials.json                   # Google OAuth client secrets (gitignored)
  google/
    gdocs_token.json                 # Google Docs / Drive token (gitignored)
    clarity-concision-editor.gdocs-map.json
  msjc/
    roster.md                        # board-secretary name notes (gitignored)
  handoffs/                          # private tier of handoff notes (gitignored)
    YYYYMMDD-HHMM-<thread>.md
  decisions/                         # market-analyst log (gitignored)
    market_decisions.duckdb
    playbooks/
      <id>.md
    inbox/
      <id>.json
    export/                          # local CSV dumps only
```

Create the local directories once:

```bash
mkdir -p Sensitive/google Sensitive/handoffs Sensitive/decisions/playbooks Sensitive/decisions/inbox
```

```powershell
New-Item -ItemType Directory -Force Sensitive\google, Sensitive\handoffs, Sensitive\decisions\playbooks, Sensitive\decisions\inbox
```

Place `credentials.json` at `Sensitive/credentials.json`. Token and map files are written under `Sensitive/google/` by the gdocs sync tool.

## What is tracked

- `Sensitive/README.md` only

Pre-commit, pre-push CI, and `.gitignore` block every other path under `Sensitive/`.

## Handoff notes

`Sensitive/handoffs/` holds an optional private supplement, and only when a checkpoint must withhold detail from the public head in `handoffs/`. See `.cursor/skills/handoff-notes/SKILL.md`.

`Sensitive/decisions/` holds the market-analyst decision log: the DuckDB file, the playbook for each review, and the inbox JSON. The schema and the CLI are tracked. See `python/decision_log/README.md`.

`Sensitive/msjc/roster.md` holds congregation name-expansion notes for the board-secretary skill. The skill points at that path. The file is gitignored.

## Related

- Guardrail runbook: `docs/workflow-guardrails.md`
- Public handoff tier: `handoffs/README.md`
- Sync script: `python/Project/Gem_Factory/tools/gdocs_sync/`
