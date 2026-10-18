"""OOC.VOICE passage selection and voice references. Invented Ashfall cast only."""

from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path

import yaml
from test_cursor_agent import _wrap
from test_layer_b import FIXTURE

from doctor.cli import build_report
from doctor.layerb import (
    CLI_ENV,
    G9_ENV,
    CursorAgentProvider,
    DeterministicMockProvider,
    build_prompt,
    build_voice_prompt,
    default_limit,
    speaker_turns,
    validate_response,
)


class Recorder(DeterministicMockProvider):
    def __init__(self):
        super().__init__()
        self.requests: list[dict] = []

    def complete(self, prompt_hash, request=None):
        self.requests.append(request)
        return super().complete(prompt_hash, request)


def _work(tmp_path: Path, chapters: int = 8, teodor_talks: bool = True) -> Path:
    work = tmp_path / "work"
    work.mkdir()
    intake = yaml.safe_load((FIXTURE / "intake.yaml").read_text(encoding="utf-8"))
    (work / "intake.yaml").write_text(yaml.safe_dump(intake), encoding="utf-8")
    for number in range(1, chapters + 1):
        teodor = (
            f'"Ash again," Teodor said. "Day {number} and still ash."'
            if teodor_talks
            else "The wind moved past Teodor."
        )
        (work / f"ch{number:02d}.md").write_text(
            f'"Hold the line," Mara said. "This is day {number}."\n\n'
            f'"Count the crates again before night," Mara said.\n\n'
            f"{teodor}\n\n"
            f'"Bring the spare lantern before dark," Teodor said.\n\n'
            f"Mara counted the crates twice, as she did every night of week {number}.\n\n"
            "A gull passed over the camp.",
            encoding="utf-8",
        )
    return work


def _voice(provider):
    return [
        request
        for request in provider.requests
        if request.get("rule") == "OOC.VOICE" and request.get("kind") != "voice_profile"
    ]


def test_short_and_narration_turns_are_not_targets():
    turns, missed = speaker_turns('"Go," Mara said.', _named('"Go," Mara said.', mara="Mara"), {})
    assert turns[0]["words"] == 1 and missed == 0
    assert speaker_turns("The wind moved past Teodor.", _named("The wind moved past Teodor.", teodor="Teodor"), {}) == ([], 0)


def test_voice_prompt_quotes_only_speaker_segments(tmp_path: Path):
    provider = Recorder()
    build_report(_work(tmp_path), layer_b=True, home=tmp_path, provider=provider)
    requests = _voice(provider)
    judgments = [request for request in requests if request.get("kind") != "voice_profile"]
    assert judgments
    for request in judgments:
        assert request["segments"]
        assert request["profile"]["syntax"]
        prompt = build_voice_prompt(request)
        assert "SEGMENT 1" in prompt and "Voice profile" in prompt
        assert prompt.index("SEGMENT 1") < prompt.index("TARGET passage to judge")
    assert any(request.get("kind") == "voice_profile" for request in provider.requests)


def test_quote_from_a_reference_is_rejected():
    target = '"We go at dawn," Mara said.'
    reference = '"Hold the line," Mara said.'
    response = {
        "kind": "note",
        "label": "drift",
        "quote": "Hold the line",
        "observed": "Hold the line",
        "interpretation": "Sharper than before.",
    }
    assert reference.startswith('"Hold')
    assert validate_response("OOC.VOICE", response, target) == "quote_not_in_paragraph"


def test_selection_skips_mention_only_and_spreads_across_chapters(tmp_path: Path):
    provider = Recorder()
    work = _work(tmp_path, chapters=12)
    from doctor import cli

    report = cli.build_report(
        work, layer_b=True, home=tmp_path, provider=provider, max_passages=4
    )
    targets = sorted({r["paragraph_id"] for r in _voice(provider)})
    assert len(targets) == 4
    chapters = sorted({int(t[2:4]) for t in targets})
    assert len(chapters) >= 3 and chapters[-1] - chapters[0] >= 6
    assert all(not t.endswith(".p4") for t in targets)  # the gull paragraph has no cast
    subjects = {r["subject"] for r in _voice(provider)}
    assert subjects == {"mara", "teodor"}
    again = Recorder()
    cli.build_report(work, layer_b=True, home=tmp_path, provider=again, max_passages=4)
    assert sorted({r["paragraph_id"] for r in _voice(again)}) == targets
    assert report["summary"]


def test_character_without_reference_text_is_skipped_with_coverage(tmp_path: Path):
    provider = Recorder()
    work = _work(tmp_path, teodor_talks=False)
    report = build_report(work, layer_b=True, home=tmp_path, provider=provider)
    assert {r["subject"] for r in _voice(provider)} == {"mara"}
    notes = [i["symptom"] for i in report["items"] if i["item_state"] == "coverage"]
    assert any("OOC.VOICE skipped teodor" in n for n in notes)


def test_single_chapter_work_has_no_voice_tasks(tmp_path: Path):
    provider = Recorder()
    report = build_report(
        _work(tmp_path, chapters=1), layer_b=True, home=tmp_path, provider=provider
    )
    assert _voice(provider) == []
    assert any(
        "OOC.VOICE skipped mara" in i["symptom"]
        for i in report["items"]
        if i["item_state"] == "coverage"
    )


def test_cursor_agent_runs_three_votes_in_parallel(tmp_path: Path):
    active = {"now": 0, "peak": 0}
    lock = threading.Lock()

    def runner(argv, **kwargs):
        with lock:
            active["now"] += 1
            active["peak"] = max(active["peak"], active["now"])
        time.sleep(0.05)
        prompt = kwargs["input"]
        if "VOICE PROFILE" in prompt:
            answer = {
                "register": "terse",
                "cadence": "short",
                "syntax": "plain words",
                "diction": "camp orders",
                "range": "stays clipped",
            }
        else:
            segment = prompt.split("<<<SEGMENT 1\n", 1)[1].split("\nSEGMENT 1>>>", 1)[0]
            words = " ".join(segment.split()[:4])
            answer = {
                "kind": "note",
                "label": "in_voice",
                "quote": words,
                "observed": words,
                "interpretation": "Matches the clipped orders in the profile.",
                "evidence_strength": "sufficient",
            }
        with lock:
            active["now"] -= 1
        return subprocess.CompletedProcess(argv, 0, _wrap(answer), "")

    provider = CursorAgentProvider(env={G9_ENV: "1", CLI_ENV: "/fake"}, runner=runner)
    report = build_report(
        _work(tmp_path), layer_b=True, home=tmp_path, provider=provider, max_passages=2
    )
    assert active["peak"] == 3
    assert provider.calls > 6 and not provider.failures
    voice = [
        i
        for i in report["items"]
        if i["rule_id"] == "OOC.VOICE" and i["item_state"] == "note"
    ]
    assert voice and all(i["agreement"] == "3_of_3" for i in voice)


def test_prompt_asks_for_paraphrase_only():
    prompt = build_prompt(
        {"rule": "OOC.VOICE", "labels": ["in_voice"], "paragraph_text": "Mara ran."}
    )
    assert "paraphrase only: no quotation marks" in prompt


def _named(text: str, **names: str) -> list[tuple[int, int, str]]:
    rows = []
    for entity, surface in names.items():
        at = text.find(surface)
        while at >= 0:
            rows.append((at, at + len(surface), entity))
            at = text.find(surface, at + 1)
    return rows


def test_speaker_from_tag_after_quote():
    text = '"Hold the line," Mara said, glancing at Teodor.'
    turns, missed = speaker_turns(text, _named(text, mara="Mara", teodor="Teodor"), {})
    assert [turn["subject"] for turn in turns] == ["mara"] and missed == 0
    text = '"Hold the line," said Teodor, while Mara watched.'
    turns, _missed = speaker_turns(text, _named(text, mara="Mara", teodor="Teodor"), {})
    assert [turn["subject"] for turn in turns] == ["teodor"]


def test_speaker_from_tag_before_quote():
    text = 'Mara watched as Teodor asked, "Where is the ford?"'
    turns, _missed = speaker_turns(text, _named(text, mara="Mara", teodor="Teodor"), {})
    assert [turn["subject"] for turn in turns] == ["teodor"]


def test_pronoun_tag_only_when_unambiguous():
    text = 'Teodor shrugged. "Fine," he said.'
    turns, _missed = speaker_turns(text, _named(text, teodor="Teodor"), {"teodor": {"he"}})
    assert [turn["subject"] for turn in turns] == ["teodor"]
    text = 'Mara looked at Teodor. "Fine," she said.'
    turns, missed = speaker_turns(text, _named(text, mara="Mara", teodor="Teodor"), {})
    assert turns == [] and missed == 1
    turns, missed = speaker_turns(
        text, _named(text, mara="Mara", teodor="Teodor"), {"mara": {"she"}, "teodor": {"he"}}
    )
    assert [turn["subject"] for turn in turns] == ["mara"] and missed == 0


def test_untagged_quote_and_names_inside_quotes_are_not_speakers():
    text = 'Mara set down the map. "We cross at dawn." Teodor would hate it.'
    turns, missed = speaker_turns(text, _named(text, mara="Mara", teodor="Teodor"), {})
    assert turns == [] and missed == 1
    text = 'Mara looked up. "Come on, Teodor," he said.'
    turns, missed = speaker_turns(
        text, _named(text, mara="Mara", teodor="Teodor"), {"mara": {"she"}, "teodor": {"he"}}
    )
    assert turns == [] and missed == 1
    text = "Mara thought about Teodor for a long time."
    assert speaker_turns(text, _named(text, mara="Mara", teodor="Teodor"), {}) == ([], 0)


def test_each_character_with_references_gets_a_slot(tmp_path: Path):
    provider = Recorder()
    work = _work(tmp_path, chapters=10)
    build_report(work, layer_b=True, home=tmp_path, provider=provider, max_passages=2)
    assert {r["subject"] for r in _voice(provider)} == {"mara", "teodor"}


def test_cap_smaller_than_cast_reports_no_slot(tmp_path: Path):
    provider = Recorder()
    work = _work(tmp_path, chapters=6)
    report = build_report(
        work, layer_b=True, home=tmp_path, provider=provider, max_passages=1
    )
    assert {r["subject"] for r in _voice(provider)} == {"mara"}
    notes = [i["symptom"] for i in report["items"] if i["item_state"] == "coverage"]
    assert any("no slot for teodor" in n for n in notes)


def test_opt_out_skips_provider_call_for_that_rule(tmp_path: Path):
    from test_layer_b import _branch_work

    work = _branch_work(tmp_path)
    (work / "profile.yaml").write_text(
        yaml.safe_dump({"opt_out": ["OOC.VOICE"]}), encoding="utf-8"
    )
    provider = Recorder()
    report = build_report(work, layer_b=True, home=tmp_path, provider=provider)
    assert all(request["rule"] != "OOC.VOICE" for request in provider.requests)
    assert any(request["rule"] == "CANON.RAILS" for request in provider.requests)
    lens = {row["rule_id"]: row["reason"] for row in report["lens"]}
    assert lens["OOC.VOICE"] == "opted_out"


def test_default_cap_is_two_per_chapter_and_configurable(tmp_path: Path):
    from doctor.normalize import normalize_sources

    doc = normalize_sources([("ch01.md", "a"), ("ch02.md", "b"), ("ch03.md", "c")])
    assert default_limit(doc) == 6 and default_limit(doc, 1) == 3
    provider = Recorder()
    work = _work(tmp_path, chapters=12)
    report = build_report(work, layer_b=True, home=tmp_path, provider=provider)

    def _notes(home_report):
        return [
            item
            for item in home_report["items"]
            if item["rule_id"] == "OOC.VOICE" and item["item_state"] == "note"
        ]

    default = len(_notes(report))
    fewer_report = build_report(work, layer_b=True, home=tmp_path, per_chapter=1)
    fewer = len(_notes(fewer_report))
    capped = build_report(
        work, layer_b=True, home=tmp_path, per_chapter=1, max_passages=3
    )
    assert default > fewer >= 3
    assert len(_notes(capped)) == 3
