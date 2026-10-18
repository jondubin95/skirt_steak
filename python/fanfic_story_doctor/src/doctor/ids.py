"""Paragraph and scene ids. Order is int tuples, not strings."""

from __future__ import annotations

import re

_PARA = re.compile(r"^ch(\d+)\.s(\d+)\.p(\d+)$")
_SCENE = re.compile(r"^ch(\d+)\.s(\d+)$")


def format_paragraph_id(chapter: int, scene: int, paragraph: int) -> str:
    return f"ch{chapter:02d}.s{scene}.p{paragraph}"


def format_scene_id(chapter: int, scene: int) -> str:
    return f"ch{chapter:02d}.s{scene}"


def parse_paragraph_id(value: str) -> tuple[int, int, int]:
    match = _PARA.match(value)
    if not match:
        raise ValueError(f"not a paragraph id: {value}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def parse_scene_id(value: str) -> tuple[int, int]:
    match = _SCENE.match(value)
    if not match:
        raise ValueError(f"not a scene id: {value}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def scene_of(paragraph_id: str) -> str:
    chapter, scene, _paragraph = parse_paragraph_id(paragraph_id)
    return format_scene_id(chapter, scene)


def paragraph_index(paragraph_id: str) -> int:
    return parse_paragraph_id(paragraph_id)[2]


def id_tuple(value: str) -> tuple[int, ...]:
    if _PARA.match(value):
        return parse_paragraph_id(value)
    if _SCENE.match(value):
        return parse_scene_id(value)
    raise ValueError(f"not an id: {value}")


def compare_ids(left: str, right: str) -> int:
    """Return -1, 0, or 1. Chapter 100 sorts after chapter 99. Scene 2 sorts before scene 10."""
    a = id_tuple(left)
    b = id_tuple(right)
    width = max(len(a), len(b))
    a = a + (0,) * (width - len(a))
    b = b + (0,) * (width - len(b))
    if a < b:
        return -1
    if a > b:
        return 1
    return 0
