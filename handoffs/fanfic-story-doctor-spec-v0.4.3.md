# Fanfic Story Doctor Skill – Spec (Draft v0.4.3)

**Status:** Draft v0.4.3, implementation revision  
**Owner:** Jon Dubin  
**Last updated:** October 10, 2026  
**Previous version:** v0.4.2 (kept unchanged in private notes; not published in this repo)

Build from this file. Where this file does not amend a section, v0.4.2 remains in force; that text lives in private notes, not in this public repo. Nothing in v0.4.2 is deleted.

> **Implementation status.** v0.4.2's legend still applies. This revision does not mark anything Implemented or Test passed. Package status lives in `python/fanfic_story_doctor/STATUS.md`, keyed by spec section and test id. CI fails if a row says "Test passed" and the named test is missing.

## D2. Change log (v0.4.2 → v0.4.3)

| Item | Change |
|---|---|
| 1 | `CANON.DIVERGENCE` checks `event_order` against `au.divergence_event`. Before the branch is a finding. At or after the branch is coverage. |
| 2 | Public-thread tally (10 Oct 2026) locked the M5 predicate as `event_order`. Alive/dead is not that predicate. |
| 3 | First user is the friend, on her drafts. Another fandom is a new private ledger and intake, not a code change. Checking other people's posted fics is Later. |
| 4 | MVP evaluation is synthetic tests plus one tester tagging useful / noise / wrong. Two annotators and holdout wait for section 17.10. |
| 5 | Canon ledger rows record who confirmed them. |
| 6 | Contradictions with v0.4.2 are resolved below: private ledger allowed, SAME-class story bounds, evidence kinds, re-anchoring, ID order, Cursor host, `DOCTOR_HOME`. |
| 7 | Judgment checks, including `CANON.RAILS`, stay in Layer B. Info only. Never a fact-rule YES/NO. |

## 1. Divergence rule

`au.divergence_event` from intake is load-bearing. `CANON.DIVERGENCE` compares a ledger `event_order` with a primary-canon `event_order` for the same events.

| Where `q` falls relative to the divergence event | Result |
|---|---|
| BEFORE | finding, severity `should`, kind `internal_inconsistency` |
| SAME or AFTER | coverage item, never a finding |
| UNKNOWN | unverifiable, plus a `TIMELINE_ANCHOR` question if load-bearing |
| Work not declared AU | info item |
| Declared AU and no divergence event | info item, plus one intake question |
| AU override covers `q` with the ledger's value | coverage at any point |
| Ledger order matches canon | nothing |
| Canon cover is not YES | nothing |
| Canon citation stale or disputed | unverifiable, no fall-through to a lower canon source |

`CONT.TIMELINE_ORDER` is a different rule. It fires on a cycle of confirmed edges. It is not this rule. Canon `event_order` edges are not asserted into the work's timeline graph for any pair the ledger or AU layer orders itself, so a deliberate branch never forms a `CONT.TIMELINE_ORDER` cycle. The pre-canon inference (a later mainline scene stays before an event an earlier scene precedes) applies only to the intake `window.event` when `window.relation` is `before`.

`CANON.RAILS` is not this rule. "Later events should have changed" is a Layer B judgment.

This replaces v0.4.2 section 6.5's "ledger or au vs canon: higher layer wins silently" for `event_order`.

## 2. Predicate

M5's predicate is `event_order`. The ledger may store other predicates. A new predicate still needs the v0.4.2 section 6.2 process before a rule consumes it.

## 3. Users

Writer self-check on her drafts is the first use. Jon may run it for her. Those drafts live under `DOCTOR_HOME` on his machine. Consent is recorded locally.

Another fandom is `DOCTOR_HOME/canon/<source_id>/` plus a new `intake.yaml`. Rules, schemas, and timeline code contain no fandom branches. Book versus show is `primary_canon_source`.

## 4. Evaluation

Until section 17.10's tester bar is met: synthetic suites, plus the writer tagging each report item useful / noise / wrong, counted per rule. Acceptance criteria are committed before any holdout run. Writer-approved facts are not ground truth.

## 5. Canon provenance

Each canon fact records `confirmed_by`. Corrections to canon rows are counted separately from corrections to draft facts. She can mark a canon row `disputed`.

## 6. Amendments to v0.4.2 mechanics

**Private canon.** A per-user ledger under `DOCTOR_HOME` is allowed. No shared or published canon database. Canon facts load from intake or from `DOCTOR_HOME/canon/<source_id>/facts.json`. Extraction writes `proposed` rows only. Confirmed rows are enforceable. Book text, quotes, and series facts never enter git, CI logs, manifests, or chat.

`DOCTOR_HOME/canon/<source_id>/text/` holds chapter files. `normalized/` is normalizer output. `facts.json` uses the fact schema, `layer: canon:<source_id>`, with a local citation (paragraph id, exact quote, paragraph hash). `doctor canon load` refuses a path inside the repo. The default folder is `%USERPROFILE%\doctor-home` (Windows) or `~/doctor-home`; set `DOCTOR_HOME` to override. The tool does not download books.

**SAME-class story bounds.** If `covers` would return YES only because `compare` of a story-time `from` bound and a paragraph is SAME across two different nodes in one class, return UNKNOWN and queue "where in this scene does this change?" Work-position bounds still order by paragraph index. Scenes strictly after the event stay YES.

**`default_value`.** Only `status` defaults to `unspecified`. Other predicates with no covering fact are absent.

**Same-paragraph payoff.** A setup and a payoff on the same work position yield UNKNOWN.

**`unspecified`.** Violation rules return NO. The report includes "status facts cover X of Y main-cast characters." If X is 0, Continuity does not say only "nothing found."

**Re-anchoring.** A bound whose paragraph is `citation.at` follows the re-anchored citation. Any other work-position bound stores that paragraph's `content_hash` and re-finds a unique hash in the chapter; otherwise `stale`. Story-time bounds do not drift. An annotation re-anchors by paragraph `content_hash` plus span. If that hash is gone, do not search by surface; mark it stale.

**IDs.** Compare IDs as int tuples `(chapter, scene, paragraph)`. Display chapter padded to at least 2 digits (`ch07`, `ch100`). Scene and paragraph are unpadded. `s2` sorts before `s10`. `ch99` sorts before `ch100`.

**Evidence.** Closed kinds: `prose` (paragraph id plus exact quote) or `file` (relative path plus field name, no quote).

**Never-rewrite source.** A quoted string in free text must be an exact substring of a cited paragraph, or the object or surface string of a cited fact or annotation.

**Host.** Cursor is the MVP runtime host. "Layer A only" means the package makes no provider calls. Real drafts, `works/`, `runs/`, and `cache/` live under `DOCTOR_HOME`, outside the workspace. `.cursorignore` is defense in depth. It is not the privacy boundary. Gate G9: Cursor data and retention settings checked on the actual account before a real draft is processed.

**Report honesty.** A rule that has not been built is `skipped`, with a reason. `skipped` is never rendered as "nothing found."

## 7. Layer B

`OOC.VOICE` and `CANON.RAILS` share one contract: fixed rubric, closed labels, exact quote, `observed` separate from `interpretation`, severity info, never a blocker. Agreement is reported and is not correctness.

`CANON.RAILS` labels: `consequence_shown`, `on_rails`, `not_enough_evidence`. It asks whether a declared branch has an on-page consequence in a later passage. It ships with the mock provider first.

> **Status (2026-10-17).** `doctor run --layer-b` runs both rules on the deterministic mock provider (three runs, vote, cache). `OOC.VOICE` labels: `in_voice`, `drift`, `break`, `intentional_evolution`, `not_enough_evidence`. `CANON.RAILS` runs only when the work declares an AU with a divergence event, and only on passages ordered after it. Notes are item_state `note`, severity `info`; the validator rejects any Layer B item above info or as a finding. A non-mock provider is refused while gate G9 is closed (`DOCTOR_G9_OPT_IN`), and no real provider exists yet.

## 8. What the first code packet includes

Normalize (Markdown, text, AO3 HTML), intake, fact store, timeline (E1–E8 plus the SAME-class rule), private canon load, report schema and renderer, alias-exact mentions, temporal markers. `CANON.DIVERGENCE` is in this revision's code once M5 is built; until that code exists the report says `skipped`.

Real chapters and real books are not fixtures. Tests use the invented Ashfall cast only.
