# Fanfic Story Doctor Skill – Spec (Draft v0.4.4)

**Status:** Draft v0.4.4, implementation revision
**Owner:** Jon Dubin
**Last updated:** October 18, 2026
**Previous version:** v0.4.3

This amendment adds the Trial 7 voice and spelling contracts. Where it does not speak, v0.4.3 remains in force.

## OOC.VOICE

`drift` means inconsistent with the character's cached early-work profile. It does not mean inconsistent with canon or with a nearby passage. Canon voice enters only through an intake override. Override fields follow the profile rules: intake refuses quotation marks, straight or curly, and rewrite phrasing before any model call. The profile cache holds only the generated profile; overrides are merged when it is used. `intentional_evolution` means the judged passage itself marks the change as deliberate. Character-arc markers stay deferred.

A profile is built from name-tagged turns spread across the chapter range, at least four turns across two chapters and at most sixteen, preferring longer lines. It is cached by work, character, pronouns, model, and contract. A changed sample regenerates it. `--refresh-voice-profiles` regenerates it even when the sample is unchanged. `--reuse-stale-voice-profiles` keeps the cached profile. A rejected profile is retried once and then cached for that same sample; timeouts are not cached. A cached rejection holds only for the profile prompt and sample that produced it. Fields are `register`, `cadence`, `syntax`, `diction`, `range`, and `dialect_or_l2` (dialect or second-language speech). Each is one sentence of at most 200 characters, and the prompt states that limit.

Targets are attributed dialogue turns. Narration is out of scope. Names inside quotation marks are not speakers. Turns of three words or fewer are skipped. One result is emitted per target. Every label needs more than half of the attempted runs. `evidence_strength: thin` counts a concern as `not_enough_evidence`. Any other split is `not_enough_evidence` with `decision: no_majority`.

`CANON.RAILS` keeps the v0.4.3 vote, prompt, and cache identity.

## Names

Nicknames are declared in `names`. `spelling_ignore` lists real near-names that must not become aliases or mentions. Mentions require letter boundaries. A typo is suppressed only when the matching aliases belong to more than one character. An undeclared prefix of at least three characters is a question when it occurs twice or drops at least two characters. A one-character truncation seen once remains a finding outside dialogue. Inside dialogue, a prefix truncation is a nickname question even once, including a one-character cut.

## Review files

`--html` and `--json` are optional and are refused inside the repository. The JSON file includes a `positions` list for each highlightable flag: rule, character, chapter, paragraph id, quote offset and length, label, and agreement. Markdown on stdout remains the default and does not print model-written profile fields. Evidence spans are Unicode code points in normalized paragraph text. The HTML review emits one chapter heading per chapter, starts `j` on the first flag, and puts each flag's read reasons in a `details` element beside that flag.
