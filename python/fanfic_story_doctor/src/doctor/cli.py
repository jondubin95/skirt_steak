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
from doctor.layerb import ProviderRefused, get_provider, run_layer_b
from doctor.normalize import normalize_sources
from doctor.pipeline import build_mentions, graph_from, run_rules
from doctor.render import render
from doctor.validate_output import validate_report

# Marker that identifies a checkout of this repo, wherever it lives.
REPO_MARKER = Path("python") / "fanfic_story_doctor" / "pyproject.toml"


def doctor_home() -> Path:
    return Path(os.environ.get("DOCTOR_HOME", Path.home() / "doctor-home"))


def _repo_roots(path: Path) -> list[Path]:
    """Checkouts of this repo that could contain `path`.

    Walks up from the path itself and from the current directory, so the guard
    holds for an installed package too (no reliance on __file__ location).
    """
    roots = []
    for start in (path.resolve(), Path.cwd().resolve()):
        for parent in [start, *start.parents]:
            if (parent / REPO_MARKER).is_file():
                roots.append(parent)
                break
    return roots


def _inside_repo(path: Path) -> bool:
    resolved = path.resolve()
    for root in _repo_roots(path):
        if resolved == root or root in resolved.parents:
            return True
    return False


def home_canon(home: Path, primary: str | None) -> list[dict]:
    """Private canon from DOCTOR_HOME/canon/<primary>/facts.json, if present."""
    if not primary:
        return []
    base = home / "canon" / primary
    ledger = base / "facts.json"
    if not ledger.is_file():
        return []
    text_dir = base / "text"
    return load_canon(ledger, text_dir if text_dir.is_dir() else None)


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
                    raise SystemExit(
                        "canon citation text is missing from the local chapter"
                    )
    # Proposed rows are never enforced. Disputed rows are kept so rules can
    # report them as unverifiable instead of silently falling through.
    return [fact for fact in facts if fact.get("status") in {"confirmed", "disputed"}]


def build_report(
    work: Path,
    layer_b: bool = False,
    home: Path | None = None,
    provider=None,
    cache: dict | None = None,
) -> dict:
    intake_data = yaml.safe_load((work / "intake.yaml").read_text(encoding="utf-8"))
    profile = {}
    if (work / "profile.yaml").exists():
        profile = load_profile(
            yaml.safe_load((work / "profile.yaml").read_text(encoding="utf-8"))
        )
    intake_data["profile"] = profile
    intake, seeded = load_intake(intake_data)
    tags = None
    if (work / "tags.yaml").exists():
        tags = load_tags(
            yaml.safe_load((work / "tags.yaml").read_text(encoding="utf-8"))
        )
    sources = [
        (path.name, path.read_text(encoding="utf-8"))
        for path in sorted(work.glob("*.md"))
    ]
    doc = normalize_sources(sources)
    extra = []
    facts_path = work / "facts.json"
    if facts_path.exists():
        extra = load_facts(facts_path.read_text(encoding="utf-8"))
    canon = home_canon(
        home if home is not None else doctor_home(), intake.get("primary_canon_source")
    )
    facts = seeded + canon + extra
    graph = graph_from(doc, facts, intake)
    mentions = build_mentions(doc, facts)
    items, lens, summary = run_rules(doc, facts, intake, tags, graph, mentions, layer_b)
    if layer_b:
        b_items, b_lens = run_layer_b(
            doc, intake, graph, mentions, provider or get_provider("mock"), cache
        )
        opted = {row["rule_id"] for row in lens if row["reason"] == "opted_out"}
        lens = [
            b_lens.get(row["rule_id"], row) if row["rule_id"] not in opted else row
            for row in lens
        ]
        items.extend(item for item in b_items if item["rule_id"] not in opted)
    report = {"summary": summary, "lens": lens, "items": items}
    paragraphs = {paragraph.id: paragraph.text for paragraph in doc.paragraphs}
    fact_index = {fact["id"]: fact for fact in facts}
    errors = validate_report(report, paragraphs, fact_index)
    if errors:
        raise SystemExit("report failed validation: " + "; ".join(errors))
    return report


def run_work(
    work: Path,
    layer_b: bool = False,
    home: Path | None = None,
    provider=None,
    cache: dict | None = None,
) -> str:
    return render(
        build_report(work, layer_b=layer_b, home=home, provider=provider, cache=cache)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="doctor")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("work")
    run.add_argument("--layer-b", action="store_true")
    run.add_argument(
        "--provider",
        default="mock",
        help="Layer B provider. Only 'mock' runs; others are refused by gate G9.",
    )
    canon = sub.add_parser("canon")
    canon_sub = canon.add_subparsers(dest="canon_cmd", required=True)
    load = canon_sub.add_parser("load")
    load.add_argument("ledger")
    load.add_argument("--text", default=None)
    args = parser.parse_args(argv)
    if args.cmd == "run":
        provider = None
        if args.layer_b:
            try:
                provider = get_provider(args.provider)
            except ProviderRefused as exc:
                sys.stderr.write(f"{exc}\n")
                return 3
        sys.stdout.write(
            run_work(Path(args.work), layer_b=args.layer_b, provider=provider)
        )
        return 0
    if args.cmd == "canon" and args.canon_cmd == "load":
        text = Path(args.text) if args.text else None
        facts = load_canon(Path(args.ledger), text)
        sys.stdout.write(
            json.dumps(
                {
                    "confirmed": sum(
                        1 for fact in facts if fact.get("status") == "confirmed"
                    )
                }
            )
        )
        return 0
    return 2
