"""Tie intake, graph, rules, and the report together."""

from __future__ import annotations

from doctor.detect import (
    alias_map_from_facts,
    ambiguous_aliases,
    detect_markers,
    detect_mentions,
)
from doctor.factstore import mark_conflicts
from doctor.intake import window_edges, window_same
from doctor.resolve import is_enforceable
from doctor.rules import (
    MVP_RULES,
    ao3_schema,
    ao3_tag_format,
    canon_divergence,
    dead_reappears,
    depends_hash,
    name_spelling,
    payoff_before_setup,
    status_coverage,
    timeline_order,
)
from doctor.timeline import Graph, SceneNode, build_graph


def graph_from(doc, facts: list[dict], intake: dict) -> Graph:
    marker_scenes = set(detect_markers(doc.paragraphs))
    anchors: dict[str, str] = {}
    before: list[tuple[str, str]] = []
    same: list[tuple[str, str]] = []
    events = [event["id"] for event in intake.get("events") or []]
    order_facts = [
        fact
        for fact in facts
        if fact.get("predicate") == "event_order" and is_enforceable(fact)
    ]
    # Canon order is compared by CANON.DIVERGENCE, not asserted into the work's
    # timeline. A canon edge is used only for a pair the ledger and AU layers
    # do not order themselves, so a deliberate branch never forms a cycle.
    local_pairs = {_pair(fact) for fact in order_facts if not _is_canon(fact)}
    for fact in order_facts:
        if _is_canon(fact) and _pair(fact) in local_pairs:
            continue
        obj = fact.get("object") or {}
        subject = fact.get("subject")
        target = obj.get("target")
        relation = obj.get("relation")
        if (
            obj.get("anchor_kind")
            and isinstance(subject, str)
            and subject.startswith("ch")
        ):
            anchors[subject] = obj["anchor_kind"]
        if relation == "same" and subject and target:
            same.append((subject, target))
        elif relation == "before" and subject and target:
            before.append((subject, target))
        elif relation == "after" and subject and target:
            before.append((target, subject))
    first = doc.scene_ids[0] if doc.scene_ids else ""
    before.extend(window_edges(intake, first))
    same_event = window_same(intake)
    if same_event and first:
        same.append((same_event, first))
    if same_event and same_event not in events:
        events.append(same_event)
    scenes = []
    for scene_id in doc.scene_ids:
        kind = anchors.get(scene_id)
        uncertain = scene_id in marker_scenes and kind is None
        scenes.append(SceneNode(scene_id, anchor_kind=kind, uncertain=uncertain))
    for node in list(before) + list(same):
        for name in node:
            if name.startswith("ev") and name not in events:
                events.append(name)
    return build_graph(
        scenes,
        events,
        before,
        same,
        paragraph_ids=[paragraph.id for paragraph in doc.paragraphs],
        window_before=_window_before(intake),
    )


def _is_canon(fact: dict) -> bool:
    return str(fact.get("layer", "")).startswith("canon:")


def _pair(fact: dict) -> frozenset:
    return frozenset((fact.get("subject"), (fact.get("object") or {}).get("target")))


def _window_before(intake: dict) -> str | None:
    window = intake.get("window") or {}
    if window.get("relation") == "before":
        return window.get("event")
    return None


def run_rules(
    doc, facts, intake, tags, graph, mentions, layer_b: bool
) -> tuple[list[dict], list[dict], str]:
    primary = intake.get("primary_canon_source")
    opted = set((intake.get("profile") or {}).get("opt_out") or [])
    alternate = au_kind(intake) == "alternate_setting"
    items: list[dict] = []
    ran: set[str] = set()
    if "CANON.DIVERGENCE" not in opted and not alternate:
        items.extend(canon_divergence(facts, graph, intake, primary))
        ran.add("CANON.DIVERGENCE")
    if "CONT.DEAD_REAPPEARS" not in opted:
        items.extend(dead_reappears(mentions, facts, graph, primary))
        ran.add("CONT.DEAD_REAPPEARS")
    if "CONT.PAYOFF_BEFORE_SETUP" not in opted:
        items.extend(payoff_before_setup(facts))
        ran.add("CONT.PAYOFF_BEFORE_SETUP")
    if "CONT.TIMELINE_ORDER" not in opted:
        items.extend(timeline_order(graph))
        ran.add("CONT.TIMELINE_ORDER")
    main = [person["entity"] for person in intake.get("main_cast") or []]
    coverage = status_coverage(facts, main, graph)
    items.append(coverage)
    ran.add("LEDGER.COVERAGE")
    notices = mark_conflicts(facts, graph)
    for notice in notices:
        if notice["kind"] == "coverage":
            items.append(
                {
                    "rule_id": "LEDGER.CONFLICT",
                    "item_state": "coverage",
                    "tier": "A1",
                    "severity": "info",
                    "kind": "coverage",
                    "symptom": notice["text"],
                    "evidence": [
                        {
                            "kind": "file",
                            "path": "facts.json",
                            "field": notice["ids"][0],
                        }
                    ],
                    "fact_ids": notice["ids"],
                    "depends_on_hash": coverage["depends_on_hash"],
                }
            )
    ran.add("LEDGER.CONFLICT")
    for surface, entities in sorted(ambiguous_aliases(facts).items()):
        items.append(
            {
                "rule_id": "LEDGER.COVERAGE",
                "item_state": "coverage",
                "tier": "A1",
                "severity": "info",
                "kind": "coverage",
                "symptom": f"{surface} is shared by {', '.join(entities)}. Mentions of it are not attributed.",
                "evidence": [
                    {"kind": "file", "path": "intake.yaml", "field": "main_cast"}
                ],
                "fact_ids": [],
                "depends_on_hash": depends_hash([surface, *entities]),
            }
        )
    aliases = [fact["object"] for fact in facts if fact.get("predicate") == "alias"]
    items.extend(name_spelling(doc.paragraphs, [str(alias) for alias in aliases]))
    ran.add("CANON.NAME_SPELLING")
    skipped: dict[str, str] = {}
    if tags:
        items.extend(ao3_schema(tags))
        ran.add("AO3.SCHEMA")
        items.extend(ao3_tag_format(tags))
        ran.add("AO3.TAG_FORMAT")
    else:
        skipped["AO3.SCHEMA"] = "no_tags_yaml"
        skipped["AO3.TAG_FORMAT"] = "no_tags_yaml"
    lens = []
    for rule in MVP_RULES:
        if rule in opted:
            lens.append({"rule_id": rule, "state": "skipped", "reason": "opted_out"})
        elif rule in {"OOC.VOICE", "CANON.RAILS"} and not layer_b:
            lens.append({"rule_id": rule, "state": "skipped", "reason": "layer_a_only"})
        elif rule in {"OOC.VOICE", "CANON.RAILS"}:
            # Filled in by doctor.layerb.run_layer_b via cli.build_report.
            lens.append(
                {"rule_id": rule, "state": "skipped", "reason": "layer_b_pending"}
            )
        elif rule == "CANON.DIVERGENCE" and alternate:
            lens.append(
                {"rule_id": rule, "state": "skipped", "reason": "alternate_setting"}
            )
        elif rule in skipped:
            lens.append({"rule_id": rule, "state": "skipped", "reason": skipped[rule]})
        elif rule in ran:
            lens.append({"rule_id": rule, "state": "applied", "reason": ""})
        else:
            lens.append({"rule_id": rule, "state": "skipped", "reason": "not_built"})
    return items, lens, summarize(items)


def summarize(items: list[dict]) -> str:
    findings = [item for item in items if item.get("item_state") == "finding"]
    blockers = [item for item in findings if item.get("severity") == "blocker"]
    coverage = next(
        (
            item
            for item in items
            if item.get("rule_id") == "LEDGER.COVERAGE" and "covered" in item
        ),
        None,
    )
    summary = f"{len(findings)} findings. {len(blockers)} blockers."
    if coverage is not None and coverage["covered"] == 0:
        summary += " No status facts are confirmed for the main cast."
    return summary


AU_KINDS = {"branch", "alternate_setting"}


def au_kind(intake: dict) -> str:
    return ((intake.get("au") or {}).get("au_kind")) or "branch"


def applicable_facts(facts: list[dict], intake: dict) -> list[dict]:
    """In an alternate setting, canon status and event order do not apply. Aliases do."""
    if au_kind(intake) != "alternate_setting":
        return facts
    return [
        fact
        for fact in facts
        if not (
            str(fact.get("layer", "")).startswith("canon:")
            and fact.get("predicate") in {"status", "event_order"}
        )
    ]


def build_mentions(doc, facts) -> list[dict]:
    return detect_mentions(doc.paragraphs, alias_map_from_facts(facts))
