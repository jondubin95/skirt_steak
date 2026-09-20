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
```

Create the local directories once:

```bash
mkdir -p Sensitive/google
```

```powershell
New-Item -ItemType Directory -Force Sensitive\google
```

Place `credentials.json` at `Sensitive/credentials.json`. Token and map files are written under `Sensitive/google/` by the gdocs sync tool.

## What is tracked

- `Sensitive/README.md` only

Pre-commit, pre-push CI, and `.gitignore` block every other path under `Sensitive/`.

## Related

- Guardrail runbook: `docs/workflow-guardrails.md`
- Sync script: `python/Project/Gem_Factory/tools/gdocs_sync/`
