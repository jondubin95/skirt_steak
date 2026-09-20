# Project Skills

These skills are keyword-triggered, not always-on and not slash-only. Cursor's agent reads each `SKILL.md` `description` and applies the skill automatically when your message contains the matching keywords below. They are not attached to every message (that would require a Custom Mode), and they don't require typing `/skill-name` (that would require `disable-model-invocation: true`).

| Skill | Trigger keywords |
| --- | --- |
| `handoff-notes` | "handoff", "handoffs" |
| `clarity-concision-editor` | "tighten", "board tone", "cut 20%", "remove jargon", "clarity concision editor", "Polish" gem |
| `paranoid-market-analyst` | "bet", "wager", "moneyline", "trade", "option", "position", "thesis" (directional market claims) |
| `operating-behavior` | implementing, debugging, refactoring, summarizing changes, or pull requests in this repo |

If a skill fires on the wrong message, or never fires when it should, tighten or loosen the keyword list in that skill's `description`. You can also still invoke any skill explicitly with `/skill-name` regardless of these keywords.

`AGENTS.md` is a separate repo guardrail file, not one of these skills.
