# MSJC Board Secretary

Keyword-triggered skill plus a guarded Google Docs tab writer. The skill drafts semantic JSON. `write_tab.py` is the only write path. `docs_mcp.py` exposes `read_doc` only.

## Semantic JSON

`schemaVersion` must be `1`. Each item is one of `masthead`, `attendance`, `section`, `presenter`, `bullet`, `motion`, or `paragraph`. The agent does not supply character offsets or style spans. A paragraph may set `"italic": true` to italicize the whole line. `attendance` uses categorized `groups` or a flat `names` list, not both. See `sample_minutes.json` for a fictional meeting.

Unknown versions, kinds, or fields fail the load. Bullet `level` is 0–3. Motion `verdict` is `passes`, `fails`, or omitted.

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
- `--input-tab` and `--output-tab` (different tab ids)
- input JSON under `Sensitive/` or outside the repo

Every `batchUpdate` sends `writeControl.requiredRevisionId` from the preceding read. If pass 1 succeeds and a later pass fails, re-run the same command. Pass 1 replaces the output tab, so the retry rebuilds it.

Defaults: client JSON `Sensitive/credentials.json`, token `Sensitive/google/gdocs_token.json`. Override the token with `--token`. The CLI does not build a client file from environment variables.

When a write says the Google token refresh failed, run `python python/msjc_board_secretary/reauth.py` from the repo root and approve the browser prompt. That replaces the token after sign-in succeeds and leaves the previous file in place if the prompt is closed. Do not replace `credentials.json` unless the message says the client itself is invalid.

A one-phrase change uses `--replace` instead of rebuilding the tab. The file is private JSON with `find` and `replaceWith`. Pass `--write`, `--document-id`, `--expected-document-title`, and `--output-tab`. The phrase must occur once on that tab.

Stdout is a short summary (title, tab, request counts, URL). It does not print the minutes text.

## Local read-only MCP

Do not commit an `mcp.json` that starts this server. For a local Cursor workspace, point `google-docs` at the absolute path of `docs_mcp.py` and reload Cursor. The server uses the same Sensitive credential paths.

Skills under `.cursor/skills/` are discovered when this repo is the Cursor workspace root.

## Tests

```bash
python -m unittest discover -s python/msjc_board_secretary/tests -p "test_*.py"
```

Those tests use the standard library only. Google client libraries are imported only when a write or `read_doc` call actually runs.
