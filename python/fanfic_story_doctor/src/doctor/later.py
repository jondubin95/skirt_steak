"""Layer B voting and cache keys."""

from __future__ import annotations

import hashlib


RAILS_LABELS = {"consequence_shown", "on_rails", "not_enough_evidence"}
OOC_LABELS = {
    "in_voice",
    "drift",
    "break",
    "intentional_evolution",
    "not_enough_evidence",
}


def vote(notes: list[dict], limit_low: int = 1) -> list[dict]:
    """Aggregate votes per label across runs. Keep a label seen in at least 2 of 3 runs.

    Notes with the same label are merged first, so two runs voting the same label
    count as one label with their votes summed. At most `limit_low` labels that
    reached only one vote are kept, marked low_agreement.
    """
    totals: dict[str, int] = {}
    first: dict[str, dict] = {}
    for note in notes:
        label = note.get("label")
        if label not in RAILS_LABELS and label not in OOC_LABELS:
            continue
        totals[label] = totals.get(label, 0) + int(note.get("votes", 1))
        first.setdefault(label, note)
    kept = []
    low = 0
    for label, votes in totals.items():
        note = dict(first[label])
        note["votes"] = votes
        if votes >= 2:
            note["agreement"] = "2_of_3" if votes == 2 else "3_of_3"
            kept.append(note)
        elif low < limit_low:
            note["agreement"] = "low_agreement"
            kept.append(note)
            low += 1
    return kept


def cache_key(text: str, ruleset: str, model: str, config: str) -> str:
    payload = f"{text}|{ruleset}|{model}|{config}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
