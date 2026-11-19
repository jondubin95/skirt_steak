"""Semantic minutes JSON: dataclasses, validation, and write-target guards.

This module has no third-party imports so CI can test it with the
standard library alone.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1
ITEM_KINDS = frozenset(
    {"masthead", "attendance", "section", "presenter", "bullet", "motion", "paragraph"}
)
VERDICTS = frozenset({"passes", "fails"})
# Straight and curly apostrophes. A raw regex string would not decode \u2019.
_CONTRACTION_NT = "n['\u2019]t"
_SECONDER = re.compile(r"(?i)\b(?:seconds|seconded)\b")
# A seconder hit is governed when a negation sits on that hit: "not seconded",
# "n't seconded" (including "hasn't been seconded"), or "seconded by no one".
_SECONDER_NEGATION = re.compile(
    rf"(?i)(?:\b(?:not|never|no(?:\s+one|\s+body)?|nobody)\b|{_CONTRACTION_NT})"
    rf"(?:\s+been)?"
    rf"\s+(?:seconds|seconded)\b"
    rf"|\b(?:seconds|seconded)\s+by\s+(?:no\s+one|nobody)\b"
)
# "did not vote" is the hole in "not voted" / "no vote". The contraction is
# the same statement.
_NO_VOTE = re.compile(
    rf"(?i)\bnot\s+voted\b|\bno\s+vote\b|\bdid\s+not\s+vote\b|\bdid{_CONTRACTION_NT}\s+vote\b"
)
# Yeas, nays, "voted down", and "vote failed" are an explicit vote. "not",
# "never", or "n't" immediately in front of "voted down" or "vote failed"
# is the vote that phrase denies. Yea and nay are not part of that prefix
# check: a tally still counts.
_EXPLICIT_VOTE = re.compile(
    r"(?i)\b(?P<phrase>voted\s+down|vote\s+failed)\b|\b(?:nay|nays|yea|yeas)\b"
)
_VOTE_NEGATION_PREFIX = re.compile(
    rf"(?i)(?:\b(?:not|never)|{_CONTRACTION_NT})\s+$"
)
# "motion failed" and "defeated" record a vote only inside a clause that does
# not say the motion died for lack of a second. They must stay separate from
# the explicit-vote pattern: a lack-of-second phrase does not cancel yea/nay
# or "voted down".
_RECORDED_FAILURE = re.compile(r"(?i)\bmotion\s+fail(?:s|ed)\b|\bdefeated\b")
_LACK_OF_SECOND = re.compile(
    r"(?i)\bwithout\s+a\s+second\b"
    r"|\black\s+of\s+(?:a|the)\s+second\b"
    r"|\bwant\s+of\s+a\s+second\b"
    r"|\b(?:receive|get)\s+a\s+second\b"
)
# The pass pair of "motion fails" / "motion failed". Bare "passed" is not a
# recorded vote. "Passed unanimously." is.
_RECORDED_PASS = re.compile(
    r"(?i)\bmotion\s+pass(?:es|ed)\b|\bpassed\s+unanimously\b"
)
_CLAUSE_BREAK = frozenset(".!?;\n")
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


def _clause_span(body: str, index: int) -> tuple[int, int]:
    start = 0
    for position, char in enumerate(body):
        if char not in _CLAUSE_BREAK:
            continue
        if position < index:
            start = position + 1
            continue
        return start, position
    return start, len(body)


def _has_explicit_vote(body: str) -> bool:
    for match in _EXPLICIT_VOTE.finditer(body):
        if match.group("phrase") is None:
            return True
        if _VOTE_NEGATION_PREFIX.search(body[: match.start()]):
            continue
        return True
    return False


def _has_recorded_pass(body: str) -> bool:
    """A pass phrase with not, never, or n't immediately in front is not a vote."""
    for match in _RECORDED_PASS.finditer(body):
        if _VOTE_NEGATION_PREFIX.search(body[: match.start()]):
            continue
        return True
    return False


def _failure_earns_verdict(body: str) -> bool:
    for match in _RECORDED_FAILURE.finditer(body):
        start, end = _clause_span(body, match.start())
        if _LACK_OF_SECOND.search(body[start:end]):
            continue
        return True
    return False


def _seconder_hit_is_negated(body: str, match: re.Match[str]) -> bool:
    start, end = _clause_span(body, match.start())
    clause = body[start:end]
    for negation in _SECONDER_NEGATION.finditer(clause):
        negation_start = start + negation.start()
        negation_end = start + negation.end()
        if negation_start < match.end() and match.start() < negation_end:
            return True
    return False


def _seconder_earns_verdict(body: str) -> bool:
    """The last seconder hit is the one the minutes settle on.

    "No one seconded at first. Jordan Hale later seconds." earns.
    "Jordan Hale seconds the motion. It was not seconded." does not.
    Negation is judged inside that hit's clause, so "no second reading"
    in an earlier clause does not swallow a later "seconds".
    """
    hits = list(_SECONDER.finditer(body))
    if not hits:
        return False
    return not _seconder_hit_is_negated(body, hits[-1])


def motion_verdict_is_earned(body: str) -> bool:
    """True when `passes` or `fails` records a seconded motion or a vote.

    "Motion Fails." is the board's line for a motion that was voted down.
    A body with no seconder and no vote, including "No second; not voted"
    and "No one seconded.", is not that line. A lack-of-second phrase is
    not itself a vote, so "motion fails" and "defeated" do not earn a
    verdict in a clause that says the motion died for want of a second.
    "did not vote" blocks a seconder. It does not block an explicit vote
    or a recorded pass.
    """
    if _has_explicit_vote(body) or _has_recorded_pass(body) or _failure_earns_verdict(body):
        return True
    if _NO_VOTE.search(body):
        return False
    return _seconder_earns_verdict(body)


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
        # bool is a subclass of int, and 1.0 == 1. A level is an int.
        if type(level) is not int or level not in BULLET_LEVELS:
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
    # True == 1 and 1.0 == 1. schemaVersion is an int, not a bool or a float.
    if type(version) is not int or version != SCHEMA_VERSION:
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
    r"(?:\s*\.?\s+|,\s+who\s+)("
    + "|".join(sorted(_SPEAKING_VERBS, key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)
# "notes" / "reports" / "moves" are nouns when "was" or "were" follows.
# "noted", "reported", and "moved" stay verbs.
_NOUN_READING = frozenset({"notes", "reports", "moves"})
_NOUN_COPULA = re.compile(r"\s+(?:was|were)\b", re.IGNORECASE)
_PRESENTED_BY = re.compile(r"(?i)\bpresented\s+by\s+$")
# A following capital token means this name is only the start of a longer
# name ("Alex" inside "Alex Rivera"). ", Jr." / ", Sr." / ", III" are the
# same continuation as " Jr.", and they are checked before "Presented by",
# so "Presented by Alex Rivera, Jr." does not credit "Alex Rivera".
_NAME_CONTINUATION = re.compile(
    r"\s+[A-Z][A-Za-z'.-]*|,\s*(?:Jr|Sr|III|II|IV)\b\.?"
)
# A preceding name token means this name is only the end of a longer name
# ("Ann" inside "Mary Ann", "Rivera" inside "alex Rivera"). A period is a
# sentence break, not part of that token, so "adjourn. Taylor Morgan
# seconded" still credits Taylor Morgan. A function word or a speaking
# verb is not a given name: "Presented by Alex Rivera" and "said Taylor
# Morgan moved" still credit the name that follows.
_PRECEDING_NAME_TOKEN = re.compile(r"([A-Za-z][A-Za-z'-]*)\s+$")
_NOT_A_GIVEN_NAME = frozenset(
    {
        "a",
        "an",
        "and",
        "but",
        "by",
        "for",
        "from",
        "of",
        "or",
        "that",
        "the",
        "this",
        "to",
        "who",
        "with",
    }
) | frozenset(verb.casefold() for verb in _SPEAKING_VERBS)
_ABSENCE_CATEGORIES = frozenset(
    {"not in attendance", "absent", "not present", "regrets"}
)
_ABSENCE_TRAILING_PUNCTUATION = ".:;,–—-"
# A name character is a letter (including non-ASCII), a digit, a hyphen, or
# an apostrophe. "Ann" is not the end of "Jo-Ann", "key2Ann", "JoséAnn", or
# "O'Brien". The lookbehind stays one character wide.
_NAME_CHAR = "(?:[^\\W_]|[-'\u2019])"
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


def _is_trailing_name_part(text: str, start: int) -> bool:
    match = _PRECEDING_NAME_TOKEN.search(text[:start])
    if match is None:
        return False
    token = match.group(1)
    if token[0].isupper():
        return True
    return token.casefold() not in _NOT_A_GIVEN_NAME


def _speaking_credit(name: str, text: str) -> bool:
    """True when `name` itself speaks, presents, moves, or seconds.

    The name must be a whole word, and it must not be part of a longer name.
    "Ann" does not match "Joann", "Jo-Ann", "Mary Ann", "key2Ann", or
    "O'Brien". "Alex" does not match "Alex Rivera Jr." A possessive
    ("Taylor Morgan's") is a mention. A comma credits the name only in
    ", who <verb>". "Taylor Morgan, the treasurer, said" is discussion.
    "notes were" is a noun, not a speech credit.
    """
    for start, end in _name_spans(name, text):
        if _is_trailing_name_part(text, start):
            continue
        if _NAME_CONTINUATION.match(text, end):
            continue
        if end < len(text) and text[end] in _POSSESSIVE_MARK:
            continue
        if _PRESENTED_BY.search(text[:start]):
            return True
        verb = _SPEAKING_VERB.match(text, end)
        if verb is None:
            continue
        if verb.group(1).casefold() in _NOUN_READING and _NOUN_COPULA.match(text, verb.end()):
            continue
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
# that is the only place a heading marker takes effect. A leading bracket
# still counts ("(II." or "[II."). Leading whitespace and format characters
# are stripped before this pattern runs, so a zero-width space is not a bypass.
_ROMAN_HEADING_TOKEN = re.compile(r"(?<![A-Za-z])([IVXLCDM]+)(?=[.)])")
_ROMAN_HEADING_AT_START = re.compile(r"^(?:[([]\s*)?([IVXLCDM]+)(?=[.)])")
_ROMAN_VALUE = re.compile(r"^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$")
_PLACEHOLDER_XXX = re.compile(r"\bXXX\b", re.IGNORECASE)
_CLOSING_SECTIONS = ("Old Business", "New Business", "Adjournment")
_ATTENDANCE_LABEL = "In attendance:"
# The empty closing section is one paragraph whose text is exactly "None.".
# A paragraph that only strips to "None." is the same marker, and it is an
# error when it is padded or when it sits beside other text. Do not strip
# inside is_empty_section_paragraph. strip_spilled_bullets strips Docs
# paragraph text before it calls that function.
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


def _strip_leading_space_and_format(value: str) -> str:
    """Drop leading whitespace and Unicode format characters.

    ``str.isspace`` covers space, tab, newline, and a non-breaking space.
    It does not cover a zero-width space or a BOM. Those are format
    characters (category ``Cf``). ``See II. above`` still does not start
    with a Roman marker after this strip.
    """
    index = 0
    while index < len(value) and (
        value[index].isspace() or unicodedata.category(value[index]) == "Cf"
    ):
        index += 1
    return value[index:]


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
        exact_marker = (
            len(content) == 1
            and content[0].kind == "paragraph"
            and is_empty_section_paragraph(content[0].text or "")
        )
        if exact_marker:
            continue
        marker_paragraphs = [
            item
            for item in content
            if item.kind == "paragraph" and (item.text or "").strip() == _EMPTY_SECTION_MARKER
        ]
        if not marker_paragraphs:
            if not content:
                errors.append(f"{title} is empty; the body must be the paragraph None.")
            continue
        sole_padded = (
            len(content) == 1
            and content[0].kind == "paragraph"
        )
        if sole_padded:
            errors.append(f"{title} empty-section marker has leading/trailing whitespace")
        else:
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
    roman_value = value
    if roman_pattern is _ROMAN_HEADING_AT_START:
        roman_value = _strip_leading_space_and_format(value)
    if _roman_heading_token(roman_value, roman_pattern):
        found.append(f"{location} contains a Roman numeral: {value!r}")
    return found


def minutes_phrase_errors(text: str) -> tuple[str, ...]:
    """Placeholder and heading-marker checks for one replacement phrase.

    A one-phrase replace has no attendance block and no closing sections, so
    those document checks do not apply. A heading marker is refused only when
    it starts the phrase, after leading whitespace and format characters.
    ``See II. above`` is ordinary text.
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
