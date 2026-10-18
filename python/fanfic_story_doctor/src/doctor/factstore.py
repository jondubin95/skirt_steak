"""Fact records, supersession, conflicts, claims, re-anchoring."""

from __future__ import annotations

import json
import uuid

from doctor.timeline import UNKNOWN, YES, overlap

CLOSED_PREDICATES = {"status", "alias", "setup_anchor", "payoff_anchor", "event_order"}
CLOSED_STATUS = {"alive", "dead", "unspecified"}
SINGLE_VALUED = {"status"}


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
        # Only single-valued predicates can conflict. An entity has many
        # aliases, and an event has many order edges.
        if fact.get("predicate") not in SINGLE_VALUED:
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


def load_facts(raw: str) -> list[dict]:
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("facts.json must be a list")
    for fact in data:
        validate_fact(fact)
    return data
