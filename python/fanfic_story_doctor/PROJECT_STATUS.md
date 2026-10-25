# Fanfic Story Doctor: Project Status

**Status: shelved on 2026-10-24.** Not abandoned. Paused because there is no clear path to value right now and the results were not groundbreaking. This page records what was built, what the trials showed, and what to try if the project resumes.

## What it is

A continuity and out-of-character (OOC) copilot for fanfic writers that diagnoses and never rewrites. The model proposes, the writer confirms, and scripts enforce.

- **Layer A** uses deterministic rules with no model call: name spelling, ledger coverage and conflicts, dead-character-reappears, payoff-before-setup, timeline order, canon divergence, and AO3 schema/tag format.
- **Layer B** uses LLM judging. `OOC.VOICE` judges one speaker turn against a generated voice profile three times and reports majority agreement. Its notes are info-only, never findings or blockers.
- **Gate G9** blocks any non-mock provider unless the writer opts in for that run.

## What was built

A CLI (`doctor run`) that handles intake, ledger, Layer A rules, and Layer B voice notes, with Markdown/HTML/JSON reports and highlightable flag positions. It also has voice profiles that rebuild when their sample changes, a strict response contract that rejects malformed or non-verbatim responses, and 145 tests that pass with the mock provider. Specs run from v0.4.3 to v0.4.4 (see `handoffs/`).

## Results

All runs were local, on texts that stay outside the repo (`<doctor-home>`). Only aggregate counts are shown here.

| Run | What | Calls / time | Voice outcome | Layer A |
|---|---|---|---|---|
| Trial 7 (v0.4.3) | Long multi-chapter work, 116 targets | 348 calls, ~35 min | Several drift notes, 1 break; ~40+ not_enough_evidence | 2 name-spelling findings |
| Trial 8 | Same work, sampling fixes | 135 calls, ~18 min | 2 of 3 profiles rejected for exceeding the 200-char field limit | - |
| Trial 9 | Same work, fixed profiles | 116 calls, ~15 min | 81 targets: in_voice 75, not_enough_evidence 5, drift 1; 129 of 243 reads thin | - |
| Second work | Different 20-chapter work, same universe | 107 calls, 0 failures, 433 s | 35 notes: in_voice 33, not_enough_evidence 2, 0 concerns; 81 of 105 reads thin (77%) | 1 name-spelling finding (false positive) |
| Planted defects | Second work with 7 planted edits | 15 calls, 82 s | 1 register swap caught (3/3) | 2 planted misspellings caught |

The one Trial 9 drift flag was reviewed by hand and judged a false positive: the single-line check missed the running banter around it. The second-work name finding was a valid feminine surname ending (-a/-ova), not a typo.

**Planted-defect proof of concept.** Six plants were meant to fire and one was a control. The run caught 3 of the 6: one register swap with 3/3 agreement, plus two name misspellings caught by Layer A. Of the 3 misses, one was judged and passed as fine (a subtle edit on a short line with thin evidence). The other two never reached a judge, because only one line per character per chapter is judged and only name-tagged quotes count, and shortening a line changed which line was picked. The control stayed quiet, and there were no false positives.

## What worked

- The name-spelling check caught real misspellings.
- Gross register swaps were caught with full agreement.
- Runs were deterministic, with stable cache and agreement behavior.
- The tool abstained when evidence was thin instead of guessing.
- The privacy gate (G9) and the rule of keeping real text out of git both held.
- The control produced no false positives.

## Where it fell short

- There were zero confirmed true positives on real, unedited text.
- The voice check gave little information on short lines: about 77% of reads were thin.
- Coverage is limited to one line per character per chapter, and only name-tagged quotes count.
- Judging a single line misses context such as banter.
- The name check overlaps with an ordinary spell checker.
- OOC is subjective, which makes "correct" hard to define.
- There was no real-writer feedback loop, because the test writer's drafts are private.

## Decision

Shelved on 2026-10-24. There is no clear path to value and nothing groundbreaking. The code, tests, and specs stay in place so the project can resume.

## What was learned / reusable

- **Propose-confirm-enforce ledger.** The LLM proposes facts, a human confirms them, and scripts enforce them. This fits domains built on objective facts better than subjective voice.
- **Planted-defect evaluation.** Editing known defects into a real text, plus a control, is a cheap way to measure recall when no labeled data exists.
- **Determinism and abstention testing.** Majority-of-3 voting, response contracts, and counting "not enough evidence" as its own outcome all carry over to other LLM-judge tools.

Research notes on fanfic critique: most sources are fan opinion. OOC is highly subjective and is only confidently OOC when it contradicts canon action. No labeled OOC-in-fanfic dataset exists. The closest reusable labeled data is the [Project Dialogism Novel Corpus](https://github.com/Priya22/project-dialogism-novel-corpus) (speaker-attributed quotes) and role-play benchmarks. [Spotting Out-of-Character Behavior (ACL 2025 Findings)](https://aclanthology.org/2025.findings-acl.1349/) suggests per-sentence scoring and summing weak signals. Background: [Fanlore: Out of Character](https://fanlore.org/wiki/Out_of_Character).

## If resumed

- Judge a turn together with its 2-3 neighboring lines.
- Sum weak signals across lines instead of flagging single lines (per the ACL 2025 paper).
- Show a low-confidence flag when all reads agree that evidence is thin.
- Accept -a/-ova surname endings, or document `spelling_ignore` for them.
- Test the continuity rules (dead-reappears, timeline order) on a real multi-chapter work.
- Compare against a plain LLM-prompt baseline.
- Any real run needs a writer who consents.
