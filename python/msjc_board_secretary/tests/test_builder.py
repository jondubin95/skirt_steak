"""Builder request shapes. Standard library only."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from msjc_board_secretary.builder import (  # noqa: E402
    compose,
    disc_requests,
    docs_len,
    document_to_paragraphs,
    nesting_requests,
    requests_for_replace,
)
from msjc_board_secretary.schema import MinutesItem, load_minutes_document  # noqa: E402

SAMPLE = Path(__file__).resolve().parents[1] / "sample_minutes.json"


def _sample_doc():
    return load_minutes_document(json.loads(SAMPLE.read_text(encoding="utf-8")))


class BuilderTests(unittest.TestCase):
    def test_sample_paragraphs_and_attendance_style(self) -> None:
        paragraphs = document_to_paragraphs(_sample_doc())
        kinds = [p.kind for p in paragraphs]
        self.assertIn("h3", kinds)
        self.assertEqual(kinds.count("blank"), 2)
        officers = next(p for p in paragraphs if p.text.startswith("Officers:"))
        bold = next(span for span in officers.spans if span.bold)
        self.assertEqual(bold.size, 12)
        self.assertEqual(officers.text[: bold.end], "Officers: ")

    def test_motion_spans(self) -> None:
        doc = load_minutes_document(
            {
                "schemaVersion": 1,
                "items": [
                    {
                        "kind": "motion",
                        "body": "Alex Rivera moves to adjourn. Jordan Hale seconds.",
                        "verdict": "passes",
                    }
                ],
            }
        )
        paragraphs = document_to_paragraphs(doc)
        motion = next(p for p in paragraphs if p.kind == "motion")
        self.assertTrue(motion.text.startswith("Motion: "))
        self.assertTrue(motion.text.endswith("Motion Passes."))
        width = docs_len(motion.text)
        underline = next(span for span in motion.spans if span.underline)
        self.assertEqual((underline.start, underline.end), (0, width))
        bolds = [span for span in motion.spans if span.bold]
        self.assertEqual(bolds[0].end, docs_len("Motion"))
        self.assertEqual(bolds[-1].start, width - docs_len("Motion Passes."))

    def test_roman_headings_are_one_list(self) -> None:
        paragraphs = document_to_paragraphs(_sample_doc())
        reqs = requests_for_replace("tab", 2, paragraphs)
        creates = [
            r["createParagraphBullets"]
            for r in reqs
            if r.get("createParagraphBullets", {}).get("bulletPreset")
            == "NUMBERED_UPPERROMAN_UPPERALPHA_DECIMAL"
        ]
        self.assertEqual(len(creates), 1)
        deleted = [
            r["deleteParagraphBullets"]["range"]
            for r in reqs
            if "deleteParagraphBullets" in r
        ]
        heading_ranges = []
        for req in reqs:
            style = req.get("updateParagraphStyle")
            if not style:
                continue
            if style["paragraphStyle"].get("namedStyleType") == "HEADING_3":
                heading_ranges.append(
                    (style["range"]["startIndex"], style["range"]["endIndex"])
                )
        self.assertGreaterEqual(len(heading_ranges), 2)
        for start, end in heading_ranges:
            self.assertNotIn({"tabId": "tab", "startIndex": start, "endIndex": end}, deleted)
        for req in reqs:
            style = req.get("updateTextStyle")
            if not style or style.get("fields") != "bold,fontSize,weightedFontFamily,foregroundColor":
                continue
            self.assertEqual(style["textStyle"]["fontSize"]["magnitude"], 13)
            self.assertTrue(style["textStyle"]["bold"])

    def test_nested_bullet_requests(self) -> None:
        paragraphs = document_to_paragraphs(
            load_minutes_document(
                {
                    "schemaVersion": 1,
                    "items": [
                        {"kind": "bullet", "level": 0, "text": "Hall rental"},
                        {"kind": "bullet", "level": 1, "text": "Volunteer schedule"},
                    ],
                }
            )
        )
        tab = {
            "documentTab": {
                "body": {
                    "content": [
                        {
                            "startIndex": 1,
                            "endIndex": 13,
                            "paragraph": {"elements": [{"textRun": {"content": "Hall rental\n"}}]},
                        },
                        {
                            "startIndex": 13,
                            "endIndex": 32,
                            "paragraph": {
                                "elements": [{"textRun": {"content": "Volunteer schedule\n"}}]
                            },
                        },
                    ]
                }
            }
        }
        reqs = nesting_requests("tab", tab, paragraphs)
        texts = [r["insertText"]["text"] for r in reqs]
        self.assertIn("\n", texts)
        self.assertIn("\t", texts)
        discs = disc_requests("tab", tab, paragraphs)
        presets = [
            r["createParagraphBullets"]["bulletPreset"]
            for r in discs
            if "createParagraphBullets" in r
        ]
        self.assertEqual(presets, ["BULLET_DISC_CIRCLE_SQUARE"])

    def test_supplementary_unicode_uses_utf16(self) -> None:
        text = "A\U0001f680"
        self.assertEqual(len(text), 2)
        self.assertEqual(docs_len(text), 3)
        paragraphs = document_to_paragraphs(
            load_minutes_document(
                {"schemaVersion": 1, "items": [{"kind": "bullet", "text": text, "level": 0}]}
            )
        )
        _body, meta, _spans = compose(paragraphs)
        self.assertEqual(meta[0]["end"], docs_len(text) + 1)
        reqs = requests_for_replace("tab", 2, paragraphs)
        styled = [
            r["updateTextStyle"]["range"]
            for r in reqs
            if r.get("updateTextStyle", {}).get("fields") == "weightedFontFamily"
        ]
        self.assertEqual(styled[0]["endIndex"], 1 + docs_len(text))

    def test_presenter_is_italic(self) -> None:
        paragraphs = document_to_paragraphs(
            load_minutes_document(
                {
                    "schemaVersion": 1,
                    "items": [{"kind": "presenter", "text": "Presented by Alex Rivera."}],
                }
            )
        )
        reqs = requests_for_replace("tab", 2, paragraphs)
        italics = [
            r
            for r in reqs
            if r.get("updateTextStyle", {}).get("textStyle", {}).get("italic") is True
        ]
        self.assertTrue(italics)


class ItemShapeTests(unittest.TestCase):
    def test_minutes_item_defaults(self) -> None:
        item = MinutesItem(kind="paragraph", text="None.")
        self.assertEqual(item.level, 0)


if __name__ == "__main__":
    unittest.main()
