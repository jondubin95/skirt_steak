# Fanfic Story Doctor Skill – Spec (Draft v0.4.4)

**Status:** Draft v0.4.4, implementation revision
**Owner:** Jon Dubin
**Last updated:** October 18, 2026
**Previous version:** v0.4.3

This amendment adds the Trial 7 voice and spelling contracts. Where it does not speak, v0.4.3 remains in force.

## OOC.VOICE

`drift` means inconsistent with the character's cached early-work profile. It does not mean inconsistent with canon or with a nearby passage. Canon voice enters only through an intake override. Override fields follow the profile rules: intake refuses quotation marks, straight or curly, and rewrite phrasing before any model call. The profile cache holds only the generated profile; overrides are merged when it is used. `intentional_evolution` means the judged passage itself marks the change as deliberate. Character-arc markers stay deferred.

A profile is built once from the earliest name-tagged turns, at least four turns across two chapters and at most eight, then cached by work, character, pronouns, model, and contract. Appending chapters does not regenerate it. `--refresh-voice-profiles` does. A rejected profile is retried once and then cached; timeouts are not cached.

Targets are attributed dialogue turns. Narration is out of scope. Names inside quotation marks are not speakers. Turns of three words or fewer are skipped. One result is emitted per target. Every label needs more than half of the attempted runs. `evidence_strength: thin` counts a concern as `not_enough_evidence`. Any other split is `not_enough_evidence` with `decision: no_majority`.

`CANON.RAILS` keeps the v0.4.3 vote, prompt, and cache identity.

## Names

Nicknames are declared in `names`. `spelling_ignore` lists real near-names that must not become aliases or mentions. Mentions require letter boundaries. A typo is suppressed only when the matching aliases belong to more than one character. An undeclared prefix of at least three characters is a question when it occurs twice or drops at least two characters. A one-character truncation seen once remains a finding.
