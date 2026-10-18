"""Intake, tags, and profile loaders. Closed enums."""

from __future__ import annotations

from doctor.factstore import validate_fact

RATINGS = {
    "Not Rated",
    "General Audiences",
    "Teen And Up Audiences",
    "Mature",
    "Explicit",
}
WARNINGS = {
    "Graphic Depictions Of Violence",
    "Major Character Death",
    "Rape/Non-Con",
    "Underage",
    "Creator Chose Not To Use Archive Warnings",
    "No Archive Warnings Apply",
}
CATEGORIES = {"F/F", "F/M", "Gen", "M/M", "Multi", "Other"}
WINDOWS = {"before", "after", "same"}
LAYERS = {"canon", "au", "ledger"}


class IntakeError(ValueError):
    pass


def load_intake(data: dict) -> tuple[dict, list[dict]]:
    if not isinstance(data, dict):
        raise IntakeError("intake must be a mapping")
    sources = data.get("canon_sources") or []
    if not sources:
        raise IntakeError("canon_sources is required")
    ids = [source["id"] for source in sources]
    primary = data.get("primary_canon_source")
    if primary not in ids:
        raise IntakeError("primary_canon_source must be one of canon_sources")
    window = data.get("window") or {}
    if window.get("relation") not in WINDOWS:
        raise IntakeError("window.relation must be before, after, or same")
    kind = (data.get("au") or {}).get("au_kind") or "branch"
    if kind not in {"branch", "alternate_setting"}:
        raise IntakeError("au.au_kind must be branch or alternate_setting")
    for event in data.get("events") or []:
        if event.get("layer") not in LAYERS:
            raise IntakeError(f"unknown event layer: {event.get('layer')}")
    _validate_cast(data)
    facts = _seed(data, primary)
    for fact in facts:
        validate_fact(fact)
    return data, facts


def _validate_cast(data: dict) -> None:
    people = list(data.get("main_cast") or []) + list(data.get("other_entities") or [])
    for person in people:
        entity = person.get("entity")
        if not isinstance(entity, str) or not entity:
            raise IntakeError("every cast entry needs an entity")
    ignored = data.get("spelling_ignore") or []
    if not isinstance(ignored, list) or any(
        not isinstance(item, str) or not item.strip() for item in ignored
    ):
        raise IntakeError("spelling_ignore must be a list of names")


def _seed(data: dict, primary: str) -> list[dict]:
    facts: list[dict] = []
    counter = 0

    def add(fact: dict) -> None:
        nonlocal counter
        counter += 1
        fact["id"] = fact.get("id") or f"f-intake-{counter:04d}"
        fact["status"] = "confirmed"
        fact["assertion"] = fact.get("assertion", "state")
        fact["citation_state"] = "ok"
        fact["confirmation_method"] = "intake_inherited"
        fact["provenance"] = {"created_by": "intake"}
        facts.append(fact)

    for person in data.get("main_cast") or []:
        for name in person.get("names") or []:
            add(
                {
                    "subject": person["entity"],
                    "predicate": "alias",
                    "object": name,
                    "layer": "ledger",
                }
            )
    for person in data.get("other_entities") or []:
        for name in person.get("names") or []:
            add(
                {
                    "subject": person["entity"],
                    "predicate": "alias",
                    "object": name,
                    "layer": "ledger",
                }
            )
    canon_layer = f"canon:{primary}"
    for row in data.get("canon_status") or []:
        interval = {}
        if row.get("from_event"):
            interval["from"] = {"story": row["from_event"]}
        if row.get("to_event"):
            interval["to"] = {"story": row["to_event"]}
        add(
            {
                "subject": row["entity"],
                "predicate": "status",
                "object": row["value"],
                "layer": canon_layer,
                "interval": interval or None,
                "citation": {"text": None, "at": None, "source": row.get("source")},
            }
        )
    for pair in data.get("canon_event_order") or []:
        earlier, later = pair
        add(
            {
                "subject": later,
                "predicate": "event_order",
                "object": {
                    "relation": "after",
                    "target": earlier,
                    "anchor_kind": "explicit_order",
                },
                "layer": canon_layer,
            }
        )
    au = data.get("au") or {}
    for row in au.get("status_overrides") or []:
        interval = {}
        if row.get("from_event"):
            interval["from"] = {"story": row["from_event"]}
        add(
            {
                "subject": row["entity"],
                "predicate": "status",
                "object": row["value"],
                "layer": "au",
                "interval": interval or None,
            }
        )
    return facts


def window_edges(data: dict, first_scene: str) -> list[tuple[str, str]]:
    window = data.get("window") or {}
    event = window.get("event")
    relation = window.get("relation")
    if not event or not first_scene:
        return []
    if relation == "after":
        return [(event, first_scene)]
    if relation == "before":
        return [(first_scene, event)]
    if relation == "same":
        return []
    return []


def window_same(data: dict) -> str | None:
    window = data.get("window") or {}
    if window.get("relation") == "same":
        return window.get("event")
    return None


def load_tags(data: dict | None) -> dict:
    if data is None:
        return {}
    rating = data.get("rating")
    if rating is not None and rating not in RATINGS:
        raise IntakeError(f"unknown rating: {rating}")
    for warning in data.get("archive_warnings") or []:
        if warning not in WARNINGS:
            raise IntakeError(f"unknown archive warning: {warning}")
    for category in data.get("categories") or []:
        if category not in CATEGORIES:
            raise IntakeError(f"unknown category: {category}")
    return data


def load_profile(data: dict | None) -> dict:
    data = data or {}
    depth = data.get("depth", "quick")
    if depth not in {"quick", "thorough"}:
        raise IntakeError("depth must be quick or thorough")
    return data
