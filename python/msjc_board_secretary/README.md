# MSJC Board Secretary

Keyword-triggered skill plus a guarded Google Docs tab writer. The skill drafts semantic JSON. `write_tab.py` is the only write path. `docs_mcp.py` exposes `read_doc` only.

## Semantic JSON

`schemaVersion` must be `1`. Each item is one of `masthead`, `attendance`, `section`, `presenter`, `bullet`, `motion`, or `paragraph`. The agent does not supply character offsets or style spans. A paragraph may set `"italic": true` to italicize the whole line. `attendance` uses categorized `groups` or a flat `names` list, not both. See `sample_minutes.json` for a fictional meeting.

Unknown versions, kinds, or fields fail the load. Bullet `level` is 0–3. Motion `verdict` is `passes`, `fails`, or omitted. Either verdict is refused unless the body names a seconder or a recorded vote. A lack of a second is not a recorded vote. A motion with no seconder and no vote has no verdict.

## Guarded CLI

From the repo root:

```bash
python python/msjc_board_secretary/write_tab.py --input path/to/minutes.json
```

That is a dry-run. It prints paragraph and pass-1 request counts and does not load credentials or call Google.

A write also needs all of:

- `--write`
- `--document-id`
- `--expected-document-title` (must match the live title exactly)
- `--input-tab` and `--output-tab` (different tab ids; the live output tab title must match exactly)
- `--confirmed-document-title` and `--confirmed-output-tab`, equal to that document title and that output tab, unless the person types both at the prompt
- input JSON under `Sensitive/` or outside the repo

Before a dry-run or a write, the script refuses an absent person credited with a speaking part (the whole name only; mentioning them is allowed), a `___` or `XXX` placeholder, an attendance label other than `In attendance:`, a presenter line that is not `Presented by <name>.`, a markdown or Roman heading in a section title, or closing sections other than Old Business, New Business, and Adjournment. An empty closing section is the paragraph `None.` exactly. A whitespace near-miss is refused. The check does not guess what the meeting will discuss.

Every `batchUpdate` sends `writeControl.requiredRevisionId` from the preceding read. If pass 1 succeeds and a later pass fails, re-run the same command. Pass 1 replaces the output tab, so the retry rebuilds it.

Defaults: client JSON `Sensitive/credentials.json`, token `Sensitive/google/gdocs_token.json`. Override the token with `--token`. The CLI does not build a client file from environment variables.

When a write says the Google token refresh failed, run `python python/msjc_board_secretary/reauth.py` from the repo root and complete the sign-in prompt where it is shown. That replaces the token after sign-in succeeds and leaves the previous file in place if the prompt is closed. Do not replace `credentials.json` unless the message says the client itself is invalid. Do not hand the command off.

A one-phrase change uses `--replace` instead of rebuilding the tab. The file is private JSON with `find` and `replaceWith`. Pass `--write`, `--document-id`, `--expected-document-title`, and `--output-tab`. The phrase must occur once on that tab. Before credentials load, `replaceWith` is refused for a `___` placeholder, `XXX` in any capitalization, a leading markdown `#`, or a Roman heading marker at the start of the phrase. `See II. above` is allowed.

Stdout is a short summary (title, tab, request counts, URL). It does not print the minutes text.

## Revisions CLI

`revisions.py` is read-only. It lists Drive revisions, exports them, and writes comments. It does not edit the doc. Scope is `drive.readonly` only. That scope can read the whole Drive, not only this document. That is a different token from the writer.

From the repo root:

```bash
python python/msjc_board_secretary/revisions.py list 'https://docs.google.com/document/d/<docId>/edit'
python python/msjc_board_secretary/revisions.py export <docId> <revisionId> --mime text/markdown
python python/msjc_board_secretary/revisions.py export <docId> --all --mime text/plain
python python/msjc_board_secretary/revisions.py comments <docId>
```

`--mime` is `text/markdown` (default), `text/plain`, or the Word docx type. Export falls back to plain text when the requested type has no link, and it says so. Pass revision ids, or `--all`, not both. An incomplete export prints a count and exits non-zero.

An export download makes 6 attempts. Between 429 responses it waits 5, 10, 20, 40, then 80 seconds, and it does not wait after the last attempt. `revisions.list`, `comments.list`, and `files.get` pass `num_retries=5` to the Google client's `execute()`. That client retry covers HTTP 429, 5xx, and 403 `rateLimitExceeded` / `userRateLimitExceeded`. The client chooses those waits.

Defaults:

- client JSON `Sensitive/credentials.json` (same client file as the writer)
- token `Sensitive/google/gdocs_token_drive_readonly.json`
- output `Sensitive/msjc/revisions/<docId>/`

`.gitignore` already ignores `/Sensitive/**`, so those exports stay untracked. Do not commit them.

The first run that needs a token opens a one-time consent through this CLI and saves that token. The consent screen is forced (`prompt=consent`). The prompt waits 300 seconds and then exits if nobody approves it. `reauth.py` does not do it. `reauth.py` updates the writer token (`Sensitive/google/gdocs_token.json`) for the Docs and `drive.file` scopes. If this token's refresh fails, move the drive read-only token file aside and run the revisions command again.

`list` prints the doc name, revision count, and each revision id, time, and display name. `export` writes one file per revision and prints the path. `comments` writes `comments.json` (comment text and replies) and prints the path. Do not print full minutes or comments into chat. Summarize, and say which listed revisions were checked. Drive coalesces micro-edits, so an unlisted edit was not a separate revision.

## Local read-only MCP

Do not commit an `mcp.json` that starts this server. From the repo root, run `python python/msjc_board_secretary/setup_local_mcp.py`. That writes `.cursor/mcp.json` with this interpreter and the absolute path of `docs_mcp.py`, and leaves the file untracked. If the file already exists, the script refuses to overwrite it. Pass `--replace` to overwrite; it copies the current file to `.cursor/mcp.json.bak` first and says where that copy is. Enable the server in Cursor if it shows up disabled. The server uses the same Sensitive credential paths.

Skills under `.cursor/skills/` are discovered when this repo is the Cursor workspace root.

## Tests

```bash
python -m unittest discover -s python/msjc_board_secretary/tests -p "test_*.py"
```

Those tests use the standard library only. Google client libraries are imported only when a write or `read_doc` call actually runs.
