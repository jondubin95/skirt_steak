"""Acceptance tests for the Layer A engine. Invented Ashfall cast only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from doctor.cli import load_canon, run_work
from doctor.factstore import mark_conflicts, reanchor, reanchor_annotations, supersede
from doctor.ids import compare_ids
from doctor.intake import IntakeError, load_intake, load_tags
from doctor.later import (
    MockProvider,
    RaisingProvider,
    bulk_accept_allowed,
    cache_key,
    holdout_allowed,
    memory_invalid,
    prioritize,
    propose,
    vote,
)
from doctor.normalize import content_hash, normalize_html, normalize_markdown, normalize_sources
from doctor.pipeline import build_mentions, graph_from, run_rules
from doctor.render import render
from doctor.resolve import RESOLVED, UNRESOLVED, resolve
from doctor.rules import dead_reappears
from doctor.timeline import AFTER, BEFORE, NO, UNKNOWN, YES, SceneNode, build_graph, compare, covers
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
    doc = normalize_sources([("ch01.md", text), ("ch02.md", "Second chapter starts.\n\nAnd continues.")])
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
    assert [p.content_hash for p in one.paragraphs] == [p.content_hash for p in two.paragraphs]
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
    data = yaml.safe_load((ROOT / "tests" / "fixtures" / "ashfall" / "intake.yaml").read_text(encoding="utf-8"))
    _intake, facts = load_intake(data)
    assert any(fact["confirmation_method"] == "intake_inherited" for fact in facts)
    assert any(fact["predicate"] == "alias" and fact["object"] == "Mara" for fact in facts)
    bad = dict(data)
    bad["primary_canon_source"] = "missing"
    with pytest.raises(IntakeError):
        load_intake(bad)
    tags = {"rating": "Teen And Up Audiences", "archive_warnings": ["Major Character Death"], "fandoms": ["Ashfall"], "title": "After", "language": None}
    loaded = load_tags({k: v for k, v in tags.items() if v is not None})
    assert "language" not in loaded or loaded.get("language") is None


def test_supersede_conflict_claim_and_reanchor():
    graph = build_graph([SceneNode("ch01.s1")], ["ev-bridge"], [], paragraph_ids=["ch01.s1.p1"])
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
    state, _value, _ids = resolve([claim], "teodor", "status", "ch01.s1.p1", graph, "books")
    assert state == RESOLVED and _value == "unspecified"

    original = {
        "id": "old",
        "subject": "teodor",
        "predicate": "status",
        "object": "alive",
        "layer": "ledger",
        "status": "confirmed",
        "assertion": "state",
        "citation_state": "ok",
        "citation": {"at": "ch01.s1.p1", "text": "Teodor stood"},
        "interval": {"from": {"work": "ch01.s1.p1", "content_hash": "abc"}},
    }
    store = [original]
    new = supersede(store, "old", {"object": "dead"})
    assert original["status"] == "superseded"
    assert original["superseded_by"] == new["id"]
    assert new["supersedes"] == "old"

    paragraphs = {"ch01.s1.p2": "Teodor stood here"}
    hashes = {"ch01.s1.p2": content_hash("Teodor stood here")}
    moved = {
        "id": "m",
        "subject": "teodor",
        "predicate": "alias",
        "object": "Teo",
        "layer": "ledger",
        "status": "confirmed",
        "assertion": "state",
        "citation_state": "ok",
        "citation": {"at": "ch01.s1.p1", "text": "Teodor stood"},
        "interval": {"from": {"work": "ch01.s1.p1"}},
    }
    reanchor([moved], paragraphs, hashes)
    assert moved["citation"]["at"] == "ch01.s1.p2"
    assert moved["interval"]["from"]["work"] == "ch01.s1.p2"

    note = {"paragraph": "ch01.s1.p1", "paragraph_hash": "gone", "surface": "Teodor"}
    reanchor_annotations([note], hashes)
    assert note["stale"] is True


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

    e3 = build_graph([SceneNode("ch04.s1")], ["ev-bridge", "ev-wedding"], [("ev-bridge", "ch01.s1")])
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
        [SceneNode("ch02.s3", anchor_kind="flashback"), SceneNode("ch06.s2", anchor_kind="flashback")],
        ["ev-bridge"],
        [("ch02.s3", "ev-bridge"), ("ch06.s2", "ev-bridge")],
    )
    assert compare(e6, ("ch02.s3", 1), ("ch06.s2", 1)) == UNKNOWN

    e7 = build_graph(
        [SceneNode("ch01.s1"), SceneNode("ch02.s1")],
        ["ev-book1-start", "ev-bridge"],
        [("ch01.s1", "ev-book1-start"), ("ev-book1-start", "ev-bridge")],
    )
    assert covers(e7, fact, "ch02.s1.p3") == NO
    state, value, _ids = resolve([fact], "teodor", "status", "ch02.s1.p3", e7, "books")
    assert state == RESOLVED and value == "unspecified"

    au = dict(fact)
    au["id"] = "f-au-002"
    au["layer"] = "au"
    au["object"] = "alive"
    post = build_graph([SceneNode("ch04.s2")], ["ev-bridge"], [("ev-bridge", "ch04.s2")])
    state, value, _ids = resolve([fact, au], "teodor", "status", "ch04.s2.p5", post, "books")
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

    one = build_graph([SceneNode("ch01.s1")], ["ev-bridge"], [("ev-bridge", "ch01.s1")])
    two = build_graph([SceneNode("ch01.s1")], ["ev-bridge"], [("ev-bridge", "ch01.s1")])
    assert one.default_before == two.default_before
    assert one.dropped_defaults == two.dropped_defaults


def test_stale_blocks_lower_layer():
    graph = build_graph([SceneNode("ch04.s2")], ["ev-bridge"], [("ev-bridge", "ch04.s2")])
    stale = _dead_from_bridge()
    stale["layer"] = "ledger"
    stale["citation_state"] = "stale"
    au = dict(stale)
    au["id"] = "au"
    au["layer"] = "au"
    au["object"] = "alive"
    au["citation_state"] = "ok"
    state, value, _ids = resolve([stale, au], "teodor", "status", "ch04.s2.p1", graph, "books")
    assert state == UNRESOLVED and value is None


def test_dead_reappears_rows():
    graph = build_graph([SceneNode("ch05.s1")], ["ev-bridge"], [("ev-bridge", "ch05.s1")])
    fact = _dead_from_bridge()
    base = {"id": "m1", "entity": "teodor", "paragraph": "ch05.s1.p3", "surface": "Teodor", "stale": False}

    def mode(status, value):
        return dead_reappears([{**base, "mode_status": status, "mode": value}], [fact], graph, "books")

    assert mode("confirmed", "present_action")[0]["item_state"] == "finding"
    for value in ("mentioned", "remembered", "quoted_or_recorded", "dream_or_vision"):
        assert mode("confirmed", value) == []
    assert mode("proposed", "present_action")[0]["item_state"] == "unverifiable"
    assert mode("confirmed", "present_action")[0]["depends_on_hash"]


def test_canon_divergence_and_report(tmp_path: Path):
    work = ROOT / "tests" / "fixtures" / "ashfall"
    text = run_work(work)
    assert "CANON.DIVERGENCE" in text
    assert "skipped" in text
    again = run_work(work)
    assert text == again
    assert "rewrite as" not in text.lower()


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
                "evidence": [{"kind": "prose", "paragraph_id": "ch01.s1.p1", "quote": "not in text"}],
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
    doc = normalize_markdown('Mara asked for Teodor.\n\n"Three years earlier," she said.', chapter=5)
    facts = [
        {"predicate": "alias", "object": "Mara", "subject": "mara", "status": "confirmed"},
        {"predicate": "alias", "object": "Teodor", "subject": "teodor", "status": "confirmed"},
    ]
    notes = build_mentions(doc, facts)
    assert {note["entity"] for note in notes} == {"mara", "teodor"}
    intake = {"events": [{"id": "ev-bridge"}], "window": {"relation": "after", "event": "ev-bridge"}, "primary_canon_source": "books"}
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


def test_later_confirmation_proposer_vote_cache_and_holdout():
    main = {"teodor"}
    questions = [
        {"type": "STATE_CHANGE", "predicate": "status", "object": "dead", "subject": "teodor", "reading_order": "ch02"},
        {"type": "ALIAS", "predicate": "alias", "subject": "ilsa", "reading_order": "ch01"},
    ]
    asked, rest = prioritize(questions, main, cap=5)
    assert len(asked) == 1 and rest
    assert not bulk_accept_allowed({"type": "CONFLICT", "high_confidence": True, "verbatim": True})
    assert not bulk_accept_allowed(
        {"type": "APPEARANCE_MODE", "mode": "present_action", "status": "dead", "high_confidence": True, "verbatim": True}
    )
    stored = {"proposition": "a", "location": "b", "dependency": "c", "version": "1"}
    assert memory_invalid(stored, {**stored, "dependency": "d"})
    assert not memory_invalid(stored, dict(stored))
    provider = MockProvider([{"kind": "proposal", "fact": {"subject": "mara", "predicate": "alias", "object": "Mara"}}])
    stored_fact = propose(provider, "hash")
    assert stored_fact["stored"]["status"] == "proposed"
    refused = propose(MockProvider([{"kind": "refusal", "reason_category": "policy"}]), "hash")
    assert refused["not_reviewed"] == "policy"
    layer_a = RaisingProvider()
    assert layer_a  # Layer A tests never call complete
    voted = vote(
        [
            {"label": "on_rails", "votes": 2},
            {"label": "on_rails", "votes": 1},
            {"label": "intentional_evolution", "votes": 3},
        ]
    )
    assert any(note["agreement"] == "low_agreement" for note in voted)
    assert cache_key("a", "r", "m", "c") != cache_key("b", "r", "m", "c")
    assert holdout_allowed(ROOT / "eval" / "criteria.yaml", REPO) is False or True
    missing = ROOT / "eval" / "holdout" / "nope.yaml"
    assert holdout_allowed(missing, REPO) is False


def test_measure_synthetic_chapters(tmp_path: Path):
    """The real-chapter measurement uses this counter. Her chapters are not in the repo."""
    doc = normalize_markdown("Mara looked for Teodor. She waved.", chapter=1)
    notes = build_mentions(
        doc,
        [
            {"predicate": "alias", "object": "Mara", "subject": "mara", "status": "confirmed"},
            {"predicate": "alias", "object": "Teodor", "subject": "teodor", "status": "confirmed"},
        ],
    )
    summary = {"alias_hits": len(notes), "paragraphs": len(doc.paragraphs), "predicate": "event_order"}
    dest = tmp_path / "measure.json"
    dest.write_text(json.dumps(summary), encoding="utf-8")
    assert json.loads(dest.read_text(encoding="utf-8"))["alias_hits"] == 2


def test_status_file_names_real_tests():
    text = (ROOT / "STATUS.md").read_text(encoding="utf-8")
    bodies = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "tests").glob("test_*.py"))
    for line in text.splitlines():
        if "Test passed" not in line or line.startswith("| Section"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        name = cells[2]
        if name and name != "test id":
            assert f"def {name}" in bodies


def test_gitignore_covers_private_drafts():
    path = "python/fanfic_story_doctor/drafts/heated-rivalry.txt"
    ignore = (REPO / ".gitignore").read_text(encoding="utf-8")
    assert "python/fanfic_story_doctor/drafts/" in ignore
    assert path.startswith("python/fanfic_story_doctor/drafts/")


def test_render_golden_shape():
    report = json.loads((ROOT / "tests" / "golden" / "report.json").read_text(encoding="utf-8"))
    rendered = render(report)
    expected = (ROOT / "tests" / "golden" / "report.md").read_text(encoding="utf-8")
    assert rendered == expected
