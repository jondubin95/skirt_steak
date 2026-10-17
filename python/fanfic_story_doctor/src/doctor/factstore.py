"""Fact records, supersession, conflicts, claims, re-anchoring."""

from __future__ import annotations

import hashlib
import json
import uuid
from copy import deepcopy

from doctor.timeline import UNKNOWN, YES, overlap

CLOSED_PREDICATES = {"status", "alias", "setup_anchor", "payoff_anchor", "event_order"}
CLOSED_STATUS = {"alive", "dead", "unspecified"}


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def validate_fact(fact: dict) -> None:
    if fact.get("predicate") not in CLOSED_PREDICATES:
        raise ValueError(f"unknown predicate: {fact.get('predicate')}")
    if fact.get("predicate") == "status" and fact.get("object") not in CLOSED_STATUS:
        raise ValueError(f"unknown status: {fact.get('object')}")
    assertion = fact.get("assertion", "state")
    if assertion not in {"state", "claim"}:
        raise ValueError(f"unknown assertion: {assertion}")
    if assertion == "claim" and not fact.get("claimant"):
        raise ValueError("claim requires claimant")


def supersede(
    facts: list[dict], old_id: str, updates: dict, who: str = "writer"
) -> dict:
    old = next(fact for fact in facts if fact["id"] == old_id)
    new = deepcopy(old)
    new.update(updates)
    new["id"] = new_id("f")
    new["supersedes"] = old_id
    new["superseded_by"] = None
    new["status"] = updates.get("status", "confirmed")
    new.setdefault("provenance", {})["created_by"] = who
    validate_fact(new)
    old["status"] = "superseded"
    old["superseded_by"] = new["id"]
    facts.append(new)
    return new


def mark_conflicts(facts: list[dict], graph) -> list[dict]:
    """Same-layer incompatible overlaps become disputed. Cross-layer differences do not."""
    notices = []
    groups: dict[tuple, list[dict]] = {}
    for fact in facts:
        if fact.get("status") not in {"confirmed", "disputed"}:
            continue
        if fact.get("assertion", "state") != "state":
            continue
        if fact.get("superseded_by"):
            continue
        key = (fact.get("layer"), fact.get("subject"), fact.get("predicate"))
        groups.setdefault(key, []).append(fact)
    for key, group in groups.items():
        for i, left in enumerate(group):
            for right in group[i + 1 :]:
                if left.get("object") == right.get("object"):
                    continue
                state = overlap(graph, left, right)
                if state == YES:
                    cid = new_id("conflict")
                    for fact in (left, right):
                        fact["status"] = "disputed"
                        fact["conflict_set"] = cid
                elif state == UNKNOWN:
                    notices.append(
                        {"kind": "possible_conflict", "ids": [left["id"], right["id"]]}
                    )
    ledger = [
        fact
        for fact in facts
        if fact.get("layer") == "ledger" and fact.get("status") == "confirmed"
    ]
    au = [
        fact
        for fact in facts
        if fact.get("layer") == "au" and fact.get("status") == "confirmed"
    ]
    for left in ledger:
        for right in au:
            if left.get("subject") == right.get("subject") and left.get(
                "predicate"
            ) == right.get("predicate"):
                if (
                    left.get("object") != right.get("object")
                    and overlap(graph, left, right) == YES
                ):
                    notices.append(
                        {
                            "kind": "coverage",
                            "text": "Your draft overrides your declared AU.",
                            "ids": [left["id"], right["id"]],
                        }
                    )
    return notices


def reanchor(
    facts: list[dict], paragraphs: dict[str, str], hashes: dict[str, str]
) -> None:
    """paragraphs: id -> normalized text. hashes: id -> content hash."""
    by_chapter_text: dict[int, list[tuple[str, str]]] = {}
    by_hash: dict[str, list[str]] = {}
    for pid, text in paragraphs.items():
        chapter = int(pid.split(".")[0][2:])
        by_chapter_text.setdefault(chapter, []).append((pid, text))
        by_hash.setdefault(hashes[pid], []).append(pid)
    for fact in facts:
        citation = fact.get("citation") or {}
        quote = citation.get("text")
        at = citation.get("at")
        if quote and at:
            chapter = int(str(at).split(".")[0][2:])
            hits = [
                pid for pid, text in by_chapter_text.get(chapter, []) if quote in text
            ]
            if len(hits) == 1:
                citation["at"] = hits[0]
                fact["citation_state"] = "ok"
            else:
                fact["citation_state"] = "stale"
        interval = fact.get("interval") or {}
        for key in ("from", "to"):
            bound = interval.get(key)
            if not bound or "work" not in bound:
                continue
            if (
                citation.get("at")
                and bound["work"] == at
                and fact.get("citation_state") == "ok"
            ):
                bound["work"] = citation["at"]
                continue
            stored = bound.get("content_hash")
            if not stored:
                continue
            hits = by_hash.get(stored, [])
            if len(hits) == 1:
                bound["work"] = hits[0]
            else:
                fact["citation_state"] = "stale"


def reanchor_annotations(annotations: list[dict], hashes: dict[str, str]) -> None:
    hash_to_ids: dict[str, list[str]] = {}
    for pid, digest in hashes.items():
        hash_to_ids.setdefault(digest, []).append(pid)
    for note in annotations:
        stored = note.get("paragraph_hash")
        hits = hash_to_ids.get(stored, [])
        if stored and len(hits) == 1:
            note["paragraph"] = hits[0]
            note["mode_status"] = note.get("mode_status")
        else:
            note["stale"] = True


def dump_facts(facts: list[dict]) -> str:
    return json.dumps(facts, indent=2, sort_keys=True)


def load_facts(raw: str) -> list[dict]:
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("facts.json must be a list")
    for fact in data:
        validate_fact(fact)
    return data


def proposition_hash(fact: dict) -> str:
    payload = json.dumps(
        {
            "subject": fact.get("subject"),
            "predicate": fact.get("predicate"),
            "object": fact.get("object"),
            "interval": fact.get("interval"),
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
