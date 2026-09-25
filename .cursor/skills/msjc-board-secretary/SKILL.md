---
name: msjc-board-secretary
description: >-
  Format MSJC board minutes from raw meeting notes and write them with the
  guarded Docs tab writer. Trigger only when the user mentions "MSJC board
  minutes", "board meeting notes", or "Board Secretary".
---

# MSJC Board Secretary

You format raw board meeting notes into standardized minutes and write them into one Google Docs tab. The guarded writer is the only write path. The local Docs MCP server is read-only.

## Tools

- **Drive** (`plugin-google-drive-google-drive`): `copy_file` and `update_file` for the monthly copy and rename. `search_files` and `read_file_content` are lookup only.
- **Docs** (`google-docs`): `read_doc` only. Do not call `update_doc` or send `batchUpdate` requests yourself.
- **Writer**: `python python/msjc_board_secretary/write_tab.py`. Dry-run is the default. A write needs `--write`, `--expected-document-title`, `--input-tab`, `--output-tab`, and `--document-id`.

If `google-docs` is not connected, stop and say so. Do not fall back to a plain-text Drive write or to unrestricted Docs updates.

## Monthly workflow

1. Confirm the source document and the target month, year, and meeting date.
2. Drive `copy_file` the prior monthly document, then `update_file` the copy's title to `<Month> <Year> Board Meeting Minutes <YYYYMMDD>` (the meeting date). Example shape: `April 2026 Board Meeting Minutes 20260412`. Do not invent another title pattern. Skip copy and rename only when the user names an existing document and output tab.
3. `read_doc` the new document. Identify tab ids by title. Production input is **Notes**. Production output is the main minutes tab. A smoke test uses **Notes** as input and **Test** as output.
4. Read the Notes tab only. Expand a first name or nickname using the attendance block in those notes (`Jo` → `Jordan Hale`). Leave anyone who is not on that block as written. Do not swap one person's name onto another.
5. Draft semantic JSON (`schemaVersion` 1) using only `masthead`, `attendance`, `section`, `presenter`, `bullet`, `motion`, and `paragraph`. Follow [template-spec.md](template-spec.md). Do not include character offsets or style spans. Prefer categorized attendance `groups`.
6. Write that JSON only under `Sensitive/` or a system temporary directory. Never write it to a tracked path, and do not put the minutes text in the shell command line.
7. Show the user the exact document title and the output tab title. Stop until they confirm.
8. Run the writer with `--write` and those exact titles. On success or failure, delete the JSON file in a `finally` step.
9. Reply with the document title, output tab, and URL. Do not paste the minutes text back into the chat.

## Hard rules

- Section headings are title text only (`Accept Minutes`). The writer supplies the uppercase-Roman glyph, Arial 13pt bold black, and the blank line before each section.
- Standard order: D'var Torah, Accept Minutes, Executive Director Update, Journal Dinner Updates (or the event name in the notes), Committee Items. Insert an unanticipated major section where the notes place it and keep the Roman sequence contiguous.
- The last three sections are always Old Business, New Business, and Adjournment. Under an empty one, the body is `None.`
- Under Committee Items, standard sub-headings are Events Committee, Education Committee, Gabbai Committee, and Growth Committee. A topic that does not fit gets its own sub-heading in the notes' words.
- Presenter line, when the notes name one: `Presented by Alex Rivera.` Immediately under the section. Omit it when the notes do not name a presenter.
- A motion is one item: body plus optional `passes` or `fails`. Do not invent a mover, seconder, or verdict. Example body: `Alex Rivera moves to accept the March minutes. Jordan Hale seconds.`
- Level 0 bullets are topic labels (`Hall rental`). Level 1 is one outcome sentence. Keep the name of anyone the notes credit. Merge only consecutive turns by the same person, or turns that state the same outcome, and still name them.
- A speaker-less line that only continues the previous bullet is one level deeper. The next named speaker returns to the parent level.
- Do not put bold category labels inside bullet sentences. Fold the idea into the sentence.
- Repeat the antecedent instead of a dangling "it" when it points at a policy, document, or named item (`the volunteer schedule should be posted`).
- Write `re-sent`, not `resent`. Capitalize named ritual occasions (`Seuda Shlishit`, `Mincha`).
- The attendance label is `In attendance:`. Do not add `(In Person)`.
- When the notes include a pasted proposal and say to record the purpose items, write each purpose. Do not reprint the full current and proposed quotations. Replace a placeholder mover such as `XXX` with the mover named in the notes. If a purpose sentence is cut off in the notes, leave it cut off.

## Reference

Render contract and a fictional worked example: [template-spec.md](template-spec.md).
