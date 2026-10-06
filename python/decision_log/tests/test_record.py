"""Decision log gates, persistence, and output hygiene."""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from datetime import datetime
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from decision_log.record import (  # noqa: E402
    REPO_ROOT,
    DecisionLogError,
    apply_schema_if_empty,
    check,
    main,
    record,
    resolve,
    summary_rows,
    verify,
)

ID_READY = "11111111-1111-4111-8111-111111111111"
ID_NEXT = "22222222-2222-4222-8222-222222222222"
THESIS = "THESIS-SECRET-ALPHA"
CLAIM_DATA = "CLAIM-SECRET-BETA"
CLAIM_NARRATIVE = "CLAIM-SECRET-BETA-NARRATIVE"
INVALIDATION = "INVALIDATION-SECRET-GAMMA"
SNAPSHOT = "SNAPSHOT-SECRET-DELTA"
BASIS = "BASIS-SECRET-EPSILON"
NOTES = "NOTES-SECRET-ZETA"
PLAYBOOK = "PLAYBOOK-SECRET-ETA"
SECRETS = (
    THESIS,
    CLAIM_DATA,
    CLAIM_NARRATIVE,
    INVALIDATION,
    SNAPSHOT,
    BASIS,
    NOTES,
    PLAYBOOK,
)


def _payload(decision_id: str = ID_READY, **overrides: object) -> dict:
    body = {
        "id": decision_id,
        "market": "Synthetic market",
        "thesis": THESIS,
        "verdict": "ready",
        "invalidation": INVALIDATION,
        "observed_at": "2026-10-06T15:30:00-04:00",
        "market_snapshot": SNAPSHOT,
        "evidence": [
            {
                "claim": CLAIM_DATA,
                "class": "data-backed",
                "core": True,
                "basis_ref": BASIS,
            },
            {"claim": CLAIM_NARRATIVE, "class": "narrative-only", "core": False},
        ],
    }
    body.update(overrides)
    return body


class DecisionLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def db_path(self) -> Path:
        return self.root / "Sensitive" / "decisions" / "market_decisions.duckdb"

    def write_inbox(self, payload: dict, body: str = PLAYBOOK + "\n") -> Path:
        decision_id = payload["id"]
        playbook = (
            self.root / "Sensitive" / "decisions" / "playbooks" / f"{decision_id}.md"
        )
        playbook.parent.mkdir(parents=True, exist_ok=True)
        playbook.write_bytes(body.encode("utf-8"))
        inbox = self.root / "Sensitive" / "decisions" / "inbox" / f"{decision_id}.json"
        inbox.parent.mkdir(parents=True, exist_ok=True)
        inbox.write_text(json.dumps(payload), encoding="utf-8")
        return inbox

    def connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.db_path()))

    def record_default(self, payload: dict, **kwargs: object) -> dict:
        inbox = self.write_inbox(payload)
        return record(inbox, repo_root=self.root, **kwargs)  # type: ignore[arg-type]

    def run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = main(argv, stdout, stderr)
        return code, stdout.getvalue(), stderr.getvalue()

    def assert_no_secrets(self, text: str) -> None:
        for secret in SECRETS:
            self.assertNotIn(secret, text)

    def test_ready_stores_order_hash_and_basis(self) -> None:
        inbox = self.write_inbox(_payload())
        fixed = datetime(2026, 2, 3, 4, 5, 6)
        result = record(inbox, repo_root=self.root, now=lambda: fixed)
        self.assertEqual(
            result["playbook_sha256"],
            hashlib.sha256((PLAYBOOK + "\n").encode()).hexdigest(),
        )
        con = self.connect()
        decision = con.execute("""
            SELECT market, thesis, verdict, observed_at, created_at, playbook_path, playbook_sha256
            FROM decisions
            """).fetchone()
        self.assertEqual(decision[2], "ready")
        self.assertEqual(decision[3], datetime(2026, 10, 6, 19, 30))
        self.assertEqual(decision[4], fixed)
        self.assertEqual(decision[5], f"Sensitive/decisions/playbooks/{ID_READY}.md")
        self.assertEqual(decision[6], result["playbook_sha256"])
        rows = con.execute("""
            SELECT position, claim, evidence_class, core, basis_ref
            FROM evidence ORDER BY position
            """).fetchall()
        self.assertEqual(
            rows,
            [
                (0, CLAIM_DATA, "data-backed", True, BASIS),
                (1, CLAIM_NARRATIVE, "narrative-only", False, None),
            ],
        )
        self.assertEqual(
            con.execute("SELECT version FROM schema_meta").fetchone()[0], 1
        )
        con.close()

    def test_missing_or_blank_basis_ref_creates_no_file(self) -> None:
        for basis in (None, "  "):
            with self.subTest(basis=basis):
                evidence = [{"claim": CLAIM_DATA, "class": "data-backed", "core": True}]
                if basis is not None:
                    evidence[0]["basis_ref"] = basis
                inbox = self.write_inbox(_payload(evidence=evidence))
                with self.assertRaises(DecisionLogError) as caught:
                    record(inbox, repo_root=self.root)
                self.assertEqual(caught.exception.field, "evidence[0].basis_ref")
                self.assertFalse(self.db_path().exists())

    def test_observed_at_without_timezone_refused(self) -> None:
        inbox = self.write_inbox(_payload(observed_at="2026-10-06T15:30:00"))
        with self.assertRaises(DecisionLogError) as caught:
            record(inbox, repo_root=self.root)
        self.assertEqual(caught.exception.field, "observed_at")
        self.assertFalse(self.db_path().exists())

    def test_blank_market_snapshot_refused(self) -> None:
        inbox = self.write_inbox(_payload(market_snapshot="   "))
        with self.assertRaises(DecisionLogError) as caught:
            record(inbox, repo_root=self.root)
        self.assertEqual(caught.exception.field, "market_snapshot")

    def test_supersedes_link_and_refusals(self) -> None:
        self.record_default(_payload())
        nxt = _payload(
            ID_NEXT,
            supersedes=ID_READY,
            verdict="not ready",
            evidence=[
                {
                    "claim": CLAIM_DATA,
                    "class": "data-backed",
                    "core": False,
                    "basis_ref": BASIS,
                }
            ],
        )
        self.record_default(nxt)
        con = self.connect()
        link = con.execute(
            "SELECT supersedes FROM decisions WHERE id = ?", [ID_NEXT]
        ).fetchone()
        self.assertEqual(str(link[0]), ID_READY)
        con.close()

        own = _payload(
            "33333333-3333-4333-8333-333333333333",
            supersedes="33333333-3333-4333-8333-333333333333",
        )
        inbox = self.write_inbox(own)
        with self.assertRaises(DecisionLogError) as caught:
            record(inbox, repo_root=self.root)
        self.assertEqual(caught.exception.reason, "must not equal id")

        missing = _payload(
            "44444444-4444-4444-8444-444444444444",
            supersedes="55555555-5555-4555-8555-555555555555",
        )
        inbox = self.write_inbox(missing)
        with self.assertRaises(DecisionLogError) as caught:
            record(inbox, repo_root=self.root)
        self.assertEqual(caught.exception.reason, "not found")

    def test_ready_requires_data_backed_core(self) -> None:
        no_core = _payload(
            evidence=[
                {
                    "claim": CLAIM_DATA,
                    "class": "data-backed",
                    "core": False,
                    "basis_ref": BASIS,
                }
            ]
        )
        inbox = self.write_inbox(no_core)
        with self.assertRaises(DecisionLogError) as caught:
            record(inbox, repo_root=self.root)
        self.assertEqual(caught.exception.reason, "not allowed for this evidence")
        self.assertFalse(self.db_path().exists())

        plausible_core = _payload(
            evidence=[
                {
                    "claim": "plausible claim",
                    "class": "plausible but unverified",
                    "core": True,
                }
            ]
        )
        inbox = self.write_inbox(plausible_core)
        with self.assertRaises(DecisionLogError):
            record(inbox, repo_root=self.root)
        self.assertFalse(self.db_path().exists())

    def test_plausible_only_not_ready_and_narrative_ready_refused(self) -> None:
        plausible = _payload(
            verdict="not ready",
            evidence=[
                {"claim": "plausible claim", "class": "plausible but unverified"}
            ],
        )
        self.record_default(plausible)
        con = self.connect()
        self.assertEqual(
            con.execute("SELECT verdict FROM decisions").fetchone()[0], "not ready"
        )
        con.close()

        narrative = _payload(
            ID_NEXT,
            evidence=[{"claim": CLAIM_NARRATIVE, "class": "narrative-only"}],
        )
        inbox = self.write_inbox(narrative)
        before = self.db_path().exists()
        with self.assertRaises(DecisionLogError):
            record(inbox, repo_root=self.root)
        self.assertTrue(before)
        con = self.connect()
        self.assertEqual(con.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], 1)
        con.close()

        fresh = tempfile.TemporaryDirectory()
        self.addCleanup(fresh.cleanup)
        root = Path(fresh.name)
        inbox = root / "Sensitive" / "decisions" / "inbox" / f"{ID_READY}.json"
        playbook = root / "Sensitive" / "decisions" / "playbooks" / f"{ID_READY}.md"
        playbook.parent.mkdir(parents=True)
        playbook.write_text(PLAYBOOK, encoding="utf-8")
        inbox.parent.mkdir(parents=True)
        inbox.write_text(json.dumps(_payload()), encoding="utf-8")
        # rewrite as narrative ready in a root with no database yet
        inbox.write_text(
            json.dumps(
                _payload(
                    evidence=[{"claim": CLAIM_NARRATIVE, "class": "narrative-only"}]
                )
            ),
            encoding="utf-8",
        )
        with self.assertRaises(DecisionLogError):
            record(inbox, repo_root=root)
        self.assertFalse(
            (root / "Sensitive" / "decisions" / "market_decisions.duckdb").exists()
        )

    def test_empty_evidence_only_hard_blocked_and_missing_key_refused(self) -> None:
        payload = _payload()
        del payload["evidence"]
        inbox = self.write_inbox(payload)
        with self.assertRaises(DecisionLogError) as caught:
            record(inbox, repo_root=self.root)
        self.assertEqual(caught.exception.field, "evidence")

        blocked = _payload(verdict="hard-blocked", evidence=[])
        self.record_default(blocked)
        con = self.connect()
        self.assertEqual(con.execute("SELECT COUNT(*) FROM evidence").fetchone()[0], 0)
        self.assertEqual(
            con.execute("SELECT verdict FROM decisions").fetchone()[0], "hard-blocked"
        )
        con.close()

        mixed = _payload(
            ID_NEXT,
            verdict="hard-blocked",
            evidence=[
                {
                    "claim": CLAIM_DATA,
                    "class": "data-backed",
                    "core": True,
                    "basis_ref": BASIS,
                }
            ],
        )
        inbox = self.write_inbox(mixed)
        with self.assertRaises(DecisionLogError) as caught:
            record(inbox, repo_root=self.root)
        self.assertEqual(caught.exception.reason, "not allowed for this evidence")

    def test_unknown_fields_and_blank_strings(self) -> None:
        cases = [
            (_payload(verdict="maybe"), "verdict"),
            (
                _payload(
                    evidence=[
                        {
                            "claim": CLAIM_DATA,
                            "class": "rumor",
                            "core": True,
                            "basis_ref": BASIS,
                        }
                    ]
                ),
                "evidence[0].class",
            ),
            (_payload(playbook_path="Sensitive/nope.md"), "playbook_path"),
            (
                _payload(
                    evidence=[
                        {
                            "claim": CLAIM_DATA,
                            "class": "data-backed",
                            "core": "yes",
                            "basis_ref": BASIS,
                        }
                    ]
                ),
                "evidence[0].core",
            ),
            (_payload(invalidation="  "), "invalidation"),
            (
                _payload(evidence=[{"claim": "  ", "class": "narrative-only"}]),
                "evidence[0].claim",
            ),
        ]
        for payload, field in cases:
            with self.subTest(field=field):
                inbox = self.write_inbox(payload)
                with self.assertRaises(DecisionLogError) as caught:
                    check(inbox, repo_root=self.root)
                self.assertEqual(caught.exception.field, field)
                self.assertNotIn(str(payload.get("verdict")), caught.exception.reason)
        self.assertFalse(self.db_path().exists())

    def test_id_must_be_canonical(self) -> None:
        lettered = "abcdefab-cdef-4abc-8abc-abcdefabcdef"
        for bad in (
            None,
            "11111111-1111-4111-8111-11111111111",
            lettered.upper(),
            "{" + lettered + "}",
            "urn:uuid:" + lettered,
        ):
            with self.subTest(bad=bad):
                payload = _payload()
                if bad is None:
                    del payload["id"]
                else:
                    payload["id"] = bad
                inbox_id = bad or "missing"
                playbook = (
                    self.root
                    / "Sensitive"
                    / "decisions"
                    / "playbooks"
                    / f"{ID_READY}.md"
                )
                playbook.parent.mkdir(parents=True, exist_ok=True)
                playbook.write_text(PLAYBOOK, encoding="utf-8")
                inbox = self.root / "Sensitive" / "decisions" / "inbox" / "bad.json"
                inbox.parent.mkdir(parents=True, exist_ok=True)
                inbox.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(DecisionLogError) as caught:
                    record(inbox, repo_root=self.root)
                self.assertEqual(caught.exception.field, "id")
                self.assertNotIn(str(bad), str(caught.exception))
                del inbox_id

    def test_zero_byte_playbook_and_missing_playbook(self) -> None:
        inbox = self.write_inbox(_payload(), body="")
        with self.assertRaises(DecisionLogError) as caught:
            record(inbox, repo_root=self.root)
        self.assertEqual(caught.exception.reason, "must be non-empty")
        self.assertFalse(self.db_path().exists())

        payload = _payload(ID_NEXT)
        inbox = self.root / "Sensitive" / "decisions" / "inbox" / f"{ID_NEXT}.json"
        inbox.parent.mkdir(parents=True, exist_ok=True)
        inbox.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(DecisionLogError) as caught:
            record(inbox, repo_root=self.root)
        self.assertIn("playbook", caught.exception.field)

    def test_first_record_creates_parent_directory(self) -> None:
        payload = _payload()
        playbook = (
            self.root / "Sensitive" / "decisions" / "playbooks" / f"{ID_READY}.md"
        )
        playbook.parent.mkdir(parents=True)
        playbook.write_text(PLAYBOOK, encoding="utf-8")
        inbox = self.root / "Sensitive" / "decisions" / "inbox" / f"{ID_READY}.json"
        inbox.parent.mkdir(parents=True)
        inbox.write_text(json.dumps(payload), encoding="utf-8")
        outside = self.root / "nested" / "missing" / "log.duckdb"
        self.assertFalse(outside.parent.exists())
        record(inbox, repo_root=self.root, db_path=outside)
        self.assertTrue(outside.is_file())

    def test_inbox_outside_sensitive_refused(self) -> None:
        payload = _payload()
        playbook = (
            self.root / "Sensitive" / "decisions" / "playbooks" / f"{ID_READY}.md"
        )
        playbook.parent.mkdir(parents=True)
        playbook.write_text(PLAYBOOK, encoding="utf-8")
        inbox = self.root / "public.json"
        inbox.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(DecisionLogError) as caught:
            record(inbox, repo_root=self.root)
        self.assertEqual(caught.exception.field, "input")
        self.assertFalse(self.db_path().exists())

    def test_check_creates_no_file_and_reports_duplicate_without_writing(self) -> None:
        inbox = self.write_inbox(_payload())
        result = check(inbox, repo_root=self.root)
        self.assertEqual(result["verdict"], "ready")
        self.assertFalse(self.db_path().exists())
        record(inbox, repo_root=self.root)
        before = self.connect()
        count = before.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        before.close()
        with self.assertRaises(DecisionLogError) as caught:
            check(inbox, repo_root=self.root)
        self.assertEqual(caught.exception.reason, "duplicate id")
        after = self.connect()
        self.assertEqual(
            after.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], count
        )
        after.close()

    def test_non_database_file_and_version_mismatch(self) -> None:
        inbox = self.write_inbox(_payload())
        bogus = self.db_path()
        bogus.parent.mkdir(parents=True, exist_ok=True)
        bogus.write_text("not a database", encoding="utf-8")
        for action in (check, record):
            with self.subTest(action=action.__name__):
                with self.assertRaises(DecisionLogError) as caught:
                    action(inbox, repo_root=self.root)
                self.assertEqual(
                    caught.exception.reason,
                    "close other sessions or the file is not a database",
                )
                self.assertNotIn("Traceback", str(caught.exception))
        code, out, err = self.run_cli(
            ["record", "--input", str(inbox), "--repo-root", str(self.root)]
        )
        self.assertEqual(code, 1)
        self.assertNotIn("Traceback", err)
        self.assert_no_secrets(out + err)

        mismatch = self.root / "mismatch.duckdb"
        con = duckdb.connect(str(mismatch))
        con.execute("CREATE TABLE schema_meta (version INTEGER)")
        con.close()
        for action in (check, record):
            with self.subTest(mismatch=action.__name__):
                with self.assertRaises(DecisionLogError) as caught:
                    action(inbox, repo_root=self.root, db_path=mismatch)
                self.assertEqual(
                    caught.exception.reason,
                    "schema version mismatch, this CLI expects 1",
                )
        con = duckdb.connect(str(mismatch))
        tables = [row[0] for row in con.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'main' AND table_type = 'BASE TABLE'
                """).fetchall()]
        con.close()
        self.assertEqual(tables, ["schema_meta"])

    def test_blank_thesis_check_and_schema_not_reapplied(self) -> None:
        self.record_default(_payload())
        other = _payload(
            ID_NEXT,
            verdict="not ready",
            evidence=[
                {"claim": CLAIM_DATA, "class": "data-backed", "basis_ref": BASIS}
            ],
        )
        self.record_default(other)
        con = self.connect()
        self.assertEqual(
            con.execute("SELECT COUNT(*) FROM schema_meta").fetchone()[0], 1
        )
        self.assertEqual(con.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], 2)
        with self.assertRaises(duckdb.ConstraintException):
            con.execute(
                """
                INSERT INTO decisions (
                    id, supersedes, market, thesis, invalidation, market_snapshot,
                    observed_at, verdict, playbook_path, playbook_sha256, created_at
                ) VALUES (?, NULL, 'm', '   ', 'i', 's', ?, 'not ready', 'p', ?, ?)
                """,
                [
                    str(uuid.uuid4()),
                    datetime(2026, 1, 1, 0, 0),
                    "a" * 64,
                    datetime(2026, 1, 1, 0, 0),
                ],
            )
        con.close()

    def test_db_outside_sensitive_and_duplicate_record(self) -> None:
        inbox = self.write_inbox(_payload())
        outside = Path(tempfile.mkdtemp()) / "outside.duckdb"
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        record(inbox, repo_root=self.root, db_path=outside)
        self.assertTrue(outside.is_file())
        self.assertFalse(self.db_path().exists())
        with self.assertRaises(DecisionLogError) as caught:
            record(inbox, repo_root=self.root, db_path=outside)
        self.assertEqual(caught.exception.reason, "duplicate id")

    def test_rollback_leaves_empty_tables(self) -> None:
        inbox = self.write_inbox(_payload())
        with self.assertRaises(DecisionLogError) as caught:
            record(inbox, repo_root=self.root, fail_after_decision=True)
        self.assertEqual(caught.exception.reason, "forced failure")
        self.assertTrue(self.db_path().is_file())
        con = self.connect()
        self.assertEqual(con.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], 0)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM evidence").fetchone()[0], 0)
        con.close()

    def test_summary_counts_include_zeros_and_outcomes(self) -> None:
        path = self.root / "empty.duckdb"
        con = duckdb.connect(str(path))
        apply_schema_if_empty(con)
        rows = [row for row in summary_rows(con) if row[0] == "count"]
        self.assertEqual(
            [(row[1], row[2]) for row in rows],
            [("ready", 0), ("not ready", 0), ("hard-blocked", 0)],
        )
        con.close()

        self.record_default(_payload(verdict="hard-blocked", evidence=[]))
        resolved_at = datetime(2026, 3, 4, 5, 6, 7)
        resolve(
            ID_READY,
            "right",
            notes=NOTES,
            repo_root=self.root,
            now=lambda: resolved_at,
        )
        con = self.connect()
        outcome_rows = [row for row in summary_rows(con) if row[0] == "outcome"]
        self.assertEqual(
            outcome_rows, [("outcome", "hard-blocked", 1, None, None, None, "right")]
        )
        con.close()
        with self.assertRaises(DecisionLogError) as caught:
            resolve(ID_READY, "wrong", notes=NOTES, repo_root=self.root)
        self.assertEqual(caught.exception.reason, "already resolved")
        con = self.connect()
        self.assertEqual(
            con.execute("SELECT outcome FROM decisions").fetchone()[0], "right"
        )
        con.close()

    def test_resolve_unknown_invalid_and_verify(self) -> None:
        with self.assertRaises(DecisionLogError) as caught:
            resolve(ID_READY, "sideways", repo_root=self.root)
        self.assertEqual(caught.exception.field, "outcome")
        self.assertFalse(self.db_path().exists())

        self.record_default(_payload(verdict="hard-blocked", evidence=[]))
        with self.assertRaises(DecisionLogError) as caught:
            resolve(ID_NEXT, "right", repo_root=self.root)
        self.assertEqual(caught.exception.reason, "not found")

        matched = verify(ID_READY, repo_root=self.root)
        self.assertTrue(matched["match"])
        playbook = (
            self.root / "Sensitive" / "decisions" / "playbooks" / f"{ID_READY}.md"
        )
        playbook.write_text(PLAYBOOK + " changed\n", encoding="utf-8")
        changed = verify(ID_READY, repo_root=self.root)
        self.assertFalse(changed["match"])
        code, out, err = self.run_cli(
            ["verify", "--id", ID_READY, "--repo-root", str(self.root)]
        )
        self.assertEqual(code, 1)
        self.assertIn("match: no", out)
        self.assertIn(matched["playbook_sha256"], out)
        self.assertNotIn(PLAYBOOK, out + err)
        self.assert_no_secrets(out + err)

    def test_refusal_field_path_and_output_hygiene(self) -> None:
        bad_class = "SECRET-CLASS-VALUE"
        payload = _payload(
            evidence=[
                {
                    "claim": CLAIM_DATA,
                    "class": bad_class,
                    "core": True,
                    "basis_ref": BASIS,
                }
            ]
        )
        inbox = self.write_inbox(payload)
        code, out, err = self.run_cli(
            ["record", "--input", str(inbox), "--repo-root", str(self.root)]
        )
        self.assertEqual(code, 1)
        self.assertIn("evidence[0].class", err)
        self.assertNotIn(bad_class, out + err)
        self.assert_no_secrets(out + err)
        self.assertNotIn("Traceback", err)

        inbox = self.write_inbox(_payload())
        code, out, err = self.run_cli(
            ["record", "--input", str(inbox), "--repo-root", str(self.root)]
        )
        self.assertEqual(code, 0, err)
        self.assertIn("verdict: ready", out)
        self.assert_no_secrets(out + err)

        code, out, err = self.run_cli(
            [
                "resolve",
                "--id",
                ID_READY,
                "--outcome",
                "wrong",
                "--notes",
                NOTES,
                "--repo-root",
                str(self.root),
            ]
        )
        self.assertEqual(code, 0, err)
        self.assertIn("outcome: wrong", out)
        self.assert_no_secrets(out + err)
        con = self.connect()
        self.assertEqual(con.execute("SELECT COUNT(*) FROM evidence").fetchone()[0], 2)
        self.assertEqual(
            con.execute("SELECT outcome_notes FROM decisions").fetchone()[0], NOTES
        )
        con.close()

        code, out, err = self.run_cli(
            ["verify", "--id", ID_READY, "--repo-root", str(self.root)]
        )
        self.assertEqual(code, 0, err)
        self.assertIn("match: yes", out)
        self.assert_no_secrets(out + err)

    def test_cli_cwd_does_not_create_a_stray_database(self) -> None:
        inbox = self.write_inbox(_payload())
        other = Path(tempfile.mkdtemp())
        script = REPO_ROOT / "python" / "decision_log" / "record.py"
        completed = subprocess.run(
            [
                sys.executable,
                str(script),
                "record",
                "--input",
                str(inbox),
                "--repo-root",
                str(self.root),
            ],
            cwd=other,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(self.db_path().is_file())
        self.assertFalse(any(other.glob("*.duckdb")))
        self.assertFalse((other / "Sensitive").exists())
        self.assert_no_secrets(completed.stdout + completed.stderr)

    def test_summary_narrative_claim_on_ready_row(self) -> None:
        self.record_default(_payload())
        con = self.connect()
        narrative = [row for row in summary_rows(con) if row[0] == "narrative-only"]
        self.assertEqual(len(narrative), 1)
        self.assertEqual(str(narrative[0][3]), ID_READY)
        self.assertEqual(narrative[0][4], 1)
        self.assertEqual(narrative[0][5], CLAIM_NARRATIVE)
        con.close()


if __name__ == "__main__":
    unittest.main()
