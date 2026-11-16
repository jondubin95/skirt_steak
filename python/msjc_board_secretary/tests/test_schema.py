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
    absent_speaker_conflicts,
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

    def test_italic_paragraph(self) -> None:
        doc = load_minutes_document(
            {
                "schemaVersion": 1,
                "items": [
                    {
                        "kind": "paragraph",
                        "text": "Executive session concluded",
                        "italic": True,
                    }
                ],
            }
        )
        self.assertTrue(doc.items[0].italic)

    def test_italic_must_be_boolean(self) -> None:
        with self.assertRaises(SchemaError):
            load_minutes_document(
                {
                    "schemaVersion": 1,
                    "items": [{"kind": "paragraph", "text": "Executive session concluded", "italic": "yes"}],
                }
            )

    def test_bad_verdict(self) -> None:
        with self.assertRaises(SchemaError):
            load_minutes_document(
                {
                    "schemaVersion": 1,
                    "items": [{"kind": "motion", "body": "Alex Rivera moves to adjourn.", "verdict": "maybe"}],
                }
            )

    def _attendance_doc(self, *items: dict) -> dict:
        return {
            "schemaVersion": 1,
            "items": [
                {
                    "kind": "attendance",
                    "label": "In attendance:",
                    "groups": [
                        {"category": "Officers", "names": ["Alex Rivera"]},
                        {"category": "Not in attendance:", "names": ["Taylor Morgan"]},
                    ],
                },
                *items,
            ],
        }

    def test_sample_has_no_absent_speaker(self) -> None:
        doc = load_minutes_document(json.loads(SAMPLE.read_text(encoding="utf-8")))
        self.assertEqual(absent_speaker_conflicts(doc), ())

    def test_absent_speaker_verbs_and_presenter(self) -> None:
        for text, kind, field in (
            ("Taylor Morgan said the hall is open.", "bullet", "text"),
            ("Taylor Morgan asked who has the key.", "bullet", "text"),
            ("Taylor Morgan moves to adjourn.", "motion", "body"),
            ("Alex Rivera moves to adjourn. Taylor Morgan seconds.", "motion", "body"),
            ("Presented by Taylor Morgan.", "presenter", "text"),
        ):
            item = {"kind": kind, field: text}
            if kind == "bullet":
                item["level"] = 1
            doc = load_minutes_document(self._attendance_doc(item))
            self.assertEqual(absent_speaker_conflicts(doc), ("Taylor Morgan",), text)

    def test_discussing_an_absent_person_is_allowed(self) -> None:
        doc = load_minutes_document(
            self._attendance_doc(
                {
                    "kind": "bullet",
                    "level": 1,
                    "text": "Alex Rivera said the board discussed Taylor Morgan.",
                }
            )
        )
        self.assertEqual(absent_speaker_conflicts(doc), ())

    def test_present_speaker_is_allowed(self) -> None:
        doc = load_minutes_document(
            self._attendance_doc(
                {"kind": "bullet", "level": 1, "text": "Alex Rivera said the hall is open."}
            )
        )
        self.assertEqual(absent_speaker_conflicts(doc), ())

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
