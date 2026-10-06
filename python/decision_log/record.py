#!/usr/bin/env python3
"""Record, check, resolve, and verify market-analyst decisions.

The database and playbooks stay under Sensitive/. This script checks that
the JSON fields agree with each other. It does not check that a claim is true.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TextIO

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "sql" / "decision_log" / "schema.sql"
SUMMARY_PATH = REPO_ROOT / "sql" / "decision_log" / "review_summary.sql"
DEFAULT_DB = Path("Sensitive") / "decisions" / "market_decisions.duckdb"
PLAYBOOK_TEMPLATE = "Sensitive/decisions/playbooks/{id}.md"

VERDICTS = frozenset({"ready", "not ready", "hard-blocked"})
OUTCOMES = frozenset({"right", "wrong", "inconclusive"})
EVIDENCE_CLASSES = frozenset(
    {"data-backed", "plausible but unverified", "narrative-only"}
)
RECORD_FIELDS = frozenset(
    {
        "id",
        "supersedes",
        "market",
        "thesis",
        "verdict",
        "invalidation",
        "observed_at",
        "market_snapshot",
        "evidence",
    }
)
EVIDENCE_FIELDS = frozenset({"claim", "class", "core", "basis_ref"})
SCHEMA_VERSION = 1
DB_LOCK_MESSAGE = "close other sessions or the file is not a database"
VERSION_MESSAGE = "schema version mismatch, this CLI expects 1"


class DecisionLogError(Exception):
    """A refusal that names a field path and a reason, never a field value."""

    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        super().__init__(f"{field}: {reason}")


def _statements(sql: str) -> list[str]:
    lines = []
    for line in sql.splitlines():
        if line.strip().startswith("--"):
            continue
        lines.append(line)
    return [part.strip() for part in "\n".join(lines).split(";") if part.strip()]


def _under_sensitive(path: Path, repo_root: Path) -> bool:
    try:
        path.resolve().relative_to((repo_root / "Sensitive").resolve())
    except ValueError:
        return False
    return True


def _canonical_uuid(value: Any, field: str) -> uuid.UUID:
    if not isinstance(value, str):
        raise DecisionLogError(field, "must be a canonical uuid")
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise DecisionLogError(field, "must be a canonical uuid") from exc
    if str(parsed) != value:
        raise DecisionLogError(field, "must be a canonical uuid")
    return parsed


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise DecisionLogError(field, "must be a string")
    text = value.strip()
    if not text:
        raise DecisionLogError(field, "must be non-empty")
    return text


def _parse_observed_at(value: Any) -> datetime:
    field = "observed_at"
    if not isinstance(value, str):
        raise DecisionLogError(field, "must be an ISO-8601 timestamp with a timezone")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise DecisionLogError(
            field, "must be an ISO-8601 timestamp with a timezone"
        ) from exc
    if parsed.tzinfo is None:
        raise DecisionLogError(field, "must include a timezone")
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _playbook_relative(decision_id: uuid.UUID) -> str:
    return PLAYBOOK_TEMPLATE.format(id=decision_id)


def _hash_playbook(repo_root: Path, decision_id: uuid.UUID) -> tuple[str, str]:
    relative = _playbook_relative(decision_id)
    path = repo_root / relative
    if not _under_sensitive(path, repo_root) or not path.is_file():
        raise DecisionLogError("playbook", "must be a non-empty file under Sensitive")
    if path.stat().st_size == 0:
        raise DecisionLogError("playbook", "must be non-empty")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return relative, digest


def _parse_evidence(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        raise DecisionLogError("evidence", "must be a list")
    parsed: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        prefix = f"evidence[{index}]"
        if not isinstance(item, dict):
            raise DecisionLogError(prefix, "must be an object")
        unknown = set(item) - EVIDENCE_FIELDS
        if unknown:
            name = sorted(unknown)[0]
            raise DecisionLogError(f"{prefix}.{name}", "unknown field")
        if "class" not in item:
            raise DecisionLogError(f"{prefix}.class", "required")
        evidence_class = item["class"]
        if evidence_class not in EVIDENCE_CLASSES:
            raise DecisionLogError(f"{prefix}.class", "must be a known evidence class")
        claim = _required_text(item.get("claim"), f"{prefix}.claim")
        if "core" in item and not isinstance(item["core"], bool):
            raise DecisionLogError(f"{prefix}.core", "must be a boolean")
        core = bool(item["core"]) if "core" in item else False
        basis_ref = None
        if "basis_ref" in item and item["basis_ref"] is not None:
            basis_ref = _required_text(item["basis_ref"], f"{prefix}.basis_ref")
        if evidence_class == "data-backed" and not basis_ref:
            raise DecisionLogError(f"{prefix}.basis_ref", "required for data-backed")
        parsed.append(
            {
                "claim": claim,
                "class": evidence_class,
                "core": core,
                "basis_ref": basis_ref,
            }
        )
    return parsed


def _allowed_verdicts(evidence: list[dict[str, Any]]) -> set[str]:
    classes = [item["class"] for item in evidence]
    has_data = "data-backed" in classes
    has_plausible = "plausible but unverified" in classes
    if not has_data and not has_plausible:
        return {"hard-blocked"}
    if not has_data:
        return {"not ready"}
    allowed = {"not ready"}
    cores = [item for item in evidence if item["core"]]
    if cores and all(item["class"] == "data-backed" for item in cores):
        allowed.add("ready")
    return allowed


def _load_payload(inbox_path: Path, repo_root: Path) -> dict[str, Any]:
    if not inbox_path.is_file() or not _under_sensitive(inbox_path, repo_root):
        raise DecisionLogError("input", "must be a file under Sensitive")
    try:
        raw = json.loads(inbox_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise DecisionLogError("input", "must be JSON") from exc
    if not isinstance(raw, dict):
        raise DecisionLogError("input", "must be a JSON object")
    unknown = set(raw) - RECORD_FIELDS
    if unknown:
        raise DecisionLogError(sorted(unknown)[0], "unknown field")
    if "id" not in raw:
        raise DecisionLogError("id", "required")
    decision_id = _canonical_uuid(raw["id"], "id")
    supersedes = None
    if "supersedes" in raw and raw["supersedes"] is not None:
        supersedes = _canonical_uuid(raw["supersedes"], "supersedes")
        if supersedes == decision_id:
            raise DecisionLogError("supersedes", "must not equal id")
    if "verdict" not in raw:
        raise DecisionLogError("verdict", "required")
    if raw["verdict"] not in VERDICTS:
        raise DecisionLogError("verdict", "must be ready, not ready, or hard-blocked")
    if "evidence" not in raw:
        raise DecisionLogError("evidence", "required")
    evidence = _parse_evidence(raw["evidence"])
    if raw["verdict"] not in _allowed_verdicts(evidence):
        raise DecisionLogError("verdict", "not allowed for this evidence")
    for field in ("market", "thesis", "invalidation", "market_snapshot"):
        if field not in raw:
            raise DecisionLogError(field, "required")
    if "observed_at" not in raw:
        raise DecisionLogError("observed_at", "required")
    relative, digest = _hash_playbook(repo_root, decision_id)
    counts = Counter(item["class"] for item in evidence)
    return {
        "id": decision_id,
        "supersedes": supersedes,
        "market": _required_text(raw["market"], "market"),
        "thesis": _required_text(raw["thesis"], "thesis"),
        "verdict": raw["verdict"],
        "invalidation": _required_text(raw["invalidation"], "invalidation"),
        "observed_at": _parse_observed_at(raw["observed_at"]),
        "market_snapshot": _required_text(raw["market_snapshot"], "market_snapshot"),
        "evidence": evidence,
        "playbook_path": relative,
        "playbook_sha256": digest,
        "counts": counts,
        "core_count": sum(1 for item in evidence if item["core"]),
    }


def _db_path(repo_root: Path, db_path: Path | None) -> Path:
    if db_path is None:
        return repo_root / DEFAULT_DB
    return db_path


def _connect(path: Path, *, read_only: bool) -> duckdb.DuckDBPyConnection:
    try:
        return duckdb.connect(str(path), read_only=read_only)
    except duckdb.Error as exc:
        raise DecisionLogError("database", DB_LOCK_MESSAGE) from exc


def _main_tables(con: duckdb.DuckDBPyConnection) -> list[str]:
    try:
        rows = con.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main' AND table_type = 'BASE TABLE'
            """).fetchall()
    except duckdb.Error as exc:
        raise DecisionLogError("database", DB_LOCK_MESSAGE) from exc
    return [row[0] for row in rows]


def _require_version(con: duckdb.DuckDBPyConnection) -> None:
    try:
        rows = con.execute("SELECT version FROM schema_meta").fetchall()
    except duckdb.CatalogException as exc:
        raise DecisionLogError("schema_meta", VERSION_MESSAGE) from exc
    except duckdb.Error as exc:
        raise DecisionLogError("database", DB_LOCK_MESSAGE) from exc
    if len(rows) != 1 or rows[0][0] != SCHEMA_VERSION:
        raise DecisionLogError("schema_meta", VERSION_MESSAGE)


def apply_schema_if_empty(con: duckdb.DuckDBPyConnection) -> None:
    """Create version-1 tables only when the file has no user tables."""
    if _main_tables(con):
        _require_version(con)
        return
    try:
        for statement in _statements(SCHEMA_PATH.read_text(encoding="utf-8")):
            con.execute(statement)
    except duckdb.Error as exc:
        raise DecisionLogError("database", DB_LOCK_MESSAGE) from exc


def summary_rows(con: duckdb.DuckDBPyConnection) -> list[tuple[Any, ...]]:
    sql = SUMMARY_PATH.read_text(encoding="utf-8")
    return con.execute(sql).fetchall()


def _format_review(payload: dict[str, Any]) -> str:
    counts = payload["counts"]
    lines = [
        f"id: {payload['id']}",
        f"verdict: {payload['verdict']}",
        f"data-backed: {counts['data-backed']}",
        f"plausible but unverified: {counts['plausible but unverified']}",
        f"narrative-only: {counts['narrative-only']}",
        f"core: {payload['core_count']}",
        f"playbook_sha256: {payload['playbook_sha256']}",
    ]
    return "\n".join(lines) + "\n"


def _reject_duplicate_and_missing_parent(
    con: duckdb.DuckDBPyConnection, payload: dict[str, Any]
) -> None:
    _require_version(con)
    found = con.execute(
        "SELECT 1 FROM decisions WHERE id = ?", [str(payload["id"])]
    ).fetchone()
    if found:
        raise DecisionLogError("id", "duplicate id")
    if payload["supersedes"] is not None:
        parent = con.execute(
            "SELECT 1 FROM decisions WHERE id = ?", [str(payload["supersedes"])]
        ).fetchone()
        if parent is None:
            raise DecisionLogError("supersedes", "not found")


def check(
    inbox_path: Path,
    *,
    repo_root: Path = REPO_ROOT,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Validate JSON and the playbook. Open the database only when it exists."""
    payload = _load_payload(inbox_path, repo_root)
    path = _db_path(repo_root, db_path)
    if not path.is_file():
        if payload["supersedes"] is not None:
            raise DecisionLogError("supersedes", "not found")
        return payload
    con = _connect(path, read_only=True)
    try:
        _reject_duplicate_and_missing_parent(con, payload)
    finally:
        con.close()
    return payload


def record(
    inbox_path: Path,
    *,
    repo_root: Path = REPO_ROOT,
    db_path: Path | None = None,
    now: Callable[[], datetime] | None = None,
    fail_after_decision: bool = False,
) -> dict[str, Any]:
    """Insert one decision and its claims after static validation succeeds."""
    payload = _load_payload(inbox_path, repo_root)
    path = _db_path(repo_root, db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    created = not path.is_file()
    con = _connect(path, read_only=False)
    try:
        if created or not _main_tables(con):
            apply_schema_if_empty(con)
        else:
            _require_version(con)
        _reject_duplicate_and_missing_parent(con, payload)
        created_at = (now or _utc_now)()
        try:
            con.begin()
            con.execute(
                """
                INSERT INTO decisions (
                    id, supersedes, market, thesis, invalidation, market_snapshot,
                    observed_at, verdict, playbook_path, playbook_sha256, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    str(payload["id"]),
                    (
                        None
                        if payload["supersedes"] is None
                        else str(payload["supersedes"])
                    ),
                    payload["market"],
                    payload["thesis"],
                    payload["invalidation"],
                    payload["market_snapshot"],
                    payload["observed_at"],
                    payload["verdict"],
                    payload["playbook_path"],
                    payload["playbook_sha256"],
                    created_at,
                ],
            )
            if fail_after_decision:
                raise DecisionLogError("insert", "forced failure")
            for position, item in enumerate(payload["evidence"]):
                con.execute(
                    """
                    INSERT INTO evidence (
                        id, decision_id, position, claim, evidence_class, core, basis_ref
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        str(uuid.uuid4()),
                        str(payload["id"]),
                        position,
                        item["claim"],
                        item["class"],
                        item["core"],
                        item["basis_ref"],
                    ],
                )
            con.commit()
        except Exception:
            con.rollback()
            raise
    except Exception:
        con.close()
        if created and path.is_file():
            # A failed first open can leave an empty file. Validation already passed,
            # so keep a schema-only file when the insert itself rolled back.
            pass
        raise
    else:
        con.close()
    payload["created_at"] = created_at
    return payload


def resolve(
    decision_id: str,
    outcome: str,
    *,
    notes: str | None = None,
    repo_root: Path = REPO_ROOT,
    db_path: Path | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Set outcome once. Does not create a database."""
    parsed_id = _canonical_uuid(decision_id, "id")
    if outcome not in OUTCOMES:
        raise DecisionLogError("outcome", "must be right, wrong, or inconclusive")
    path = _db_path(repo_root, db_path)
    if not path.is_file():
        raise DecisionLogError("database", "not found")
    con = _connect(path, read_only=False)
    try:
        _require_version(con)
        resolved_at = (now or _utc_now)()
        stored_notes = None if notes is None else notes
        existing = con.execute(
            "SELECT outcome FROM decisions WHERE id = ?", [str(parsed_id)]
        ).fetchone()
        if existing is None:
            raise DecisionLogError("id", "not found")
        if existing[0] is not None:
            raise DecisionLogError("outcome", "already resolved")
        evidence = con.execute(
            """
            SELECT id, decision_id, position, claim, evidence_class, core, basis_ref
            FROM evidence WHERE decision_id = ?
            ORDER BY position
            """,
            [str(parsed_id)],
        ).fetchall()
        # DuckDB rejects UPDATE of a referenced row until the child delete has
        # committed, so this cannot be one transaction. Restore the claims if
        # the outcome write fails.
        removed = False
        try:
            if evidence:
                con.execute(
                    "DELETE FROM evidence WHERE decision_id = ?", [str(parsed_id)]
                )
                removed = True
            updated = con.execute(
                """
                UPDATE decisions
                SET outcome = ?, resolved_at = ?, outcome_notes = ?
                WHERE id = ? AND outcome IS NULL
                """,
                [outcome, resolved_at, stored_notes, str(parsed_id)],
            ).fetchone()
            if updated is None or updated[0] != 1:
                raise DecisionLogError("id", "not found")
            if evidence:
                con.executemany(
                    "INSERT INTO evidence VALUES (?, ?, ?, ?, ?, ?, ?)",
                    evidence,
                )
                removed = False
        except Exception:
            if removed:
                con.executemany(
                    "INSERT INTO evidence VALUES (?, ?, ?, ?, ?, ?, ?)",
                    evidence,
                )
            raise
    finally:
        con.close()
    return {"id": parsed_id, "outcome": outcome, "resolved_at": resolved_at}


def _stored_playbook(repo_root: Path, relative: str) -> Path:
    if (
        not isinstance(relative, str)
        or not relative.startswith("Sensitive/decisions/playbooks/")
        or ".." in relative.replace("\\", "/")
    ):
        raise DecisionLogError("playbook_path", "invalid")
    path = repo_root / Path(relative)
    if not _under_sensitive(path, repo_root):
        raise DecisionLogError("playbook_path", "invalid")
    return path


def verify(
    decision_id: str,
    *,
    repo_root: Path = REPO_ROOT,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Re-hash the playbook and compare it to the stored digest."""
    parsed_id = _canonical_uuid(decision_id, "id")
    path = _db_path(repo_root, db_path)
    if not path.is_file():
        raise DecisionLogError("database", "not found")
    con = _connect(path, read_only=True)
    try:
        _require_version(con)
        row = con.execute(
            "SELECT playbook_path, playbook_sha256 FROM decisions WHERE id = ?",
            [str(parsed_id)],
        ).fetchone()
    finally:
        con.close()
    if row is None:
        raise DecisionLogError("id", "not found")
    relative, stored = row
    playbook = _stored_playbook(repo_root, relative)
    matches = (
        playbook.is_file()
        and hashlib.sha256(playbook.read_bytes()).hexdigest() == stored
    )
    return {
        "id": parsed_id,
        "playbook_sha256": stored,
        "match": matches,
    }


def _format_resolve(result: dict[str, Any]) -> str:
    return (
        f"id: {result['id']}\n"
        f"outcome: {result['outcome']}\n"
        f"resolved_at: {result['resolved_at'].isoformat()}\n"
    )


def _format_verify(result: dict[str, Any]) -> str:
    flag = "yes" if result["match"] else "no"
    return (
        f"id: {result['id']}\n"
        f"playbook_sha256: {result['playbook_sha256']}\n"
        f"match: {flag}\n"
    )


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)


def main(
    argv: list[str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    out = stdout or sys.stdout
    err = stderr or sys.stderr
    parser = argparse.ArgumentParser(description="Local market decision log")
    sub = parser.add_subparsers(dest="command", required=True)

    check_parser = sub.add_parser("check")
    _add_common(check_parser)
    check_parser.add_argument("--input", type=Path, required=True)

    record_parser = sub.add_parser("record")
    _add_common(record_parser)
    record_parser.add_argument("--input", type=Path, required=True)

    resolve_parser = sub.add_parser("resolve")
    _add_common(resolve_parser)
    resolve_parser.add_argument("--id", required=True)
    resolve_parser.add_argument("--outcome", required=True)
    resolve_parser.add_argument("--notes", default=None)

    verify_parser = sub.add_parser("verify")
    _add_common(verify_parser)
    verify_parser.add_argument("--id", required=True)

    args = parser.parse_args(argv)
    repo_root = args.repo_root
    try:
        if args.command == "check":
            payload = check(args.input, repo_root=repo_root, db_path=args.db)
            out.write(_format_review(payload))
            return 0
        if args.command == "record":
            payload = record(args.input, repo_root=repo_root, db_path=args.db)
            out.write(_format_review(payload))
            return 0
        if args.command == "resolve":
            result = resolve(
                args.id,
                args.outcome,
                notes=args.notes,
                repo_root=repo_root,
                db_path=args.db,
            )
            out.write(_format_resolve(result))
            return 0
        result = verify(args.id, repo_root=repo_root, db_path=args.db)
        out.write(_format_verify(result))
        return 0 if result["match"] else 1
    except DecisionLogError as exc:
        err.write(f"{exc.field}: {exc.reason}\n")
        return 1
    except Exception:
        err.write(f"database: {DB_LOCK_MESSAGE}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
