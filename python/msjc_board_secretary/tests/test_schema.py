"""Schema validation. Standard library only."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from msjc_board_secretary.schema import (  # noqa: E402
    SchemaError,
    WriteGuardError,
    load_minutes_document,
    validate_write_guards,
)

SAMPLE = Path(__file__).resolve().parents[1] / "sample_minutes.json"


class SchemaTests(unittest.TestCase):
    def test_sample_loads(self) -> None:
        doc = load_minutes_document(json.loads(SAMPLE.read_text(encoding="utf-8")))
        self.assertEqual(doc.schema_version, 1)
        kinds = [item.kind for item in doc.items]
        self.assertEqual(
            kinds,
            [
                "masthead",
                "attendance",
                "section",
                "presenter",
                "motion",
                "section",
                "bullet",
                "bullet",
                "paragraph",
            ],
        )
        self.assertEqual(doc.items[1].groups[0].category, "Officers")
        self.assertEqual(doc.items[1].groups[0].names, ("Sam Ortiz",))

    def test_flat_names_attendance(self) -> None:
        doc = load_minutes_document(
            {
                "schemaVersion": 1,
                "items": [
                    {
                        "kind": "attendance",
                        "label": "In attendance:",
                        "names": ["Sam Ortiz", "Alex Rivera"],
                    }
                ],
            }
        )
        self.assertEqual(doc.items[0].names, ("Sam Ortiz", "Alex Rivera"))

    def test_rejects_both_groups_and_names(self) -> None:
        with self.assertRaises(SchemaError):
            load_minutes_document(
                {
                    "schemaVersion": 1,
                    "items": [
                        {
                            "kind": "attendance",
                            "label": "In attendance:",
                            "groups": [{"category": "Officers", "names": ["Sam Ortiz"]}],
                            "names": ["Alex Rivera"],
                        }
                    ],
                }
            )

    def test_unsupported_version(self) -> None:
        with self.assertRaises(SchemaError):
            load_minutes_document({"schemaVersion": 2, "items": [{"kind": "paragraph", "text": "Hi"}]})

    def test_unknown_field(self) -> None:
        with self.assertRaises(SchemaError):
            load_minutes_document(
                {"schemaVersion": 1, "items": [{"kind": "section", "title": "Hall", "extra": 1}]}
            )

    def test_unknown_kind(self) -> None:
        with self.assertRaises(SchemaError):
            load_minutes_document({"schemaVersion": 1, "items": [{"kind": "table"}]})

    def test_bad_level(self) -> None:
        with self.assertRaises(SchemaError):
            load_minutes_document(
                {"schemaVersion": 1, "items": [{"kind": "bullet", "text": "Hall", "level": 4}]}
            )

    def test_bad_verdict(self) -> None:
        with self.assertRaises(SchemaError):
            load_minutes_document(
                {
                    "schemaVersion": 1,
                    "items": [{"kind": "motion", "body": "Alex Rivera moves to adjourn.", "verdict": "maybe"}],
                }
            )

    def test_write_guards(self) -> None:
        with self.assertRaises(WriteGuardError):
            validate_write_guards(
                write=False,
                input_tab_id="a",
                output_tab_id="b",
                actual_title="T",
                expected_title="T",
                revision_id="rev",
            )
        with self.assertRaises(WriteGuardError):
            validate_write_guards(
                write=True,
                input_tab_id="same",
                output_tab_id="same",
                actual_title="T",
                expected_title="T",
                revision_id="rev",
            )
        with self.assertRaises(WriteGuardError):
            validate_write_guards(
                write=True,
                input_tab_id="a",
                output_tab_id="b",
                actual_title="Other",
                expected_title="T",
                revision_id="rev",
            )
        with self.assertRaises(WriteGuardError):
            validate_write_guards(
                write=True,
                input_tab_id="a",
                output_tab_id="b",
                actual_title="T",
                expected_title="T",
                revision_id="",
            )


if __name__ == "__main__":
    unittest.main()
