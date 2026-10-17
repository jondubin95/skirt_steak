"""Alias-exact mentions and temporal markers. Tier A1. No spaCy."""

from __future__ import annotations

import re

from doctor.ids import scene_of

_MARKER = re.compile(
    r"\b(three years earlier|years earlier|years later|the next day|meanwhile|earlier that|flashback)\b",
    re.IGNORECASE,
)


def detect_mentions(paragraphs: list, alias_map: dict[str, str]) -> list[dict]:
    """alias_map is surface -> entity id. Exact match, case-sensitive first."""
    notes = []
    surfaces = sorted(alias_map, key=len, reverse=True)
    for paragraph in paragraphs:
        taken: list[tuple[int, int]] = []
        for surface in surfaces:
            start = 0
            while True:
                at = paragraph.text.find(surface, start)
                if at < 0:
                    break
                end = at + len(surface)
                if any(not (end <= a or at >= b) for a, b in taken):
                    start = end
                    continue
                taken.append((at, end))
                notes.append(
                    {
                        "id": f"m-{paragraph.id}-{alias_map[surface]}-{at}",
                        "entity": alias_map[surface],
                        "paragraph": paragraph.id,
                        "paragraph_hash": paragraph.content_hash,
                        "span": [at, end],
                        "surface": surface,
                        "mode": None,
                        "mode_status": "proposed",
                        "stale": False,
                    }
                )
                start = end
    return notes


def detect_markers(paragraphs: list) -> list[str]:
    """Scene ids that contain an unconfirmed temporal marker."""
    scenes = []
    for paragraph in paragraphs:
        if _MARKER.search(paragraph.text):
            scene = scene_of(paragraph.id)
            if scene not in scenes:
                scenes.append(scene)
    return scenes


def alias_map_from_facts(facts: list[dict]) -> dict[str, str]:
    mapping = {}
    for fact in facts:
        if fact.get("predicate") == "alias" and fact.get("status") == "confirmed":
            mapping[str(fact["object"])] = str(fact["subject"])
    return mapping
