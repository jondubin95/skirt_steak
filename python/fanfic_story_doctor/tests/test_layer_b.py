"""Layer B (OOC.VOICE, CANON.RAILS) on the mock provider. Invented Ashfall cast only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from doctor.cli import build_report, main, run_work
from doctor.later import OOC_LABELS, RAILS_LABELS
from doctor.layerb import (
    G9_ENV,
    LABELS,
    DeterministicMockProvider,
    ProviderRefused,
    get_provider,
    validate_response,
)
from doctor.render import render
from doctor.validate_output import validate_report

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "ashfall"


def _branch_work(tmp_path: Path) -> Path:
    """A work set after the declared branch, so CANON.RAILS has later passages."""
    work = tmp_path / "work"
    work.mkdir()
    intake = yaml.safe_load((FIXTURE / "intake.yaml").read_text(encoding="utf-8"))
    intake["window"] = {"relation": "after", "event": "ev-bridge"}
    (work / "intake.yaml").write_text(yaml.safe_dump(intake), encoding="utf-8")
    (work / "ch01.md").write_text(
        "Mara crossed the broken bridge alone.\n\n***\n\n"
        "Teodor waited at the camp gate.\n\n"
        '"Keep your lantern low," Mara said. "The ash hides more than it shows."\n\n'
        '"I always keep it low," Teodor said, grinning.\n\n'
        '"Then keep it lower," Mara said, and did not smile back.\n\n'
        '"You worry like a quartermaster," Teodor said.',
        encoding="utf-8",
    )
    (work / "ch02.md").write_text(
        '"We go at dawn," Mara said. "No fires, no songs."\n\n'
        '"No songs at all?" Teodor said. "That is the cruelest order yet."',
        encoding="utf-8",
    )
    return work


def _notes(report: dict, rule: str | None = None) -> list[dict]:
    return [
        item
        for item in report["items"]
        if item.get("tier") == "B"
        and item["item_state"] == "note"
        and (rule is None or item["rule_id"] == rule)
    ]


def test_prompt_hash_covers_reference_id_and_text():
    from doctor.layerb import _prompt_hash

    base = {
        "paragraph_id": "ch02.s1.p1",
        "paragraph_text": "Mara said go.",
        "subject": "mara",
        "references": [{"paragraph_id": "ch01.s1.p1", "text": "Mara said stay."}],
    }
    other_text = {
        **base,
        "references": [{"paragraph_id": "ch01.s1.p1", "text": "Yes."}],
    }
    other_id = {
        **base,
        "references": [{"paragraph_id": "ch01.s1.p2", "text": "Mara said stay."}],
    }
    assert _prompt_hash("OOC.VOICE", base) != _prompt_hash("OOC.VOICE", other_text)
    assert _prompt_hash("OOC.VOICE", base) != _prompt_hash("OOC.VOICE", other_id)
    assert _prompt_hash("OOC.VOICE", base) == _prompt_hash("OOC.VOICE", {**base})


def test_without_flag_layer_b_is_skipped_layer_a_only(tmp_path: Path):
    report = build_report(FIXTURE, home=tmp_path)
    lens = {row["rule_id"]: (row["state"], row["reason"]) for row in report["lens"]}
    assert lens["OOC.VOICE"] == ("skipped", "layer_a_only")
    assert lens["CANON.RAILS"] == ("skipped", "layer_a_only")
    assert _notes(report) == []


def test_labels_are_closed_and_match_rubric_files():
    assert (
        LABELS["CANON.RAILS"]
        == {"consequence_shown", "on_rails", "not_enough_evidence"}
        == RAILS_LABELS
    )
    assert LABELS["OOC.VOICE"] == OOC_LABELS
    for rule, name in (
        ("CANON.RAILS", "canon_rails.md"),
        ("OOC.VOICE", "ooc_voice.md"),
    ):
        text = (ROOT / "rubrics" / name).read_text(encoding="utf-8")
        line = next(row for row in text.splitlines() if row.startswith("Labels:"))
        listed = {label.strip(" .") for label in line.split(":", 1)[1].split(",")}
        assert listed == LABELS[rule]


def test_voice_majority_and_thin_reads_are_one_result():
    from doctor.layerb import aggregate_voice

    thin = {
        "kind": "note",
        "label": "drift",
        "evidence_strength": "thin",
        "quote": "Come to dinner",
        "observed": "Come to dinner",
        "interpretation": "A set phrase shows little.",
    }
    drift = {**thin, "evidence_strength": "sufficient", "interpretation": "The syntax breaks."}
    steady = {**drift, "label": "in_voice", "interpretation": "This matches."}
    split = aggregate_voice([drift, {**drift, "label": "break", "interpretation": "A break."}, steady])
    assert split["label"] == "not_enough_evidence" and split["decision"] == "no_majority"
    assert split["agreement"] == "0_of_3"
    majority = aggregate_voice([drift, drift, steady])
    assert majority["label"] == "drift" and majority["agreement"] == "2_of_3"
    coerced = aggregate_voice([thin, thin, steady])
    assert coerced["label"] == "not_enough_evidence"
    assert coerced["reads"][0]["counted_as"] == "not_enough_evidence"
    assert aggregate_voice([{"rejected": True}, {"rejected": True}, drift])["label"] == "not_enough_evidence"


def test_layer_b_runs_mock_and_contract_holds(tmp_path: Path):
    work = _branch_work(tmp_path)
    plain = build_report(work, home=tmp_path)
    report = build_report(work, layer_b=True, home=tmp_path)
    lens = {row["rule_id"]: row for row in report["lens"]}
    assert lens["OOC.VOICE"]["state"] == "applied"
    assert lens["CANON.RAILS"]["state"] == "applied"
    assert "provider=mock" in lens["CANON.RAILS"]["reason"]
    rails, voice = _notes(report, "CANON.RAILS"), _notes(report, "OOC.VOICE")
    assert rails and voice == []
    assert any("fewer than 4" in item["symptom"] for item in report["items"])
    for note in rails + voice:
        assert note["severity"] == "info"
        assert note["label"] in LABELS[note["rule_id"]]
        assert note["observed"] != note["interpretation"]
        assert note["agreement"] in {"2_of_3", "3_of_3", "low_agreement"}
        assert "not correctness" in note["symptom"]
    # Layer B never changes findings or blockers.
    assert report["summary"] == plain["summary"]
    finding_ids = lambda r: [
        i["rule_id"] for i in r["items"] if i["item_state"] == "finding"
    ]
    assert finding_ids(report) == finding_ids(plain)


def test_canon_rails_needs_a_declared_branch_and_later_passages(tmp_path: Path):
    # The Ashfall fixture is set before its branch: no later passage, no RAILS notes.
    report = build_report(FIXTURE, layer_b=True, home=tmp_path)
    assert _notes(report, "CANON.RAILS") == []
    assert {row["rule_id"]: row["reason"] for row in report["lens"]}[
        "CANON.RAILS"
    ].endswith("tasks=0")
    # Not declared AU: RAILS is skipped, not run.
    work = _branch_work(tmp_path)
    intake = yaml.safe_load((work / "intake.yaml").read_text(encoding="utf-8"))
    intake["au"]["is_au"] = False
    (work / "intake.yaml").write_text(yaml.safe_dump(intake), encoding="utf-8")
    report = build_report(work, layer_b=True, home=tmp_path)
    rows = {row["rule_id"]: (row["state"], row["reason"]) for row in report["lens"]}
    assert rows["CANON.RAILS"] == ("skipped", "no_declared_branch")


def test_mock_is_deterministic(tmp_path: Path):
    work = _branch_work(tmp_path)
    one = build_report(work, layer_b=True, home=tmp_path)
    two = build_report(work, layer_b=True, home=tmp_path)
    assert json.dumps(one, sort_keys=True) == json.dumps(two, sort_keys=True)
    request = {"labels": ["a", "b", "c"], "paragraph_text": "Mara ran.", "run": 0}
    assert DeterministicMockProvider().complete(
        "h", request
    ) == DeterministicMockProvider().complete("h", request)


def test_invalid_responses_are_rejected_not_shown(tmp_path: Path):
    text = "Mara crossed the broken bridge alone."
    good = {
        "kind": "note",
        "label": "on_rails",
        "quote": "Mara crossed",
        "observed": "Mara crossed",
        "interpretation": "x",
    }
    assert validate_response("CANON.RAILS", good, text) is None
    assert (
        validate_response("CANON.RAILS", {**good, "quote": "Mara flew"}, text)
        == "quote_not_in_paragraph"
    )
    assert (
        validate_response("CANON.RAILS", {**good, "label": "drift"}, text)
        == "label_not_closed"
    )
    assert (
        validate_response("OOC.VOICE", {**good, "label": "totally_ooc"}, text)
        == "label_not_closed"
    )
    assert (
        validate_response("CANON.RAILS", {**good, "observed": "Mara soared"}, text)
        == "observed_not_verbatim"
    )
    assert (
        validate_response(
            "CANON.RAILS", {**good, "interpretation": "Mara crossed"}, text
        )
        == "observed_equals_interpretation"
    )
    assert (
        validate_response("CANON.RAILS", {"kind": "refusal"}, text) == "invalid_output"
    )
    assert (
        validate_response("CANON.RAILS", {**good, "observed": ""}, text)
        == "observed_not_verbatim"
    )
    assert (
        validate_response("CANON.RAILS", {**good, "observed": " "}, text)
        == "observed_not_verbatim"
    )
    assert (
        validate_response("CANON.RAILS", {**good, "quote": " "}, text)
        == "quote_not_in_paragraph"
    )

    bad = {**good, "quote": "not in the draft", "observed": "not in the draft"}
    class Scripted:
        name = "scripted"

        def complete(self, prompt_hash, request=None):
            return dict(bad)

    provider = Scripted()
    report = build_report(
        _branch_work(tmp_path), layer_b=True, home=tmp_path, provider=provider
    )
    assert _notes(report) == []
    rejected = [
        i
        for i in report["items"]
        if i.get("tier") == "B" and i["item_state"] == "coverage"
    ]
    assert any("rejected" in item["symptom"] for item in rejected)


def test_normalized_punctuation_note_is_shown(tmp_path: Path):
    work = _branch_work(tmp_path)
    (work / "ch02.md").unlink()
    straight = 'Mara said "Go" - now.'
    (work / "ch01.md").write_text(straight + "\n", encoding="utf-8")
    curly = "Mara said \u201cGo\u201d \u2014 now."

    class Scripted:
        name = "scripted"

        def complete(self, prompt_hash, request=None):
            return {
                "kind": "note",
                "label": "on_rails",
                "quote": curly,
                "observed": curly,
                "interpretation": "The order is given on the page.",
            }

    report = build_report(work, layer_b=True, home=tmp_path, provider=Scripted())
    notes = [item for item in report["items"] if item["item_state"] == "note"]
    assert len(notes) == 1
    assert notes[0]["evidence"][0]["quote"] == straight
    assert notes[0]["observed"] == straight
    assert not any(item["rule_id"] == "REPORT.VALIDATION" for item in report["items"])


def test_validator_blocks_layer_b_above_info():
    paragraphs = {"ch01.s1.p1": "Mara walked"}
    note = {
        "rule_id": "OOC.VOICE",
        "item_state": "note",
        "tier": "B",
        "severity": "info",
        "kind": "judgment",
        "symptom": "label break",
        "evidence": [{"kind": "prose", "paragraph_id": "ch01.s1.p1", "quote": "Mara"}],
        "fact_ids": [],
        "depends_on_hash": "h",
        "observed": "Mara",
        "interpretation": "A judgment.",
        "label": "break",
        "agreement": "3_of_3",
    }
    report = {"summary": "x", "lens": [], "items": [note]}
    assert validate_report(report, paragraphs, {}) == []
    for change, message in (
        ({"severity": "blocker"}, "layer-b severity above info: OOC.VOICE"),
        ({"severity": "should"}, "layer-b severity above info: OOC.VOICE"),
        ({"item_state": "finding"}, "layer-b item_state not allowed: OOC.VOICE"),
        ({"label": "on_fire"}, "layer-b label not closed: OOC.VOICE"),
    ):
        assert message in validate_report(
            {**report, "items": [{**note, **change}]}, paragraphs, {}
        )
    quoted = {**note, "interpretation": 'She says "Mara flew".'}
    assert "never-rewrite: OOC.VOICE" in validate_report(
        {**report, "items": [quoted]}, paragraphs, {}
    )


def test_non_mock_provider_refuses_without_g9_opt_in(tmp_path: Path, capsys):
    with pytest.raises(ProviderRefused, match="G9"):
        get_provider("openai", env={})
    with pytest.raises(ProviderRefused, match="not implemented"):
        get_provider("openai", env={G9_ENV: "1"})
    assert isinstance(get_provider("mock", env={}), DeterministicMockProvider)
    code = main(["run", str(FIXTURE), "--layer-b", "--provider", "anthropic"])
    assert code == 3
    assert "G9" in capsys.readouterr().err


def test_cache_skips_provider_on_second_run(tmp_path: Path):
    work = _branch_work(tmp_path)
    cache: dict = {}
    first = DeterministicMockProvider()
    one = build_report(work, layer_b=True, home=tmp_path, provider=first, cache=cache)
    assert first.calls > 0 and cache
    second = DeterministicMockProvider()
    two = build_report(work, layer_b=True, home=tmp_path, provider=second, cache=cache)
    assert second.calls == 0
    assert one == two


def test_layer_b_report_on_fixture(tmp_path: Path):
    work = _branch_work(tmp_path)
    report = build_report(work, layer_b=True, home=tmp_path)
    notes = [
        (i["rule_id"], i["label"], i["agreement"], i["subject"], i["chapter"])
        for i in report["items"]
        if i["item_state"] == "note"
    ]
    assert notes == [
        ("CANON.RAILS", "consequence_shown", "2_of_3", "ev-bridge", 1),
        ("CANON.RAILS", "on_rails", "low_agreement", "ev-bridge", 1),
        ("CANON.RAILS", "on_rails", "2_of_3", "ev-bridge", 1),
        ("CANON.RAILS", "not_enough_evidence", "low_agreement", "ev-bridge", 1),
        ("CANON.RAILS", "on_rails", "2_of_3", "ev-bridge", 1),
        ("CANON.RAILS", "not_enough_evidence", "low_agreement", "ev-bridge", 1),
        ("CANON.RAILS", "not_enough_evidence", "3_of_3", "ev-bridge", 1),
    ]
    lens = {r["rule_id"]: r["reason"] for r in report["lens"]}
    assert lens["OOC.VOICE"] == "provider=mock; tasks=0; profiles=0"
    assert lens["CANON.RAILS"] == "provider=mock; tasks=4"
    text = run_work(work, layer_b=True, home=tmp_path)
    assert text == render(report)
    assert "OOC.VOICE skipped mara" in text
