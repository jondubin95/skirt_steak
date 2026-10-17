"""Tie intake, graph, rules, and the report together."""

from __future__ import annotations

from doctor.detect import alias_map_from_facts, detect_markers, detect_mentions
from doctor.factstore import mark_conflicts
from doctor.ids import scene_of
from doctor.intake import window_edges, window_same
from doctor.resolve import is_enforceable
from doctor.rules import (
    MVP_RULES,
    ao3_schema,
    ao3_tag_format,
    canon_divergence,
    dead_reappears,
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
    for fact in facts:
        if fact.get("predicate") != "event_order" or not is_enforceable(fact):
            continue
        obj = fact.get("object") or {}
        subject = fact.get("subject")
        target = obj.get("target")
        relation = obj.get("relation")
        if obj.get("anchor_kind") and isinstance(subject, str) and subject.startswith("ch"):
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
    for event in events:
        if event not in events:
            events.append(event)
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
    )


def run_rules(doc, facts, intake, tags, graph, mentions, layer_b: bool) -> tuple[list[dict], list[dict]]:
    primary = intake.get("primary_canon_source")
    opted = set((intake.get("profile") or {}).get("opt_out") or [])
    items: list[dict] = []
    ran: set[str] = set()
    if "CANON.DIVERGENCE" not in opted:
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
                    "evidence": [{"kind": "file", "path": "facts.json", "field": notice["ids"][0]}],
                    "fact_ids": notice["ids"],
                    "depends_on_hash": coverage["depends_on_hash"],
                }
            )
    ran.add("LEDGER.CONFLICT")
    aliases = [fact["object"] for fact in facts if fact.get("predicate") == "alias"]
    items.extend(name_spelling(doc.paragraphs, [str(alias) for alias in aliases]))
    ran.add("CANON.NAME_SPELLING")
    items.extend(ao3_schema(tags))
    ran.add("AO3.SCHEMA")
    items.extend(ao3_tag_format(tags))
    ran.add("AO3.TAG_FORMAT")
    lens = []
    for rule in MVP_RULES:
        if rule in opted:
            lens.append({"rule_id": rule, "state": "skipped", "reason": "opted_out"})
        elif rule in {"OOC.VOICE", "CANON.RAILS"} and not layer_b:
            lens.append({"rule_id": rule, "state": "skipped", "reason": "layer_a_only"})
        elif rule in ran:
            lens.append({"rule_id": rule, "state": "applied", "reason": ""})
        else:
            lens.append({"rule_id": rule, "state": "skipped", "reason": "not_built"})
    findings = [item for item in items if item.get("item_state") == "finding"]
    blockers = [item for item in findings if item.get("severity") == "blocker"]
    if coverage["covered"] == 0:
        summary = (
            f"{len(findings)} findings. {len(blockers)} blockers. "
            "No status facts are confirmed for the main cast."
        )
    else:
        summary = f"{len(findings)} findings. {len(blockers)} blockers."
    return items, lens, summary  # type: ignore[return-value]


def build_mentions(doc, facts) -> list[dict]:
    return detect_mentions(doc.paragraphs, alias_map_from_facts(facts))
