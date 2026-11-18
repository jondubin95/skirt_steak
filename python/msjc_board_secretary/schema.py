"""Semantic minutes JSON: dataclasses, validation, and write-target guards.

This module has no third-party imports so CI can test it with the
standard library alone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1
ITEM_KINDS = frozenset(
    {"masthead", "attendance", "section", "presenter", "bullet", "motion", "paragraph"}
)
VERDICTS = frozenset({"passes", "fails"})
_SECONDER = re.compile(r"(?i)\b(?:seconds|seconded)\b")
# "seconded" and "nobody" are included. "Jordan Hale seconds" does not match:
# these phrases all require a negation.
_NO_SECOND_OR_VOTE = re.compile(
    r"(?i)\bno\s+(?:one\s+|body\s+)?second(?:s|ed)?\b"
    r"|\bnobody\s+second(?:s|ed)?\b"
    r"|\bnever\s+seconded\b"
    r"|\bwithout\s+a\s+second\b"
    r"|\black\s+of\s+a\s+second\b"
    r"|\bnot\s+voted\b"
    r"|\bno\s+vote\b"
)
# "motion fails" and "defeated" record a vote only when the body does not
# also say the motion died for lack of a second. Yeas, nays, "voted down",
# and "vote failed" are an explicit vote either way.
_EXPLICIT_VOTE = re.compile(
    r"(?i)\b(?:voted\s+down|vote\s+failed)\b|\b(?:nay|nays|yea|yeas)\b"
)
_RECORDED_VOTE = re.compile(
    r"(?i)\b(?:voted\s+down|vote\s+failed|motion\s+failed|motion\s+fails|defeated)\b"
    r"|\b(?:nay|nays|yea|yeas)\b"
)
BULLET_LEVELS = frozenset({0, 1, 2, 3})

MASTHEAD_FIELDS = frozenset({"kind", "date", "organization", "title"})
ATTENDANCE_FIELDS = frozenset({"kind", "label", "groups", "names"})
GROUP_FIELDS = frozenset({"category", "names"})
SECTION_FIELDS = frozenset({"kind", "title"})
PRESENTER_FIELDS = frozenset({"kind", "text"})
BULLET_FIELDS = frozenset({"kind", "text", "level"})
MOTION_FIELDS = frozenset({"kind", "body", "verdict"})
PARAGRAPH_FIELDS = frozenset({"kind", "text", "italic"})
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
    italic: bool = False


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


def motion_verdict_is_earned(body: str) -> bool:
    """True when `passes` or `fails` records a seconded motion or a vote.

    "Motion Fails." is the board's line for a motion that was voted down.
    A body with no seconder and no vote, including "No second; not voted"
    and "No one seconded.", is not that line. A lack-of-second phrase is
    not itself a vote, so "motion fails" and "defeated" do not earn a
    verdict while one is present.
    """
    if _NO_SECOND_OR_VOTE.search(body) and not _EXPLICIT_VOTE.search(body):
        return False
    return _SECONDER.search(body) is not None or _RECORDED_VOTE.search(body) is not None


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
        body = _require_str(obj.get("body"), f"{label}.body")
        if verdict is not None and not motion_verdict_is_earned(body):
            raise SchemaError(
                f"{label}.verdict {verdict} needs a seconder or a recorded vote; "
                "a motion with no seconder and no vote has no verdict"
            )
        return MinutesItem(
            kind=kind,
            body=body,
            verdict=verdict,
        )
    _reject_unknown(obj, PARAGRAPH_FIELDS, label)
    italic = obj.get("italic", False)
    if not isinstance(italic, bool):
        raise SchemaError(f"{label}.italic must be a boolean")
    return MinutesItem(
        kind=kind,
        text=_require_str(obj.get("text"), f"{label}.text"),
        italic=italic,
    )


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


def validate_target_identity(
    *,
    actual_title: str,
    expected_title: str,
    actual_output_tab: str,
    expected_output_tab: str,
    revision_id: str | None,
) -> None:
    """The live document title and the live output tab must both match exactly."""
    if actual_title != expected_title:
        raise WriteGuardError(
            f"document title {actual_title!r} does not match expected {expected_title!r}"
        )
    if actual_output_tab != expected_output_tab:
        raise WriteGuardError(
            f"output tab {actual_output_tab!r} does not match expected {expected_output_tab!r}"
        )
    if not revision_id:
        raise WriteGuardError("missing document revisionId for writeControl")


def validate_write_guards(
    *,
    write: bool,
    input_tab_id: str,
    output_tab_id: str,
    actual_title: str,
    expected_title: str,
    actual_output_tab: str,
    expected_output_tab: str,
    revision_id: str | None,
) -> None:
    if not write:
        raise WriteGuardError("refusing to write without --write")
    if not input_tab_id or not output_tab_id:
        raise WriteGuardError("input and output tab ids are required")
    if input_tab_id == output_tab_id:
        raise WriteGuardError("input and output tabs resolved to the same tabId")
    validate_target_identity(
        actual_title=actual_title,
        expected_title=expected_title,
        actual_output_tab=actual_output_tab,
        expected_output_tab=expected_output_tab,
        revision_id=revision_id,
    )


_SPEAKING_VERBS = (
    "added",
    "adds",
    "agreed",
    "agrees",
    "announced",
    "announces",
    "answered",
    "answers",
    "asked",
    "asks",
    "commented",
    "comments",
    "confirmed",
    "confirms",
    "described",
    "describes",
    "explained",
    "explains",
    "mentioned",
    "mentions",
    "moved",
    "moves",
    "noted",
    "notes",
    "offered",
    "offers",
    "presented",
    "presents",
    "presenting",
    "proposed",
    "proposes",
    "remarked",
    "remarks",
    "replied",
    "replies",
    "reported",
    "reports",
    "said",
    "says",
    "seconded",
    "seconding",
    "seconds",
    "shared",
    "shares",
    "stated",
    "states",
    "suggested",
    "suggests",
    "thanked",
    "thanks",
    "told",
    "tells",
)
_SPEAKING_VERB = re.compile(
    r"(?:\s*\.?\s+|,\s+who\s+)(?:"
    + "|".join(sorted(_SPEAKING_VERBS, key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)
_PRESENTED_BY = re.compile(r"(?i)\bpresented\s+by\s+$")
# A capital token means the roster name is only the start of a longer name
# ("Alex" inside "Alex Rivera" or "Alex Rivera Jr.").
_NAME_CONTINUATION = re.compile(r"\s+[A-Z][A-Za-z'.-]*")
_ABSENCE_CATEGORIES = frozenset(
    {"not in attendance", "absent", "not present", "regrets"}
)
_ABSENCE_TRAILING_PUNCTUATION = ".:;,–—-"
# A name character is a letter (including non-ASCII), a digit, or a hyphen.
# "Ann" is not the end of "Jo-Ann" or "key2Ann" or "JoséAnn".
_NAME_CHAR = r"(?:[^\W_]|-)"
_POSSESSIVE_MARK = frozenset({"'", "\u2019"})


def _absence_category(category: str) -> str:
    return category.strip().rstrip(_ABSENCE_TRAILING_PUNCTUATION).strip().casefold()


def _absent_names(document: MinutesDocument) -> tuple[str, ...]:
    names: list[str] = []
    for item in document.items:
        if item.kind != "attendance":
            continue
        for group in item.groups:
            if _absence_category(group.category) in _ABSENCE_CATEGORIES:
                names.extend(group.names)
    return tuple(names)


def _name_spans(name: str, text: str) -> list[tuple[int, int]]:
    pattern = re.compile(
        rf"(?i)(?<!{_NAME_CHAR}){re.escape(name)}(?!{_NAME_CHAR})"
    )
    return [(match.start(), match.end()) for match in pattern.finditer(text)]


def _speaking_credit(name: str, text: str) -> bool:
    """True when `name` itself speaks, presents, moves, or seconds.

    The name must be a whole word, and it must not be the prefix of a longer
    name. "Ann" does not match "Joann", "Jo-Ann", or "key2Ann". "Alex" does
    not match "Alex Rivera Jr." A possessive ("Taylor Morgan's") is a mention.
    A comma credits the name only in ", who <verb>". "Taylor Morgan, the
    treasurer, said" is discussion.
    """
    for start, end in _name_spans(name, text):
        if _NAME_CONTINUATION.match(text, end):
            continue
        if end < len(text) and text[end] in _POSSESSIVE_MARK:
            continue
        if _PRESENTED_BY.search(text[:start]):
            return True
        if _SPEAKING_VERB.match(text, end):
            return True
    return False


def absent_speaker_conflicts(document: MinutesDocument) -> tuple[str, ...]:
    """Names marked absent who are credited with a speaking part.

    Absence labels are "Not in attendance", "Absent", "Not present", and
    "Regrets", ignoring trailing punctuation such as "." or "-". A mention
    that does not use a speaking, presenting, moving, or seconding verb, and
    is not "Presented by", is discussion, and it is allowed.
    """
    texts: list[str] = []
    for item in document.items:
        if item.kind in {"presenter", "bullet", "paragraph"} and item.text:
            texts.append(item.text)
        elif item.kind == "motion" and item.body:
            texts.append(item.body)
    conflicts: list[str] = []
    for name in _absent_names(document):
        if any(_speaking_credit(name, text) for text in texts):
            conflicts.append(name)
    return tuple(conflicts)


_PRESENTER_LINE = re.compile(r"^Presented by \S.*\.$")
# A markdown heading is a leading "#", not a hash later in the title ("Item #4").
_MARKDOWN_HEADING = re.compile(r"^\s{0,3}#")
# A typed Roman heading is an uppercase numeral token followed by "." or ")",
# as in "II. Accept Minutes". Lowercase "iv." is title text. The token is not
# split on apostrophes, so "D'var Torah" is a title. A year such as
# "2027 Membership Pricing" is title text, not a heading number.
# In a section title the token may sit after punctuation ("(II." or "[II.").
# In a replacement the token counts only at the start of the phrase, because
# that is the only place a heading marker takes effect.
_ROMAN_HEADING_TOKEN = re.compile(r"(?<![A-Za-z])([IVXLCDM]+)(?=[.)])")
_ROMAN_HEADING_AT_START = re.compile(r"^([IVXLCDM]+)(?=[.)])")
_ROMAN_VALUE = re.compile(r"^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$")
_PLACEHOLDER_XXX = re.compile(r"\bXXX\b", re.IGNORECASE)
_CLOSING_SECTIONS = ("Old Business", "New Business", "Adjournment")
_ATTENDANCE_LABEL = "In attendance:"
# The empty closing section is a paragraph whose entire text is "None.".
# Leading and trailing spaces are a different paragraph. Do not strip here.
# strip_spilled_bullets strips Docs paragraph text before it calls this.
_EMPTY_SECTION_MARKER = "None."


def _item_strings(item: MinutesItem) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for label, value in (
        ("date", item.date),
        ("organization", item.organization),
        ("title", item.title),
        ("label", item.label),
        ("text", item.text),
        ("body", item.body),
    ):
        if value:
            found.append((label, value))
    for group in item.groups:
        found.append(("category", group.category))
        found.extend(("name", name) for name in group.names)
    found.extend(("name", name) for name in item.names)
    return found


def _section_bodies(items: tuple[MinutesItem, ...]) -> list[tuple[MinutesItem, tuple[MinutesItem, ...]]]:
    indexes = [i for i, item in enumerate(items) if item.kind == "section"]
    bodies: list[tuple[MinutesItem, tuple[MinutesItem, ...]]] = []
    for position, index in enumerate(indexes):
        end = indexes[position + 1] if position + 1 < len(indexes) else len(items)
        bodies.append((items[index], items[index + 1 : end]))
    return bodies


def _roman_heading_token(title: str, pattern: re.Pattern[str]) -> str | None:
    for match in pattern.finditer(title):
        token = match.group(1)
        if _ROMAN_VALUE.fullmatch(token):
            return token
    return None


def is_empty_section_paragraph(text: str) -> bool:
    """True only when the whole paragraph is the empty-section marker.

    Spaces stay part of the text, so `` None.`` and ``None. `` are not the
    marker. A sentence that contains ``None.`` is not the marker either.
    """
    return text == _EMPTY_SECTION_MARKER


def _closing_section_errors(document: MinutesDocument) -> list[str]:
    bodies = _section_bodies(document.items)
    titles = tuple((section.title or "") for section, _body in bodies)
    if len(titles) < len(_CLOSING_SECTIONS) or titles[-3:] != _CLOSING_SECTIONS:
        expected = ", ".join(_CLOSING_SECTIONS)
        return [f"closing sections must be {expected}"]
    errors: list[str] = []
    for section, body in bodies[-3:]:
        title = section.title or ""
        content = list(body)
        if (
            len(content) == 1
            and content[0].kind == "paragraph"
            and (content[0].text or "").strip() == _EMPTY_SECTION_MARKER
            and not is_empty_section_paragraph(content[0].text or "")
        ):
            errors.append(f"{title} empty-section marker has leading/trailing whitespace")
            continue
        only_empty = (
            len(content) == 1
            and content[0].kind == "paragraph"
            and is_empty_section_paragraph(content[0].text or "")
        )
        if only_empty:
            continue
        has_empty_line = any(
            item.kind == "paragraph" and is_empty_section_paragraph(item.text or "")
            for item in content
        )
        if not content:
            errors.append(f"{title} is empty; the body must be the paragraph None.")
        elif has_empty_line:
            errors.append(f"{title} has None. alongside other text")
    return errors


def _placeholder_errors(value: str, location: str) -> list[str]:
    found: list[str] = []
    if "___" in value:
        found.append(f"placeholder ___ in {location}")
    if _PLACEHOLDER_XXX.search(value):
        found.append(f"placeholder XXX in {location}")
    return found


def _heading_marker_errors(
    value: str, location: str, roman_pattern: re.Pattern[str]
) -> list[str]:
    found: list[str] = []
    if _MARKDOWN_HEADING.search(value):
        found.append(f"{location} contains markdown: {value!r}")
    if _roman_heading_token(value, roman_pattern):
        found.append(f"{location} contains a Roman numeral: {value!r}")
    return found


def minutes_phrase_errors(text: str) -> tuple[str, ...]:
    """Placeholder and heading-marker checks for one replacement phrase.

    A one-phrase replace has no attendance block and no closing sections, so
    those document checks do not apply. A heading marker is refused only when
    it starts the phrase. ``See II. above`` is ordinary text.
    """
    errors = _placeholder_errors(text, "replacement")
    errors.extend(_heading_marker_errors(text, "replacement", _ROMAN_HEADING_AT_START))
    return tuple(errors)


def minutes_shape_errors(document: MinutesDocument) -> tuple[str, ...]:
    """Shape rules the JSON can violate without reading the meeting notes."""
    errors: list[str] = []
    for index, item in enumerate(document.items):
        where = f"items[{index}]"
        for label, value in _item_strings(item):
            errors.extend(_placeholder_errors(value, f"{where} {label}"))
        if item.kind == "attendance" and item.label != _ATTENDANCE_LABEL:
            errors.append(f"{where} attendance label must be {_ATTENDANCE_LABEL!r}")
        if item.kind == "presenter" and not _PRESENTER_LINE.fullmatch(item.text or ""):
            errors.append(f"{where} presenter must be 'Presented by <name>.'")
        if item.kind == "section" and item.title:
            errors.extend(
                _heading_marker_errors(item.title, f"{where} section title", _ROMAN_HEADING_TOKEN)
            )
    errors.extend(_closing_section_errors(document))
    return tuple(errors)
