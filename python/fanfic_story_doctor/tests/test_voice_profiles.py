"""OOC.VOICE profiles: retry, cache, overrides, refresh, and a scripted drift majority.
Invented Ashfall cast only."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from test_layer_b import FIXTURE
from test_voice_selection import Recorder, _work

from doctor.cli import build_report
from doctor.intake import IntakeError, load_intake
from doctor.layerb import resolve_profiles
from doctor.render import render

GOOD = {
    "register": "terse",
    "cadence": "short",
    "syntax": "plain words",
    "diction": "camp orders",
    "range": "stays clipped",
}
PROSE = {**GOOD, "syntax": 'Says "hold" a lot.'}
TURNS = [
    {"dialogue": "Hold the line until the relief comes.", "paragraph_id": "ch01.s1.p1"},
    {"dialogue": "Count the crates again before night.", "paragraph_id": "ch01.s1.p2"},
    {"dialogue": "Nobody sleeps until the gate is barred.", "paragraph_id": "ch02.s1.p1"},
    {"dialogue": "Bring the spare lantern before dark.", "paragraph_id": "ch02.s1.p2"},
]


class Script:
    """Answers profile calls in order, then the good profile."""

    name = "scripted"

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = 0

    def complete(self, prompt_hash, request=None):
        self.calls += 1
        return dict(self.answers.pop(0)) if self.answers else dict(GOOD)


class ProfileReader:
    """Reads drift on runs 0 and 1 only when the request carries the marked profile."""

    name = "profile-reader"

    def __init__(self, marker: str = "drops articles"):
        self.marker = marker
        self.kinds: list[str] = []

    def complete(self, prompt_hash, request=None):
        assert request["rule"] == "OOC.VOICE"
        self.kinds.append(request.get("kind") or "judgment")
        if request.get("kind") == "voice_profile":
            return {**GOOD, "syntax": self.marker}
        drifting = request["profile"]["syntax"] == self.marker and request["run"] < 2
        quote = request["segments"][0]
        return {
            "kind": "note",
            "label": "drift" if drifting else "in_voice",
            "evidence_strength": "sufficient",
            "quote": quote,
            "observed": quote,
            "interpretation": "Reads against the profile." if drifting else "Matches the profile.",
        }


def _resolve(provider, cache, overrides=None, turns=TURNS, refresh=False):
    intake = {
        "work_id": "ashfall-after",
        "main_cast": [{"entity": "mara", "pronouns": ["she"]}],
        "voice_profiles": overrides or {},
    }
    return resolve_profiles(
        [{"subject": "mara"}], {"mara": turns}, intake, provider, cache, refresh, None
    )


def _voice_notes(report: dict) -> list[dict]:
    return [
        item
        for item in report["items"]
        if item["rule_id"] == "OOC.VOICE" and item["item_state"] == "note"
    ]


def test_rejected_profile_is_retried_once_then_cached():
    cache: dict = {}
    retried = Script({"kind": "rejected", "reason": "extra_fields"})
    profiles, _notes, calls = _resolve(retried, cache)
    assert calls == retried.calls == 2
    assert profiles["mara"]["source"] == "generated"

    cache = {}
    profiles, notes, calls = _resolve(Script(PROSE, PROSE), cache)
    assert profiles == {} and calls == 2
    assert [entry["reason"] for entry in cache.values()] == ["profile_prose"]
    assert "was rejected (profile_prose)" in notes[-1]["symptom"]
    again = Script()
    profiles, notes, calls = _resolve(again, cache)
    assert profiles == {} and calls == again.calls == 0
    assert "was rejected (profile_prose)" in notes[-1]["symptom"]


def test_timeout_is_not_cached_so_the_next_run_retries():
    cache: dict = {}
    profiles, notes, calls = _resolve(Script({"kind": "rejected", "reason": "timeout"}), cache)
    assert profiles == {} and calls == 1 and cache == {}
    assert "was rejected (timeout)" in notes[-1]["symptom"]
    profiles, _notes, calls = _resolve(Script(), cache)
    assert calls == 1 and profiles["mara"]["source"] == "generated"


def test_complete_override_makes_no_call_and_partial_override_merges():
    provider = Script()
    cache: dict = {}
    complete = {"mara": {**GOOD, "syntax": "drops articles under stress"}}
    profiles, _notes, calls = _resolve(provider, cache, complete)
    assert calls == provider.calls == 0 and cache == {}
    assert profiles["mara"]["source"] == "override"
    assert profiles["mara"]["syntax"] == "drops articles under stress"

    partial = {"mara": {"syntax": "drops articles under stress"}}
    profiles, _notes, calls = _resolve(Script(), cache, partial)
    assert calls == 1 and profiles["mara"]["source"] == "mixed"
    assert profiles["mara"]["syntax"] == "drops articles under stress"
    assert profiles["mara"]["diction"] == GOOD["diction"]
    assert [entry["profile"] for entry in cache.values()] == [GOOD]
    changed = {"mara": {"range": "rarely raises her voice"}}
    profiles, _notes, calls = _resolve(Script(), cache, changed)
    assert calls == 0 and profiles["mara"]["source"] == "mixed"
    assert profiles["mara"]["range"] == "rarely raises her voice"
    assert profiles["mara"]["syntax"] == GOOD["syntax"]


def test_changed_sample_keeps_the_stale_profile_until_refresh():
    cache: dict = {}
    _resolve(Script(), cache)
    edited = [{**TURNS[0], "dialogue": "Hold the ford until the relief comes."}, *TURNS[1:]]
    provider = Script({**GOOD, "cadence": "longer now"})
    profiles, notes, calls = _resolve(provider, cache, turns=edited)
    assert calls == provider.calls == 0
    assert profiles["mara"]["source"] == "stale" and profiles["mara"]["stale"]
    assert profiles["mara"]["cadence"] == GOOD["cadence"]
    assert "--refresh-voice-profiles" in notes[-1]["symptom"]

    profiles, _notes, calls = _resolve(provider, cache, turns=edited, refresh=True)
    assert calls == 1 and profiles["mara"]["source"] == "generated"
    assert not profiles["mara"]["stale"] and profiles["mara"]["cadence"] == "longer now"
    profiles, _notes, calls = _resolve(Script(), cache, turns=edited)
    assert calls == 0 and profiles["mara"]["cadence"] == "longer now"


def test_refresh_regenerates_an_unchanged_or_rejected_profile():
    cache: dict = {}
    _resolve(Script(PROSE, PROSE), cache)
    profiles, _notes, calls = _resolve(Script(), cache, refresh=True)
    assert calls == 1 and profiles["mara"]["source"] == "generated"
    profiles, _notes, calls = _resolve(Script({**GOOD, "register": "formal"}), cache, refresh=True)
    assert calls == 1 and profiles["mara"]["register"] == "formal"


@pytest.mark.parametrize(
    "text",
    [
        'says "hold" a lot',
        "says \u201chold\u201d a lot",
        "short orders, for example: hold",
        "rewrite as shorter orders",
    ],
)
def test_override_that_quotes_or_suggests_a_rewrite_fails_at_intake(text):
    data = yaml.safe_load((FIXTURE / "intake.yaml").read_text(encoding="utf-8"))
    data["voice_profiles"] = {"mara": {"syntax": text}}
    with pytest.raises(IntakeError, match="mara voice profile syntax"):
        load_intake(data)


def test_bad_override_stops_the_run_before_any_model_call(tmp_path: Path):
    work = _work(tmp_path)
    intake = yaml.safe_load((work / "intake.yaml").read_text(encoding="utf-8"))
    intake["voice_profiles"] = {"mara": {**GOOD, "diction": "camp orders, for example: hold"}}
    (work / "intake.yaml").write_text(yaml.safe_dump(intake), encoding="utf-8")
    provider = Recorder()
    with pytest.raises(IntakeError, match="mara voice profile diction"):
        build_report(work, layer_b=True, home=tmp_path, provider=provider)
    assert provider.requests == []


def test_override_rejected_after_merge_keeps_the_model_profile_cached():
    cache: dict = {}
    bad = {"mara": {"syntax": "short orders, for example: hold"}}
    profiles, notes, calls = _resolve(Script(), cache, bad)
    assert profiles == {} and calls == 1
    assert "was rejected (profile_prose)" in notes[-1]["symptom"]
    assert [entry.get("profile") for entry in cache.values()] == [GOOD]
    fixed = {"mara": {"syntax": "short orders"}}
    profiles, _notes, calls = _resolve(Script(), cache, fixed)
    assert calls == 0 and profiles["mara"]["source"] == "mixed"


def test_appended_chapter_reuses_the_cached_profile(tmp_path: Path):
    work = _work(tmp_path, chapters=8)
    cache: dict = {}
    first = Recorder()
    build_report(work, layer_b=True, home=tmp_path, provider=first, profile_cache=cache)
    assert sum(request.get("kind") == "voice_profile" for request in first.requests) == 2
    (work / "ch09.md").write_text(
        '"Hold the gate until the ninth bell," Mara said.\n\n'
        '"Ash on ash again tonight," Teodor said.',
        encoding="utf-8",
    )
    second = Recorder()
    report = build_report(work, layer_b=True, home=tmp_path, provider=second, profile_cache=cache)
    assert not any(request.get("kind") == "voice_profile" for request in second.requests)
    assert {profile["source"] for profile in report["voice_profiles"].values()} == {"generated"}


def test_two_of_three_drift_reads_survive_into_the_report(tmp_path: Path):
    work = _work(tmp_path)
    provider = ProfileReader()
    report = build_report(work, layer_b=True, home=tmp_path, provider=provider, max_passages=2)
    voice = _voice_notes(report)
    assert {item["subject"] for item in voice} == {"mara", "teodor"}
    assert {(item["label"], item["agreement"], item["decision"]) for item in voice} == {
        ("drift", "2_of_3", "majority")
    }
    assert render(report).count("label=drift agreement=2_of_3") == len(voice)
    assert {profile["syntax"] for profile in report["voice_profiles"].values()} == {"drops articles"}

    intake = yaml.safe_load((work / "intake.yaml").read_text(encoding="utf-8"))
    intake["voice_profiles"] = {entity: dict(GOOD) for entity in ("mara", "teodor")}
    (work / "intake.yaml").write_text(yaml.safe_dump(intake), encoding="utf-8")
    provider = ProfileReader()
    report = build_report(work, layer_b=True, home=tmp_path, provider=provider, max_passages=2)
    assert "voice_profile" not in provider.kinds
    assert {item["label"] for item in _voice_notes(report)} == {"in_voice"}
