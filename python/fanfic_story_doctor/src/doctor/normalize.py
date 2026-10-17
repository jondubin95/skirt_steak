"""Markdown, plain text, and AO3 HTML normalization. Tier A1."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from html.parser import HTMLParser

from doctor.ids import format_paragraph_id, format_scene_id

_SCENE_BREAK = re.compile(
    r"^(?:\*{3,}|(?:\*\s+){2,}\*|-{3,}|~{3,}|_{3,}|<hr\s*/?>)$",
    re.IGNORECASE,
)
_AUTHOR_NOTE = re.compile(r"^\s*A/N\b", re.IGNORECASE)
_CHAPTER_HEADING = re.compile(r"^#{1,3}\s+(.+)$")


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_inline(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    for src, dst in (
        ("\u201c", '"'),
        ("\u201d", '"'),
        ("\u2018", "'"),
        ("\u2019", "'"),
        ("\u2014", "-"),
        ("\u2013", "-"),
        ("\u2026", "..."),
    ):
        text = text.replace(src, dst)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    text = " ".join(lines)
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text


@dataclass
class Paragraph:
    id: str
    scene_id: str
    text: str
    content_hash: str
    chapter: int
    scene: int
    index: int


@dataclass
class Document:
    paragraphs: list[Paragraph] = field(default_factory=list)
    author_notes: list[str] = field(default_factory=list)
    scene_ids: list[str] = field(default_factory=list)

    def by_id(self) -> dict[str, Paragraph]:
        return {paragraph.id: paragraph for paragraph in self.paragraphs}


def _is_scene_break(line: str) -> bool:
    stripped = line.strip()
    if _SCENE_BREAK.match(stripped):
        return True
    compact = re.sub(r"\s+", "", stripped)
    return bool(compact) and set(compact) <= set("*~-_") and len(compact) >= 3


def _chapter_from_name(name: str, fallback: int) -> int:
    match = re.search(r"ch(?:apter)?[^\d]*(\d+)", name, re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d+)", name)
    if match:
        return int(match.group(1))
    return fallback


def normalize_markdown(text: str, chapter: int = 1) -> Document:
    """Split one chapter's markdown or plain text into paragraphs."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks: list[str] = re.split(r"\n\s*\n", text)
    doc = Document()
    scene = 1
    index = 0
    scene_id = format_scene_id(chapter, scene)
    doc.scene_ids.append(scene_id)
    for block in blocks:
        raw_lines = [line.rstrip() for line in block.split("\n")]
        kept: list[str] = []
        for line in raw_lines:
            if not line.strip():
                continue
            if _CHAPTER_HEADING.match(line.strip()):
                continue
            if _AUTHOR_NOTE.match(line):
                doc.author_notes.append(line.strip())
                continue
            if _is_scene_break(line):
                if kept:
                    _emit(doc, chapter, scene, index, kept)
                    index += 1
                    kept = []
                scene += 1
                index = 0
                scene_id = format_scene_id(chapter, scene)
                if scene_id not in doc.scene_ids:
                    doc.scene_ids.append(scene_id)
                continue
            kept.append(line)
        if kept:
            _emit(doc, chapter, scene, index, kept)
            index += 1
    return doc


def _emit(
    doc: Document, chapter: int, scene: int, index: int, lines: list[str]
) -> None:
    text = normalize_inline("\n".join(lines))
    if not text:
        return
    paragraph_index = index + 1
    paragraph = Paragraph(
        id=format_paragraph_id(chapter, scene, paragraph_index),
        scene_id=format_scene_id(chapter, scene),
        text=text,
        content_hash=content_hash(text),
        chapter=chapter,
        scene=scene,
        index=paragraph_index,
    )
    doc.paragraphs.append(paragraph)


def normalize_sources(sources: list[tuple[str, str]]) -> Document:
    """sources are (filename or label, markdown text) in reading order."""
    merged = Document()
    for offset, (name, text) in enumerate(sources, start=1):
        chapter = _chapter_from_name(name, offset)
        part = normalize_markdown(text, chapter=chapter)
        merged.paragraphs.extend(part.paragraphs)
        merged.author_notes.extend(part.author_notes)
        for scene_id in part.scene_ids:
            if scene_id not in merged.scene_ids:
                merged.scene_ids.append(scene_id)
    return merged


class _Ao3Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.capture: list[str] = []
        self.blocks: list[tuple[str, str]] = []
        self._in_p = False
        self._p_parts: list[str] = []
        self.notes: list[str] = []
        self._in_note = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): (value or "") for key, value in attrs}
        blob = f"{attr.get('class', '')} {attr.get('id', '')}".lower()
        if any(
            token in blob
            for token in ("notes", "feedback", "preface", "kudos", "bookmark")
        ):
            self.skip_depth += 1
            self._in_note = "notes" in blob or "preface" in blob
        if self.skip_depth:
            return
        if tag == "p":
            self._in_p = True
            self._p_parts = []
        elif tag == "hr":
            self.blocks.append(("break", ""))
        elif tag == "br" and self._in_p:
            self._p_parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if self.skip_depth and tag in {"div", "section"}:
            self.skip_depth = max(0, self.skip_depth - 1)
            self._in_note = False
            return
        if tag == "p" and self._in_p:
            text = normalize_inline("".join(self._p_parts))
            if text:
                self.blocks.append(("p", text))
            self._in_p = False
            self._p_parts = []

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            if self._in_note and data.strip():
                self.notes.append(data.strip())
            return
        if self._in_p:
            self._p_parts.append(data)


def normalize_html(html: str, chapter: int = 1) -> Document:
    parser = _Ao3Parser()
    parser.feed(html)
    doc = Document()
    doc.author_notes.extend(parser.notes)
    scene = 1
    index = 0
    doc.scene_ids.append(format_scene_id(chapter, scene))
    for kind, text in parser.blocks:
        if kind == "break":
            scene += 1
            index = 0
            scene_id = format_scene_id(chapter, scene)
            if scene_id not in doc.scene_ids:
                doc.scene_ids.append(scene_id)
            continue
        if _AUTHOR_NOTE.match(text):
            doc.author_notes.append(text)
            continue
        paragraph_index = index + 1
        doc.paragraphs.append(
            Paragraph(
                id=format_paragraph_id(chapter, scene, paragraph_index),
                scene_id=format_scene_id(chapter, scene),
                text=text,
                content_hash=content_hash(text),
                chapter=chapter,
                scene=scene,
                index=paragraph_index,
            )
        )
        index += 1
    return doc
