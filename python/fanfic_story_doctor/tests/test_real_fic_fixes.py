"""Fixes found by running on a real posted work. Synthetic Ashfall text only."""

from __future__ import annotations

from pathlib import Path

import pytest

import yaml

from doctor.cli import build_report, drop_invalid_items
from doctor.intake import IntakeError, load_intake
from doctor.detect import alias_map_from_facts, ambiguous_aliases
from doctor.normalize import (
    normalize_ao3_work,
    normalize_html,
    normalize_markdown,
    normalize_sources,
)
from doctor.rules import _candidates, name_spelling

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "ashfall"
ALIASES = ["Mara Venn", "Mara", "Venn", "Teodor Venn", "Teodor", "Ilsa", "Brannoch"]


def _spell(text: str, aliases=ALIASES) -> list[str]:
    doc = normalize_markdown(text, chapter=1)
    return [
        item["evidence"][0]["quote"] for item in name_spelling(doc.paragraphs, aliases)
    ]


def test_candidates_never_cross_punctuation_and_are_substrings():
    text = '"Teodor." A gull cried. Fine, Mara. I know. Mara Venn Smiled'
    cands = _candidates(text)
    assert "Teodor A" not in cands and "Mara I" not in cands
    assert all(c in text for c in cands)
    assert "Mara Venn Smiled" in cands


def test_possessives_stammers_and_plural_surnames_are_not_flagged():
    text = "Teodor's coat. Mara\u2019s map. The Venns arrived. The Venns' cart. M-Mara- wait. Teodor- no. Teod- wait. Teodor Venn's oath."
    assert _spell(text) == []


def test_alias_plus_s_is_not_flagged_but_real_typo_is():
    # alias+s ("Teodors") is read as a possessive without the apostrophe, not a typo.
    found = _spell("She took Teodors knife. Then Teodr left.")
    assert found == ["Teodr"]


def test_common_words_are_not_flagged_against_short_names():
    text = "Mars was red. Maria laughed. Mara ran. Mare grazed by the mare."
    found = _spell(
        text, ["Mara", "Mars"]
    )  # Mars is an alias here, so only Mare/Maria matter
    assert "Mare" not in found  # lowercase "mare" appears in the document
    assert _spell("Shame burned. Harder now.", ["Shawe", "Harden"]) == []
    assert _spell("Shawn burned.", ["Shawe"]) == ["Shawn"]


def test_short_alias_does_not_match_inside_a_longer_word():
    from doctor.detect import detect_mentions

    doc = normalize_markdown("Marathon day. Mara's pack. Teodor called.", chapter=1)
    notes = detect_mentions(
        doc.paragraphs,
        alias_map_from_facts(
            [
                {
                    "predicate": "alias",
                    "object": "Mara",
                    "subject": "mara",
                    "status": "confirmed",
                },
                {
                    "predicate": "alias",
                    "object": "Teo",
                    "subject": "teodor",
                    "status": "confirmed",
                },
            ]
        ),
    )
    assert [note["surface"] for note in notes] == ["Mara"]


def test_same_character_aliases_still_flag_and_order_does_not_matter():
    owners = {"Teodor": {"teodor"}, "Teo": {"teodor"}}
    text = "Teodo ran."
    one = name_spelling(
        normalize_markdown(text, chapter=1).paragraphs,
        ["Teodor", "Teo"],
        owners=owners,
    )
    two = name_spelling(
        normalize_markdown(text, chapter=1).paragraphs,
        ["Teo", "Teodor"],
        owners=owners,
    )
    assert [item["item_state"] for item in one] == ["finding"]
    assert one[0]["evidence"][0]["quote"] == "Teodo"
    assert [item["symptom"] for item in two] == [item["symptom"] for item in one]


def test_long_or_repeated_prefix_is_one_nickname_question():
    long_tail = name_spelling(
        normalize_markdown("Teod ran.", chapter=1).paragraphs,
        ["Teodor"],
        owners={"Teodor": {"teodor"}},
    )
    assert long_tail[0]["item_state"] == "question"
    assert "nickname for Teodor" in long_tail[0]["symptom"]
    repeated = name_spelling(
        normalize_markdown("Teodo waved.\n\nTeodo left.", chapter=1).paragraphs,
        ["Teodor"],
        owners={"Teodor": {"teodor"}},
    )
    assert len(repeated) == 1 and repeated[0]["item_state"] == "question"
    assert (
        name_spelling(
            normalize_markdown("Mari waited.", chapter=1).paragraphs,
            ["Mara", "Maris"],
            owners={"Mara": {"mara"}, "Maris": {"maris"}},
        )
        == []
    )


def test_spelling_span_matches_the_normalized_paragraph():
    doc = normalize_markdown("Teodr ran.", chapter=1)
    items = name_spelling(doc.paragraphs, ["Teodor"])
    evidence = items[0]["evidence"][0]
    start, end = evidence["span"]
    assert doc.paragraphs[0].text[start:end] == "Teodr"
    assert evidence["paragraph_hash"] == doc.paragraphs[0].content_hash


def test_html_review_is_escaped_and_refuses_the_repo(tmp_path: Path, monkeypatch):
    from doctor.cli import run_work
    from doctor.normalize import normalize_markdown
    from doctor.render import render_html
    from test_engine import _fake_checkout

    doc = normalize_markdown("Teodr <ran>.", chapter=1)
    report = {
        "summary": "1 finding.",
        "lens": [{"rule_id": "CANON.NAME_SPELLING", "state": "applied", "reason": "ok"}],
        "items": name_spelling(doc.paragraphs, ["Teodor"]),
        "voice_profiles": {},
    }
    for item in report["items"]:
        item["chapter"] = 1
    html = render_html(report, doc.paragraphs)
    assert "&lt;ran&gt;" in html and "<ran>" not in html
    assert "sha256-" in html and "keydown" in html
    fake = _fake_checkout(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    with pytest.raises(SystemExit, match="this repo"):
        run_work(
            FIXTURE,
            home=tmp_path / "home",
            html_path=fake / "python" / "fanfic_story_doctor" / "report.html",
        )


def test_intake_accepts_pronouns_overrides_and_spelling_ignore():
    data = yaml.safe_load((FIXTURE / "intake.yaml").read_text(encoding="utf-8"))
    data["main_cast"][0]["pronouns"] = "she"
    data["voice_profiles"] = {"mara": {"syntax": "short clipped orders"}}
    data["spelling_ignore"] = ["Brennock"]
    intake, _facts = load_intake(data)
    assert intake["main_cast"][0]["pronouns"] == ["she"]
    data["main_cast"][0]["pronouns"] = ["it"]
    with pytest.raises(IntakeError, match="pronouns"):
        load_intake(data)


def test_spelling_ignore_suppresses_without_creating_an_alias():
    doc = normalize_markdown("Brennock arrived.", chapter=1)
    assert name_spelling(doc.paragraphs, ["Brannoch"], dismissed=["Brennock"]) == []
    assert name_spelling(doc.paragraphs, ["Brannoch"])[0]["item_state"] == "finding"


def test_shared_surname_is_ambiguous_not_attributed():
    facts = [
        {
            "predicate": "alias",
            "subject": "mara",
            "object": "Mara Venn",
            "status": "confirmed",
        },
        {
            "predicate": "alias",
            "subject": "mara",
            "object": "Venn",
            "status": "confirmed",
        },
        {
            "predicate": "alias",
            "subject": "teodor",
            "object": "Teodor Venn",
            "status": "confirmed",
        },
    ]
    assert ambiguous_aliases(facts) == {"Venn": ["mara", "teodor"]}
    assert "Venn" not in alias_map_from_facts(facts)
    assert alias_map_from_facts(facts)["Mara Venn"] == "mara"


AO3_WORK = """<html><body>
<div id="header"><p>Archive chrome</p></div>
<div class="preface group"><h2 class="title">Ashfall Test</h2>
  <div class="summary module"><blockquote class="userstuff"><p>Summary text here.</p></blockquote></div>
  <div class="notes module"><blockquote class="userstuff"><p>Work note <div><span>nested</span></div> still note.</p></blockquote></div>
</div>
<div id="chapters">
 <div class="chapter" id="chapter-1">
  <div class="chapter preface group"><h3 class="title">Chapter 1</h3>
   <div class="notes module"><blockquote class="userstuff"><p>Chapter one note.</p><div><p>deep note</p></div></blockquote></div>
  </div>
  <div class="userstuff module" role="article"><h3 class="landmark heading">Chapter Text</h3>
   <p>Mara crossed the ford.</p><p>She <em>waited</em><br/>there.</p><hr/><p>Teodor came at dusk.</p>
  </div>
  <div class="chapter preface group" id="chapter-1-end"><div class="end notes module"><blockquote class="userstuff"><p>End note one.</p></blockquote></div></div>
 </div>
 <div class="chapter" id="chapter-2">
  <div class="userstuff module" role="article"><p>Ilsa lit the lamp.</p><p>***</p><p>Morning came.</p></div>
 </div>
</div>
<div id="feedback"><p>Kudos and comments</p></div>
</body></html>"""


def test_ao3_full_work_splits_chapters_and_strips_notes():
    doc = normalize_ao3_work(AO3_WORK)
    assert [(p.id, p.text) for p in doc.paragraphs] == [
        ("ch01.s1.p1", "Mara crossed the ford."),
        ("ch01.s1.p2", "She waited there."),
        ("ch01.s2.p1", "Teodor came at dusk."),
        ("ch02.s1.p1", "Ilsa lit the lamp."),
        ("ch02.s2.p1", "Morning came."),
    ]
    text = " ".join(p.text for p in doc.paragraphs)
    for leaked in ("chrome", "Summary", "note", "Kudos", "Chapter Text"):
        assert leaked not in text
    assert any("Chapter one note" in note for note in doc.author_notes)


def test_html_chapter_files_and_full_work_run_through_doctor_run(tmp_path: Path):
    work = tmp_path / "work"
    work.mkdir()
    for name in ("intake.yaml", "tags.yaml"):
        (work / name).write_text(
            (FIXTURE / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    (work / "work.html").write_text(AO3_WORK, encoding="utf-8")
    report = build_report(work, home=tmp_path)
    assert [
        (item["rule_id"], item["item_state"], item["severity"])
        for item in report["items"]
    ] == [
        ("LEDGER.COVERAGE", "coverage", "info"),
        ("AO3.SCHEMA", "finding", "should"),
    ]
    single = normalize_sources(
        [("ch03.html", '<div class="userstuff"><p>Mara slept.</p></div>')]
    )
    assert [p.id for p in single.paragraphs] == ["ch03.s1.p1"]
    assert (
        normalize_html("<p>Bare fragment.</p>").paragraphs[0].text == "Bare fragment."
    )


def test_invalid_item_is_dropped_not_fatal():
    paragraphs = {"ch01.s1.p1": "Mara walked"}
    good = {
        "rule_id": "CANON.NAME_SPELLING",
        "item_state": "finding",
        "tier": "A1",
        "severity": "info",
        "kind": "k",
        "symptom": "ok",
        "evidence": [{"kind": "prose", "paragraph_id": "ch01.s1.p1", "quote": "Mara"}],
        "fact_ids": [],
        "depends_on_hash": "h",
    }
    bad = {
        **good,
        "evidence": [
            {"kind": "prose", "paragraph_id": "ch01.s1.p1", "quote": "Mara W"}
        ],
    }
    report = drop_invalid_items(
        {"summary": "2 findings. 0 blockers.", "lens": [], "items": [good, bad]},
        paragraphs,
        {},
    )
    states = [(item["rule_id"], item["item_state"]) for item in report["items"]]
    assert states == [
        ("CANON.NAME_SPELLING", "finding"),
        ("REPORT.VALIDATION", "unverifiable"),
    ]
    assert report["summary"].startswith("1 findings. 0 blockers.")


def _intake_variant(tmp_path: Path, **au) -> Path:
    work = tmp_path / ("w-" + "-".join(f"{k}{v}" for k, v in au.items()))
    work.mkdir()
    intake = yaml.safe_load((FIXTURE / "intake.yaml").read_text(encoding="utf-8"))
    intake["au"].update(au)
    intake["canon_status"] = [
        {"entity": "teodor", "value": "dead", "from_event": "ev-start"}
    ]
    (work / "intake.yaml").write_text(yaml.safe_dump(intake), encoding="utf-8")
    for name in ("tags.yaml", "facts.json"):
        (work / name).write_text(
            (FIXTURE / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    (work / "ch01.md").write_text(
        "Teodor stood at the gate. Mara waved.", encoding="utf-8"
    )
    return work


def test_alternate_setting_drops_canon_status_and_order_keeps_aliases(tmp_path: Path):
    work = _intake_variant(tmp_path, au_kind="alternate_setting", divergence_event=None)
    report = build_report(work, home=tmp_path)
    rules = {item["rule_id"] for item in report["items"]}
    assert "CANON.DIVERGENCE" not in rules
    assert not [i for i in report["items"] if i["rule_id"] == "CONT.DEAD_REAPPEARS"]
    lens = {row["rule_id"]: (row["state"], row["reason"]) for row in report["lens"]}
    assert lens["CANON.DIVERGENCE"] == ("skipped", "alternate_setting")
    # Aliases still apply: the Teodr typo in the fixture style is still caught.
    (work / "ch01.md").write_text("Teodr stood at the gate.", encoding="utf-8")
    report = build_report(work, home=tmp_path)
    assert [
        i["evidence"][0]["quote"]
        for i in report["items"]
        if i["rule_id"] == "CANON.NAME_SPELLING"
    ] == ["Teodr"]


def test_branch_au_without_divergence_event_gets_question_without_disagreement(
    tmp_path: Path,
):
    work = _intake_variant(tmp_path, divergence_event=None)
    (work / "facts.json").write_text("[]", encoding="utf-8")
    report = build_report(work, home=tmp_path)
    questions = [i for i in report["items"] if i["item_state"] == "question"]
    assert [q["kind"] for q in questions] == ["DIVERGENCE_EVENT"]


def test_multiple_aliases_and_order_edges_are_not_conflicts(tmp_path: Path):
    from doctor.factstore import mark_conflicts
    from doctor.timeline import SceneNode, build_graph

    graph = build_graph([SceneNode("ch01.s1")], ["ev-a", "ev-b", "ev-c"], [])
    base = {
        "layer": "ledger",
        "status": "confirmed",
        "assertion": "state",
        "citation_state": "ok",
    }
    facts = [
        {
            **base,
            "id": "a1",
            "subject": "mara",
            "predicate": "alias",
            "object": "Mara Venn",
        },
        {**base, "id": "a2", "subject": "mara", "predicate": "alias", "object": "Mara"},
        {
            **base,
            "id": "o1",
            "subject": "ev-b",
            "predicate": "event_order",
            "object": {"relation": "after", "target": "ev-a"},
        },
        {
            **base,
            "id": "o2",
            "subject": "ev-b",
            "predicate": "event_order",
            "object": {"relation": "before", "target": "ev-c"},
        },
    ]
    mark_conflicts(facts, graph)
    assert {fact["status"] for fact in facts} == {"confirmed"}
    # Through the full run, a multi-alias cast keeps its shared-surname note.
    work = tmp_path / "w"
    work.mkdir()
    intake = yaml.safe_load((FIXTURE / "intake.yaml").read_text(encoding="utf-8"))
    intake["main_cast"] = [
        {"entity": "mara", "names": ["Mara Venn", "Mara", "Venn"]},
        {"entity": "teodor", "names": ["Teodor Venn", "Teodor"]},
    ]
    (work / "intake.yaml").write_text(yaml.safe_dump(intake), encoding="utf-8")
    (work / "ch01.md").write_text("Venn nodded. Mara Venn smiled.", encoding="utf-8")
    report = build_report(work, home=tmp_path)
    notes = [i["symptom"] for i in report["items"] if i["rule_id"] == "LEDGER.COVERAGE"]
    assert "Venn is shared by mara, teodor. Mentions of it are not attributed." in notes
