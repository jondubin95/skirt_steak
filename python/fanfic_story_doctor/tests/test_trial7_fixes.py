"""Trial 7 follow-up fixes. Synthetic Ashfall text only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from doctor.intake import IntakeError, load_intake
from doctor.layerb import SAMPLE_MAX, _sample_turns
from doctor.normalize import normalize_markdown, normalize_sources
from doctor.render import flag_positions, render, render_html
from doctor.rules import name_spelling

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "ashfall"


def _turn(chapter: int, paragraph: int, dialogue: str, words: int | None = None) -> dict:
    return {
        "chapter": chapter,
        "paragraph_id": f"ch{chapter:02d}.s1.p{paragraph}",
        "turn_index": paragraph,
        "order": chapter * 100 + paragraph,
        "words": words if words is not None else len(dialogue.split()),
        "dialogue": dialogue,
    }


def test_sample_spreads_across_the_work_and_prefers_longer_lines():
    turns = []
    for chapter in range(1, 59):
        turns.append(_turn(chapter, 1, "Go now please today", words=4))
        turns.append(
            _turn(
                chapter,
                2,
                "Hold the ford until the spare watch arrives tonight please",
                words=12,
            )
        )
    sample = _sample_turns(turns)
    chapters = [turn["chapter"] for turn in sample]
    assert len(sample) == SAMPLE_MAX == 16
    assert chapters == sorted(chapters)
    assert chapters[0] == 1 and chapters[-1] == 58
    assert chapters != list(range(1, 17))
    assert all(turn["words"] == 12 for turn in sample)
    assert _sample_turns(turns) == sample

    varied = [
        _turn(1, 1, "ash ash ash ash ash ash"),
        _turn(1, 2, "hold the ford until dawn breaks"),
        _turn(2, 1, "count the crates before dark tonight"),
        _turn(3, 1, "bring the spare lantern before dusk"),
        _turn(4, 1, "nobody sleeps until the gate is barred"),
    ]
    picked = _sample_turns(varied)
    assert [turn["dialogue"] for turn in picked][0] == "hold the ford until dawn breaks"
    assert "ash ash ash ash ash ash" not in [turn["dialogue"] for turn in picked]
    assert _sample_turns([_turn(1, 1, "Only one chapter speaks here tonight")]) == []


def test_dialogue_prefix_is_a_nickname_question_outside_stays_a_finding():
    owners = {"Mara": {"mara"}, "Teodor": {"teodor"}}
    inside = name_spelling(
        normalize_markdown('"Mar," Mara said.', chapter=1).paragraphs,
        ["Mara", "Teodor"],
        owners=owners,
    )
    assert [item["item_state"] for item in inside] == ["question"]
    assert inside[0]["severity"] == "info"
    assert "nickname for Mara" in inside[0]["symptom"]
    outside = name_spelling(
        normalize_markdown("Mar waited by the gate.", chapter=1).paragraphs,
        ["Mara"],
        owners={"Mara": {"mara"}},
    )
    assert outside[0]["item_state"] == "finding"
    typo = name_spelling(
        normalize_markdown('"Teodr," Mara said.', chapter=2).paragraphs,
        ["Teodor", "Mara"],
        owners=owners,
    )
    assert typo[0]["item_state"] == "finding"
    assert typo[0]["evidence"][0]["quote"] == "Teodr"


def test_html_renders_rule_flags_once_per_chapter_with_reasons_beside_them():
    doc = normalize_sources(
        [
            ("ch01.md", "Teodr ran.\n\nMara waited."),
            ("ch02.md", '"Mar," Mara said. He kept walking.'),
        ]
    )
    items = name_spelling(doc.paragraphs, ["Teodor", "Mara"])
    voice = {
        "rule_id": "OOC.VOICE",
        "item_state": "note",
        "tier": "B",
        "severity": "info",
        "kind": "judgment",
        "symptom": "drift",
        "subject": "mara",
        "label": "drift",
        "agreement": "2_of_3",
        "evidence": [
            {
                "kind": "prose",
                "paragraph_id": doc.paragraphs[0].id,
                "quote": "Teodr",
                "span": [0, 5],
            }
        ],
        "fact_ids": [],
        "depends_on_hash": "h",
        "reads": [
            {"interpretation": "First read reason."},
            {"interpretation": "Second read reason."},
        ],
    }
    report = {"summary": "s", "lens": [], "items": [voice, *items]}
    html = render_html(report, doc.paragraphs)
    assert html.count("<h2>Chapter 1</h2>") == 1
    assert html.count("<h2>Chapter 2</h2>") == 1
    assert '<mark id="flag-1"' in html and 'href="#flag-1"' in html
    assert "let index=-1;" in html
    assert "<aside" not in html
    assert html.index("First read reason.") < html.index("<h2>Chapter 2</h2>")
    assert "Second read reason." in html
    assert html.index(doc.paragraphs[0].id) < html.index("First read reason.")
    nickname = next(item for item in items if item["item_state"] == "question")
    assert "nickname for Mara" in html
    assert nickname["evidence"][0]["paragraph_id"] in html


def test_markdown_reason_escapes_quotes():
    report = {
        "summary": "s",
        "lens": [],
        "items": [
            {
                "rule_id": "OOC.VOICE",
                "item_state": "note",
                "subject": "mara",
                "chapter": 2,
                "label": "drift",
                "agreement": "2_of_3",
                "interpretation": 'She said "hold" once.',
                "evidence": [{"kind": "prose", "quote": 'Say "hold"'}],
            }
        ],
    }
    text = render(report)
    assert 'quote="Say \\"hold\\""' in text
    assert 'reason="She said \\"hold\\" once."' in text


def test_json_writes_positions_and_refuses_the_repo(tmp_path: Path, monkeypatch):
    from doctor.cli import run_work
    from doctor.validate_output import load_schema
    from test_engine import _fake_checkout
    from test_voice_selection import _work

    work = _work(tmp_path, chapters=4)
    chapter = work / "ch01.md"
    chapter.write_text(
        chapter.read_text(encoding="utf-8") + "\n\nTeodr ran toward the gate.\n",
        encoding="utf-8",
    )
    dest = tmp_path / "review" / "report.json"
    run_work(work, layer_b=True, home=tmp_path / "home", json_path=dest, max_passages=2)
    payload = json.loads(dest.read_text(encoding="utf-8"))
    import jsonschema

    jsonschema.validate(payload, load_schema())
    spelling = [row for row in payload["positions"] if row["rule"] == "CANON.NAME_SPELLING"]
    assert len(spelling) == 1
    assert spelling[0]["paragraph_id"].startswith("ch01")
    assert spelling[0]["chapter"] == 1
    assert spelling[0]["offset"] >= 0
    assert spelling[0]["length"] == len("Teodr")
    assert spelling[0]["label"] is None and spelling[0]["agreement"] is None
    voice = [row for row in payload["positions"] if row["rule"] == "OOC.VOICE"]
    assert voice
    assert voice[0]["character"] in {"mara", "teodor"}
    assert voice[0]["label"] and voice[0]["agreement"]
    assert voice[0]["length"] > 0
    fake = _fake_checkout(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    with pytest.raises(SystemExit, match="this repo"):
        run_work(
            work,
            home=tmp_path / "home",
            json_path=fake / "python" / "fanfic_story_doctor" / "report.json",
        )


def test_intake_dialect_field_keeps_the_two_hundred_character_limit():
    data = yaml.safe_load((FIXTURE / "intake.yaml").read_text(encoding="utf-8"))
    data["voice_profiles"] = {"mara": {"dialect_or_l2": "drops articles and copulas"}}
    intake, _facts = load_intake(data)
    assert intake["voice_profiles"]["mara"]["dialect_or_l2"] == "drops articles and copulas"
    data["voice_profiles"] = {"mara": {"dialect_or_l2": "x" * 201}}
    with pytest.raises(IntakeError, match="1-200"):
        load_intake(data)


def test_reuse_stale_flag_reaches_the_report(tmp_path: Path):
    from doctor.cli import build_report
    from test_voice_selection import Recorder, _work

    work = _work(tmp_path, chapters=4)
    cache: dict = {}
    build_report(
        work,
        layer_b=True,
        home=tmp_path,
        provider=Recorder(),
        profile_cache=cache,
        max_passages=1,
    )
    (work / "ch01.md").write_text(
        '"Hold the ford until the relief watch arrives," Mara said.\n\n'
        '"Count every crate before night closes," Mara said.\n\n'
        '"Ash again on the long road," Teodor said. "Day 1 and still ash."\n\n'
        '"Bring the last lantern before full dark," Teodor said.\n\n'
        "Mara counted the crates twice.\n\n"
        "A gull passed.",
        encoding="utf-8",
    )
    second = Recorder()
    report = build_report(
        work,
        layer_b=True,
        home=tmp_path,
        provider=second,
        profile_cache=cache,
        max_passages=1,
        reuse_stale=True,
    )
    assert not any(request.get("kind") == "voice_profile" for request in second.requests)
    assert any(profile["stale"] for profile in report["voice_profiles"].values())
