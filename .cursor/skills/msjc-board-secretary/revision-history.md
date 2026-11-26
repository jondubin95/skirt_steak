# Google Doc revision history lookup

Use when the user asks what an older version of a Google Doc said, whether something was removed or edited, or to look through a doc's revision history.

# Why this skill exists

The Google Drive/Docs/Gmail connectors return the current doc, plus comments. They do not expose revision history. Do not borrow connector tokens to call the Drive API.

# Command

From the repo root, `python python/msjc_board_secretary/revisions.py` is read-only. Scope is `drive.readonly` only. The token is `Sensitive/google/gdocs_token_drive_readonly.json`, not the writer token. `reauth.py` does not mint this token. The first run that needs a token opens consent through this CLI.

```bash
python python/msjc_board_secretary/revisions.py list '<doc url or id>'
python python/msjc_board_secretary/revisions.py export '<doc url or id>' <revisionId> --mime text/markdown
python python/msjc_board_secretary/revisions.py export '<doc url or id>' --all
python python/msjc_board_secretary/revisions.py comments '<doc url or id>'
```

Exports and `comments.json` go under `Sensitive/msjc/revisions/<docId>/`. That tree is gitignored. Do not commit it. If a refresh fails, move that token file aside and run the same command again. Do not point this CLI at the writer token.

# Steps

1. Get the doc id from the URL (the long string after `/d/`) or pass the URL through. The CLI accepts either.
2. Run `list`. Read the ids, times, and display names. Drive coalesces micro-edits, so a report says which listed revisions were checked. An edit that never became its own revision was not checked.
3. Export only the revisions the question needs (`export` with those ids, or `--all` when the range is the whole list). Search the files for the words the user cares about. Report the revision id, the wording that answers the question, and what changed. Do not print full minutes or comments into chat. Summarize.
4. `comments` writes replies into `comments.json`. Summarize those the same way. Do not paste the file into chat.
5. If this machine has no client file or the person has not consented yet, they run the CLI where the sign-in can be approved. In a group chat, do not start that sign-in. Hand it to the 1:1.
6. If the CLI cannot be run, the person can open File > Version history > See version history and paste the old text.

# Rules

- Read-only. Never edit, comment on, or share the doc from this command.
- Do not print full minutes or comments into chat. Summarize, and name the listed revisions that were checked.
- Never commit or print a dump under `Sensitive/msjc/revisions/`.
