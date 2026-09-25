"""Semantic minutes JSON: dataclasses, validation, and write-target guards.

This module has no third-party imports so CI can test it with the
standard library alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1
ITEM_KINDS = frozenset(
    {"masthead", "attendance", "section", "presenter", "bullet", "motion", "paragraph"}
)
VERDICTS = frozenset({"passes", "fails"})
BULLET_LEVELS = frozenset({0, 1, 2, 3})

MASTHEAD_FIELDS = frozenset({"kind", "date", "organization", "title"})
ATTENDANCE_FIELDS = frozenset({"kind", "label", "groups", "names"})
GROUP_FIELDS = frozenset({"category", "names"})
SECTION_FIELDS = frozenset({"kind", "title"})
PRESENTER_FIELDS = frozenset({"kind", "text"})
BULLET_FIELDS = frozenset({"kind", "text", "level"})
MOTION_FIELDS = frozenset({"kind", "body", "verdict"})
PARAGRAPH_FIELDS = frozenset({"kind", "text"})
DOCUMENT_FIELDS = frozenset({"schemaVersion", "items"})


class SchemaError(ValueError):
    """Raised when minutes JSON is invalid."""


class WriteGuardError(ValueError):
    """Raised when a destructive write is refused."""


@dataclass(frozen=True)
class AttendanceGroup:
    category: str
    names: tuple[str, ...]


@dataclass(frozen=True)
class MinutesItem:
    kind: str
    date: str | None = None
    organization: str | None = None
    title: str | None = None
    label: str | None = None
    groups: tuple[AttendanceGroup, ...] = ()
    names: tuple[str, ...] = ()
    text: str | None = None
    body: str | None = None
    verdict: str | None = None
    level: int = 0


@dataclass(frozen=True)
class MinutesDocument:
    schema_version: int
    items: tuple[MinutesItem, ...] = field(default_factory=tuple)


def _require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError(f"{label} must be an object")
    return value


def _require_str(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SchemaError(f"{label} must be a non-empty string")
    return value


def _require_str_list(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise SchemaError(f"{label} must be a non-empty list of strings")
    names: list[str] = []
    for i, item in enumerate(value):
        names.append(_require_str(item, f"{label}[{i}]"))
    return tuple(names)


def _reject_unknown(obj: dict[str, Any], allowed: frozenset[str], label: str) -> None:
    extra = set(obj) - allowed
    if extra:
        raise SchemaError(f"{label} has unknown fields: {sorted(extra)}")


def _parse_group(raw: Any, label: str) -> AttendanceGroup:
    obj = _require_dict(raw, label)
    _reject_unknown(obj, GROUP_FIELDS, label)
    return AttendanceGroup(
        category=_require_str(obj.get("category"), f"{label}.category"),
        names=_require_str_list(obj.get("names"), f"{label}.names"),
    )


def _parse_item(raw: Any, index: int) -> MinutesItem:
    label = f"items[{index}]"
    obj = _require_dict(raw, label)
    kind = obj.get("kind")
    if kind not in ITEM_KINDS:
        raise SchemaError(f"{label}.kind must be one of {sorted(ITEM_KINDS)}")

    if kind == "masthead":
        _reject_unknown(obj, MASTHEAD_FIELDS, label)
        return MinutesItem(
            kind=kind,
            date=_require_str(obj.get("date"), f"{label}.date"),
            organization=_require_str(obj.get("organization"), f"{label}.organization"),
            title=_require_str(obj.get("title"), f"{label}.title"),
        )
    if kind == "attendance":
        _reject_unknown(obj, ATTENDANCE_FIELDS, label)
        has_groups = "groups" in obj
        has_names = "names" in obj
        if has_groups == has_names:
            raise SchemaError(f"{label} must have exactly one of groups or names")
        groups: tuple[AttendanceGroup, ...] = ()
        names: tuple[str, ...] = ()
        if has_groups:
            raw_groups = obj.get("groups")
            if not isinstance(raw_groups, list) or not raw_groups:
                raise SchemaError(f"{label}.groups must be a non-empty list")
            groups = tuple(
                _parse_group(group, f"{label}.groups[{i}]")
                for i, group in enumerate(raw_groups)
            )
        else:
            names = _require_str_list(obj.get("names"), f"{label}.names")
        return MinutesItem(
            kind=kind,
            label=_require_str(obj.get("label"), f"{label}.label"),
            groups=groups,
            names=names,
        )
    if kind == "section":
        _reject_unknown(obj, SECTION_FIELDS, label)
        return MinutesItem(kind=kind, title=_require_str(obj.get("title"), f"{label}.title"))
    if kind == "presenter":
        _reject_unknown(obj, PRESENTER_FIELDS, label)
        return MinutesItem(kind=kind, text=_require_str(obj.get("text"), f"{label}.text"))
    if kind == "bullet":
        _reject_unknown(obj, BULLET_FIELDS, label)
        level = obj.get("level", 0)
        if not isinstance(level, int) or level not in BULLET_LEVELS:
            raise SchemaError(f"{label}.level must be one of {sorted(BULLET_LEVELS)}")
        return MinutesItem(
            kind=kind,
            text=_require_str(obj.get("text"), f"{label}.text"),
            level=level,
        )
    if kind == "motion":
        _reject_unknown(obj, MOTION_FIELDS, label)
        verdict = obj.get("verdict")
        if verdict is not None and verdict not in VERDICTS:
            raise SchemaError(f"{label}.verdict must be one of {sorted(VERDICTS)}")
        return MinutesItem(
            kind=kind,
            body=_require_str(obj.get("body"), f"{label}.body"),
            verdict=verdict,
        )
    _reject_unknown(obj, PARAGRAPH_FIELDS, label)
    return MinutesItem(kind=kind, text=_require_str(obj.get("text"), f"{label}.text"))


def load_minutes_document(raw: Any) -> MinutesDocument:
    obj = _require_dict(raw, "document")
    _reject_unknown(obj, DOCUMENT_FIELDS, "document")
    version = obj.get("schemaVersion")
    if version != SCHEMA_VERSION:
        raise SchemaError(f"unsupported schemaVersion: {version!r}")
    items_raw = obj.get("items")
    if not isinstance(items_raw, list) or not items_raw:
        raise SchemaError("items must be a non-empty list")
    items = tuple(_parse_item(item, i) for i, item in enumerate(items_raw))
    return MinutesDocument(schema_version=version, items=items)


def validate_write_guards(
    *,
    write: bool,
    input_tab_id: str,
    output_tab_id: str,
    actual_title: str,
    expected_title: str,
    revision_id: str | None,
) -> None:
    if not write:
        raise WriteGuardError("refusing to write without --write")
    if not input_tab_id or not output_tab_id:
        raise WriteGuardError("input and output tab ids are required")
    if input_tab_id == output_tab_id:
        raise WriteGuardError("input and output tabs resolved to the same tabId")
    if actual_title != expected_title:
        raise WriteGuardError(
            f"document title {actual_title!r} does not match expected {expected_title!r}"
        )
    if not revision_id:
        raise WriteGuardError("missing document revisionId for writeControl")
