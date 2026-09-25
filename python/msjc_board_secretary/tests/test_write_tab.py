"""Writer guards. Standard library only; no Google client imports."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from msjc_board_secretary.builder import document_to_paragraphs  # noqa: E402
from msjc_board_secretary.schema import WriteGuardError, load_minutes_document  # noqa: E402
from msjc_board_secretary import write_tab  # noqa: E402

SAMPLE = Path(__file__).resolve().parents[1] / "sample_minutes.json"


class FakeDocs:
    def __init__(self, doc: dict, *, fail_on_update: int | None = None) -> None:
        self.doc = doc
        self.updates: list[dict] = []
        self.fail_on_update = fail_on_update
        self.reads = 0

    def get_document(self, document_id: str) -> dict:
        self.reads += 1
        return self.doc

    def batch_update(self, document_id: str, body: dict) -> dict:
        self.updates.append(body)
        if self.fail_on_update is not None and len(self.updates) == self.fail_on_update:
            raise RuntimeError("network timeout")
        self.doc = dict(self.doc)
        self.doc["revisionId"] = f"rev-{len(self.updates) + 1}"
        return {}


def _content_for(document) -> list[dict]:
    """Docs-shaped paragraphs so later passes see the same item count as the plan."""
    content = []
    cursor = 1
    for paragraph in document_to_paragraphs(document):
        body = paragraph.text + "\n"
        style = "HEADING_3" if paragraph.kind == "h3" else "NORMAL_TEXT"
        end = cursor + len(body)
        content.append(
            {
                "startIndex": cursor,
                "endIndex": end,
                "paragraph": {
                    "elements": [{"textRun": {"content": body}}],
                    "paragraphStyle": {"namedStyleType": style},
                },
            }
        )
        cursor = end
    return content


def _doc(title: str = "April 2026 Board Meeting Minutes 20260412", document=None) -> dict:
    notes = {
        "tabProperties": {"title": "Notes", "tabId": "tab-notes"},
        "documentTab": {
            "body": {
                "content": [
                    {
                        "startIndex": 1,
                        "endIndex": 2,
                        "paragraph": {"elements": [{"textRun": {"content": "\n"}}]},
                    }
                ]
            }
        },
    }
    test_content = _content_for(document) if document is not None else notes["documentTab"]["body"]["content"]
    test = {
        "tabProperties": {"title": "Test", "tabId": "tab-test"},
        "documentTab": {"body": {"content": test_content}},
    }
    return {"title": title, "revisionId": "rev-1", "tabs": [notes, test]}


class WriteGuardTests(unittest.TestCase):
    def test_dry_run_does_not_construct_credentials(self) -> None:
        def boom(*_args, **_kwargs):
            raise AssertionError("credentials or service constructed")

        original_creds = write_tab.load_credentials
        original_build = write_tab.build_docs_service
        write_tab.load_credentials = boom
        write_tab.build_docs_service = boom
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = write_tab.main(["--input", str(SAMPLE)])
            self.assertEqual(code, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["mode"], "dry-run")
            self.assertGreater(payload["pass1Requests"], 0)
        finally:
            write_tab.load_credentials = original_creds
            write_tab.build_docs_service = original_build

    def test_repo_json_refuses_write_before_credentials(self) -> None:
        called = {"creds": 0}

        def boom(*_args, **_kwargs):
            called["creds"] += 1
            raise AssertionError("credentials constructed")

        original = write_tab.load_credentials
        write_tab.load_credentials = boom
        try:
            with self.assertRaises(SystemExit):
                write_tab.main(
                    [
                        "--input",
                        str(SAMPLE),
                        "--write",
                        "--document-id", "doc",
                        "--expected-document-title", "April 2026 Board Meeting Minutes 20260412",
                        "--input-tab", "Notes",
                        "--output-tab", "Test",
                    ]
                )
            self.assertEqual(called["creds"], 0)
        finally:
            write_tab.load_credentials = original

    def test_same_tab_and_wrong_title_do_not_mutate(self) -> None:
        document = load_minutes_document(json.loads(SAMPLE.read_text(encoding="utf-8")))
        same = FakeDocs(_doc(document=document))
        same.doc["tabs"][1]["tabProperties"]["tabId"] = "tab-notes"
        with self.assertRaises(WriteGuardError):
            write_tab.perform_write(
                same,
                document,
                document_id="doc",
                expected_title="April 2026 Board Meeting Minutes 20260412",
                input_tab="Notes",
                output_tab="Test",
            )
        self.assertEqual(same.updates, [])

        wrong = FakeDocs(_doc("Other title", document))
        with self.assertRaises(WriteGuardError):
            write_tab.perform_write(
                wrong,
                document,
                document_id="doc",
                expected_title="April 2026 Board Meeting Minutes 20260412",
                input_tab="Notes",
                output_tab="Test",
            )
        self.assertEqual(wrong.updates, [])

    def test_missing_revision_aborts_before_mutation(self) -> None:
        document = load_minutes_document(json.loads(SAMPLE.read_text(encoding="utf-8")))
        client = FakeDocs(_doc(document=document))
        client.doc["revisionId"] = ""
        with self.assertRaises(WriteGuardError):
            write_tab.perform_write(
                client,
                document,
                document_id="doc",
                expected_title="April 2026 Board Meeting Minutes 20260412",
                input_tab="Notes",
                output_tab="Test",
            )
        self.assertEqual(client.updates, [])

    def test_each_batch_locks_the_prior_revision(self) -> None:
        document = load_minutes_document(json.loads(SAMPLE.read_text(encoding="utf-8")))
        client = FakeDocs(_doc(document=document))
        summary = write_tab.perform_write(
            client,
            document,
            document_id="doc",
            expected_title="April 2026 Board Meeting Minutes 20260412",
            input_tab="Notes",
            output_tab="Test",
        )
        self.assertGreaterEqual(len(client.updates), 1)
        self.assertEqual(client.updates[0]["writeControl"]["requiredRevisionId"], "rev-1")
        for previous, body in enumerate(client.updates):
            self.assertEqual(body["writeControl"]["requiredRevisionId"], f"rev-{previous + 1}")
        self.assertEqual(summary["tabId"], "tab-test")
        self.assertNotIn("Motion", json.dumps(summary))

    def test_later_pass_failure_prints_recovery(self) -> None:
        document = load_minutes_document(json.loads(SAMPLE.read_text(encoding="utf-8")))
        client = FakeDocs(_doc(document=document), fail_on_update=2)
        err = io.StringIO()
        with redirect_stderr(err):
            with self.assertRaises(RuntimeError):
                write_tab.perform_write(
                    client,
                    document,
                    document_id="doc",
                    expected_title="April 2026 Board Meeting Minutes 20260412",
                    input_tab="Notes",
                    output_tab="Test",
                )
        self.assertIn("Pass 1 replaced the tab", err.getvalue())
        self.assertEqual(len(client.updates), 2)

    def test_private_temp_file_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "minutes.json"
            path.write_text(SAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
            self.assertTrue(write_tab.input_is_private(path))
        self.assertFalse(write_tab.input_is_private(SAMPLE))


if __name__ == "__main__":
    unittest.main()
