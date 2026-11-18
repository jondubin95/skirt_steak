---
name: msjc-board-secretary
description: >-
  Format MSJC board minutes from raw meeting notes and write them with the
  guarded Docs tab writer. Also sets up the monthly blank minutes doc and looks up
  Google Doc revision history. Trigger only when the user mentions "MSJC board
  minutes", "board meeting notes", "Board Secretary", "set up the minutes doc",
  "meeting mins", "revision history", or "version history".
---

# MSJC Board Secretary

## Purpose

You format raw board meeting notes into standardized minutes and write them into one Google Docs tab. The guarded writer is the only write path. The local Docs MCP server is read-only.

## Inputs

The source document, the target month, year, and meeting date, and the Notes tab. The steps below say how each is used.

## Steps

### Tools

- **Drive** (`plugin-google-drive-google-drive`): `copy_file` and `update_file` for the monthly copy and rename. `search_files` and `read_file_content` are lookup only. Do not write minutes text through Drive.
- **Docs read**: use the local `google-docs` server's `read_doc` when that server is connected. If Cursor left the project server disabled, read through the connected Google Docs plugin `read_document` (`plugin-google-docs-google-docs`). Do not call `update_doc`, `batchUpdate`, or any other Docs write.
- **Writer**: `python python/msjc_board_secretary/write_tab.py`. Dry-run is the default. A write needs `--write`, `--expected-document-title`, `--input-tab`, `--output-tab`, and `--document-id`. That script is the only minutes write.

If neither the local server nor the plugin read is available, stop and say so. Do not fall back to a plain-text Drive write or to unrestricted Docs updates. A disabled local server is not a stop when the plugin read is connected.

### Sign-in

A failed token refresh is not a reason to replace `Sensitive/credentials.json`. From the repo root, run:

`python python/msjc_board_secretary/reauth.py`

Do not hand the user the command. The person approves the sign-in prompt where it is shown. The script replaces the saved token only after that approval succeeds, removes a leftover bad token file, and prints `token saved`. It does not print the token or the authorization code. If the prompt is closed, the previous token file stays in place. When `token saved` appears, retry the same writer command. A link from an earlier run is dead.

### Monthly workflow

1. Confirm the source document and the target month, year, and meeting date.
2. Drive `copy_file` the prior monthly document, then `update_file` the copy's title to `<Month> <Year> Board Meeting Minutes <YYYYMMDD>` (the meeting date). Example shape: `April 2026 Board Meeting Minutes 20260412`. Do not invent another title pattern. Skip copy and rename only when the user names an existing document and output tab.
3. Read the new document with `read_doc`, or with the plugin `read_document` when the local server is disabled. Identify tab ids by title. Production input is **Notes**. Production output is the main minutes tab. A smoke test uses **Notes** as input and **Test** as output.
4. Read the Notes tab. `read_document` flattens list nesting, so also export the same doc through Drive as Markdown and use that indent. Expand a first name or nickname from the attendance block. When Notes have no attendance block, copy the attendance already on the Minutes tab as-is. When the notes do not name a presenter, keep a presenter line already on the Minutes tab. Keep a filled motion that already has real names and no blanks. Drop motions that are still `___` placeholders. Drop a prefilled section the notes never discuss. Leave anyone who is not on the attendance block as written, except the names in `Sensitive/msjc/roster.md`. Do not swap one person's name onto another. Before the first write, compare person names and ritual phrases with the previous month's minutes and use that spelling when it is the same person or the same phrase.
5. Draft semantic JSON (`schemaVersion` 1) using only `masthead`, `attendance`, `section`, `presenter`, `bullet`, `motion`, and `paragraph`. Follow [template-spec.md](template-spec.md). Do not include character offsets or style spans. Prefer categorized attendance `groups`.
6. Write that JSON only under `Sensitive/` or a system temporary directory. Never write it to a tracked path, and do not put the minutes text in the shell command line.
7. Show the user the exact document title and the output tab title. When the user already named that document and that output tab in the request, treat that as the confirmation. Otherwise stop until they confirm. A document title alone is not confirmation. Example: replace the Minutes tab of `April 2026 Board Meeting Minutes 20260412`.
8. Run the writer with `--write` and those exact titles, plus `--confirmed-document-title` and `--confirmed-output-tab` set to the same two strings. The writer refuses the full-tab replace until both match. That full write is for the first fold-in, or for a change that adds, removes, or reorders paragraphs. A later wording fix uses `--replace` together with `--write`, as Corrections describes. Keep the JSON file until the user says the minutes are finished. When pass 1 has replaced the tab and a later pass fails, keep that file and re-run the same command with `--write`. The retry rebuilds the tab from it.
9. Reply with the document title, output tab, and URL. Do not paste the minutes text back into the chat.

### Corrections

Do not redraft from Notes, and do not rebuild the Minutes tab, for a wording fix. The Notes tab stays untouched after the first fold-in.

A wording fix is one exact phrase that already appears once on the Minutes tab. Write `{"find": "...", "replaceWith": "..."}` under `Sensitive/`, then run `write_tab.py --replace` with `--write`, `--document-id`, `--expected-document-title`, and `--output-tab`. Do not pass `--input`. The command refuses unless that phrase occurs once on the output tab, and it does not edit any other tab. Before it loads credentials, it also refuses a `replaceWith` that contains `___`, `XXX` in any capitalization, a leading markdown `#`, or a Roman numeral token followed by `.` or `)`. Delete the replace JSON afterward.

If the user has edited the Minutes tab by hand, those edits are the current text. A structural rewrite must re-read that live tab into the JSON first. Do not write an older JSON back over those edits.

### Executive session

The meeting has two note sets. Open business is on Notes. The executive session has its own notes, usually the Executive Session tab. Write those notes in full. Keep names, amounts, and who said what. Do not anonymize them, and do not replace a named remark with a neutral summary.

The full minutes include that text under the agenda item, between the motion to enter executive session and this paragraph:

```json
{"kind": "paragraph", "text": "Executive session concluded", "italic": true}
```

The writer italicizes that whole line. A full rewrite keeps the italic. A formal motion that must appear in the redacted minutes sits after that line.

The redacted minutes are the full minutes with the interior of each session deleted. Do not fold the Executive Session tab into the redacted Minutes tab. If the open Notes only record the enter motion, the redacted tab gets that motion and the italic line `Executive session concluded`, and nothing said inside the session.

## Limits

### Hard rules

- Section headings are title text only (`Accept Minutes`). The writer supplies the uppercase-Roman glyph, Arial 13pt bold black, and the blank line before each section.
- Standard order: D'var Torah, Accept Minutes, Executive Director Update, Journal Dinner Updates (or the event name in the notes), Committee Items. Insert an unanticipated major section where the notes place it and keep the Roman sequence contiguous.
- The last three sections are always Old Business, New Business, and Adjournment. Under an empty one, the body is `None.`
- Under Committee Items, standard sub-headings are Events Committee, Education Committee, Gabbai Committee, and Growth Committee. A topic that does not fit gets its own sub-heading in the notes' words.
- Presenter line: `Presented by Alex Rivera.` Immediately under the section. When the notes name a presenter, use that. When the notes are silent, keep a presenter line already on the Minutes tab. Omit the line only when neither source names a presenter.
- A motion is one item: body plus optional `passes` or `fails`. Do not invent a mover, seconder, or verdict. Use the verdict the notes record. A seconded motion with no recorded result has no verdict. `fails` is only for a motion the notes record as voted down, and the body names a seconder or the vote. A named motion the notes leave unfinished, with no seconder and no vote, is still recorded, with no verdict. Say that in the body, for example `No second; not voted`. Do not write `Motion Fails.` for that motion. Leave a cut-off sentence cut off. Example body: `Alex Rivera moves to accept the March minutes. Jordan Hale seconds.`
- Level 0 bullets are topic labels (`Hall rental`). Level 1 is one outcome sentence. Keep the name of anyone the notes credit. Merge only consecutive turns by the same person, or turns that state the same outcome, and still name them.
- A speaker-less line that only continues the previous bullet is one level deeper. The next named speaker returns to the parent level.
- Do not put bold category labels inside bullet sentences. Fold the idea into the sentence.
- Repeat the antecedent instead of a dangling "it" when it points at a policy, document, or named item (`the volunteer schedule should be posted`).
- Write `re-sent`, not `resent`. Capitalize named ritual occasions (`Seuda Shlishit`, `Mincha`).
- The attendance label is `In attendance:`. Do not add `(In Person)`.
- Notes order wins over the pre-meeting skeleton. A topic the notes nest under Executive Director Update, such as the boiler, stays in that section.
- In this congregation, the program called groups is youth groups. That includes Friday night, Yom Kippur, group leaders, and the groups budget. Leave a WhatsApp group, or any other group that is not that program, unchanged.
- Before expanding a name, read `Sensitive/msjc/roster.md`. That file is local only.
- When the notes include a pasted proposal and say to record the purpose items, write each purpose. Do not reprint the full current and proposed quotations. Replace a placeholder mover such as `XXX` with the mover named in the notes. If a purpose sentence is cut off in the notes, leave it cut off.

## Reference

Render contract and a fictional worked example: [template-spec.md](template-spec.md).

## Related workflows

- Monthly meeting setup (blank fill-in minutes skeleton from the agenda in the chat, before the meeting): [monthly-setup.md](monthly-setup.md). Trigger on "set up the minutes doc", "meeting mins", or "monthly minutes setup".
- Google Doc revision history lookup (what an older version said, whether something was removed): [revision-history.md](revision-history.md). Trigger on "revision history", "version history", or "what did the doc say before".
