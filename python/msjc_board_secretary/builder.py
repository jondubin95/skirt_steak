"""Convert semantic minutes into Google Docs batchUpdate requests.

Pure Python: no Google client imports. All text offsets are UTF-16 code units.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .schema import MinutesDocument, MinutesItem

HEADING_TEXT_STYLE = {
    "bold": True,
    "fontSize": {"magnitude": 13, "unit": "PT"},
    "weightedFontFamily": {"fontFamily": "Arial", "weight": 400},
    "foregroundColor": {"color": {"rgbColor": {"red": 0, "green": 0, "blue": 0}}},
}
HEADING_TEXT_FIELDS = "bold,fontSize,weightedFontFamily,foregroundColor"
BODY_TEXT_STYLE = {"weightedFontFamily": {"fontFamily": "Arial", "weight": 400}}
BODY_TEXT_FIELDS = "weightedFontFamily"
VERDICT_TEXT = {"passes": "Motion Passes.", "fails": "Motion Fails."}


@dataclass
class Span:
    start: int
    end: int
    bold: bool = False
    italic: bool = False
    underline: bool = False
    size: float | None = None


@dataclass
class Paragraph:
    text: str
    kind: str
    level: int = 0
    spans: list[Span] = field(default_factory=list)


def docs_len(text: str) -> int:
    """Google Docs index width: UTF-16 code units."""
    return len(text.encode("utf-16-le")) // 2


def para(kind: str, text: str, level: int = 0, spans: list[Span] | None = None) -> Paragraph:
    return Paragraph(text=text, kind=kind, level=level, spans=spans or [])


def motion_paragraph(body: str, verdict: str | None = None) -> Paragraph:
    prefix = "Motion: "
    text = prefix + body
    verdict_text = VERDICT_TEXT.get(verdict or "")
    if verdict_text:
        text = f"{text} {verdict_text}"
    spans = [
        Span(0, docs_len(text), underline=True),
        Span(0, docs_len("Motion"), bold=True),
    ]
    if verdict_text:
        spans.append(Span(docs_len(text) - docs_len(verdict_text), docs_len(text), bold=True))
    return para("motion", text, spans=spans)


def _masthead_paragraphs(item: MinutesItem) -> list[Paragraph]:
    title = f"{item.organization}\v{item.title}"
    break_at = docs_len(item.organization or "")
    return [
        para("date", item.date or ""),
        para(
            "title",
            title,
            spans=[
                Span(0, break_at, bold=True, underline=True, size=14),
                Span(break_at + 1, docs_len(title), underline=True, size=12),
            ],
        ),
    ]


def _attendance_paragraphs(item: MinutesItem) -> list[Paragraph]:
    out = [para("date", item.label or "In attendance:")]
    if item.groups:
        for group in item.groups:
            label = f"{group.category}: "
            names = ", ".join(group.names)
            text = label + names
            out.append(
                para(
                    "bullet",
                    text,
                    spans=[
                        Span(0, docs_len(label), bold=True, size=12),
                        Span(docs_len(label), docs_len(text), size=12),
                    ],
                )
            )
        return out
    if item.names:
        out.append(para("bullet", ", ".join(item.names)))
    return out


def document_to_paragraphs(document: MinutesDocument) -> list[Paragraph]:
    minutes: list[Paragraph] = []
    for item in document.items:
        if item.kind == "masthead":
            minutes.extend(_masthead_paragraphs(item))
        elif item.kind == "attendance":
            minutes.extend(_attendance_paragraphs(item))
        elif item.kind == "section":
            minutes.append(para("h3", item.title or ""))
        elif item.kind == "presenter":
            minutes.append(para("presenter", item.text or ""))
        elif item.kind == "bullet":
            minutes.append(para("bullet", item.text or "", item.level))
        elif item.kind == "motion":
            minutes.append(motion_paragraph(item.body or "", item.verdict))
        else:
            minutes.append(para("normal", item.text or ""))

    spaced: list[Paragraph] = []
    for item in minutes:
        if item.kind == "h3":
            spaced.append(para("blank", ""))
        spaced.append(item)
    return spaced


def preflight_paragraphs(paragraphs: list[Paragraph]) -> None:
    if not paragraphs:
        raise ValueError("minutes produced no paragraphs")
    nonempty = [p for p in paragraphs if p.text.strip() or p.kind == "blank"]
    if not nonempty:
        raise ValueError("minutes produced no usable paragraphs")
    for i, paragraph in enumerate(paragraphs):
        if paragraph.kind != "blank" and docs_len(paragraph.text) == 0:
            raise ValueError(f"paragraph {i} ({paragraph.kind}) has empty text")
        for span in paragraph.spans:
            width = docs_len(paragraph.text)
            if span.start < 0 or span.end < span.start or span.end > width:
                raise ValueError(f"paragraph {i} has a span outside its UTF-16 width")


def compose(
    paragraphs: list[Paragraph],
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    chunks: list[str] = []
    meta: list[dict[str, Any]] = []
    text_spans: list[dict[str, Any]] = []
    cursor = 0
    for p in paragraphs:
        body = p.text
        start = cursor
        end = start + docs_len(body)
        chunks.append(body + "\n")
        meta.append({"kind": p.kind, "start": start, "end": end + 1, "level": p.level})
        for span in p.spans:
            text_spans.append(
                {
                    "start": start + span.start,
                    "end": start + span.end,
                    "bold": span.bold,
                    "italic": span.italic,
                    "underline": span.underline,
                    "size": span.size,
                }
            )
        if p.kind == "presenter":
            text_spans.append({"start": start, "end": end, "bold": False, "italic": True})
        cursor = end + 1
    return "".join(chunks), meta, text_spans


def requests_for_replace(
    tab_id: str, end_index: int, paragraphs: list[Paragraph]
) -> list[dict[str, Any]]:
    text, meta, spans = compose(paragraphs)
    origin = 1
    reqs: list[dict[str, Any]] = []
    if end_index > 2:
        reqs.append(
            {
                "deleteContentRange": {
                    "range": {"tabId": tab_id, "startIndex": 1, "endIndex": end_index - 1}
                }
            }
        )
    reqs.append({"insertText": {"location": {"tabId": tab_id, "index": origin}, "text": text}})
    for item in meta:
        start = origin + item["start"]
        end = origin + item["end"]
        if item["kind"] == "h3":
            reqs.append(
                {
                    "updateParagraphStyle": {
                        "range": {"tabId": tab_id, "startIndex": start, "endIndex": end},
                        "paragraphStyle": {
                            "namedStyleType": "HEADING_3",
                            "spaceAbove": {"magnitude": 0, "unit": "PT"},
                            "spaceBelow": {"magnitude": 0, "unit": "PT"},
                        },
                        "fields": "namedStyleType,spaceAbove,spaceBelow",
                    }
                }
            )
        elif item["kind"] == "motion":
            reqs.append(
                {
                    "updateParagraphStyle": {
                        "range": {"tabId": tab_id, "startIndex": start, "endIndex": end},
                        "paragraphStyle": {
                            "namedStyleType": "NORMAL_TEXT",
                            "spaceBelow": {"magnitude": 12, "unit": "PT"},
                            "indentEnd": {"magnitude": 30, "unit": "PT"},
                        },
                        "fields": "namedStyleType,spaceBelow,indentEnd",
                    }
                }
            )
        elif item["kind"] == "title":
            reqs.append(
                {
                    "updateParagraphStyle": {
                        "range": {"tabId": tab_id, "startIndex": start, "endIndex": end},
                        "paragraphStyle": {"namedStyleType": "NORMAL_TEXT", "alignment": "CENTER"},
                        "fields": "namedStyleType,alignment",
                    }
                }
            )
        elif item["kind"] == "normal":
            reqs.append(
                {
                    "updateParagraphStyle": {
                        "range": {"tabId": tab_id, "startIndex": start, "endIndex": end},
                        "paragraphStyle": {
                            "namedStyleType": "NORMAL_TEXT",
                            "spaceBelow": {"magnitude": 12, "unit": "PT"},
                        },
                        "fields": "namedStyleType,spaceBelow",
                    }
                }
            )
        elif item["kind"] in {"presenter", "bullet", "date", "blank"}:
            reqs.append(
                {
                    "updateParagraphStyle": {
                        "range": {"tabId": tab_id, "startIndex": start, "endIndex": end},
                        "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                        "fields": "namedStyleType",
                    }
                }
            )
    if meta:
        reqs.append(
            {
                "createParagraphBullets": {
                    "range": {
                        "tabId": tab_id,
                        "startIndex": origin,
                        "endIndex": origin + meta[-1]["end"],
                    },
                    "bulletPreset": "NUMBERED_UPPERROMAN_UPPERALPHA_DECIMAL",
                }
            }
        )
    for item in meta:
        if item["kind"] == "h3":
            continue
        reqs.append(
            {
                "deleteParagraphBullets": {
                    "range": {
                        "tabId": tab_id,
                        "startIndex": origin + item["start"],
                        "endIndex": origin + item["end"],
                    }
                }
            }
        )
    for item in meta:
        start = origin + item["start"]
        end = origin + item["end"]
        if item["kind"] == "h3":
            reqs.append(
                {
                    "updateTextStyle": {
                        "range": {"tabId": tab_id, "startIndex": start, "endIndex": end - 1},
                        "textStyle": HEADING_TEXT_STYLE,
                        "fields": HEADING_TEXT_FIELDS,
                    }
                }
            )
        elif item["kind"] == "date":
            reqs.append(
                {
                    "updateTextStyle": {
                        "range": {"tabId": tab_id, "startIndex": start, "endIndex": end - 1},
                        "textStyle": {"fontSize": {"magnitude": 12, "unit": "PT"}},
                        "fields": "fontSize",
                    }
                }
            )
        elif item["kind"] == "bullet":
            reqs.append(
                {
                    "updateTextStyle": {
                        "range": {"tabId": tab_id, "startIndex": start, "endIndex": end - 1},
                        "textStyle": BODY_TEXT_STYLE,
                        "fields": BODY_TEXT_FIELDS,
                    }
                }
            )
    for span in spans:
        fields = []
        style: dict[str, Any] = {}
        if span.get("bold"):
            style["bold"] = True
            fields.append("bold")
        if span.get("italic"):
            style["italic"] = True
            fields.append("italic")
        if span.get("underline"):
            style["underline"] = True
            fields.append("underline")
        if span.get("size"):
            style["fontSize"] = {"magnitude": span["size"], "unit": "PT"}
            fields.append("fontSize")
        if not fields:
            continue
        reqs.append(
            {
                "updateTextStyle": {
                    "range": {
                        "tabId": tab_id,
                        "startIndex": origin + span["start"],
                        "endIndex": origin + span["end"],
                    },
                    "textStyle": style,
                    "fields": ",".join(fields),
                }
            }
        )
    return reqs


def paragraph_text(para_el: dict[str, Any]) -> str:
    return "".join(
        (el.get("textRun") or {}).get("content", "") for el in para_el.get("elements") or []
    )


def _para_text(el: dict[str, Any]) -> str:
    para_el = el.get("paragraph") or {}
    return "".join(
        (e.get("textRun") or {}).get("content", "") for e in para_el.get("elements") or []
    ).strip()


def nesting_requests(
    tab_id: str, tab: dict[str, Any], paragraphs: list[Paragraph]
) -> list[dict[str, Any]]:
    content = (tab.get("documentTab") or {}).get("body", {}).get("content") or []
    live = [el for el in content if el.get("paragraph") and _para_text(el)]
    planned_text = [p for p in paragraphs if p.text.strip()]
    if len(live) != len(planned_text):
        raise ValueError(
            f"Paragraph count mismatch after write: doc {len(live)} vs plan {len(planned_text)}"
        )
    ops: list[tuple[int, str]] = []
    run_open = False
    for el, planned in zip(live, planned_text):
        if planned.kind != "bullet":
            run_open = False
            continue
        if not run_open:
            ops.append((int(el["startIndex"]), "\n"))
            run_open = True
        if planned.level > 0:
            ops.append((int(el["startIndex"]), "\t" * planned.level))
    reqs: list[dict[str, Any]] = []
    for index, text in sorted(ops, key=lambda item: (-item[0], 0 if item[1].startswith("\t") else 1)):
        reqs.append({"insertText": {"location": {"tabId": tab_id, "index": index}, "text": text}})
    return reqs


def disc_requests(
    tab_id: str, tab: dict[str, Any], paragraphs: list[Paragraph]
) -> list[dict[str, Any]]:
    content = (tab.get("documentTab") or {}).get("body", {}).get("content") or []
    live = [el for el in content if el.get("paragraph")]
    nonempty = [el for el in live if _para_text(el)]
    planned_text = [p for p in paragraphs if p.text.strip()]
    if len(nonempty) != len(planned_text):
        raise ValueError(
            f"Paragraph count mismatch before discs: doc {len(nonempty)} vs plan {len(planned_text)}"
        )
    wanted = {id(el) for el, planned in zip(nonempty, planned_text) if planned.kind == "bullet"}
    reqs: list[dict[str, Any]] = []
    creates: list[dict[str, Any]] = []
    run: list[dict[str, Any]] = []

    def close_run() -> None:
        if not run:
            return
        creates.append(
            {
                "createParagraphBullets": {
                    "range": {
                        "tabId": tab_id,
                        "startIndex": int(run[0]["startIndex"]),
                        "endIndex": int(run[-1]["endIndex"]),
                    },
                    "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
                }
            }
        )
        run.clear()

    prev_empty: dict[str, Any] | None = None
    for el in live:
        if not _para_text(el):
            close_run()
            prev_empty = el
            continue
        if id(el) in wanted:
            if not run and prev_empty is not None:
                reqs.append(
                    {
                        "deleteParagraphBullets": {
                            "range": {
                                "tabId": tab_id,
                                "startIndex": int(prev_empty["startIndex"]),
                                "endIndex": int(prev_empty["endIndex"]),
                            }
                        }
                    }
                )
            run.append(el)
        else:
            close_run()
        prev_empty = None
    close_run()
    reqs.extend(reversed(creates))
    return reqs


def blank_paragraph_requests(tab_id: str, tab: dict[str, Any]) -> list[dict[str, Any]]:
    content = (tab.get("documentTab") or {}).get("body", {}).get("content") or []
    paras = [el for el in content if el.get("paragraph")]
    reqs: list[dict[str, Any]] = []
    for i, el in enumerate(paras[:-1]):
        if _para_text(el):
            continue
        nxt = paras[i + 1].get("paragraph") or {}
        if (nxt.get("paragraphStyle") or {}).get("namedStyleType") == "HEADING_3":
            continue
        if not nxt.get("bullet"):
            continue
        reqs.append(
            {
                "deleteContentRange": {
                    "range": {
                        "tabId": tab_id,
                        "startIndex": int(el["startIndex"]),
                        "endIndex": int(el["endIndex"]),
                    }
                }
            }
        )
    reqs.reverse()
    return reqs


def strip_spilled_bullets(tab_id: str, tab: dict[str, Any]) -> list[dict[str, Any]]:
    reqs: list[dict[str, Any]] = []
    content = (tab.get("documentTab") or {}).get("body", {}).get("content") or []
    for el in content:
        para_el = el.get("paragraph")
        if not para_el or not para_el.get("bullet"):
            continue
        text = paragraph_text(para_el).strip()
        style = (para_el.get("paragraphStyle") or {}).get("namedStyleType")
        if style == "HEADING_3":
            continue
        is_motion = text.startswith("Motion:")
        is_none = text == "None."
        if not (is_motion or is_none):
            continue
        start = int(el["startIndex"])
        end = int(el["endIndex"])
        reqs.append(
            {
                "deleteParagraphBullets": {
                    "range": {"tabId": tab_id, "startIndex": start, "endIndex": end}
                }
            }
        )
        if is_motion:
            reqs.append(
                {
                    "updateParagraphStyle": {
                        "range": {"tabId": tab_id, "startIndex": start, "endIndex": end},
                        "paragraphStyle": {
                            "namedStyleType": "NORMAL_TEXT",
                            "spaceBelow": {"magnitude": 12, "unit": "PT"},
                            "indentEnd": {"magnitude": 30, "unit": "PT"},
                        },
                        "fields": "namedStyleType,spaceBelow,indentEnd",
                    }
                }
            )
    return reqs


def attach_write_control(body: dict[str, Any], revision_id: str) -> dict[str, Any]:
    if not revision_id:
        raise ValueError("revisionId is required for writeControl")
    payload = dict(body)
    payload["writeControl"] = {"requiredRevisionId": revision_id}
    return payload
