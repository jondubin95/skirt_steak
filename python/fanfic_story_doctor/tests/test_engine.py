"""Acceptance tests for the Layer A engine. Invented Ashfall cast only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from doctor.cli import build_report, load_canon, main, run_work
from doctor.factstore import mark_conflicts
from doctor.ids import compare_ids
from doctor.intake import IntakeError, load_intake, load_tags
from doctor.later import cache_key, vote
from doctor.normalize import (
    content_hash,
    normalize_html,
    normalize_markdown,
    normalize_sources,
)
from doctor.pipeline import build_mentions, graph_from, run_rules
from doctor.render import render
from doctor.resolve import RESOLVED, UNRESOLVED, resolve
from doctor.rules import ao3_schema, dead_reappears
from doctor.timeline import (
    AFTER,
    BEFORE,
    NO,
    UNKNOWN,
    YES,
    SceneNode,
    build_graph,
    compare,
    covers,
)
from doctor.validate_output import validate_report

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


def test_id_order_scene_and_chapter_100():
    assert compare_ids("ch02.s2.p1", "ch02.s10.p1") < 0
    assert compare_ids("ch99.s1.p1", "ch100.s1.p1") < 0


def test_two_chapters_three_breaks_and_author_notes():
    text = "\n".join(
        [
            "Mara walked in.",
            "",
            "A/N: ignore this note",
            "",
            "***",
            "",
            "She stopped.",
            "",
            "* * *",
            "",
            "Then she left.",
            "",
            "---",
            "",
            "The end.",
        ]
    )
    doc = normalize_sources(
        [("ch01.md", text), ("ch02.md", "Second chapter starts.\n\nAnd continues.")]
    )
    assert [p.id for p in doc.paragraphs] == [
        "ch01.s1.p1",
        "ch01.s2.p1",
        "ch01.s3.p1",
        "ch01.s4.p1",
        "ch02.s1.p1",
        "ch02.s1.p2",
    ]
    assert doc.author_notes == ["A/N: ignore this note"]
    assert "ignore this note" not in " ".join(p.text for p in doc.paragraphs)


def test_hard_wrap_and_quotes_and_stable_hash():
    raw = "Mara\nwalked into\nthe camp."
    curly = "Mara\u2019s \u201ceyes\u201d \u2014 wide\u2026"
    one = normalize_markdown(raw + "\n\n" + curly, chapter=1)
    two = normalize_markdown(raw + "\n\n" + curly, chapter=1)
    assert one.paragraphs[0].text == "Mara walked into the camp."
    assert one.paragraphs[1].text == 'Mara\'s "eyes" - wide...'
    assert [p.content_hash for p in one.paragraphs] == [
        p.content_hash for p in two.paragraphs
    ]
    assert one.paragraphs[0].content_hash == content_hash(one.paragraphs[0].text)


def test_html_matches_markdown_ids():
    html = """
    <div id="feedback">site chrome</div>
    <div class="notes">A/N: hello</div>
    <div class="userstuff"><p>Mara walked in.</p><hr><p>She stopped.</p></div>
    """
    html_doc = normalize_html(html, chapter=1)
    md_doc = normalize_markdown("Mara walked in.\n\n***\n\nShe stopped.", chapter=1)
    assert [p.id for p in html_doc.paragraphs] == [p.id for p in md_doc.paragraphs]
    assert [p.text for p in html_doc.paragraphs] == [p.text for p in md_doc.paragraphs]
    assert all("chrome" not in p.text for p in html_doc.paragraphs)
    assert html_doc.author_notes


def test_intake_seeds_and_rejects():
    data = yaml.safe_load(
        (ROOT / "tests" / "fixtures" / "ashfall" / "intake.yaml").read_text(
            encoding="utf-8"
        )
    )
    _intake, facts = load_intake(data)
    assert any(fact["confirmation_method"] == "intake_inherited" for fact in facts)
    assert any(
        fact["predicate"] == "alias" and fact["object"] == "Mara" for fact in facts
    )
    bad = dict(data)
    bad["primary_canon_source"] = "missing"
    with pytest.raises(IntakeError):
        load_intake(bad)
    tags = {
        "rating": "Teen And Up Audiences",
        "archive_warnings": ["Major Character Death"],
        "fandoms": ["Ashfall"],
        "title": "After",
    }
    missing = ao3_schema(load_tags(tags))
    assert (
        len(missing) == 1
        and missing[0]["symptom"] == "Required AO3 field missing: language."
    )
    assert ao3_schema(load_tags({**tags, "language": "English"})) == []
    with pytest.raises(IntakeError):
        load_tags({**tags, "rating": "PG-13"})


def test_conflict_and_claim():
    graph = build_graph(
        [SceneNode("ch01.s1")], ["ev-bridge"], [], paragraph_ids=["ch01.s1.p1"]
    )
    alive = {
        "id": "f1",
        "subject": "teodor",
        "predicate": "status",
        "object": "alive",
        "layer": "ledger",
        "status": "confirmed",
        "assertion": "state",
        "citation_state": "ok",
    }
    dead = dict(alive)
    dead["id"] = "f2"
    dead["object"] = "dead"
    facts = [alive, dead]
    mark_conflicts(facts, graph)
    assert alive["status"] == "disputed" and dead["status"] == "disputed"
    assert alive["conflict_set"] == dead["conflict_set"]

    early = {
        "id": "a",
        "subject": "teodor",
        "predicate": "status",
        "object": "alive",
        "layer": "ledger",
        "status": "confirmed",
        "assertion": "state",
        "citation_state": "ok",
        "interval": {"to": {"story": "ev-bridge"}},
    }
    late = dict(early)
    late["id"] = "b"
    late["object"] = "dead"
    late["interval"] = {"from": {"story": "ev-bridge"}}
    g2 = build_graph(
        [SceneNode("ch01.s1"), SceneNode("ch02.s1")],
        ["ev-bridge"],
        [("ch01.s1", "ev-bridge"), ("ev-bridge", "ch02.s1")],
        paragraph_ids=["ch01.s1.p1", "ch02.s1.p1"],
    )
    pair = [early, late]
    mark_conflicts(pair, g2)
    assert early["status"] == "confirmed" and late["status"] == "confirmed"

    ledger = dict(alive)
    ledger["status"] = "confirmed"
    ledger["conflict_set"] = None
    au = dict(ledger)
    au["id"] = "au1"
    au["layer"] = "au"
    au["object"] = "dead"
    notices = mark_conflicts([ledger, au], graph)
    assert ledger["status"] == "confirmed"
    assert any(note["kind"] == "coverage" for note in notices)

    claim = dict(alive)
    claim["id"] = "c"
    claim["status"] = "confirmed"
    claim["assertion"] = "claim"
    claim["claimant"] = "ilsa"
    state, _value, _ids = resolve(
        [claim], "teodor", "status", "ch01.s1.p1", graph, "books"
    )
    assert state == RESOLVED and _value == "unspecified"


def _dead_from_bridge():
    return {
        "id": "f-canon-001",
        "subject": "teodor",
        "predicate": "status",
        "object": "dead",
        "layer": "canon:books",
        "status": "confirmed",
        "assertion": "state",
        "citation_state": "ok",
        "interval": {"from": {"story": "ev-bridge"}},
    }


def test_e1_through_e8_and_same_class():
    fact = _dead_from_bridge()
    e1 = build_graph(
        [
            SceneNode("ch01.s1"),
            SceneNode("ch06.s1"),
            SceneNode("ch07.s1", anchor_kind="flashback"),
            SceneNode("ch07.s2"),
        ],
        ["ev-bridge"],
        [("ev-bridge", "ch01.s1"), ("ch07.s1", "ev-bridge")],
        paragraph_ids=["ch07.s1.p4", "ch07.s2.p1"],
    )
    assert compare(e1, ("ev-bridge", None), ("ch07.s1", 4)) == AFTER
    assert covers(e1, fact, "ch07.s1.p4") == NO
    assert ("ch06.s1", "ch07.s2") in e1.default_before
    assert ("ch07.s1", "ch07.s2") not in e1.default_before

    e2 = build_graph(
        [SceneNode("ch01.s1"), SceneNode("ch03.s2", anchor_kind="time_skip")],
        ["ev-bridge"],
        [("ch01.s1", "ev-bridge"), ("ev-bridge", "ch03.s2")],
    )
    assert covers(e2, fact, "ch03.s2.p1") == YES

    e3 = build_graph(
        [SceneNode("ch04.s1")], ["ev-bridge", "ev-wedding"], [("ev-bridge", "ch01.s1")]
    )
    # ch01 not in scenes; wedding disconnected from ch04
    assert compare(e3, ("ev-wedding", None), ("ch04.s1", 1)) == UNKNOWN

    e4 = build_graph(
        [SceneNode("ch05.s1")],
        ["ev-siege", "ev-bridge"],
        [("ev-siege", "ev-bridge"), ("ev-bridge", "ch05.s1"), ("ch05.s1", "ev-siege")],
    )
    assert e4.contradicted
    assert compare(e4, ("ev-bridge", None), ("ch05.s1", 1)) == UNKNOWN

    e5 = build_graph(
        [SceneNode(f"ch0{i}.s1") for i in range(1, 5)],
        ["ev-bridge"],
        [("ev-bridge", "ch01.s1"), ("ch04.s1", "ev-bridge")],
    )
    assert ("ch03.s1", "ch04.s1") in e5.dropped_defaults
    assert not e5.contradicted

    e6 = build_graph(
        [
            SceneNode("ch02.s3", anchor_kind="flashback"),
            SceneNode("ch06.s2", anchor_kind="flashback"),
        ],
        ["ev-bridge"],
        [("ch02.s3", "ev-bridge"), ("ch06.s2", "ev-bridge")],
    )
    assert compare(e6, ("ch02.s3", 1), ("ch06.s2", 1)) == UNKNOWN

    e7 = build_graph(
        [SceneNode("ch01.s1"), SceneNode("ch02.s1")],
        ["ev-book1-start", "ev-bridge"],
        [("ch01.s1", "ev-book1-start"), ("ev-book1-start", "ev-bridge")],
        window_before="ev-book1-start",
    )
    assert covers(e7, fact, "ch02.s1.p3") == NO
    state, value, _ids = resolve([fact], "teodor", "status", "ch02.s1.p3", e7, "books")
    assert state == RESOLVED and value == "unspecified"

    au = dict(fact)
    au["id"] = "f-au-002"
    au["layer"] = "au"
    au["object"] = "alive"
    post = build_graph(
        [SceneNode("ch04.s2")], ["ev-bridge"], [("ev-bridge", "ch04.s2")]
    )
    state, value, _ids = resolve(
        [fact, au], "teodor", "status", "ch04.s2.p5", post, "books"
    )
    assert state == RESOLVED and value == "alive"

    same = build_graph(
        [SceneNode("ch01.s1")],
        ["ev-bridge"],
        [],
        same_pairs=[("ev-bridge", "ch01.s1")],
        paragraph_ids=["ch01.s1.p1", "ch01.s1.p6"],
    )
    assert covers(same, fact, "ch01.s1.p1") == UNKNOWN
    work = dict(fact)
    work["interval"] = {"from": {"work": "ch01.s1.p5"}}
    assert covers(same, work, "ch01.s1.p6") == YES
    assert covers(same, work, "ch01.s1.p1") == NO

    # The pre-canon rule is scoped to the intake window event. Without a
    # `before` window, a later chapter is not pulled before the event.
    unscoped = build_graph(
        [SceneNode("ch01.s1"), SceneNode("ch09.s1")],
        ["ev-bridge"],
        [("ch01.s1", "ev-bridge")],
    )
    assert compare(unscoped, ("ch09.s1", 1), ("ev-bridge", None)) == UNKNOWN
    scoped = build_graph(
        [SceneNode("ch01.s1"), SceneNode("ch09.s1")],
        ["ev-bridge", "ev-other"],
        [("ch01.s1", "ev-bridge"), ("ch01.s1", "ev-other")],
        window_before="ev-bridge",
    )
    assert compare(scoped, ("ch09.s1", 1), ("ev-bridge", None)) == BEFORE
    assert compare(scoped, ("ch09.s1", 1), ("ev-other", None)) == UNKNOWN

    one = build_graph([SceneNode("ch01.s1")], ["ev-bridge"], [("ev-bridge", "ch01.s1")])
    two = build_graph([SceneNode("ch01.s1")], ["ev-bridge"], [("ev-bridge", "ch01.s1")])
    assert one.default_before == two.default_before
    assert one.dropped_defaults == two.dropped_defaults


def test_stale_blocks_lower_layer():
    graph = build_graph(
        [SceneNode("ch04.s2")], ["ev-bridge"], [("ev-bridge", "ch04.s2")]
    )
    stale = _dead_from_bridge()
    stale["layer"] = "ledger"
    stale["citation_state"] = "stale"
    au = dict(stale)
    au["id"] = "au"
    au["layer"] = "au"
    au["object"] = "alive"
    au["citation_state"] = "ok"
    state, value, _ids = resolve(
        [stale, au], "teodor", "status", "ch04.s2.p1", graph, "books"
    )
    assert state == UNRESOLVED and value is None


def _report_rows(report: dict, rule: str) -> list[tuple[str, str]]:
    return [
        (item["item_state"], item["severity"])
        for item in report["items"]
        if item["rule_id"] == rule
    ]


def test_canon_divergence_and_report(tmp_path: Path):
    work = ROOT / "tests" / "fixtures" / "ashfall"
    report = build_report(work, home=tmp_path)
    # Ledger puts ev-bridge before ev-start; canon says the reverse. The work is
    # set before ev-bridge, the declared branch, so this is a should finding.
    assert _report_rows(report, "CANON.DIVERGENCE") == [("finding", "should")]
    # A deliberate divergence is not a timeline cycle.
    assert _report_rows(report, "CONT.TIMELINE_ORDER") == []
    spelling = [
        item for item in report["items"] if item["rule_id"] == "CANON.NAME_SPELLING"
    ]
    assert [item["evidence"][0]["quote"] for item in spelling] == ["Teodr"]
    schema = [item for item in report["items"] if item["rule_id"] == "AO3.SCHEMA"]
    assert [item["symptom"] for item in schema] == [
        "Required AO3 field missing: language."
    ]
    assert report["summary"].startswith("3 findings. 0 blockers.")
    text = run_work(work, home=tmp_path)
    assert text == run_work(work, home=tmp_path)
    assert "rewrite as" not in text.lower()


def _divergence_case(
    is_au=True,
    divergence="ev-x",
    window=("after", "ev-x"),
    au_rows=None,
    canon_status="confirmed",
    citation_state="ok",
):
    intake = {
        "canon_sources": [{"id": "books"}],
        "primary_canon_source": "books",
        "window": {"relation": window[0], "event": window[1]},
        "events": [
            {"id": event, "layer": "canon"} for event in ("ev-x", "ev-a", "ev-b")
        ],
        "canon_event_order": [],
        "main_cast": [],
        "au": {"is_au": is_au, "divergence_event": divergence},
    }
    intake, seeded = load_intake(intake)
    doc = normalize_sources([("ch01.md", "The duel came first.")])
    canon = [
        {
            "id": "c-xa",
            "subject": "ev-a",
            "predicate": "event_order",
            "object": {"relation": "after", "target": "ev-x"},
            "layer": "canon:books",
            "status": "confirmed",
        },
        {
            "id": "c-ab",
            "subject": "ev-b",
            "predicate": "event_order",
            "object": {"relation": "after", "target": "ev-a"},
            "layer": "canon:books",
            "status": canon_status,
            "citation_state": citation_state,
        },
    ]
    ledger = {
        "id": "L",
        "subject": "ev-b",
        "predicate": "event_order",
        "object": {"relation": "before", "target": "ev-a"},
        "layer": "ledger",
        "status": "confirmed",
        "citation": {"at": "ch01.s1.p1", "text": "The duel"},
    }
    facts = seeded + canon + [ledger] + list(au_rows or [])
    graph = graph_from(doc, facts, intake)
    items, _lens, summary = run_rules(doc, facts, intake, None, graph, [], False)
    return items, summary


def _rows(items, rule="CANON.DIVERGENCE"):
    return [
        (item["item_state"], item["severity"])
        for item in items
        if item["rule_id"] == rule
    ]


def test_canon_divergence_classification():
    # After the branch: coverage, and no timeline blocker.
    items, summary = _divergence_case()
    assert _rows(items) == [("coverage", "info")]
    assert _rows(items, "CONT.TIMELINE_ORDER") == []
    assert summary.startswith("0 findings. 0 blockers.")
    # Before the branch: finding, severity should.
    items, _ = _divergence_case(divergence="ev-x", window=("before", "ev-x"))
    assert _rows(items) == [("finding", "should")]
    # Not declared AU: info, never a finding.
    items, summary = _divergence_case(is_au=False)
    assert _rows(items) == [("info", "info")]
    assert summary.startswith("0 findings.")
    # Declared AU, no divergence event: info plus one intake question.
    items, _ = _divergence_case(divergence=None)
    assert _rows(items) == [("info", "info"), ("question", "info")]
    assert [item["kind"] for item in items if item["item_state"] == "question"] == [
        "DIVERGENCE_EVENT"
    ]
    # Unordered against the branch: unverifiable plus a TIMELINE_ANCHOR question.
    items, _ = _divergence_case(window=("after", "ev-b"))
    assert _rows(items) == [("unverifiable", "info"), ("question", "info")]
    assert [item["kind"] for item in items if item["item_state"] == "question"] == [
        "TIMELINE_ANCHOR"
    ]
    # AU override with the ledger's order: coverage at any point.
    au = {
        "id": "au1",
        "subject": "ev-b",
        "predicate": "event_order",
        "object": {"relation": "before", "target": "ev-a"},
        "layer": "au",
        "status": "confirmed",
    }
    items, _ = _divergence_case(window=("before", "ev-x"), au_rows=[au])
    assert _rows(items) == [("coverage", "info")]
    # Stale or disputed canon: unverifiable, no fall-through.
    for status, citation in (("confirmed", "stale"), ("disputed", "ok")):
        items, _ = _divergence_case(canon_status=status, citation_state=citation)
        assert _rows(items) == [("unverifiable", "info")]


def test_validator_rejects_unknown_quote_and_rewrite():
    paragraphs = {"ch01.s1.p1": "Mara walked"}
    report = {
        "summary": "x",
        "lens": [{"rule_id": "CANON.DIVERGENCE", "state": "applied", "reason": ""}],
        "items": [
            {
                "rule_id": "CANON.DIVERGENCE",
                "item_state": "finding",
                "tier": "A1",
                "severity": "should",
                "kind": "internal_inconsistency",
                "symptom": "nope",
                "evidence": [
                    {
                        "kind": "prose",
                        "paragraph_id": "ch01.s1.p1",
                        "quote": "not in text",
                    }
                ],
                "fact_ids": [],
                "depends_on_hash": "abc",
            }
        ],
    }
    assert validate_report(report, paragraphs, {})
    report["items"][0]["evidence"][0]["quote"] = "Mara"
    report["items"][0]["suggested_fix"] = "rewrite as something else entirely"
    assert validate_report(report, paragraphs, {})
    report["items"][0]["suggested_fix"] = None
    report["extra"] = True
    assert validate_report(report, paragraphs, {})


def test_mentions_are_alias_exact_and_markers_uncertain():
    doc = normalize_markdown(
        'Mara asked for Teodor.\n\n"Three years earlier," she said.', chapter=5
    )
    facts = [
        {
            "predicate": "alias",
            "object": "Mara",
            "subject": "mara",
            "status": "confirmed",
        },
        {
            "predicate": "alias",
            "object": "Teodor",
            "subject": "teodor",
            "status": "confirmed",
        },
    ]
    notes = build_mentions(doc, facts)
    assert {note["entity"] for note in notes} == {"mara", "teodor"}
    intake = {
        "events": [{"id": "ev-bridge"}],
        "window": {"relation": "after", "event": "ev-bridge"},
        "primary_canon_source": "books",
    }
    graph = graph_from(doc, [], intake)
    assert any(scene.uncertain for scene in graph.scenes)


def test_canon_load_refuses_repo_and_missing_quote(tmp_path: Path):
    inside = ROOT / "drafts"
    inside.mkdir(exist_ok=True)
    ledger = inside / "facts.json"
    ledger.write_text("[]", encoding="utf-8")
    with pytest.raises(SystemExit):
        load_canon(ledger)
    ledger.unlink()
    outside = tmp_path / "facts.json"
    chapter = tmp_path / "text"
    chapter.mkdir()
    (chapter / "ch01.md").write_text("Mara crossed the bridge.", encoding="utf-8")
    outside.write_text(
        json.dumps(
            [
                {
                    "id": "f-canon-1",
                    "subject": "mara",
                    "predicate": "alias",
                    "object": "Mara",
                    "layer": "canon:books",
                    "status": "confirmed",
                    "assertion": "state",
                    "citation_state": "ok",
                    "citation": {"text": "not in the chapter", "at": "ch01.s1.p1"},
                }
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit):
        load_canon(outside, chapter)
    good = json.loads(outside.read_text(encoding="utf-8"))
    good[0]["citation"]["text"] = "Mara crossed"
    good[0]["status"] = "proposed"
    outside.write_text(json.dumps(good), encoding="utf-8")
    assert load_canon(outside, chapter) == []


def test_vote_and_cache_key():
    voted = vote(
        [
            {"label": "on_rails", "votes": 1},
            {"label": "on_rails", "votes": 1},
            {"label": "drift", "votes": 3},
            {"label": "consequence_shown", "votes": 1},
            {"label": "in_voice", "votes": 1},
            {"label": "made_up", "votes": 3},
        ]
    )
    by_label = {note["label"]: note["agreement"] for note in voted}
    assert by_label == {
        "on_rails": "2_of_3",
        "drift": "3_of_3",
        "consequence_shown": "low_agreement",
    }
    assert cache_key("a", "r", "m", "c") != cache_key("b", "r", "m", "c")


def test_measure_synthetic_chapters(tmp_path: Path):
    """The real-chapter measurement uses this counter. Her chapters are not in the repo."""
    doc = normalize_markdown("Mara looked for Teodor. She waved.", chapter=1)
    notes = build_mentions(
        doc,
        [
            {
                "predicate": "alias",
                "object": "Mara",
                "subject": "mara",
                "status": "confirmed",
            },
            {
                "predicate": "alias",
                "object": "Teodor",
                "subject": "teodor",
                "status": "confirmed",
            },
        ],
    )
    summary = {
        "alias_hits": len(notes),
        "paragraphs": len(doc.paragraphs),
        "predicate": "event_order",
    }
    dest = tmp_path / "measure.json"
    dest.write_text(json.dumps(summary), encoding="utf-8")
    assert json.loads(dest.read_text(encoding="utf-8"))["alias_hits"] == 2


def test_layer_a_report_on_fixture(tmp_path: Path):
    work = ROOT / "tests" / "fixtures" / "ashfall"
    report = build_report(work, home=tmp_path)
    assert report["summary"] == (
        "3 findings. 0 blockers. No status facts are confirmed for the main cast."
    )
    assert [(i["rule_id"], i["item_state"], i["severity"]) for i in report["items"]] == [
        ("CANON.DIVERGENCE", "finding", "should"),
        ("LEDGER.COVERAGE", "coverage", "info"),
        ("CANON.NAME_SPELLING", "finding", "info"),
        ("AO3.SCHEMA", "finding", "should"),
    ]
    skipped = {r["rule_id"]: r["reason"] for r in report["lens"] if r["state"] != "applied"}
    assert skipped == {"OOC.VOICE": "layer_a_only", "CANON.RAILS": "layer_a_only"}
    text = run_work(work, home=tmp_path)
    assert text == render(report)
    assert (
        "- [finding] CANON.NAME_SPELLING: Teodr is near the alias Teodor and is not itself an alias."
        in text.splitlines()
    )


def test_validator_rewrite_markers_with_space():
    paragraphs = {"ch01.s1.p1": "Mara walked"}
    for text in (
        "try: Mara runs",
        "For example: she runs",
        "Rewrite as she runs",
        "replace with a run",
    ):
        report = {
            "summary": "x",
            "lens": [],
            "items": [
                {
                    "rule_id": "R",
                    "item_state": "finding",
                    "tier": "A1",
                    "severity": "info",
                    "kind": "k",
                    "symptom": "ok",
                    "suggested_fix": text,
                    "evidence": [],
                    "fact_ids": [],
                    "depends_on_hash": "h",
                }
            ],
        }
        assert validate_report(report, paragraphs, {}) == ["never-rewrite: R"], text
    report["items"][0]["suggested_fix"] = "Consider placing the scene later."
    assert validate_report(report, paragraphs, {}) == []


def test_doctor_home_canon_loads_in_run(tmp_path: Path):
    work = ROOT / "tests" / "fixtures" / "ashfall"
    home = tmp_path / "home"
    (home / "canon" / "books").mkdir(parents=True)
    disputed = {
        "id": "f-home-1",
        "subject": "ev-bridge",
        "predicate": "event_order",
        "object": {"relation": "after", "target": "ev-start"},
        "layer": "canon:books",
        "status": "disputed",
        "assertion": "state",
        "citation_state": "ok",
    }
    (home / "canon" / "books" / "facts.json").write_text(
        json.dumps([disputed]), encoding="utf-8"
    )
    report = build_report(work, home=home)
    ids = {fid for item in report["items"] for fid in item.get("fact_ids", [])}
    assert (
        "f-home-1" not in ids
    )  # the intake canon row still decides; disputed home row is loaded but not enforced
    assert _report_rows(report, "CANON.DIVERGENCE") == [("finding", "should")]


def test_canon_load_guard_does_not_depend_on_install_location(
    tmp_path: Path, monkeypatch
):
    inside = ROOT / "cache"
    inside.mkdir(exist_ok=True)
    ledger = inside / "guard-facts.json"
    ledger.write_text("[]", encoding="utf-8")
    try:
        monkeypatch.chdir(tmp_path)  # not inside the repo
        with pytest.raises(SystemExit):
            load_canon(ledger)
    finally:
        ledger.unlink()
    outside = tmp_path / "facts.json"
    outside.write_text("[]", encoding="utf-8")
    monkeypatch.chdir(REPO)
    assert load_canon(outside) == []


def test_chapter_files_merge_in_numeric_order():
    doc = normalize_sources(
        [("ch2.md", "Second.\n"), ("ch10.md", "Tenth.\n"), ("ch1.md", "First.\n")]
    )
    assert [p.id for p in doc.paragraphs] == [
        "ch01.s1.p1",
        "ch02.s1.p1",
        "ch10.s1.p1",
    ]
    assert doc.scene_ids == ["ch01.s1", "ch02.s1", "ch10.s1"]


def test_duplicate_explicit_chapter_raises():
    with pytest.raises(ValueError, match="ch01.md") as exc:
        normalize_sources(
            [("ch01.md", "One.\n"), ("chapter-1-draft.md", "Two.\n")]
        )
    assert "chapter-1-draft.md" in str(exc.value)


def test_no_digit_filename_does_not_collide():
    doc = normalize_sources([("notes.md", "A note.\n"), ("ch01.md", "Mara.\n")])
    assert [p.chapter for p in doc.paragraphs] == [1, 1]


def test_multichapter_html_is_exempt():
    from test_real_fic_fixes import AO3_WORK

    doc = normalize_sources([("work.html", AO3_WORK), ("ch01.md", "Mara waited.\n")])
    assert doc.paragraphs


def test_duplicate_chapter_exits_cleanly(tmp_path: Path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "intake.yaml").write_text(
        (ROOT / "tests" / "fixtures" / "ashfall" / "intake.yaml").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    (work / "ch01.md").write_text("One.\n", encoding="utf-8")
    (work / "chapter-1-draft.md").write_text("Two.\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="duplicate chapter"):
        main(["run", str(work)])


def test_ao3_lens_skips_without_tags(tmp_path: Path):
    doc = normalize_sources([("ch01.md", "Mara walked.")])
    intake = {
        "window": {"relation": "after", "event": "ev-bridge"},
        "events": [],
        "primary_canon_source": "books",
    }
    graph = graph_from(doc, [], intake)
    items, lens, _summary = run_rules(doc, [], intake, None, graph, [], False)
    states = {row["rule_id"]: (row["state"], row["reason"]) for row in lens}
    assert states["AO3.SCHEMA"] == ("skipped", "no_tags_yaml")
    assert states["AO3.TAG_FORMAT"] == ("skipped", "no_tags_yaml")
    assert not [item for item in items if item["rule_id"].startswith("AO3.")]
    _items, lens_b, _ = run_rules(doc, [], intake, None, graph, [], True)
    assert {row["rule_id"]: row["reason"] for row in lens_b}[
        "CANON.RAILS"
    ] == "layer_b_pending"
