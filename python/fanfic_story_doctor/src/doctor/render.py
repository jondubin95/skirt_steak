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


BASELINE_LABELS = {"in_voice", "not_enough_evidence"}


def _flagged_chapters(report: dict) -> set[int]:
    chapters = set()
    for item in report.get("items") or []:
        if item.get("item_state") in {"finding", "question", "unverifiable"}:
            for evidence in item.get("evidence") or []:
                if evidence.get("kind") == "prose" and item.get("chapter") is not None:
                    chapters.add(item["chapter"])
        if (
            item.get("rule_id") == "OOC.VOICE"
            and item.get("item_state") == "note"
            and item.get("label") not in BASELINE_LABELS
            and item.get("chapter") is not None
        ):
            chapters.add(item["chapter"])
        if item.get("item_state") in {"finding", "question", "unverifiable"} and item.get(
            "chapter"
        ) is not None:
            chapters.add(item["chapter"])
    return chapters


def _segments(text: str, marks: list[tuple[int, int, str]]) -> list[tuple[str, list[str]]]:
    points = {0, len(text)}
    for start, end, _flag in marks:
        points.add(max(0, min(len(text), start)))
        points.add(max(0, min(len(text), end)))
    ordered = sorted(points)
    pieces = []
    for start, end in zip(ordered, ordered[1:]):
        if start == end:
            continue
        active = [
            flag
            for mark_start, mark_end, flag in marks
            if mark_start <= start and end <= mark_end
        ]
        pieces.append((text[start:end], active))
    return pieces


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _json_for_script(payload: object) -> str:
    import json

    return (
        json.dumps(payload)
        .replace("<", "\\u003c")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_html(report: dict, paragraphs: list) -> str:
    """Self-contained review page. Spans are code points in normalized text."""
    import base64
    import hashlib

    flagged = _flagged_chapters(report)
    by_paragraph: dict[str, list[tuple[int, int, str]]] = {}
    flags = []
    for number, item in enumerate(report.get("items") or [], 1):
        flag_id = f"flag-{number}"
        prose = [
            evidence
            for evidence in item.get("evidence") or []
            if evidence.get("kind") == "prose" and evidence.get("span")
        ]
        if not prose:
            continue
        evidence = prose[0]
        start, end = evidence["span"]
        by_paragraph.setdefault(evidence["paragraph_id"], []).append((start, end, flag_id))
        flags.append(
            {
                "id": flag_id,
                "rule": item.get("rule_id"),
                "state": item.get("item_state"),
                "label": item.get("label"),
                "chapter": item.get("chapter"),
                "symptom": item.get("symptom"),
                "reads": item.get("reads") or [],
            }
        )
    style = (
        "body{font:16px/1.5 Georgia,serif;margin:2rem;}"
        "mark{background:#f6e2a8;}"
        "aside{border-left:3px solid #999;margin:1rem 0;padding-left:1rem;}"
        "nav a{margin-right:1rem;}"
    )
    script = (
        "const flags=[...document.querySelectorAll('[data-flag]')];"
        "let index=0;"
        "document.addEventListener('keydown',(event)=>{"
        "if(event.key!=='j'&&event.key!=='k')return;"
        "if(!flags.length)return;"
        "index=event.key==='j'?Math.min(flags.length-1,index+1):Math.max(0,index-1);"
        "flags[index].scrollIntoView({block:'center'});"
        "});"
    )
    style_hash = "sha256-" + base64.b64encode(hashlib.sha256(style.encode()).digest()).decode()
    script_hash = "sha256-" + base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        f'<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'{style_hash}\'; script-src \'{script_hash}\'">',
        f"<style>{style}</style></head><body>",
        "<h1>Story Doctor report</h1>",
        f"<p>{_escape(report.get('summary') or '')}</p>",
        "<h2>Lens</h2><ul>",
    ]
    for row in report.get("lens") or []:
        parts.append(
            f"<li>{_escape(row['rule_id'])}: {_escape(row['state'])} ({_escape(row.get('reason') or '')})</li>"
        )
    parts.append("</ul><h2>Coverage and questions</h2><ul>")
    for item in report.get("items") or []:
        if item.get("item_state") in {"coverage", "question", "unverifiable"}:
            parts.append(f"<li>{_escape(item.get('symptom') or '')}</li>")
    parts.append("</ul><h2>Voice profiles</h2><ul>")
    for entity, profile in (report.get("voice_profiles") or {}).items():
        sample = ", ".join(profile.get("sample_paragraph_ids") or [])
        parts.append(
            f"<li>{_escape(entity)}: {_escape(str(profile.get('source')))} "
            f"sample_count={profile.get('sample_count')} {_escape(sample)}</li>"
        )
    counts: dict[str, int] = {}
    for item in report.get("items") or []:
        if item.get("label") in BASELINE_LABELS:
            who = str(item.get("subject") or "(unknown)")
            counts[who] = counts.get(who, 0) + 1
    parts.append("</ul><h2>Baseline voice counts</h2><ul>")
    for who, count in counts.items():
        parts.append(f"<li>{_escape(who)}: {count}</li>")
    parts.append('</ul><nav id="flag-index"><h2>Flags</h2>')
    for flag in flags:
        parts.append(
            f'<a href="#{flag["id"]}">{_escape(flag["id"])} {_escape(str(flag["rule"]))}</a>'
        )
    parts.append("</nav>")
    for paragraph in paragraphs:
        if paragraph.chapter not in flagged:
            continue
        parts.append(f"<h2>Chapter {paragraph.chapter}</h2>")
        parts.append(f'<p id="{_escape(paragraph.id)}">')
        for text, active in _segments(paragraph.text, by_paragraph.get(paragraph.id, [])):
            if active:
                parts.append(
                    f'<mark id="{_escape(active[0])}" data-flag="{" ".join(active)}">{_escape(text)}</mark>'
                )
            else:
                parts.append(_escape(text))
        parts.append("</p>")
    for flag in flags:
        reads = "".join(
            f"<li>{_escape(str(read.get('interpretation') or ''))}</li>"
            for read in flag["reads"]
        )
        parts.append(
            f'<aside id="{flag["id"]}-detail"><strong>{_escape(str(flag["rule"]))}</strong> '
            f'{_escape(flag.get("symptom") or "")}<ul>{reads}</ul></aside>'
        )
    parts.append(f'<script type="application/json" id="flags">{_json_for_script(flags)}</script>')
    parts.append(f"<script>{script}</script></body></html>")
    return "".join(parts)
