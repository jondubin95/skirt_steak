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
    minutes_shape_errors,
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
                "section",
                "paragraph",
                "section",
                "paragraph",
                "section",
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

    def _full_minutes(self, *middle: dict) -> dict:
        return {
            "schemaVersion": 1,
            "items": [
                {
                    "kind": "attendance",
                    "label": "In attendance:",
                    "names": ["Alex Rivera"],
                },
                *middle,
                {"kind": "section", "title": "Old Business"},
                {"kind": "paragraph", "text": "None."},
                {"kind": "section", "title": "New Business"},
                {"kind": "paragraph", "text": "None."},
                {"kind": "section", "title": "Adjournment"},
                {
                    "kind": "motion",
                    "body": "Alex Rivera moves to adjourn. Jordan Hale seconds.",
                    "verdict": "passes",
                },
            ],
        }

    def test_sample_shape_is_writable(self) -> None:
        doc = load_minutes_document(json.loads(SAMPLE.read_text(encoding="utf-8")))
        self.assertEqual(minutes_shape_errors(doc), ())

    def test_shape_accepts_a_filled_closing_section_and_a_titled_presenter(self) -> None:
        doc = load_minutes_document(
            self._full_minutes({"kind": "presenter", "text": "Presented by Dr. Schwartz."})
        )
        self.assertEqual(minutes_shape_errors(doc), ())

    def test_shape_refuses_placeholders_label_presenter_and_heading(self) -> None:
        doc = load_minutes_document(
            self._full_minutes(
                {"kind": "motion", "body": "___ moves to accept. XXX seconds."},
                {"kind": "attendance", "label": "In attendance (In Person):", "names": ["Alex Rivera"]},
                {"kind": "presenter", "text": "Presented by Alex Rivera"},
                {"kind": "section", "title": "### II. Accept Minutes"},
            )
        )
        errors = minutes_shape_errors(doc)
        self.assertIn("placeholder ___ in items[1] body", errors)
        self.assertIn("placeholder XXX in items[1] body", errors)
        self.assertTrue(any("attendance label" in error for error in errors))
        self.assertTrue(any("presenter must be" in error for error in errors))
        self.assertTrue(any("markdown" in error for error in errors))
        self.assertTrue(any("Roman numeral" in error for error in errors))

    def test_shape_refuses_missing_or_mixed_closing_sections(self) -> None:
        missing = load_minutes_document(
            {"schemaVersion": 1, "items": [{"kind": "paragraph", "text": "Hello."}]}
        )
        self.assertTrue(any("closing sections" in error for error in minutes_shape_errors(missing)))
        mixed = load_minutes_document(
            {
                "schemaVersion": 1,
                "items": [
                    {"kind": "section", "title": "Old Business"},
                    {"kind": "paragraph", "text": "None."},
                    {"kind": "bullet", "level": 1, "text": "The boiler was discussed."},
                    {"kind": "section", "title": "New Business"},
                    {"kind": "section", "title": "Adjournment"},
                    {"kind": "paragraph", "text": "None."},
                ],
            }
        )
        errors = minutes_shape_errors(mixed)
        self.assertIn("Old Business has None. alongside other text", errors)
        self.assertIn("New Business is empty; the body must be the paragraph None.", errors)

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
