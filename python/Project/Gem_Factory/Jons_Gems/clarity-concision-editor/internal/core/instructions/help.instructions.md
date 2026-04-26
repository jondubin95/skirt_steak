==============================================

INSTRUCTION FOR AGENT: It is CRITICAL that you retain ALL codefence/codeblock formatting, preserve markdown structure, and keep all HTTP links exactly as provided.

==============================================

# Polish - Clarity & Concision Editor Help

## Available Commands

- **`/tighten`** — Tighten for clarity and concision while preserving meaning
- **`/board-tone`** — Rewrite for board-application tone (direct, confident, non-fluffy)
- **`/cut-20-percent`** — Reduce length by ~20% (or to a target cap)
- **`/remove-jargon`** — Replace jargon with plain English (keep necessary terms)
- **`/help`** — View this help message

---

## What to Provide (Best Inputs)

Paste:

1) **Your text** (raw is fine)
2) **Constraints** (any that apply):
   - Target audience (which board? who reads it?)
   - Length constraint (word cap / character cap / “make it shorter”)
   - Must-keep points (names, numbers, achievements, claims)
   - Tone constraints (“confident but humble”, “warm but direct”, etc.)
3) **Optional**: 1–2 examples of the tone you like

---

## Output Format (Default)

Unless you ask otherwise, respond with:

- **Rewritten Version** (ready to paste)
- **Edits Made** (short bullets)
- **Questions** (only if needed to avoid changing meaning)

---

## Gem Information

**Version:** _{{ clarity-concision-editor.package.gdoc | version }}_

**Recent Updates:**

_{{ clarity-concision-editor.package.gdoc | release-notes.[version] }}_
