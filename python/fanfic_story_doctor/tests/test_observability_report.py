"""Layer B progress lines, per-call cache saves, voice report layout, and
possessive/dedupe handling in CANON.NAME_SPELLING. Invented Ashfall cast only."""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

from test_cursor_agent import ENV, FakeRunner
from test_layer_b import _branch_work

from doctor.cli import cache_path, run_work
from doctor.layerb import CursorAgentProvider
from doctor.normalize import normalize_markdown
from doctor.render import render
from doctor.rules import name_spelling

LINE = re.compile(
    r"^\[layerb\] (\d+)/(\d+) ch=\S+ char=\S+ cache=(hit|miss) \d+\.\d+s label=\S+$"
)


def _provider(runner):
    provider = CursorAgentProvider(env=ENV, runner=runner)
    provider.parallel = 1
    return provider


def test_progress_lines_on_stderr_and_cache_hits_on_rerun(tmp_path: Path, capsys):
    work = _branch_work(tmp_path)
    run_work(work, layer_b=True, home=tmp_path, provider=_provider(FakeRunner()))
    err = capsys.readouterr().err.splitlines()
    assert err[0].startswith("[layerb] start tasks=")
    assert err[-1].startswith("[layerb] done tasks=")
    rows = [LINE.match(line) for line in err[1:-1]]
    assert rows and all(rows)
    total = int(rows[0].group(2))
    assert [int(r.group(1)) for r in rows] == list(range(1, total + 1))
    assert {r.group(3) for r in rows} == {"miss"}
    assert any("char=mara" in line or "char=teodor" in line for line in err)
    runner = FakeRunner()
    run_work(work, layer_b=True, home=tmp_path, provider=_provider(runner))
    err = capsys.readouterr().err.splitlines()
    assert all("cache=hit" in line for line in err[1:-1])
    assert runner.calls == []
    assert f"cache_hits={total}" in err[-1]


def test_cache_saved_atomically_after_each_call(tmp_path: Path, capsys):
    work = _branch_work(tmp_path)
    path = cache_path(tmp_path)
    seen: list[int] = []

    class Interrupting(FakeRunner):
        def __call__(self, argv, **kwargs):
            seen.append(len(json.loads(path.read_text())) if path.exists() else 0)
            if len(self.calls) >= 6:  # interrupt on the third task (3 runs per task)
                raise KeyboardInterrupt
            return super().__call__(argv, **kwargs)

    try:
        run_work(work, layer_b=True, home=tmp_path, provider=_provider(Interrupting()))
    except KeyboardInterrupt:
        pass
    assert seen[3] == 1 and seen[6] == 2  # saved after each finished task
    assert len(json.loads(path.read_text())) == 2
    assert not list(path.parent.glob("*.tmp"))


def _note(subject, chapter, label, agreement, quote, pid="ch02.s1.p1"):
    return {
        "rule_id": "OOC.VOICE",
        "item_state": "note",
        "subject": subject,
        "chapter": chapter,
        "label": label,
        "agreement": agreement,
        "symptom": "x",
        "evidence": [{"kind": "prose", "paragraph_id": pid, "quote": quote}],
    }


def test_voice_report_collapses_quiet_labels_and_lists_drift_and_break():
    report = {
        "summary": "s",
        "lens": [],
        "items": [
            _note("mara", 2, "in_voice", "3_of_3", "Mara nodded"),
            _note("mara", 3, "in_voice", "2_of_3", "Mara waited"),
            _note("mara", 3, "not_enough_evidence", "2_of_3", "Mara left"),
            _note("teodor", 2, "drift", "2_of_3", "Teodor laughed loudly"),
            _note("teodor", 4, "break", "low_agreement", "Teodor wept"),
        ],
    }
    text = render(report)
    assert "- [note] OOC.VOICE mara: in_voice x2, not_enough_evidence x1" in text
    assert 'teodor ch2 label=drift agreement=2_of_3 quote="Teodor laughed loudly"' in text
    assert (
        '(tentative) teodor ch4 label=break agreement=low_agreement quote="Teodor wept"'
        in text
    )
    assert "Mara nodded" not in text
    assert "(tentative) teodor ch2" not in text


def _spell(text, aliases):
    doc = normalize_markdown(text, chapter=1)
    return name_spelling(doc.paragraphs, aliases)


def test_possessive_forms_of_alias_are_not_flagged():
    text = "Ilyas coat. Ilyas' coat. Ilya's coat. Ilya\u2019s map. Ilyas's knife."
    assert _spell(text, ["Ilya"]) == []
    assert _spell(text, ["Ilyas"]) == []


def test_identical_spelling_findings_are_deduped_with_count():
    items = _spell("Teodr ran. Teodr hid.\n\nTeodr came back.", ["Teodor"])
    assert len(items) == 1
    assert items[0]["total"] == 3
    assert items[0]["symptom"].endswith("Seen 3 times.")
    assert len(items[0]["evidence"]) == 3
