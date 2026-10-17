"""Layered resolve. Only status has a default value."""

from __future__ import annotations

from doctor.timeline import UNKNOWN, YES, covers

RESOLVED = "RESOLVED"
UNRESOLVED = "UNRESOLVED"


def is_enforceable(fact: dict) -> bool:
    return (
        fact.get("status") == "confirmed"
        and fact.get("assertion", "state") == "state"
        and not fact.get("superseded_by")
        and fact.get("citation_state", "ok") == "ok"
    )


def _layer_rank(layer: str, primary: str | None) -> tuple[int, int]:
    if layer == "ledger":
        return (0, 0)
    if layer == "au":
        return (1, 0)
    if layer.startswith("canon:"):
        source = layer.split(":", 1)[1]
        return (2, 0 if primary and source == primary else 1)
    if layer == "default":
        return (3, 0)
    return (9, 0)


def resolve(facts: list[dict], subject: str, predicate: str, paragraph_id: str, graph, primary: str | None = None):
    grouped: dict[str, list[dict]] = {}
    for fact in facts:
        if fact.get("subject") != subject or fact.get("predicate") != predicate:
            continue
        if fact.get("assertion", "state") != "state":
            continue
        grouped.setdefault(fact.get("layer", "ledger"), []).append(fact)
    layers = sorted(grouped, key=lambda layer: _layer_rank(layer, primary))
    for layer in layers:
        layer_facts = grouped[layer]
        enforceable = [fact for fact in layer_facts if is_enforceable(fact)]
        blocked = [
            fact
            for fact in layer_facts
            if fact.get("citation_state") == "stale" or fact.get("status") == "disputed"
        ]
        yes = [fact for fact in enforceable if covers(graph, fact, paragraph_id) == YES]
        unk = [fact for fact in enforceable if covers(graph, fact, paragraph_id) == UNKNOWN]
        unk = unk + blocked
        if yes:
            objects = {repr(fact.get("object")) for fact in yes}
            ids = [fact["id"] for fact in yes]
            if len(objects) > 1:
                return UNRESOLVED, None, ids
            if any(fact.get("object") != yes[0].get("object") for fact in unk):
                return UNRESOLVED, None, ids + [fact["id"] for fact in unk]
            return RESOLVED, yes[0].get("object"), ids
        if unk:
            return UNRESOLVED, None, [fact["id"] for fact in unk]
    if predicate == "status":
        return RESOLVED, "unspecified", []
    return UNRESOLVED, None, []
