"""doctor run / doctor canon load. Layer A makes no provider call."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

from doctor.factstore import load_facts
from doctor.intake import load_intake, load_profile, load_tags
from doctor.normalize import normalize_sources
from doctor.pipeline import build_mentions, graph_from, run_rules
from doctor.render import render
from doctor.validate_output import validate_report

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PACKAGE_ROOT.parents[1]


def doctor_home() -> Path:
    return Path(os.environ.get("DOCTOR_HOME", Path.home() / "doctor-home"))


def _inside_repo(path: Path) -> bool:
    try:
        path.resolve().relative_to(REPO_ROOT.resolve())
        return True
    except ValueError:
        return False


def load_canon(path: Path, text_dir: Path | None = None) -> list[dict]:
    if _inside_repo(path):
        raise SystemExit("refusing a canon ledger inside the repo")
    facts = load_facts(path.read_text(encoding="utf-8"))
    if text_dir is not None:
        chapters = []
        for file in sorted(text_dir.glob("*.md")):
            chapters.append((file.name, file.read_text(encoding="utf-8")))
        doc = normalize_sources(chapters) if chapters else None
        if doc is not None:
            paragraphs = {paragraph.id: paragraph.text for paragraph in doc.paragraphs}
            for fact in facts:
                quote = (fact.get("citation") or {}).get("text")
                if quote and not any(quote in text for text in paragraphs.values()):
                    raise SystemExit("canon citation text is missing from the local chapter")
    return [fact for fact in facts if fact.get("status") == "confirmed"]


def run_work(work: Path, layer_b: bool = False) -> str:
    intake_data = yaml.safe_load((work / "intake.yaml").read_text(encoding="utf-8"))
    profile = {}
    if (work / "profile.yaml").exists():
        profile = load_profile(yaml.safe_load((work / "profile.yaml").read_text(encoding="utf-8")))
    intake_data["profile"] = profile
    intake, seeded = load_intake(intake_data)
    tags = None
    if (work / "tags.yaml").exists():
        tags = load_tags(yaml.safe_load((work / "tags.yaml").read_text(encoding="utf-8")))
    sources = [(path.name, path.read_text(encoding="utf-8")) for path in sorted(work.glob("*.md"))]
    doc = normalize_sources(sources)
    extra = []
    facts_path = work / "facts.json"
    if facts_path.exists():
        extra = load_facts(facts_path.read_text(encoding="utf-8"))
    facts = seeded + extra
    graph = graph_from(doc, facts, intake)
    mentions = build_mentions(doc, facts)
    items, lens, summary = run_rules(doc, facts, intake, tags, graph, mentions, layer_b)
    report = {"summary": summary, "lens": lens, "items": items}
    paragraphs = {paragraph.id: paragraph.text for paragraph in doc.paragraphs}
    fact_index = {fact["id"]: fact for fact in facts}
    errors = validate_report(report, paragraphs, fact_index)
    if errors:
        raise SystemExit("report failed validation: " + "; ".join(errors))
    return render(report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="doctor")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("work")
    run.add_argument("--layer-b", action="store_true")
    canon = sub.add_parser("canon")
    canon_sub = canon.add_subparsers(dest="canon_cmd", required=True)
    load = canon_sub.add_parser("load")
    load.add_argument("ledger")
    load.add_argument("--text", default=None)
    args = parser.parse_args(argv)
    if args.cmd == "run":
        sys.stdout.write(run_work(Path(args.work), layer_b=args.layer_b))
        return 0
    if args.cmd == "canon" and args.canon_cmd == "load":
        text = Path(args.text) if args.text else None
        facts = load_canon(Path(args.ledger), text)
        sys.stdout.write(json.dumps({"confirmed": len(facts)}))
        return 0
    return 2
