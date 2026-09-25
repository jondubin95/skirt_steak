# MSJC Board Minutes — Template Spec

Deterministic rules for the Board Secretary skill. The writer turns semantic JSON into Docs requests. Examples use a fictional roster: Sam Ortiz, Alex Rivera, Jordan Hale, Taylor Morgan, and guest Rabbi Mendes. Nickname pair: `Jo` → `Jordan Hale`.

## Section order

- Order standard sections as they appear in the notes:
  - D'var Torah
  - Accept Minutes
  - Executive Director Update
  - Journal Dinner Updates (or the current event name)
  - Committee Items
- The last three sections are always Old Business, New Business, and Adjournment, in that order. If one is empty, its body is `None.`
- An unanticipated major section (for example a special presentation) is inserted where the notes place it. Numbering stays contiguous because the writer emits one uppercase-Roman list, not numerals typed into the heading.

## Render contract

The agent supplies title text only. The writer generates glyphs, spacing, and styles.

| Item | Semantic field | What the writer emits |
|---|---|---|
| Masthead | `date`, `organization`, `title` | Date at 12pt. Organization and title centered, underlined; organization 14pt bold. |
| Attendance | `label` plus `groups` or `names` | Label at 12pt. Each group is a bullet whose category prefix is bold 12pt (`Officers: Sam Ortiz`). |
| Section | `title` | Blank paragraph, then a `HEADING_3` whose text is the title only. One `UPPER_ROMAN` list (`glyphFormat` `%0.`) covers every section. Run override: Arial, 13pt, bold, black. |
| Presenter | `text` | Italic normal paragraph, for example `Presented by Alex Rivera.` |
| Bullet | `text`, `level` | Default disc list. Level is leading tabs, not typed spaces. Body stays Arial 11. |
| Motion | `body`, optional `verdict` | Plain paragraph, 12pt below, no border. The whole line is underlined. `Motion` and `Motion Passes.` or `Motion Fails.` are bold. |
| Paragraph | `text` | Normal paragraph. `None.` is not a list item. |

Do not type `### I.` or a blockquote. Those forms are not the minutes.

Named styles on a typical source doc are not the minutes look (`HEADING_3` is 14pt gray). The writer overrides the runs.

## Bullet voice

Notes are a transcript. Minutes are one bullet per point.

- Level 0 is a short topic label (`Hall rental`, `Volunteer schedule`), not a sentence.
- Level 1 states the outcome and keeps the roster name of anyone the notes credit. Merge only consecutive turns by the same person, or turns that state the same outcome, into one sentence that still names them.
- A line with no speaker stays unattributed. Do not collapse several people's distinct positions into one nameless bullet.
- Drop placeholder lines. Do not write a bullet that says the notes omitted something.
- A speaker-less line that only continues the previous bullet is one level deeper. The next named speaker returns to the parent level.
- If "it" points at a policy, document, or named item, repeat that name.
- House style: `re-sent`, not `resent`. Capitalize named ritual occasions (`Seuda Shlishit`, `Mincha`). The attendance label is `In attendance:`, without `(In Person)`.

Notes fragment:

```
- Jo - the hall rental fee is too low for the volunteer schedule we already posted
- Alex says the events group keeps having this conversation
- Rabbi Mendes - leave the guest welcome as it was announced
```

Target items:

- `Hall rental` at level 0
- `Jordan Hale said the hall rental fee is too low for the volunteer schedule already posted.` at level 1
- `Alex Rivera said the events group keeps having this conversation.` at level 1
- `Rabbi Mendes said to leave the guest welcome as announced.` at level 1

`Rabbi Mendes` stays as written when that guest is not given another name in the attendance block.

## Committee sub-headings

Under Committee Items, standard labels are Events Committee, Education Committee, Gabbai Committee, and Growth Committee. A topic that does not fit those labels gets a custom sub-heading in the notes' own words. Do not force it into a standard category.

## Motions

One `motion` item. Do not invent a mover, seconder, or verdict.

```json
{
  "kind": "motion",
  "body": "Alex Rivera moves to accept the March minutes. Jordan Hale seconds.",
  "verdict": "passes"
}
```

Omit `verdict` when the notes do not record pass or fail. Replace a placeholder mover such as `XXX` with the mover named in the notes.

## Names

Expand a first name or nickname only to the full name in the Notes attendance block (`Jo` → `Jordan Hale`). Someone who is not on that block stays as written. Do not swap two different people onto one name. If the notes say `Alex` and the attendance block lists `Alex Rivera`, use `Alex Rivera`. If the notes name a different person who is not on the block, leave that name unchanged.

## Proposals

When the notes paste a proposal and say to record the purpose items, write each purpose. Do not reprint the full current and proposed quotations. If a purpose sentence is cut off in the notes, leave it cut off.

## Document title

`<Month> <Year> Board Meeting Minutes <YYYYMMDD>`

- `<Month>` is the full month name.
- `<YYYYMMDD>` is the meeting date.

Example: `April 2026 Board Meeting Minutes 20260412`.

## Worked example

Fictional raw note:

```
- jo moved to accept the march minutes, jordan seconded, passed
```

Semantic items (heading text only; the Roman glyph is not in the JSON):

```json
{"kind": "section", "title": "Accept Minutes"}
{"kind": "presenter", "text": "Presented by Alex Rivera."}
{"kind": "motion", "body": "Alex Rivera moves to accept the March minutes. Jordan Hale seconds.", "verdict": "passes"}
```

Failure modes to avoid, described without a source document:

| Failure | Required result |
|---|---|
| Heading text includes `###` or a typed Roman numeral | Title only, real `HEADING_3`, one contiguous uppercase-Roman list |
| A motion is a blockquote or an inline bold sentence | Plain underlined paragraph from the writer |
| Presenter line is a heading | Italic normal paragraph under the section |
| Bullet starts with a bold `Topic:` label | The topic is part of the sentence, or a level-0 label with no colon prefix |
| Roman sequence skips or repeats | One list, so later sections continue the count |
