"""Markdown is rendered only from validated report JSON."""

from __future__ import annotations


def render(report: dict) -> str:
    lines = ["# Story Doctor report", ""]
    lines.append(report.get("summary", ""))
    lines.append("")
    lines.append("## Lens")
    for row in report.get("lens") or []:
        lines.append(f"- {row['rule_id']}: {row['state']} ({row.get('reason', '')})")
    lines.append("")
    lines.append("## Items")
    for item in report.get("items") or []:
        lines.append(
            f"- [{item.get('item_state')}] {item.get('rule_id')}: {item.get('symptom')}"
        )
    lines.append("")
    lines.append(
        "Archive Warnings were not scanned. Whether a warning applies is your call."
    )
    lines.append("")
    return "\n".join(lines)
