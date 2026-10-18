"""doctor run / doctor canon load. Layer A makes no provider call."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

import yaml

from doctor.factstore import load_facts
from doctor.intake import load_intake, load_profile, load_tags
from doctor.layerb import (
    PASSAGES_PER_CHAPTER,
    ProviderRefused,
    get_provider,
    run_layer_b,
)
from doctor.normalize import DuplicateChapter, normalize_sources
from doctor.pipeline import (
    applicable_facts,
    build_mentions,
    graph_from,
    run_rules,
    summarize,
)
from doctor.render import render
from doctor.validate_output import validate_report

SOURCE_SUFFIXES = {".md", ".txt", ".html", ".htm"}

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
    max_passages: int | None = None,
    per_chapter: int | None = None,
    on_call=None,
    profile_cache: dict | None = None,
    refresh_profiles: bool = False,
    on_profile=None,
) -> dict:
    intake_data = yaml.safe_load((work / "intake.yaml").read_text(encoding="utf-8"))
    profile = {}
    if (work / "profile.yaml").exists():
        profile = load_profile(
            yaml.safe_load((work / "profile.yaml").read_text(encoding="utf-8"))
        )
    intake_data["profile"] = profile
    intake_data["_work_name"] = work.name
    intake, seeded = load_intake(intake_data)
    tags = None
    if (work / "tags.yaml").exists():
        tags = load_tags(
            yaml.safe_load((work / "tags.yaml").read_text(encoding="utf-8"))
        )
    sources = [
        (path.name, path.read_text(encoding="utf-8"))
        for path in sorted(work.iterdir())
        if path.suffix.lower() in SOURCE_SUFFIXES and path.is_file()
    ]
    doc = normalize_sources(sources)
    extra = []
    facts_path = work / "facts.json"
    if facts_path.exists():
        extra = load_facts(facts_path.read_text(encoding="utf-8"))
    canon = home_canon(
        home if home is not None else doctor_home(), intake.get("primary_canon_source")
    )
    facts = applicable_facts(seeded + canon + extra, intake)
    graph = graph_from(doc, facts, intake)
    mentions = build_mentions(doc, facts)
    items, lens, summary = run_rules(doc, facts, intake, tags, graph, mentions, layer_b)
    if layer_b:
        b_items, b_lens, voice_profiles = run_layer_b(
            doc,
            intake,
            graph,
            mentions,
            provider or get_provider("mock"),
            cache,
            max_passages,
            per_chapter or PASSAGES_PER_CHAPTER,
            on_call=on_call,
            profile_cache=profile_cache,
            refresh_profiles=refresh_profiles,
            on_profile=on_profile,
        )
        opted = {row["rule_id"] for row in lens if row["reason"] == "opted_out"}
        lens = [
            b_lens.get(row["rule_id"], row) if row["rule_id"] not in opted else row
            for row in lens
        ]
        items.extend(item for item in b_items if item["rule_id"] not in opted)
    report = {"summary": summary, "lens": lens, "items": items}
    if layer_b:
        report["voice_profiles"] = voice_profiles
    paragraphs = {paragraph.id: paragraph.text for paragraph in doc.paragraphs}
    hashes = {paragraph.id: paragraph.content_hash for paragraph in doc.paragraphs}
    fact_index = {fact["id"]: fact for fact in facts}
    report = drop_invalid_items(report, paragraphs, fact_index, hashes)
    errors = validate_report(report, paragraphs, fact_index, hashes)
    if errors:
        raise SystemExit("report failed validation: " + "; ".join(errors))
    return report


def drop_invalid_items(
    report: dict, paragraphs: dict, fact_index: dict, hashes: dict | None = None
) -> dict:
    """Drop any item that fails validation instead of losing the whole report.

    Dropped items are counted in one unverifiable note so the gap is visible.
    """
    kept, reasons = [], []
    for item in report["items"]:
        errors = validate_report(
            {"summary": "", "lens": [], "items": [item]}, paragraphs, fact_index, hashes
        )
        if errors:
            reasons.append(f"{item.get('rule_id')}: {errors[0]}")
        else:
            kept.append(item)
    if not reasons:
        return report
    kept.append(
        {
            "rule_id": "REPORT.VALIDATION",
            "item_state": "unverifiable",
            "tier": "A1",
            "severity": "info",
            "kind": "unverifiable",
            "symptom": f"{len(reasons)} items failed validation and were dropped. First: {reasons[0]}"[
                :300
            ],
            "evidence": [{"kind": "file", "path": "report.json", "field": "items"}],
            "fact_ids": [],
            "depends_on_hash": hashlib.sha256(
                "|".join(reasons).encode("utf-8")
            ).hexdigest(),
        }
    )
    return {**report, "items": kept, "summary": summarize(kept)}


def cache_path(home: Path) -> Path:
    return home / "cache" / "layerb.json"


def load_cache(home: Path) -> dict:
    path = cache_path(home)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def save_cache(home: Path, cache: dict) -> None:
    path = cache_path(home)
    if _inside_repo(path):
        raise SystemExit(
            f"refusing to write the Layer B cache inside this repo: {path}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="layerb.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(cache, sort_keys=True))
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def profiles_path(home: Path) -> Path:
    return home / "cache" / "profiles.json"


def load_profile_cache(home: Path) -> dict:
    path = profiles_path(home)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def save_profile_cache(home: Path, cache: dict) -> None:
    path = profiles_path(home)
    if _inside_repo(path):
        raise SystemExit(
            f"refusing to write the voice-profile cache inside this repo: {path}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="profiles.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(cache, sort_keys=True))
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def run_work(
    work: Path,
    layer_b: bool = False,
    home: Path | None = None,
    provider=None,
    cache: dict | None = None,
    max_passages: int | None = None,
    per_chapter: int | None = None,
    refresh_profiles: bool = False,
) -> str:
    """Render a report. With a real provider the cache persists under DOCTOR_HOME/cache."""
    persist = (
        cache is None and layer_b and provider is not None and provider.name != "mock"
    )
    root = home if home is not None else doctor_home()
    if persist:
        cache = load_cache(root)
        profile_cache = load_profile_cache(root)
    else:
        profile_cache = None
    try:
        report = build_report(
            work,
            layer_b=layer_b,
            home=home,
            provider=provider,
            cache=cache,
            max_passages=max_passages,
            per_chapter=per_chapter,
            on_call=(lambda c: save_cache(root, c)) if persist else None,
            profile_cache=profile_cache,
            refresh_profiles=refresh_profiles,
            on_profile=(lambda c: save_profile_cache(root, c)) if persist else None,
        )
    finally:
        if persist:
            save_cache(root, cache)
            save_profile_cache(root, profile_cache)
    return render(report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="doctor")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("work")
    run.add_argument("--layer-b", action="store_true")
    run.add_argument(
        "--provider",
        default="mock",
        help="Layer B provider: 'mock' or 'cursor-agent'. Non-mock needs DOCTOR_G9_OPT_IN=1.",
    )
    run.add_argument(
        "--max-passages",
        type=int,
        default=None,
        help="Cap on Layer B passages per rule. Overrides --per-chapter.",
    )
    run.add_argument(
        "--per-chapter",
        type=int,
        default=None,
        help=f"Default cap: this many passages per chapter per rule ({PASSAGES_PER_CHAPTER}).",
    )
    run.add_argument(
        "--refresh-voice-profiles",
        action="store_true",
        help="Regenerate cached OOC voice profiles even when the sample is unchanged.",
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
        try:
            text = run_work(
                Path(args.work),
                layer_b=args.layer_b,
                provider=provider,
                max_passages=args.max_passages,
                per_chapter=args.per_chapter,
                refresh_profiles=args.refresh_voice_profiles,
            )
        except DuplicateChapter as exc:
            raise SystemExit(str(exc)) from exc
        sys.stdout.write(text)
        stats = getattr(provider, "failures", None)
        if stats is not None:
            sys.stderr.write(
                json.dumps(
                    {
                        "provider": provider.name,
                        "calls": provider.calls,
                        "seconds": round(provider.seconds, 1),
                        "failures": dict(stats),
                        "usage": dict(provider.usage),
                    }
                )
                + "\n"
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
