---
thread: msjc-board-secretary
status: active
created: 2026-11-18T15:29Z
supersedes: handoffs/archive/msjc-board-secretary/20261118-1515-msjc-board-secretary.md
private_detail: null
---

# MSJC board secretary

## Objective

Implement the round-3 fixes from the adversarial consolidation review of pull request 25, in priority order, without weakening any owner decision. The full review report is embedded verbatim below and is the source of truth for what to change.

## Current State

- Pull request 25 is open and unmerged: https://github.com/jondub95/skirt_steak/pull/25
- Branch `feature/board-secretary-friction`, head `8ca51f7`. The review added no code; this checkpoint is the only new content.
- Review validation on 2026-11-18: `python3 -m unittest discover -s python/msjc_board_secretary/tests -p "test_*.py"` = 62 tests, OK. `python3 -m ruff check python/msjc_board_secretary` = All checks passed. Every Part B finding was confirmed by executing probes against the real validators, not by reading alone. No live Google Doc was written.
- `tools/workflow_guardrails/preflight.sh` still exits 1 because the Docs client file and token directory are not on this machine. That is the Docs sync preflight, not the minutes suite.
- Do not pop the stash named `board secretary handoff checkpoint`. It belongs to `feature/close-stale-handoffs`.

## Owner Decisions Still In Force

- `fails` is only for motions the notes record as actually voted down. An unseconded or unvoted motion is plain text with no verdict, for example `No second; not voted`. Never `Motion Fails.` for it.
- Step 7 stops unless the request named both the exact document title and the exact output tab. Do not weaken this.
- Do not implement native Google Docs code blocks or horizontal rules. Do not build tooling to accept or reject Docs suggestions.
- Do not open a new pull request. Jon merges.
- Do not commit credential files or an `mcp.json` that launches the local server.

## Full Review Report (verbatim)

### Verdict

**Approve-with-changes blocked on two Blockers** — the motion-verdict guard is one-sided and bypassable: `passes` is entirely unguarded, and `fails` can be earned by phrases that mean "never seconded" or "died without a vote". Consolidation can remove roughly **280–290 lines (~17%)** with no intended functionality loss, more than half of it superseded handoff checkpoints. The 62-test suite passes and ruff is clean on this machine; all findings below were confirmed with live probes against the actual code, not just reading.

### Part A — Consolidation (ranked by lines saved vs risk)

| # | Location | What to merge/cut | Lines saved | Risk / functionality lost |
|---|---|---|---|---|
| 1 | `handoffs/archive/msjc-board-secretary/20261118-1502-…md` (90) and `…20261118-1512-…md` (66) | Delete both superseded checkpoints; repoint the live head `handoffs/20261118-1515-…md`'s `supersedes:` to the 1620 archive. 1512 is ~98% identical to 1515. Keep 1620 (unique live-November context) and 1515. `handoffs/INDEX.md` already points at 1515. | **~156** | None. Pure intermediate states; no reader depends on them. |
| 2 | `tests/test_write_tab.py:121–176, 228–267, 425–464` | The creds-monkeypatch boilerplate (`called={"creds":0}` + `boom` + try/finally, ~9 lines) appears 6×, and the 10-line CLI arg list ~5×. Extract an `assert_no_credentials()` context manager and a module-level `WRITE_ARGS` constant. | **~55–65** | Low. Pure test refactor; identical assertions. |
| 3 | `tests/test_schema.py:249–271, 279–298` (inline attendance docs) and `219–244` (5 labels × 6 verbs = 30 subcases) | Reuse `_attendance_doc` (line 186) in the two tests that hand-build it; collapse the matrix to 5 labels × 1 verb + 1 label × 6 verbs. | **~25** | Honest loss: 24 redundant pairwise label×verb combos. Negligible — a bug that hits only one specific pair would be missed. |
| 4 | `python/msjc_board_secretary/setup_local_mcp.py:26–38, 54` | Merge `google_docs_server` into `config_with_google_docs` (one caller); drop the `repo_root` parameter from `write_local_mcp` — it is never used in the body (tests pass it needlessly). | **~10** | Low; update 3 test call sites. |
| 5 | `python/msjc_board_secretary/builder.py:351–361` | `paragraph_text` and `_para_text` are near-duplicate paragraph-text extractors. Make `_para_text` = `paragraph_text(el.get("paragraph") or {}).strip()`. | **~6** | None. |
| 6 | `python/msjc_board_secretary/write_tab.py:301` | Post-reload `if not revision` is redundant with the loop-top check at line 293; after the *last* pass nothing consumes the revision. | **2** | None. |
| 7 | `write_tab.py:407–421` vs `452–465` | Two hand-rolled missing-flag blocks; generalize `_require_write_args(args, flags)` and reuse in the replace branch. | **~6** | Low. |
| 8 | `python/msjc_board_secretary/schema.py:314` | `_NAME_CONTINUATION`: `Jr\.?\|Sr\.?\|III\|II\|IV\|V` is fully subsumed by `[A-Z][A-Za-z'.-]*` (verified by probe — identical on all 12 cases). Collapse to `\s+[A-Z][A-Za-z'.-]*`. | **1** (+ clarity) | None. |
| 9 | `schema.py:393, 432–438` | `_EMPTY_SECTION.fullmatch` ≡ `text == "None."`. Replace the regex with a string constant; delete the now-stale "A search would also hit…" comment. | **~3** | None. |
| 10 | `schema.py:450` | `item.kind != "section"` filter is dead — `_section_bodies` slices between consecutive sections, so a body can never contain one. | **0** (+ clarity) | None. |
| 11 | `.cursor/skills/.../template-spec.md:77`, `python/msjc_board_secretary/README.md:30` | The `fails` rule is stated at length in three places (SKILL.md hard rules, template-spec Motions, README); trim template-spec to one sentence. The README 150-word refusal run-on can lose ~3 lines. `InstructionTextTests` pins only sign-in/step-8 strings, so this is safe. | **~7** | Low; keep the canonical long form in SKILL.md only. |
| 12 | `tests/test_builder.py:236–239` | `test_minutes_item_defaults` asserts a dataclass default (`level == 0`). Near-zero value. | **~4** | None. |
| 13 | `write_tab.py:366` | `perform_replace` re-checks `find_text == replacement`, which `load_replace_pair` already enforces for the CLI path. | **2** | Optional — flag: dropping it loses defense-in-depth for direct API callers (tests call `perform_replace` directly). Recommend keeping. |
| 14 | `write_tab.py:222–236` | `requests_for_pass` if-chain → dict dispatch. | **~3** | None; marginal. |

**Total Part A: ~280–290 lines (~17% of +1643)** — 156 handoffs + ~125 code/tests + ~7 docs.

### Part B — Adversarial re-review

#### Blocker

**B1. `passes` verdict is completely unguarded.** `schema.py:184` guards only `verdict == "fails"`. Probes, all **ACCEPTED** and rendered as bold "Motion Passes." on the live tab:
- body `"Alex Rivera moves to raise dues. No second; not voted"` + `verdict: "passes"`
- `"…No one seconds."` + `passes`; `"…moves to raise dues."` (bare) + `passes`

The item-2 review fix protected exactly one direction of exactly one verdict. A false *pass* is the same factual corruption of minutes as a false *fail*. **Fix:** the earned check must apply to both verdicts — `verdict is not None` requires `_SECONDER` or `_RECORDED_VOTE`, and a `_NO_SECOND_OR_VOTE` body without a recorded vote forbids both. Sample and existing tests still pass (the sample's `passes` motion has a seconder).

**B2. `fails` earned by "No one seconded." — the exact case item 2 was supposed to forbid.** `schema.py:19–20` `_NO_SECOND_OR_VOTE` only matches `seconds?`/`second` (not *seconded*), so `"Alex Rivera moves to raise dues. No one seconded."` does not match it, while `_SECONDER` (line 18) matches "seconded" → `motion_fail_is_earned` returns True → **ACCEPTED with `verdict: "fails"`** (probe confirmed end-to-end). Same class: "Nobody seconded it.", "never seconded", "without a second". **Fix:** broaden to `\bno\s+(?:one\s+|body\s+)?second(?:s|ed)?\b`, `\bnever\s+seconded\b`, `\bwithout\s+a\s+second\b`, `\bdied\s+without\s+a\s+second\b`. Verify "Jordan Hale seconds." still earns (it does — "no" is required).

#### Should-fix

**S1. `fails` earned by phrases that mean "died without a vote".** Probes: `"Motion fails for lack of a second."` and `"Defeated for lack of a second."` both earn `fails=True` (`schema.py:22–23` lists `motion fails|failed` and `defeated` in `_RECORDED_VOTE`). No vote occurred. **Fix:** when any no-second/lack-of-second phrase is present, require an explicit vote phrase (`voted down`, `vote failed`, `yeas`, `nays`) rather than motion-fails/defeated, or drop those two from the earned list.

**S2. Punctuated absence labels silently skip the entire absent-speaker check.** `schema.py:320` `_absence_category` only rstrips `":"`. Probes: categories `"Regrets."`, `"Not in attendance."`, `"Absent -"` all normalize to a non-member → everyone in that group is treated as present. **Fix:** strip trailing `.:;,–—-` before casefold.

**S3. Name word-boundary excludes only ASCII letters.** `schema.py:335` `(?<![A-Za-z])name(?![A-Za-z])`. Probes: absent `"Ann"` flags `"Jo-Ann said…"` and `"The key2Ann said…"` as conflicts (real speaker Jo-Ann). **Fix:** `(?<![A-Za-z0-9-])` / `(?![A-Za-z0-9-])`.

**S4. Bracketed Roman headings pass.** `schema.py:384` requires `^` or `\s` before the token. Probes: `"(II. Accept Minutes)"` and `"[II. Budget]"` are **allowed** as titles/replacements. **Fix:** replace `(?:^|\s)` with `(?<![A-Za-z])`. "D'var Torah" still passes (lookahead fails on the apostrophe).

**S5. Speaking-verb under-match.** `schema.py:267–306`. Probes, all **allowed** for a marked-absent speaker: `shared`, `added`, `offered`, `thanked`, `agreed`, `confirmed` — none in the list; and comma adjacency breaks the immediate-verb rule: `"Taylor Morgan, who reported the leak, was absent."` is not flagged. **Fix:** add the common verbs; decide the comma case explicitly (e.g. also match `,\s+who\s+(verb)`) or document the boundary in the docstring.

**S6. Possessive handling is asymmetric and wrong in both directions.** Probes: `"The session was presented by Taylor Morgan's replacement."` → **false conflict** (the `_PRESENTED_BY` check at `schema.py:311,349` ignores a possessive suffix), while `"Alex Rivera's replacement presented the budget."` → allowed (immediate-verb check blocked by `'s`). **Fix:** if the character immediately after a name span is `'` or `’`, the mention is possessive — skip the span for both the presented-by and verb checks.

#### Nit

- **N1.** `write_tab.py:473` — the replace path prints `"refusing the minutes: …"` for a bad *replacement phrase*. Say `"refusing the replacement: …"`.
- **N2.** `schema.py:384` — lowercase `"iv. Accept Minutes"` passes (class is uppercase-only). Accept or document.
- **N3.** `write_tab.py:101–115` — `bool(document_title) and bool(output_tab)` in `full_tab_replace_is_confirmed` is dead in the CLI path (`_require_write_args` runs first at :407).
- **N4.** The `--confirmed-*` flags are agent-asserted; nothing technically binds them to a human's request. Step 7's gate is procedural (skill text + review), which is fine, but worth stating in the PR description so a reviewer doesn't over-trust the flag.
- **N5.** `find_tab` (:80) matches titles case/whitespace-insensitively while `validate_target_identity` is exact — fail-closed, but a wrong-case `--output-tab` produces "found then refused" rather than "not found"; the error strings make it debuggable. Note only.
- **N6.** `test_sample_shape_is_writable` / `test_sample_has_no_absent_speaker` (`test_schema.py:201, 338`) stay green with the checks deleted — acknowledged in the handoff; the refusal tests carry the real coverage, so no action, but don't cite these two as coverage of the shape/absence rules.
- **N7.** `test_write_tab.py:470` — `skill.split("8. ", 1)` breaks if the skill renumbers; acceptable, but a `<!-- step-8 -->` anchor would be sturdier.

#### Verified-correct (explicitly hunted, found sound)

The `--replace`/`--write`/`--input` flag matrix (mutual exclusion, replace-without-write, missing-flag refusals); revision locking per batch (`test_each_batch_locks_the_prior_revision` genuinely asserts the sequence); recovery message on pass-2 failure; phrase-count==1 gate scoped to the output tab only; credentials never constructed on dry-run or any refusal path; `find_tab` case-normalization cannot bypass the exact-title identity check; `Adjournment has None. alongside other text` correctly fires for `None.` + motion.

### The two known edge cases — what I'd change in approach

**Edge 1 (`II.` mid-sentence refused in a `--replace` phrase).** Don't make `minutes_phrase_errors` sentence-position-aware. Make it *paragraph-position*-aware, because that's the only position where the marker can do harm: a heading marker only takes effect at the start of a paragraph. For the replace path, anchor both checks to the start of the replacement — `^\s{0,3}#` (already anchored) and `^([IVXLCDM]+)(?=[.)])`. `"II. Accept Minutes"` as a full replacement is still refused; `"See II. above"`, `"Presented by D. Schwartz"`, `"Update from M. Rivera"` become allowed, killing the known edge and the single-initial false refusals together. The pre-credential guarantee from item 6 is untouched, and section titles on `--input` keep the whole-value check (a title *is* the whole paragraph).

**Edge 2 (` None.` leading space).** Stop having two normalizations; pick a doctrine and make the near-miss loud. Recommended: keep the marker exact (`text == "None."`, which is also Part A item 9), and add ~4 lines to `_closing_section_errors`: a closing section whose only content is a paragraph that *strips to* `None.` but *is not* the marker raises an error ("empty-section marker has leading/trailing whitespace"). Leave `strip_spilled_bullets`'s strip as-is (it operates on Docs text where the trailing `\n` is structural). This converts the current silent path disagreement — schema treats it as content and *no error fires today* when it's the only body — into an explicit refusal, which is strictly better than both current behaviors. Rejected alternative: stripping in the schema check, which would silently render a leading space onto the live document.

### Bottom line

- **Total estimated removable: ~280–290 lines (~17%)**, of which 156 is superseded handoff checkpoints and ~125 is genuine code/test simplification; flagged losses are only the 24 redundant label×verb subcases and (optionally, if you take item 13) one duplicate direct-call guard.
- **Must fix before merge:** B1 and B2 (and S1 is the same root cause at one remove) — these are the `fails`/`passes` verdict-integrity rules the previous review round established, and both are currently bypassable with plain English the notes plausibly contain.
- Evidence: 62 tests pass, `ruff check` clean, all Part B findings confirmed by executing probes against the real validators (outputs above); no live Google Doc write was attempted, consistent with the handoff note that Docs credentials are absent on this machine.

## Prioritized Next Best Actions

1. **Verdict integrity (B1 + B2 + S1, one change).** Guard both `passes` and `fails`: any verdict requires the body to name a seconder or a recorded vote, and a no-second/no-vote body forbids both. Broaden `_NO_SECOND_OR_VOTE` to cover `seconded` variants ("No one seconded", "Nobody seconded", "never seconded", "without a second", "died without a second", "lack of a second"). A lack-of-second phrase does not count as a recorded vote — with one present, only explicit vote phrases (`voted down`, `vote failed`, `yeas`, `nays`) earn a verdict. Add tests: `passes` on an unvoted/unseconded body refused; `fails` with "No one seconded." refused; `fails` with "Motion fails for lack of a second." refused.
2. **The two known edge cases, using the approach above.** Anchor the replace-path heading-marker checks to the start of the replacement phrase; keep `None.` exact and make a whitespace near-miss (only body strips to `None.` but is not the marker) a hard error in `_closing_section_errors`.
3. **S2–S6.** Absence-label punctuation strip, hyphen/digit name boundaries, bracketed Roman token lookbehind, verb-list additions plus an explicit comma-adjacency decision, possessive suffix skip.
4. **Part A consolidation.** Delete the two superseded archive checkpoints (`20261118-1502`, `20261118-1512`) and repoint the surviving chain; extract the test helpers; the small merges (`setup_local_mcp`, `builder` text extractors, `_NAME_CONTINUATION` collapse, `_EMPTY_SECTION` to equality, post-reload revision check, missing-flag helper, docs trims).
5. **Nits last.** N1–N7, each a small standalone change.

## Files / Artifacts / Sources

- All findings: `python/msjc_board_secretary/schema.py`, `write_tab.py`, `builder.py`, the three test files, `setup_local_mcp.py`, `.cursor/skills/msjc-board-secretary/SKILL.md`, `template-spec.md`, `python/msjc_board_secretary/README.md`.
- Human-readable iteration log: Google Doc **'PR #25 Adversarial Review'** at https://docs.google.com/document/d/1SNVx4YNpY9OYhLOwY0RBrifxnR1rzUDmqYculvZlCL0/edit (tabs: round-robin reviews, Open Edge Cases, Round 2 GLM consolidation review). Agents cannot read that document; this handoff is the source of truth.
- Validation commands: `python3 -m unittest discover -s python/msjc_board_secretary/tests -p "test_*.py"` and `python3 -m ruff check python/msjc_board_secretary`.

## Known Risks or Failure Modes

- `motion_fail_is_earned` stays a phrase check; a voted-down line using none of the recognized words is refused. Fix 1 narrows but does not remove that.
- No live Google Doc write has been exercised in any of these rounds; the credential path remains untested end-to-end.
- `--confirmed-*` flags are agent-asserted (N4); step 7's human gate is procedural.
- `preflight.sh` exits 1 on machines without the Docs client file and token directory.

## Prompt to Resume

Continue from `feature/board-secretary-friction` and this handoff; pushing updates pull request 25 and Jon merges. Implement fix 1 (verdict integrity: guard `passes` and `fails`, broaden the no-second phrases, lack-of-second is not a vote) first, then fix 2 (start-anchored replace heading checks; exact `None.` with a loud whitespace near-miss error), then S2–S6, then Part A consolidation, then the nits. Keep `fails` only for voted-down motions, keep the step-7 stop unless both exact titles were named, and avoid Docs code blocks, horizontal rules, suggestion tooling, and a new pull request. Validate every change with `python3 -m unittest discover -s python/msjc_board_secretary/tests -p "test_*.py"` plus `python3 -m ruff check python/msjc_board_secretary`.
