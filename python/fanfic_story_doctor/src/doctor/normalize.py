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


def _is_scene_break(line: str) -> bool:
    stripped = line.strip()
    if _SCENE_BREAK.match(stripped):
        return True
    compact = re.sub(r"\s+", "", stripped)
    return bool(compact) and set(compact) <= set("*~-_") and len(compact) >= 3


def _chapter_from_name(name: str, fallback: int) -> tuple[int, bool]:
    """Return (chapter, explicit). A file with no digit keeps `fallback` and is not explicit."""
    match = re.search(r"ch(?:apter)?[^\d]*(\d+)", name, re.IGNORECASE)
    if match:
        return int(match.group(1)), True
    match = re.search(r"(\d+)", name)
    if match:
        return int(match.group(1)), True
    return fallback, False


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


def _is_html(name: str) -> bool:
    return name.lower().endswith((".html", ".htm"))


def _many_chapters(name: str, text: str) -> bool:
    return _is_html(name) and len(set(re.findall(r'id="chapter-(\d+)"', text))) > 1


class DuplicateChapter(ValueError):
    """Two source files claim the same chapter number."""


def _parse(name: str, text: str, chapter: int) -> Document:
    if not _is_html(name):
        return normalize_markdown(text, chapter=chapter)
    if _many_chapters(name, text):
        return normalize_ao3_work(text, chapter)
    return normalize_html(text, chapter)


def normalize_sources(sources: list[tuple[str, str]]) -> Document:
    """sources are (filename or label, text).

    Files merge in chapter order. A file's chapter comes from its name; a
    full-work HTML file claims every chapter on its page. A file with no digit
    is numbered after the highest claimed chapter, in input order. Two files
    claiming one chapter raise DuplicateChapter, so paragraph ids stay unique.

    `.md` and `.txt` are Markdown or plain text, one chapter each. `.html` is
    AO3 HTML: a chapter page, or a full-work download that holds several
    `chapter-N` blocks (chapters then come from the page itself).
    """
    parts: list[tuple[int, int, Document]] = []
    unnamed: list[tuple[int, str, str]] = []
    owner: dict[int, str] = {}
    for offset, (name, text) in enumerate(sources):
        chapter, named = _chapter_from_name(name, 0)
        if not named and not _many_chapters(name, text):
            unnamed.append((offset, name, text))
            continue
        part = _parse(name, text, chapter or 1)
        claimed = sorted({p.chapter for p in part.paragraphs} or {chapter})
        for number in claimed:
            if number in owner:
                raise DuplicateChapter(
                    f"duplicate chapter {number}: {owner[number]}, {name}"
                )
            owner[number] = name
        parts.append((claimed[0], offset, part))
    next_chapter = max(owner, default=0) + 1
    for offset, name, text in unnamed:
        parts.append((next_chapter, offset, _parse(name, text, next_chapter)))
        next_chapter += 1
    parts.sort(key=lambda row: (row[0], row[1]))
    merged = Document()
    for _chapter, _offset, part in parts:
        merged.paragraphs.extend(part.paragraphs)
        merged.author_notes.extend(part.author_notes)
        for scene_id in part.scene_ids:
            if scene_id not in merged.scene_ids:
                merged.scene_ids.append(scene_id)
    return merged


_VOID = {
    "br",
    "hr",
    "img",
    "meta",
    "input",
    "link",
    "wbr",
    "source",
    "col",
    "area",
    "base",
    "embed",
    "param",
    "track",
}
_SKIP_TOKENS = (
    "notes",
    "feedback",
    "preface",
    "kudos",
    "bookmark",
    "summary",
    "afterword",
    "comments",
)
_CHAPTER_ID = re.compile(r"^chapter-(\d+)$")


class _Ao3Parser(HTMLParser):
    """AO3 HTML to blocks. Tracks a real element stack, so nested markup inside
    author notes or site chrome cannot end the skip early."""

    def __init__(self, require_userstuff: bool = True) -> None:
        super().__init__(convert_charrefs=True)
        self.require_userstuff = require_userstuff
        # stack entries: (tag, skip, content, chapter)
        self.stack: list[tuple[str, bool, bool, int | None]] = []
        self.blocks: list[tuple[str, str, int | None]] = []
        self.notes: list[str] = []
        self._p_parts: list[str] | None = None
        self._note_parts: list[str] = []
        self.saw_userstuff = False

    def _top(self) -> tuple[bool, bool, int | None]:
        if not self.stack:
            return False, not self.require_userstuff, None
        _tag, skip, content, chapter = self.stack[-1]
        return skip, content, chapter

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): (value or "") for key, value in attrs}
        classes = attr.get("class", "").lower()
        ident = attr.get("id", "").lower()
        skip, content, chapter = self._top()
        blob = f"{classes} {ident}"
        if any(token in blob for token in _SKIP_TOKENS):
            skip = True
        if "userstuff" in classes.split():
            content = True
            self.saw_userstuff = True
        match = _CHAPTER_ID.match(ident)
        if match:
            chapter = int(match.group(1))
        if tag == "hr":
            if not skip and content:
                self.blocks.append(("break", "", chapter))
            return
        if tag == "br":
            if self._p_parts is not None:
                self._p_parts.append(" ")
            return
        if tag in _VOID:
            return
        self.stack.append((tag, skip, content, chapter))
        if tag == "p" and not skip and content:
            self._p_parts = []

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID and self.stack and self.stack[-1][0] == tag:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID:
            return
        if not any(entry[0] == tag for entry in self.stack):
            return
        while self.stack:
            entry = self.stack.pop()
            if (
                entry[0] == "p"
                and self._p_parts is not None
                and not entry[1]
                and entry[2]
            ):
                text = normalize_inline("".join(self._p_parts))
                if text:
                    kind = "break" if _is_scene_break(text) else "p"
                    self.blocks.append((kind, text, entry[3]))
                self._p_parts = None
            if entry[0] == tag:
                break
        was_skipping = self._top()[0]
        if not was_skipping and self._note_parts:
            note = normalize_inline(" ".join(self._note_parts))
            if note:
                self.notes.append(note)
            self._note_parts = []

    def handle_data(self, data: str) -> None:
        skip, _content, _chapter = self._top()
        if skip:
            if data.strip():
                self._note_parts.append(data.strip())
            return
        if self._p_parts is not None:
            self._p_parts.append(data)


def _parse_ao3(html: str) -> _Ao3Parser:
    parser = _Ao3Parser(require_userstuff=True)
    parser.feed(html)
    parser.close()
    if not parser.saw_userstuff:
        # A bare chapter fragment with no AO3 wrapper.
        parser = _Ao3Parser(require_userstuff=False)
        parser.feed(html)
        parser.close()
    return parser


def _blocks_to_doc(blocks, notes, default_chapter: int) -> Document:
    doc = Document()
    doc.author_notes.extend(notes)
    state: dict[int, list[int]] = {}
    for kind, text, chapter in blocks:
        chapter = chapter or default_chapter
        if chapter not in state:
            state[chapter] = [1, 0]
            doc.scene_ids.append(format_scene_id(chapter, 1))
        scene, index = state[chapter]
        if kind == "break":
            if index:
                scene += 1
                index = 0
                doc.scene_ids.append(format_scene_id(chapter, scene))
            state[chapter] = [scene, index]
            continue
        if _AUTHOR_NOTE.match(text):
            doc.author_notes.append(text)
            continue
        index += 1
        doc.paragraphs.append(
            Paragraph(
                id=format_paragraph_id(chapter, scene, index),
                scene_id=format_scene_id(chapter, scene),
                text=text,
                content_hash=content_hash(text),
                chapter=chapter,
                scene=scene,
                index=index,
            )
        )
        state[chapter] = [scene, index]
    if not doc.scene_ids:
        doc.scene_ids.append(format_scene_id(default_chapter, 1))
    return doc


def normalize_html(html: str, chapter: int = 1) -> Document:
    """One AO3 chapter page or fragment. Chapter ids inside the page are ignored."""
    parser = _parse_ao3(html)
    blocks = [(kind, text, None) for kind, text, _ch in parser.blocks]
    return _blocks_to_doc(blocks, parser.notes, chapter)


def normalize_ao3_work(html: str, chapter: int = 1) -> Document:
    """A full-work AO3 download (view_full_work or the HTML download).

    Chapters come from the page's `chapter-N` ids. Author notes, summary,
    preface, kudos, comments, and site chrome are skipped.
    """
    parser = _parse_ao3(html)
    return _blocks_to_doc(parser.blocks, parser.notes, chapter)
