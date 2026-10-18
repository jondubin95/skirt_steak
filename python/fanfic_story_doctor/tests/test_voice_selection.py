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
    REF_CHARS,
    REF_MAX,
    CursorAgentProvider,
    DeterministicMockProvider,
    build_prompt,
    presence,
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
            f"{teodor}\n\n"
            f"Mara counted the crates twice, as she did every night of week {number}.\n\n"
            "A gull passed over the camp.",
            encoding="utf-8",
        )
    return work


def _voice(provider):
    return [r for r in provider.requests if r["rule"] == "OOC.VOICE"]


def test_presence_scores_dialogue_and_skips_passing_mentions():
    assert presence('"Go," Mara said.', 1) == 4
    assert presence("The wind moved past Teodor.", 1) == 1
    assert presence(" ".join(["word"] * 60) + " Mara", 1) == 2


def test_references_come_from_earlier_chapters_and_are_bounded(tmp_path: Path):
    provider = Recorder()
    build_report(_work(tmp_path), layer_b=True, home=tmp_path, provider=provider)
    requests = _voice(provider)
    assert requests
    for request in requests:
        target_chapter = int(request["paragraph_id"][2:4])
        refs = request["references"]
        assert 2 <= len(refs) <= REF_MAX
        assert all(int(ref["paragraph_id"][2:4]) < target_chapter for ref in refs)
        assert all(len(ref["text"]) <= REF_CHARS for ref in refs)
        assert request["paragraph_id"] not in {ref["paragraph_id"] for ref in refs}
    prompt = build_prompt(requests[0])
    assert "REFERENCE 1" in prompt and "Never quote them" in prompt
    assert prompt.index("REFERENCE 1") < prompt.index("TARGET passage to judge")
    assert len(prompt) < 6000


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
        passage = kwargs["input"].split("TARGET passage", 1)[1]
        passage = passage.split("<<<PASSAGE\n", 1)[1].split("\nPASSAGE>>>", 1)[0]
        words = " ".join(passage.split()[:2])
        with lock:
            active["now"] -= 1
        return subprocess.CompletedProcess(
            argv,
            0,
            _wrap(
                {
                    "kind": "note",
                    "label": "in_voice",
                    "quote": words,
                    "observed": words,
                    "interpretation": "Matches the clipped orders in the references.",
                }
            ),
            "",
        )

    provider = CursorAgentProvider(env={G9_ENV: "1", CLI_ENV: "/fake"}, runner=runner)
    report = build_report(
        _work(tmp_path), layer_b=True, home=tmp_path, provider=provider, max_passages=2
    )
    assert active["peak"] == 3
    assert provider.calls == 6 and not provider.failures
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
