"""Confirmation, mock proposer, Layer B voting, cache, and eval gate.

These stay off the Layer A provider path. The mock proposer is the only provider
in tests. spaCy is not imported; mention recall beyond aliases is a later pin.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def load_bearing(question: dict, main_cast: set[str]) -> bool:
    subject = question.get("subject")
    if subject not in main_cast and question.get("type") != "CONFLICT":
        return False
    if question.get("type") == "CONFLICT":
        return True
    if question.get("predicate") == "status" and question.get("object") in {"dead", "alive"}:
        return True
    if question.get("predicate") in {"setup_anchor", "payoff_anchor", "event_order"}:
        return True
    if question.get("type") == "APPEARANCE_MODE" and question.get("status") == "dead":
        return True
    return False


def prioritize(questions: list[dict], main_cast: set[str], cap: int = 5) -> tuple[list[dict], list[dict]]:
    ranked = sorted(
        questions,
        key=lambda item: (
            0 if load_bearing(item, main_cast) else 1,
            item.get("reading_order", ""),
        ),
    )
    asked = [item for item in ranked if load_bearing(item, main_cast)][:cap]
    rest = [item for item in ranked if item not in asked]
    return asked, rest


def bulk_accept_allowed(question: dict) -> bool:
    if question.get("type") == "CONFLICT":
        return False
    if question.get("type") == "APPEARANCE_MODE" and question.get("mode") == "present_action" and question.get("status") == "dead":
        return False
    return bool(question.get("high_confidence")) and bool(question.get("verbatim"))


def memory_key(question: dict) -> dict:
    return {
        "proposition": question.get("proposition_hash"),
        "location": question.get("location_hash"),
        "dependency": question.get("dependency_hash"),
        "version": question.get("version", "1"),
    }


def memory_invalid(stored: dict, current: dict) -> bool:
    if stored.get("dependency") != current.get("dependency"):
        return True
    if stored.get("location") != current.get("location"):
        return True
    if stored.get("version") != current.get("version"):
        return True
    return False


class MockProvider:
    """Fixture responses only. A raising provider proves Layer A made no call."""

    def __init__(self, responses: list[dict]):
        self.responses = list(responses)
        self.calls = 0

    def complete(self, prompt_hash: str) -> dict:
        self.calls += 1
        if not self.responses:
            return {"kind": "refusal", "reason_category": "empty"}
        return self.responses.pop(0)


class RaisingProvider:
    def complete(self, prompt_hash: str) -> dict:
        raise AssertionError("Layer A called a provider")


def propose(provider: MockProvider, prompt_hash: str) -> dict:
    raw = provider.complete(prompt_hash)
    if raw.get("kind") == "proposal" and raw.get("fact"):
        fact = raw["fact"]
        fact["status"] = "proposed"
        return {"stored": fact}
    return {"not_reviewed": raw.get("reason_category", "invalid_output")}


RAILS_LABELS = {"consequence_shown", "on_rails", "not_enough_evidence"}
OOC_LABELS = {"in_voice", "drift", "break", "intentional_evolution", "not_enough_evidence"}


def vote(notes: list[dict], limit_low: int = 1) -> list[dict]:
    """Keep a label seen in at least 2 of 3 runs. Cap low-agreement notes."""
    kept = []
    low = 0
    for note in notes:
        label = note.get("label")
        if label not in RAILS_LABELS and label not in OOC_LABELS:
            continue
        votes = note.get("votes", 1)
        if votes >= 2:
            note = dict(note)
            note["agreement"] = "2_of_3" if votes == 2 else "3_of_3"
            kept.append(note)
        elif low < limit_low:
            note = dict(note)
            note["agreement"] = "low_agreement"
            kept.append(note)
            low += 1
    return kept


def cache_key(text: str, ruleset: str, model: str, config: str) -> str:
    payload = f"{text}|{ruleset}|{model}|{config}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cache_get(cache: dict, key: str):
    return cache.get(key)


def holdout_allowed(criteria: Path, repo: Path) -> bool:
    """Refuse holdout when criteria.yaml is untracked or modified."""
    import subprocess

    if not criteria.exists():
        return False
    rel = criteria.resolve().relative_to(repo.resolve()).as_posix()
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", rel],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if status.stdout.strip():
        return False
    tracked = subprocess.run(
        ["git", "ls-files", "--", rel],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(tracked.stdout.strip())
