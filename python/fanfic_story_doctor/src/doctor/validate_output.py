"""Report validation. Schema, evidence, never-rewrite. Tier A1."""

from __future__ import annotations

import json
import re
from pathlib import Path

REWRITE = re.compile(
    r"\b(?:rewrite as\b|replace with\b|try:|for example:)", re.IGNORECASE
)
QUOTED = re.compile(r'"([^"]+)"')

# Shipped inside the package (see [tool.setuptools.package-data]).
SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "report.schema.json"


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_report(
    report: dict, paragraphs: dict[str, str], facts: dict[str, dict]
) -> list[str]:
    errors: list[str] = []
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("jsonschema is required") from exc
    try:
        jsonschema.validate(report, load_schema())
    except jsonschema.ValidationError as exc:
        errors.append(f"schema: {exc.message}")
        return errors
    for item in report.get("items") or []:
        for evidence in item.get("evidence") or []:
            if evidence.get("kind") == "prose":
                pid = evidence.get("paragraph_id")
                quote = evidence.get("quote") or ""
                if pid not in paragraphs:
                    errors.append(f"unknown paragraph {pid}")
                elif quote and quote not in paragraphs[pid]:
                    errors.append(f"quote is not in {pid}")
        for fact_id in item.get("fact_ids") or []:
            if fact_id and fact_id not in facts:
                errors.append(f"unknown fact {fact_id}")
        errors.extend(_layer_b_contract(item))
        if _rewrite(item, paragraphs, facts):
            errors.append(f"never-rewrite: {item.get('rule_id')}")
    return errors


LAYER_B_RULES = {"OOC.VOICE", "CANON.RAILS"}


def _layer_b_contract(item: dict) -> list[str]:
    """Layer B is info only, never a finding or blocker, labels closed."""
    from doctor.layerb import LABELS

    rule = item.get("rule_id")
    if rule not in LAYER_B_RULES and item.get("tier") != "B":
        return []
    errors = []
    if item.get("severity") != "info":
        errors.append(f"layer-b severity above info: {rule}")
    if item.get("item_state") not in {"note", "coverage"}:
        errors.append(f"layer-b item_state not allowed: {rule}")
    if item.get("item_state") == "note":
        if item.get("label") not in LABELS.get(rule, set()):
            errors.append(f"layer-b label not closed: {rule}")
        if not item.get("observed") or not item.get("interpretation"):
            errors.append(f"layer-b observed/interpretation missing: {rule}")
        prose = [
            ev
            for ev in item.get("evidence") or []
            if ev.get("kind") == "prose" and ev.get("quote")
        ]
        if not prose:
            errors.append(f"layer-b exact quote missing: {rule}")
    return errors


def _rewrite(item: dict, paragraphs: dict[str, str], facts: dict[str, dict]) -> bool:
    allowed = set()
    for evidence in item.get("evidence") or []:
        if evidence.get("kind") == "prose" and evidence.get("quote"):
            allowed.add(evidence["quote"])
            text = paragraphs.get(evidence.get("paragraph_id", ""), "")
            allowed.add(text)
    for fact_id in item.get("fact_ids") or []:
        fact = facts.get(fact_id) or {}
        obj = fact.get("object")
        if isinstance(obj, str):
            allowed.add(obj)
        citation = (fact.get("citation") or {}).get("text")
        if citation:
            allowed.add(citation)
    for field in ("symptom", "observed", "interpretation", "suggested_fix"):
        value = item.get(field) or ""
        if field == "suggested_fix" and len(value) > 240:
            return True
        if REWRITE.search(value):
            return True
        for quote in QUOTED.findall(value):
            if quote not in allowed and not any(quote in blob for blob in allowed):
                return True
    return False
