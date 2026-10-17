"""Layer B runner: OOC.VOICE and CANON.RAILS judgment notes.

Shared contract (spec v0.4.3 section 7): fixed rubric, closed labels, an exact
quote that is a substring of the cited paragraph, `observed` kept separate from
`interpretation`, severity info, never a blocker, never a finding. Agreement
across runs is reported; it is not correctness.

Only the mock provider runs. Any other provider name is refused unless the G9
opt-in is set, and even then no real provider is implemented in this package,
so no draft text ever leaves the machine from here.
"""

from __future__ import annotations

import hashlib
import json
import os

from doctor.later import OOC_LABELS, RAILS_LABELS, cache_get, cache_key, vote
from doctor.timeline import AFTER, compare, scene_of

RULESET_VERSION = "layer-b-0.4.3"
RUNS = 3
MAX_TASKS_PER_RULE = 20
G9_ENV = "DOCTOR_G9_OPT_IN"

RUBRICS = {
    "OOC.VOICE": {
        "labels": sorted(OOC_LABELS),
        "text": (
            "Is this character in voice in this paragraph? Labels: in_voice, drift, "
            "break, intentional_evolution, not_enough_evidence. Info only. A break "
            "label is not escalated. Cite an exact quote. Separate observed text "
            "from interpretation."
        ),
    },
    "CANON.RAILS": {
        "labels": sorted(RAILS_LABELS),
        "text": (
            "Does this later passage show an on-page consequence of the declared "
            "branch? Labels: consequence_shown, on_rails, not_enough_evidence. Info "
            "only. Not a fact check. Cite an exact quote. Separate observed text "
            "from interpretation."
        ),
    },
}
LABELS = {rule: set(spec["labels"]) for rule, spec in RUBRICS.items()}


class ProviderRefused(RuntimeError):
    """A non-mock provider was requested while the G9 gate is closed."""


class DeterministicMockProvider:
    """Answers from a hash of the request. No network, no model, same output every run."""

    name = "mock"

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, prompt_hash: str, request: dict | None = None) -> dict:
        self.calls += 1
        request = request or {}
        labels = request.get("labels") or ["not_enough_evidence"]
        text = request.get("paragraph_text") or ""
        run = int(request.get("run", 0))
        # Runs 0 and 1 share a seed so the mock usually agrees 2 of 3; run 2 varies.
        seed = prompt_hash if run < 2 else f"{prompt_hash}:{run}"
        pick = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % len(labels)
        surface = request.get("surface")
        quote = surface if surface and surface in text else " ".join(text.split()[:5])
        return {
            "kind": "note",
            "label": labels[pick],
            "quote": quote,
            "observed": quote,
            "interpretation": "Mock provider judgment for tests. Not a reading of the text.",
        }


class GatedProvider:
    """Placeholder for a real model. Closed by gate G9."""

    def __init__(self, name: str, env: dict | None = None) -> None:
        env = os.environ if env is None else env
        if env.get(G9_ENV) != "1":
            raise ProviderRefused(
                f"provider '{name}' refused: gate G9 is closed. Check Cursor data and "
                f"retention settings on the actual account, then set {G9_ENV}=1."
            )
        raise ProviderRefused(
            f"provider '{name}' is not implemented. Only 'mock' runs in this package."
        )


def get_provider(name: str = "mock", env: dict | None = None):
    if name == "mock":
        return DeterministicMockProvider()
    return GatedProvider(name, env)


def _prompt_hash(rule: str, task: dict) -> str:
    payload = json.dumps(
        {
            "rule": rule,
            "ruleset": RULESET_VERSION,
            "rubric": RUBRICS[rule]["text"],
            "paragraph": task["paragraph_id"],
            "text": task["paragraph_text"],
            "subject": task.get("subject"),
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_response(rule: str, response: dict, paragraph_text: str) -> str | None:
    """Return a rejection reason, or None if the response meets the contract."""
    if not isinstance(response, dict) or response.get("kind") != "note":
        return "invalid_output"
    if response.get("label") not in LABELS[rule]:
        return "label_not_closed"
    quote = response.get("quote")
    if not isinstance(quote, str) or not quote or quote not in paragraph_text:
        return "quote_not_in_paragraph"
    observed = response.get("observed")
    interpretation = response.get("interpretation")
    if not isinstance(observed, str) or observed not in paragraph_text:
        return "observed_not_verbatim"
    if not isinstance(interpretation, str) or not interpretation.strip():
        return "missing_interpretation"
    if interpretation.strip() == observed.strip():
        return "observed_equals_interpretation"
    return None


def _tasks(rule: str, doc, intake: dict, graph, mentions: list[dict]) -> list[dict]:
    texts = {paragraph.id: paragraph.text for paragraph in doc.paragraphs}
    tasks: list[dict] = []
    if rule == "OOC.VOICE":
        main = {person["entity"] for person in intake.get("main_cast") or []}
        seen = set()
        for mention in mentions:
            key = (mention["entity"], mention["paragraph"])
            if mention["entity"] not in main or key in seen:
                continue
            seen.add(key)
            tasks.append(
                {
                    "paragraph_id": mention["paragraph"],
                    "paragraph_text": texts[mention["paragraph"]],
                    "subject": mention["entity"],
                    "surface": mention.get("surface"),
                }
            )
    else:
        divergence = ((intake.get("au") or {}).get("divergence_event")) or None
        for paragraph in doc.paragraphs:
            if (
                compare(graph, (scene_of(paragraph.id), None), (divergence, None))
                == AFTER
            ):
                tasks.append(
                    {
                        "paragraph_id": paragraph.id,
                        "paragraph_text": paragraph.text,
                        "subject": divergence,
                    }
                )
    return tasks[:MAX_TASKS_PER_RULE]


def _declared_branch(intake: dict) -> bool:
    au = intake.get("au") or {}
    return bool(au.get("is_au")) and bool(au.get("divergence_event"))


def run_layer_b(
    doc, intake: dict, graph, mentions: list[dict], provider, cache: dict | None = None
):
    """Return (items, lens rows) for OOC.VOICE and CANON.RAILS."""
    cache = {} if cache is None else cache
    items: list[dict] = []
    lens: dict[str, dict] = {}
    model = getattr(provider, "name", type(provider).__name__)
    for rule in ("OOC.VOICE", "CANON.RAILS"):
        if rule == "CANON.RAILS" and not _declared_branch(intake):
            lens[rule] = {
                "rule_id": rule,
                "state": "skipped",
                "reason": "no_declared_branch",
            }
            continue
        rejected = 0
        tasks = _tasks(rule, doc, intake, graph, mentions)
        for task in tasks:
            prompt_hash = _prompt_hash(rule, task)
            key = cache_key(
                task["paragraph_text"], f"{RULESET_VERSION}:{rule}", model, prompt_hash
            )
            responses = cache_get(cache, key)
            if responses is None:
                responses = []
                for run in range(RUNS):
                    request = {
                        **task,
                        "rule": rule,
                        "labels": RUBRICS[rule]["labels"],
                        "run": run,
                    }
                    responses.append(provider.complete(prompt_hash, request))
                cache[key] = responses
            good = []
            for response in responses:
                reason = validate_response(rule, response, task["paragraph_text"])
                if reason:
                    rejected += 1
                else:
                    good.append(response)
            tallies = [
                {"label": response["label"], "votes": 1, "response": response}
                for response in good
            ]
            for note in vote(tallies):
                response = note["response"]
                items.append(
                    {
                        "rule_id": rule,
                        "item_state": "note",
                        "tier": "B",
                        "severity": "info",
                        "kind": "judgment",
                        "symptom": f"{rule} label {note['label']} ({note['agreement']}). Agreement is not correctness.",
                        "evidence": [
                            {
                                "kind": "prose",
                                "paragraph_id": task["paragraph_id"],
                                "quote": response["quote"],
                            }
                        ],
                        "fact_ids": [],
                        "depends_on_hash": key,
                        "observed": response["observed"],
                        "interpretation": response["interpretation"],
                        "label": note["label"],
                        "agreement": note["agreement"],
                    }
                )
        if rejected:
            items.append(
                {
                    "rule_id": rule,
                    "item_state": "coverage",
                    "tier": "B",
                    "severity": "info",
                    "kind": "coverage",
                    "symptom": f"{rejected} Layer B responses were rejected by the contract check and not shown.",
                    "evidence": [
                        {"kind": "file", "path": "report.json", "field": rule}
                    ],
                    "fact_ids": [],
                    "depends_on_hash": hashlib.sha256(
                        f"{rule}:{rejected}".encode()
                    ).hexdigest(),
                }
            )
        lens[rule] = {
            "rule_id": rule,
            "state": "applied",
            "reason": f"provider={model}; tasks={len(tasks)}",
        }
    return items, lens
