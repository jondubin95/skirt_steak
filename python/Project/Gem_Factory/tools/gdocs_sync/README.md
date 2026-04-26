# Google Docs Sync (Gem Instructions)

Sync local Gem instruction files (Markdown) into Google Docs so you can attach the Docs to a Gemini Gem once, then keep them updated by re-running the sync.

## What This Solves

- Create one Google Doc per local instruction file
- Update those same Docs on future runs (no manual copy/paste)
- Keep a local map file so doc IDs stay stable across updates

## Setup

1. Create an OAuth client in Google Cloud Console (Desktop app):
   - APIs: enable **Google Drive API** and **Google Docs API**
   - Credentials: create an **OAuth client ID**
2. Save the downloaded client JSON somewhere ignored by git, for example:
   - `Sensitive/credentials.json`

Your `.gitignore` already ignores `/Sensitive/`.

## Install deps

```powershell
.\.venv\Scripts\python.exe -m pip install -r python/Project/Gem_Factory/tools/gdocs_sync/requirements.txt
```

## Run (from `python/Project/Gem_Factory`)

```powershell
..\..\..\.venv\Scripts\python.exe tools\gdocs_sync\sync_gem_folder_to_gdocs.py `
  --src Jons_Gems\clarity-concision-editor\internal\core\instructions `
  --title-prefix "Polish - " `
  --client-secrets ..\..\..\Sensitive\credentials.json `
  --token ..\..\..\Sensitive\google\gdocs_token.json `
  --map ..\..\..\Sensitive\google\clarity-concision-editor.gdocs-map.json
```

On success, you should see output like:

- `SYNCED: <file> -> <doc title> (<doc id>)`
- `Done. Created: X, Updated: Y, Map: ...`

## Optional Flags

- `--folder-id <drive-folder-id>` place created docs into a specific Drive folder
- `--dry-run` preview what would be created/updated without writing

## Attach to Gemini Gem (Web)

1. Open Gemini web `Gems` and edit your gem.
2. Add the synced Google Docs as Knowledge files.
3. Keep those docs attached permanently.
4. Re-run sync whenever local instruction files change.

## Troubleshooting

`--client-secrets not found`

- Verify the file exists at the exact path passed to `--client-secrets`.
- Example expected path: `C:\Users\jondu\Repos\skirt_steak\Sensitive\credentials.json`

`SERVICE_DISABLED` for `docs.googleapis.com`

- Enable Google Docs API in the same OAuth project.
- Wait 2-5 minutes, then retry.

`Invalid requests[0].deleteContentRange: The range should not be empty`

- Fixed in the current script. Pull latest local changes and retry.

Script opens auth URL in terminal

- Open the URL in your browser, approve access, then return to terminal.

## Notes

- This sync preserves Markdown as plain text (headings stay as `#`, etc.). That's usually fine for Gemini knowledge files.
- First run will open a browser window to authorize; tokens are saved to the `--token` path.
- Keep map and token files under `Sensitive/` and out of version control.
