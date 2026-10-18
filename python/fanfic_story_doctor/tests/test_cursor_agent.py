"""CursorAgentProvider with a fake subprocess. No real CLI call. Invented Ashfall cast only."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
from test_layer_b import _branch_work

from doctor.cli import cache_path, main, run_work
from doctor.layerb import (
    CLI_ENV,
    G9_ENV,
    CursorAgentProvider,
    ProviderRefused,
    build_prompt,
    get_provider,
    parse_cli_output,
)

ENV = {G9_ENV: "1", CLI_ENV: "/fake/cursor-agent"}


def _wrap(answer) -> str:
    text = answer if isinstance(answer, str) else json.dumps(answer)
    return json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": text,
            "usage": {"inputTokens": 10, "outputTokens": 5},
        }
    )


class FakeRunner:
    def __init__(self, answer=None, returncode=0, raise_exc=None):
        self.answer = answer
        self.returncode = returncode
        self.raise_exc = raise_exc
        self.calls: list[dict] = []

    def __call__(self, argv, **kwargs):
        self.calls.append({"argv": argv, **kwargs})
        if self.raise_exc:
            raise self.raise_exc
        if self.answer is None:
            text = kwargs["input"]
            passage = text.split("<<<PASSAGE\n", 1)[1].split("\nPASSAGE>>>", 1)[0]
            words = " ".join(passage.split()[:3])
            answer = {
                "kind": "note",
                "label": "in_voice",
                "quote": words,
                "observed": words,
                "interpretation": "Reads as steady and terse.",
            }
        else:
            answer = self.answer
        return subprocess.CompletedProcess(argv, self.returncode, _wrap(answer), "")


def test_cursor_agent_refused_without_g9_even_for_public_work():
    with pytest.raises(ProviderRefused, match="G9"):
        get_provider("cursor-agent", env={CLI_ENV: "/fake/cursor-agent"})
    with pytest.raises(ProviderRefused, match="G9"):
        CursorAgentProvider(env={G9_ENV: "yes", CLI_ENV: "/x"})


def test_cursor_agent_missing_cli_refuses():
    with pytest.raises(ProviderRefused, match="CLI not found"):
        CursorAgentProvider(env={G9_ENV: "1", "PATH": ""}, runner=FakeRunner())


def test_argv_is_read_only_print_mode_with_stdin_prompt():
    runner = FakeRunner()
    provider = CursorAgentProvider(
        env={**ENV, "DOCTOR_CURSOR_MODEL": "m1"}, runner=runner
    )
    response = provider.complete(
        "h",
        {
            "rule": "OOC.VOICE",
            "labels": ["in_voice"],
            "paragraph_text": "Teodor waited at the gate.",
            "subject": "teodor",
        },
    )
    call = runner.calls[0]
    argv = call["argv"]
    assert argv[:6] == [
        "/fake/cursor-agent",
        "-p",
        "--output-format",
        "json",
        "--mode",
        "ask",
    ]
    assert "--force" not in argv and "--yolo" not in argv
    assert argv[argv.index("--model") + 1] == "m1"
    assert argv[argv.index("--workspace") + 1] == call["cwd"]
    assert "Teodor waited" in call["input"] and "Teodor" not in " ".join(argv)
    assert call["timeout"] == provider.timeout
    assert not Path(call["cwd"]).exists()  # temp workspace removed
    assert response["label"] == "in_voice"
    assert provider.usage["inputTokens"] == 10


@pytest.mark.parametrize(
    ("stdout", "reason"),
    [
        ("not json", "cli_output_not_json"),
        ("", "cli_output_not_json"),
        (json.dumps({"subtype": "error", "is_error": True}), "cli_error"),
        (_wrap("I think it is in voice."), "answer_not_json"),
        (_wrap("[1, 2]"), "answer_not_object"),
        (_wrap({"kind": "note", "label": "in_voice", "rewrite": "x"}), "extra_fields"),
    ],
)
def test_parse_failures_become_rejected(stdout, reason):
    assert parse_cli_output(stdout) == {"kind": "rejected", "reason": reason}


def test_parse_accepts_code_fence():
    fenced = "```json\n" + json.dumps({"kind": "note", "label": "drift"}) + "\n```"
    assert parse_cli_output(_wrap(fenced))["label"] == "drift"


def test_prompt_fences_passage_and_names_labels():
    prompt = build_prompt(
        {
            "rule": "OOC.VOICE",
            "labels": ["drift", "in_voice"],
            "paragraph_text": "Mara laughed.",
            "subject": "mara",
        }
    )
    assert "<<<PASSAGE\nMara laughed.\nPASSAGE>>>" in prompt
    assert "drift, in_voice" in prompt and "Do not use any tools" in prompt


def test_rejections_counted_with_reasons_and_cache_persists(
    tmp_path: Path, monkeypatch
):
    home = tmp_path / "home"
    work = _branch_work(tmp_path)
    bad = CursorAgentProvider(env=ENV, runner=FakeRunner(answer="prose answer"))
    report = run_work(work, layer_b=True, home=home, provider=bad)
    assert "rejected by the contract check" in report
    assert "invalid_output:answer_not_json" in report
    assert bad.failures["answer_not_json"] == bad.calls > 0

    good_runner = FakeRunner()
    good = CursorAgentProvider(env=ENV, runner=good_runner)
    home2 = tmp_path / "home2"
    run_work(work, layer_b=True, home=home2, provider=good)
    first = len(good_runner.calls)
    assert first > 0 and cache_path(home2).exists()
    again = CursorAgentProvider(env=ENV, runner=good_runner)
    run_work(work, layer_b=True, home=home2, provider=again)
    assert len(good_runner.calls) == first and again.calls == 0


def test_timeouts_are_rejected_and_not_cached(tmp_path: Path):
    home = tmp_path / "home"
    work = _branch_work(tmp_path)
    runner = FakeRunner(raise_exc=subprocess.TimeoutExpired("x", 1))
    provider = CursorAgentProvider(env=ENV, runner=runner)
    run_work(work, layer_b=True, home=home, provider=provider)
    assert provider.failures["timeout"] == provider.calls > 0
    assert json.loads(cache_path(home).read_text(encoding="utf-8")) == {}


def test_max_passages_caps_calls(tmp_path: Path):
    work = _branch_work(tmp_path)
    runner = FakeRunner()
    provider = CursorAgentProvider(env=ENV, runner=runner)
    text = run_work(
        work, layer_b=True, home=tmp_path / "h", provider=provider, max_passages=1
    )
    lens = re.compile(r"^- (?:OOC\.VOICE|CANON\.RAILS): applied \(")
    tasks = re.compile(r"tasks=(\d+)")
    found = []
    for line in text.splitlines():
        if lens.match(line):
            match = tasks.search(line)
            assert match is not None
            found.append(int(match.group(1)))
    assert found and all(n <= 1 for n in found)  # the cap holds per rule
    assert sum(found) >= 1
    assert len(runner.calls) == 3 * sum(found)


def test_cli_cursor_agent_refused_without_opt_in(monkeypatch, capsys):
    monkeypatch.delenv(G9_ENV, raising=False)
    from test_layer_b import FIXTURE

    assert main(["run", str(FIXTURE), "--layer-b", "--provider", "cursor-agent"]) == 3
    assert "G9" in capsys.readouterr().err
