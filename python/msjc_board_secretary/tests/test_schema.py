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
    is_empty_section_paragraph,
    load_minutes_document,
    minutes_phrase_errors,
    minutes_shape_errors,
    motion_verdict_is_earned,
    validate_target_identity,
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

    def test_verdict_requires_a_seconder_or_a_recorded_vote(self) -> None:
        earned = (
            "Alex Rivera moves to raise dues. Jordan Hale seconds.",
            "Alex Rivera moves to raise dues. Jordan Hale seconded.",
            "Alex Rivera moves to raise dues. Voted down.",
            "Alex Rivera moves to raise dues. The vote failed.",
            "Alex Rivera moves to raise dues. 3 yeas and 4 nays.",
            "Motion fails for lack of a second. Voted down, 1 yea to 6 nays.",
        )
        for body in earned:
            self.assertTrue(motion_verdict_is_earned(body), body)
            for verdict in ("passes", "fails"):
                doc = load_minutes_document(
                    {
                        "schemaVersion": 1,
                        "items": [{"kind": "motion", "body": body, "verdict": verdict}],
                    }
                )
                self.assertEqual(doc.items[0].verdict, verdict, body)

    def test_verdict_is_rejected_without_a_seconder_or_a_vote(self) -> None:
        bodies = (
            "Alex Rivera moves to raise dues.",
            "Alex Rivera moves to raise dues. No second; not voted",
            "Alex Rivera moves to raise dues. No one seconds.",
            "Alex Rivera moves to raise dues. No one seconded.",
            "Alex Rivera moves to raise dues. Nobody seconded it.",
            "Alex Rivera moves to raise dues. It was never seconded.",
            "Alex Rivera moves to raise dues. The motion died without a second.",
            "Alex Rivera moves to raise dues. It failed without a second.",
            "Motion fails for lack of a second.",
            "Defeated for lack of a second.",
        )
        for body in bodies:
            self.assertFalse(motion_verdict_is_earned(body), body)
            for verdict in ("passes", "fails"):
                with self.assertRaises(SchemaError) as caught:
                    load_minutes_document(
                        {
                            "schemaVersion": 1,
                            "items": [{"kind": "motion", "body": body, "verdict": verdict}],
                        }
                    )
                self.assertIn("no seconder and no vote", str(caught.exception))
                self.assertIn(verdict, str(caught.exception))
        unfinished = load_minutes_document(
            {
                "schemaVersion": 1,
                "items": [
                    {
                        "kind": "motion",
                        "body": "Alex Rivera moves to raise dues. No second; not voted",
                    }
                ],
            }
        )
        self.assertIsNone(unfinished.items[0].verdict)

    def _attendance_doc(
        self,
        *items: dict,
        absent: str = "Taylor Morgan",
        category: str = "Not in attendance:",
    ) -> dict:
        return {
            "schemaVersion": 1,
            "items": [
                {
                    "kind": "attendance",
                    "label": "In attendance:",
                    "groups": [
                        {"category": "Officers", "names": ["Alex Rivera"]},
                        {"category": category, "names": [absent]},
                    ],
                },
                *items,
            ],
        }

    def _conflicts(self, text: str, **attendance) -> tuple[str, ...]:
        doc = load_minutes_document(
            self._attendance_doc({"kind": "bullet", "level": 1, "text": text}, **attendance)
        )
        return absent_speaker_conflicts(doc)

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

    def test_absent_speaker_more_verbs_and_absence_labels(self) -> None:
        verbs = (
            "Taylor Morgan reported the boiler quote.",
            "Taylor Morgan moved to table the quote.",
            "Taylor Morgan presented the budget.",
            "Alex Rivera moves to adjourn. Taylor Morgan seconded.",
            "Taylor Morgan explained the leak.",
            "Taylor Morgan noted the open invoice.",
            "Taylor Morgan shared the boiler quote.",
            "Taylor Morgan added a line to the quote.",
            "Taylor Morgan offered to call the vendor.",
            "Taylor Morgan thanked the vendor.",
            "Taylor Morgan agreed to table the quote.",
            "Taylor Morgan confirmed the leak.",
        )
        labels = (
            "Not in attendance",
            "Absent",
            "Not present",
            "Regrets",
            "Absent:",
            "Regrets.",
            "Not in attendance.",
            "Absent -",
        )
        for label in labels:
            self.assertEqual(self._conflicts(verbs[0], category=label), ("Taylor Morgan",), label)
        for text in verbs:
            self.assertEqual(self._conflicts(text, category="Absent"), ("Taylor Morgan",), text)

    def test_absent_name_does_not_match_inside_a_longer_name(self) -> None:
        cases = (
            ("Ann", "Joann said the hall is open."),
            ("Ann", "Presented by Joann."),
            ("Ann", "Jo-Ann said the hall is open."),
            ("Ann", "The key2Ann said the hall is open."),
            ("Ann", "JoséAnn said the hall is open."),
            ("Alex", "Alex Rivera Jr. said the hall is open."),
            ("Alex", "Presented by Alex Rivera Jr."),
            ("Alex", "Alex Rivera said the hall is open."),
        )
        for absent, text in cases:
            self.assertEqual(self._conflicts(text, absent=absent, category="Absent"), (), f"{absent} in {text}")
        self.assertEqual(
            self._conflicts("Ann said the hall is open.", absent="Ann", category="Absent"),
            ("Ann",),
        )

    def test_full_absent_name_still_conflicts(self) -> None:
        doc = load_minutes_document(
            self._attendance_doc(
                {"kind": "presenter", "text": "Presented by Alex Rivera Jr."},
                absent="Alex Rivera Jr.",
                category="Regrets",
            )
        )
        self.assertEqual(absent_speaker_conflicts(doc), ("Alex Rivera Jr.",))

    def test_who_clause_credits_an_absent_speaker(self) -> None:
        credited = load_minutes_document(
            self._attendance_doc(
                {
                    "kind": "bullet",
                    "level": 1,
                    "text": "Taylor Morgan, who reported the leak, was absent.",
                }
            )
        )
        self.assertEqual(absent_speaker_conflicts(credited), ("Taylor Morgan",))
        discussed = load_minutes_document(
            self._attendance_doc(
                {
                    "kind": "bullet",
                    "level": 1,
                    "text": "Taylor Morgan, the treasurer, said the hall is open.",
                }
            )
        )
        self.assertEqual(absent_speaker_conflicts(discussed), ())

    def test_possessive_is_not_a_speaking_credit(self) -> None:
        for text in (
            "The session was presented by Taylor Morgan's replacement.",
            "The session was presented by Taylor Morgan\u2019s replacement.",
            "Alex Rivera said Taylor Morgan's report was late.",
        ):
            doc = load_minutes_document(
                self._attendance_doc({"kind": "bullet", "level": 1, "text": text})
            )
            self.assertEqual(absent_speaker_conflicts(doc), (), text)
        self.assertEqual(
            self._conflicts(
                "Alex Rivera's replacement presented the budget.",
                absent="Alex Rivera",
                category="Absent",
            ),
            (),
        )
        still_speaking = load_minutes_document(
            self._attendance_doc(
                {"kind": "bullet", "level": 1, "text": "Taylor Morgan presented the budget."}
            )
        )
        self.assertEqual(absent_speaker_conflicts(still_speaking), ("Taylor Morgan",))

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

    def test_november_2026_section_titles_pass(self) -> None:
        titles = (
            "D'var Torah",
            "Accept Minutes",
            "Executive Director Update",
            "Committee Items",
            "Grievance Update",
            "2027 Membership Pricing",
            "Revenue Opportunities",
            "Old Business",
            "New Business",
            "Adjournment",
        )
        items: list[dict] = [
            {
                "kind": "attendance",
                "label": "In attendance:",
                "names": ["Alex Rivera"],
            }
        ]
        for title in titles:
            items.append({"kind": "section", "title": title})
            body = "None." if title in {"Old Business", "New Business", "Adjournment"} else "Recorded."
            items.append({"kind": "paragraph", "text": body})
        doc = load_minutes_document({"schemaVersion": 1, "items": items})
        self.assertEqual([item.title for item in doc.items if item.kind == "section"], list(titles))
        self.assertEqual(minutes_shape_errors(doc), ())
        self.assertEqual(absent_speaker_conflicts(doc), ())

    def test_roman_heading_needs_a_marker_and_a_year_is_a_title(self) -> None:
        for title in (
            "II. Accept Minutes",
            "II) Accept Minutes",
            "### II. Accept Minutes",
            "(II. Accept Minutes)",
            "[II. Budget]",
            "See II. above",
        ):
            doc = load_minutes_document(self._full_minutes({"kind": "section", "title": title}))
            errors = minutes_shape_errors(doc)
            self.assertTrue(any("Roman numeral" in error for error in errors), title)
        for title in ("2027 Membership Pricing", "D'var Torah", "iv. Accept Minutes"):
            doc = load_minutes_document(self._full_minutes({"kind": "section", "title": title}))
            self.assertEqual(minutes_shape_errors(doc), (), title)

    def test_hash_inside_a_title_is_not_a_markdown_heading(self) -> None:
        doc = load_minutes_document(self._full_minutes({"kind": "section", "title": "Item #4"}))
        self.assertEqual(minutes_shape_errors(doc), ())
        marked = load_minutes_document(self._full_minutes({"kind": "section", "title": "### Budget"}))
        errors = minutes_shape_errors(marked)
        self.assertTrue(any("markdown" in error for error in errors))
        self.assertFalse(any("Roman numeral" in error for error in errors))

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

    def test_empty_section_marker_is_the_whole_paragraph(self) -> None:
        self.assertTrue(is_empty_section_paragraph("None."))
        for incidental in (" None.", "None. ", "none.", "NONE.", "The vote was None.", "None. The hall is booked."):
            self.assertFalse(is_empty_section_paragraph(incidental), incidental)
        padded = load_minutes_document(
            {
                "schemaVersion": 1,
                "items": [
                    {"kind": "section", "title": "Old Business"},
                    {"kind": "paragraph", "text": " None."},
                    {"kind": "section", "title": "New Business"},
                    {"kind": "paragraph", "text": "None. "},
                    {"kind": "section", "title": "Adjournment"},
                    {"kind": "paragraph", "text": "None."},
                ],
            }
        )
        padded_errors = minutes_shape_errors(padded)
        self.assertIn(
            "Old Business empty-section marker has leading/trailing whitespace",
            padded_errors,
        )
        self.assertIn(
            "New Business empty-section marker has leading/trailing whitespace",
            padded_errors,
        )
        self.assertFalse(any("Adjournment" in error for error in padded_errors))
        sentence = load_minutes_document(
            {
                "schemaVersion": 1,
                "items": [
                    {"kind": "section", "title": "Old Business"},
                    {"kind": "paragraph", "text": "The vote was None."},
                    {"kind": "bullet", "level": 1, "text": "The boiler was discussed."},
                    {"kind": "section", "title": "New Business"},
                    {"kind": "paragraph", "text": "None."},
                    {"kind": "section", "title": "Adjournment"},
                    {"kind": "paragraph", "text": "None."},
                ],
            }
        )
        errors = minutes_shape_errors(sentence)
        self.assertFalse(any("Old Business" in error for error in errors))
        hall = load_minutes_document(json.loads(SAMPLE.read_text(encoding="utf-8")))
        titles = [item.title for item in hall.items if item.kind == "section"]
        rental_at = titles.index("Hall Rental")
        section_indexes = [i for i, item in enumerate(hall.items) if item.kind == "section"]
        start = section_indexes[rental_at] + 1
        end = section_indexes[rental_at + 1]
        rental_text = [item.text for item in hall.items[start:end]]
        self.assertNotIn("None.", rental_text)

    def test_replacement_phrase_uses_placeholder_and_heading_checks(self) -> None:
        self.assertEqual(minutes_phrase_errors("the hall rental is confirmed"), ())
        for allowed in (
            "D'var Torah",
            "2027 Membership Pricing",
            "Item #4",
            "None.",
            "See II. above",
            "Presented by D. Schwartz",
            "Update from M. Rivera",
            "(II. Accept Minutes)",
            "[II. Budget]",
            " II. Accept Minutes",
        ):
            self.assertEqual(minutes_phrase_errors(allowed), (), allowed)
        for blocked, needle in (
            ("mover is ___", "placeholder ___"),
            ("XXX seconds", "placeholder XXX"),
            ("xxx seconds", "placeholder XXX"),
            ("### Budget", "markdown"),
            ("II. Accept Minutes", "Roman numeral"),
            ("II) Budget", "Roman numeral"),
            ("D. Schwartz", "Roman numeral"),
        ):
            errors = minutes_phrase_errors(blocked)
            self.assertTrue(any(needle in error for error in errors), blocked)

    def test_xxx_placeholder_is_case_insensitive(self) -> None:
        for body in ("xxx seconds.", "Xxx seconds.", "xxX seconds."):
            doc = load_minutes_document(self._full_minutes({"kind": "motion", "body": body}))
            errors = minutes_shape_errors(doc)
            self.assertTrue(any(error.startswith("placeholder XXX") for error in errors), body)
        longer = load_minutes_document(
            self._full_minutes({"kind": "paragraph", "text": "XXXX stays in the notes."})
        )
        self.assertFalse(
            any("placeholder XXX" in error for error in minutes_shape_errors(longer))
        )

    def test_write_guards(self) -> None:
        with self.assertRaises(WriteGuardError):
            validate_write_guards(
                write=False,
                input_tab_id="a",
                output_tab_id="b",
                actual_title="T",
                expected_title="T",
                actual_output_tab="Minutes",
                expected_output_tab="Minutes",
                revision_id="rev",
            )
        with self.assertRaises(WriteGuardError):
            validate_write_guards(
                write=True,
                input_tab_id="same",
                output_tab_id="same",
                actual_title="T",
                expected_title="T",
                actual_output_tab="Minutes",
                expected_output_tab="Minutes",
                revision_id="rev",
            )
        with self.assertRaises(WriteGuardError):
            validate_write_guards(
                write=True,
                input_tab_id="a",
                output_tab_id="b",
                actual_title="Other",
                expected_title="T",
                actual_output_tab="Minutes",
                expected_output_tab="Minutes",
                revision_id="rev",
            )
        with self.assertRaises(WriteGuardError) as tab_mismatch:
            validate_write_guards(
                write=True,
                input_tab_id="a",
                output_tab_id="b",
                actual_title="T",
                expected_title="T",
                actual_output_tab="Minutes",
                expected_output_tab="Test",
                revision_id="rev",
            )
        self.assertIn("output tab", str(tab_mismatch.exception))
        with self.assertRaises(WriteGuardError):
            validate_target_identity(
                actual_title="T",
                expected_title="T",
                actual_output_tab="Minutes",
                expected_output_tab="minutes",
                revision_id="rev",
            )
        with self.assertRaises(WriteGuardError):
            validate_write_guards(
                write=True,
                input_tab_id="a",
                output_tab_id="b",
                actual_title="T",
                expected_title="T",
                actual_output_tab="Minutes",
                expected_output_tab="Minutes",
                revision_id="",
            )
        validate_write_guards(
            write=True,
            input_tab_id="a",
            output_tab_id="b",
            actual_title="T",
            expected_title="T",
            actual_output_tab="Minutes",
            expected_output_tab="Minutes",
            revision_id="rev",
        )


if __name__ == "__main__":
    unittest.main()
