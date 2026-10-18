"""Markdown is rendered only from validated report JSON."""

from __future__ import annotations

from collections import Counter

SUMMARIZED_LABELS = ("in_voice", "not_enough_evidence")


def _quote(item: dict) -> str:
    for evidence in item.get("evidence") or []:
        if evidence.get("kind") == "prose" and evidence.get("quote"):
            return evidence["quote"]
    return ""


def _chapter(item: dict) -> str:
    chapter = item.get("chapter")
    return str(chapter) if chapter is not None else "?"


def _voice_lines(notes: list[dict]) -> list[str]:
    """OOC.VOICE notes: one summary line per character for in_voice and
    not_enough_evidence, then each drift/break (or other label) on its own line."""
    lines: list[str] = []
    per_char: dict[str, Counter] = {}
    order: list[str] = []
    for note in notes:
        who = note.get("subject") or "(unknown)"
        if who not in per_char:
            per_char[who] = Counter()
            order.append(who)
        if note.get("label") in SUMMARIZED_LABELS:
            per_char[who][note["label"]] += 1
    for who in order:
        counts = per_char[who]
        if counts:
            parts = ", ".join(f"{label} x{counts[label]}" for label in SUMMARIZED_LABELS if counts[label])
            lines.append(f"- [note] OOC.VOICE {who}: {parts}")
    for note in notes:
        if note.get("label") in SUMMARIZED_LABELS:
            continue
        agreement = note.get("agreement") or ""
        tentative = " (tentative)" if agreement == "low_agreement" else ""
        lines.append(
            f"- [note] OOC.VOICE{tentative} {note.get('subject') or '(unknown)'} "
            f"ch{_chapter(note)} label={note.get('label')} agreement={agreement} "
            f'quote="{_quote(note)}" reason="{note.get("interpretation") or ""}"'
        )
    return lines


def render(report: dict) -> str:
    lines = ["# Story Doctor report", ""]
    lines.append(report.get("summary", ""))
    lines.append("")
    lines.append("## Lens")
    for row in report.get("lens") or []:
        lines.append(f"- {row['rule_id']}: {row['state']} ({row.get('reason', '')})")
    lines.append("")
    lines.append("## Items")
    voice: list[dict] = []
    for item in report.get("items") or []:
        if item.get("rule_id") == "OOC.VOICE" and item.get("item_state") == "note":
            voice.append(item)
            continue
        lines.append(
            f"- [{item.get('item_state')}] {item.get('rule_id')}: {item.get('symptom')}"
        )
    if voice:
        lines.append("")
        lines.append("## Voice notes (info only; agreement is not correctness)")
        lines.extend(_voice_lines(voice))
    profiles = report.get("voice_profiles") or {}
    if profiles:
        lines.append("")
        lines.append("## Voice profiles")
        for entity, profile in profiles.items():
            state = " stale" if profile.get("stale") else ""
            sample = ", ".join(profile.get("sample_paragraph_ids") or [])
            lines.append(
                f"- {entity}: source={profile.get('source')}{state} "
                f"sample_count={profile.get('sample_count')} sample={sample}"
            )
    lines.append("")
    lines.append(
        "Archive Warnings were not scanned. Whether a warning applies is your call."
    )
    lines.append("")
    return "\n".join(lines)
