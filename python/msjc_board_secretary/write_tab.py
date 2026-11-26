#!/usr/bin/env python3
"""Guarded writer for one Google Docs tab.

Dry-run is the default and does not load credentials or call Google.
A real write requires --write, an expected document title, distinct input
and output tabs, and the revisionId from the preceding read on every batch.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, TextIO

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "python") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "python"))

from msjc_board_secretary.builder import (  # noqa: E402
    attach_write_control,
    blank_paragraph_requests,
    disc_requests,
    document_to_paragraphs,
    nesting_requests,
    preflight_paragraphs,
    requests_for_replace,
    strip_spilled_bullets,
)
from msjc_board_secretary.schema import (  # noqa: E402
    MinutesDocument,
    WriteGuardError,
    absent_speaker_conflicts,
    load_minutes_document,
    minutes_phrase_errors,
    minutes_shape_errors,
    validate_target_identity,
    validate_write_guards,
)

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]
DEFAULT_CREDS = REPO_ROOT / "Sensitive" / "credentials.json"
DEFAULT_TOKEN = REPO_ROOT / "Sensitive" / "google" / "gdocs_token.json"
REAUTH_MESSAGE = (
    "Google token refresh failed. Run "
    "python python/msjc_board_secretary/reauth.py from the repo "
    "root, complete the sign-in prompt where it is shown, then retry this command."
)
RECOVERY_MESSAGE = (
    "Pass 1 replaced the tab, and re-running the exact same CLI command with "
    "--write will cleanly wipe and rebuild the tab from the private JSON file."
)
PASS_NAMES = ("replace", "nesting", "discs", "blanks", "strip")


def input_is_private(path: Path, repo_root: Path = REPO_ROOT) -> bool:
    """True when the file is under Sensitive/ or outside the repo."""
    resolved = path.resolve()
    try:
        resolved.relative_to((repo_root / "Sensitive").resolve())
        return True
    except ValueError:
        pass
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError:
        return True
    return False


def flatten_tabs(tabs: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for tab in tabs or []:
        out.append(tab)
        out.extend(flatten_tabs(tab.get("childTabs")))
    return out


def find_tab(tabs: list[dict[str, Any]], title: str) -> dict[str, Any]:
    wanted = title.strip().lower()
    for tab in tabs:
        props = tab.get("tabProperties") or {}
        if (props.get("title") or "").strip().lower() == wanted:
            return tab
    titles = [(t.get("tabProperties") or {}).get("title") for t in tabs]
    raise WriteGuardError(f"Tab {title!r} not found. Available: {titles}")


def tab_id_of(tab: dict[str, Any]) -> str:
    return str((tab.get("tabProperties") or {}).get("tabId") or "")


def tab_title_of(tab: dict[str, Any]) -> str:
    return str((tab.get("tabProperties") or {}).get("title") or "")


def full_tab_replace_is_confirmed(
    *,
    document_title: str,
    output_tab: str,
    confirmed_document_title: str,
    confirmed_output_tab: str,
) -> bool:
    """True only when the request named both the document and the output tab.

    Blank titles do not match. The CLI requires those flags first; a direct
    caller can still pass blanks, and blanks must not count as confirmation.
    """
    return (
        bool(document_title)
        and bool(output_tab)
        and confirmed_document_title == document_title
        and confirmed_output_tab == output_tab
    )


def require_full_tab_confirmation(
    *,
    document_title: str,
    output_tab: str,
    confirmed_document_title: str,
    confirmed_output_tab: str,
    input_stream: TextIO,
    output_stream: TextIO,
) -> None:
    """Stop before a full-tab replace unless both titles were named.

    A matching document title with no output tab is not confirmation. When
    the names were not both supplied, a terminal may type them. A non-interactive
    caller is refused instead of waiting.
    """
    if full_tab_replace_is_confirmed(
        document_title=document_title,
        output_tab=output_tab,
        confirmed_document_title=confirmed_document_title,
        confirmed_output_tab=confirmed_output_tab,
    ):
        return
    if not input_stream.isatty():
        raise WriteGuardError(
            "refusing to replace the tab until the request names both "
            "the exact document title and the output tab"
        )
    print(
        "This replaces the entire "
        f"{output_tab!r} tab of {document_title!r}. "
        "Type the document title, a tab, and the output tab title to continue.",
        file=output_stream,
    )
    line = input_stream.readline()
    if line.rstrip("\r\n") != f"{document_title}\t{output_tab}":
        raise WriteGuardError(
            "refusing to replace the tab without confirmation of both "
            "the document title and the output tab"
        )


def tab_end_index(tab: dict[str, Any]) -> int:
    content = (tab.get("documentTab") or {}).get("body", {}).get("content") or []
    if not content:
        return 2
    return int(content[-1]["endIndex"])


def load_credentials(creds_path: Path, token_path: Path) -> Any:
    """Load or refresh OAuth credentials. Does not invent a client from the environment."""
    from msjc_board_secretary.auth import load_credentials as load_oauth_credentials

    return load_oauth_credentials(
        creds_path,
        token_path,
        SCOPES,
        refresh_failure_message=REAUTH_MESSAGE,
    )


def build_docs_service(creds: Any) -> Any:
    from googleapiclient.discovery import build

    return build("docs", "v1", credentials=creds, cache_discovery=False)


class GoogleDocsClient:
    """Thin documents.get / documents.batchUpdate wrapper."""

    def __init__(self, service: Any) -> None:
        self._service = service

    def get_document(self, document_id: str) -> dict[str, Any]:
        return (
            self._service.documents()
            .get(documentId=document_id, includeTabsContent=True)
            .execute()
        )

    def batch_update(self, document_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return (
            self._service.documents()
            .batchUpdate(documentId=document_id, body=body)
            .execute()
        )


def requests_for_pass(
    name: str,
    tab_id: str,
    paragraphs: list[Any],
    tab: dict[str, Any],
) -> list[dict[str, Any]]:
    if name == "replace":
        return requests_for_replace(tab_id, tab_end_index(tab), paragraphs)
    if name == "nesting":
        return nesting_requests(tab_id, tab, paragraphs)
    if name == "discs":
        return disc_requests(tab_id, tab, paragraphs)
    if name == "blanks":
        return blank_paragraph_requests(tab_id, tab)
    if name == "strip":
        return strip_spilled_bullets(tab_id, tab)
    raise WriteGuardError(f"unknown pass {name}")


def dry_run_summary(document: MinutesDocument) -> dict[str, Any]:
    paragraphs = document_to_paragraphs(document)
    preflight_paragraphs(paragraphs)
    reqs = requests_for_replace("dry-run", 2, paragraphs)
    return {
        "mode": "dry-run",
        "paragraphs": len(paragraphs),
        "pass1Requests": len(reqs),
    }


def _reload_output_tab(
    client: Any, document_id: str, output_tab: str
) -> tuple[dict[str, Any], dict[str, Any], str]:
    doc = client.get_document(document_id)
    revision = str(doc.get("revisionId") or "")
    tab = find_tab(flatten_tabs(doc.get("tabs")), output_tab)
    return doc, tab, revision


def perform_write(
    client: Any,
    document: MinutesDocument,
    *,
    document_id: str,
    expected_title: str,
    input_tab: str,
    output_tab: str,
) -> dict[str, Any]:
    paragraphs = document_to_paragraphs(document)
    preflight_paragraphs(paragraphs)
    doc = client.get_document(document_id)
    tabs = flatten_tabs(doc.get("tabs"))
    source = find_tab(tabs, input_tab)
    target = find_tab(tabs, output_tab)
    validate_write_guards(
        write=True,
        input_tab_id=tab_id_of(source),
        output_tab_id=tab_id_of(target),
        actual_title=str(doc.get("title") or ""),
        expected_title=expected_title,
        actual_output_tab=tab_title_of(target),
        expected_output_tab=output_tab,
        revision_id=str(doc.get("revisionId") or ""),
    )
    revision = str(doc.get("revisionId") or "")
    counts: dict[str, int] = {}
    completed = 0
    current = target
    try:
        for name in PASS_NAMES:
            reqs = requests_for_pass(name, tab_id_of(target), paragraphs, current)
            counts[name] = len(reqs)
            if not reqs:
                continue
            if not revision:
                raise WriteGuardError("missing document revisionId for writeControl")
            client.batch_update(
                document_id,
                attach_write_control({"requests": reqs}, revision),
            )
            completed += 1
            _doc, current, revision = _reload_output_tab(client, document_id, output_tab)
    except Exception:
        if completed >= 1:
            print(RECOVERY_MESSAGE, file=sys.stderr)
        raise
    return {
        "mode": "write",
        "documentTitle": expected_title,
        "outputTab": output_tab,
        "tabId": tab_id_of(target),
        "requestCounts": counts,
        "url": f"https://docs.google.com/document/d/{document_id}/edit",
    }


def tab_plain_text(tab: dict[str, Any]) -> str:
    chunks: list[str] = []
    content = (tab.get("documentTab") or {}).get("body", {}).get("content") or []
    for element in content:
        paragraph = element.get("paragraph") or {}
        for run in paragraph.get("elements") or []:
            chunks.append((run.get("textRun") or {}).get("content") or "")
    return "".join(chunks)


def replace_all_request(tab_id: str, find_text: str, replacement: str) -> dict[str, Any]:
    return {
        "replaceAllText": {
            "containsText": {"text": find_text, "matchCase": True},
            "replaceText": replacement,
            "tabsCriteria": {"tabIds": [tab_id]},
        }
    }


def load_replace_pair(path: Path) -> tuple[str, str]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid replace JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise SystemExit("replace JSON must be an object")
    find_text = raw.get("find")
    replacement = raw.get("replaceWith")
    if not isinstance(find_text, str) or not find_text:
        raise SystemExit("replace JSON find must be a non-empty string")
    if not isinstance(replacement, str):
        raise SystemExit("replace JSON replaceWith must be a string")
    if find_text == replacement:
        raise SystemExit("replace JSON find and replaceWith are the same")
    return find_text, replacement


def perform_replace(
    client: Any,
    *,
    document_id: str,
    expected_title: str,
    output_tab: str,
    find_text: str,
    replacement: str,
) -> dict[str, Any]:
    """Replace one exact phrase on the output tab. Leave every other tab alone."""
    if not find_text or find_text == replacement:
        raise WriteGuardError("replace needs two different strings")
    doc = client.get_document(document_id)
    target = find_tab(flatten_tabs(doc.get("tabs")), output_tab)
    revision = str(doc.get("revisionId") or "")
    validate_target_identity(
        actual_title=str(doc.get("title") or ""),
        expected_title=expected_title,
        actual_output_tab=tab_title_of(target),
        expected_output_tab=output_tab,
        revision_id=revision,
    )
    matches = tab_plain_text(target).count(find_text)
    if matches != 1:
        raise WriteGuardError(
            f"{output_tab} contains {matches} matches; refusing to replace"
        )
    client.batch_update(
        document_id,
        attach_write_control(
            {"requests": [replace_all_request(tab_id_of(target), find_text, replacement)]},
            revision,
        ),
    )
    return {
        "mode": "replace",
        "documentTitle": expected_title,
        "outputTab": output_tab,
        "tabId": tab_id_of(target),
        "matches": 1,
        "url": f"https://docs.google.com/document/d/{document_id}/edit",
    }


def _load_document(path: Path) -> MinutesDocument:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid minutes JSON: {exc}") from exc
    return load_minutes_document(raw)


_REPLACE_FLAGS = (
    ("--document-id", "document_id"),
    ("--expected-document-title", "expected_document_title"),
    ("--output-tab", "output_tab"),
)
_FULL_WRITE_FLAGS = _REPLACE_FLAGS + (("--input-tab", "input_tab"),)


def _require_flags(
    args: argparse.Namespace, names: tuple[tuple[str, str], ...], action: str
) -> None:
    missing = [flag for flag, attr in names if not getattr(args, attr)]
    if missing:
        raise SystemExit(f"refusing to {action} without " + ", ".join(missing))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write minutes into one Docs tab.")
    parser.add_argument("--input", default="", help="Semantic minutes JSON path.")
    parser.add_argument(
        "--replace",
        default="",
        help="Private JSON with find and replaceWith. Changes one phrase on the output tab.",
    )
    parser.add_argument("--write", action="store_true", help="Mutate the output tab.")
    parser.add_argument("--document-id", default="")
    parser.add_argument("--expected-document-title", default="")
    parser.add_argument("--input-tab", default="")
    parser.add_argument("--output-tab", default="")
    parser.add_argument(
        "--confirmed-document-title",
        default="",
        help="Document title the request already named. Required for a full-tab replace.",
    )
    parser.add_argument(
        "--confirmed-output-tab",
        default="",
        help="Output tab the request already named. Required for a full-tab replace.",
    )
    parser.add_argument("--creds", default=str(DEFAULT_CREDS))
    parser.add_argument("--token", default=str(DEFAULT_TOKEN))
    args = parser.parse_args(argv)

    if args.replace:
        if args.input:
            raise SystemExit("pass either --input or --replace, not both")
        if not args.write:
            raise SystemExit("refusing to replace without --write")
        _require_flags(args, _REPLACE_FLAGS, "replace")
        source = Path(args.replace)
        if not input_is_private(source):
            raise SystemExit(
                "replace JSON must live under Sensitive/ or outside the repo before --write"
            )
        find_text, replacement = load_replace_pair(source)
        phrase_errors = minutes_phrase_errors(replacement)
        if phrase_errors:
            raise SystemExit("refusing the replacement: " + "; ".join(phrase_errors))
        creds = load_credentials(Path(args.creds), Path(args.token))
        client = GoogleDocsClient(build_docs_service(creds))
        try:
            summary = perform_replace(
                client,
                document_id=args.document_id,
                expected_title=args.expected_document_title,
                output_tab=args.output_tab,
                find_text=find_text,
                replacement=replacement,
            )
        except WriteGuardError as exc:
            raise SystemExit(str(exc)) from exc
        print(json.dumps(summary, indent=2))
        return 0

    if not args.input:
        raise SystemExit("pass --input or --replace")

    document = _load_document(Path(args.input))
    reasons: list[str] = []
    conflicts = absent_speaker_conflicts(document)
    if conflicts:
        names = ", ".join(conflicts)
        reasons.append(
            "marked not in attendance and credited with a speaking part: " + names
        )
    reasons.extend(minutes_shape_errors(document))
    if reasons:
        raise SystemExit("refusing the minutes: " + "; ".join(reasons))
    if not args.write:
        print(json.dumps(dry_run_summary(document), indent=2))
        return 0

    _require_flags(args, _FULL_WRITE_FLAGS, "write")
    source = Path(args.input)
    if not input_is_private(source):
        raise SystemExit(
            "minutes JSON must live under Sensitive/ or outside the repo before --write"
        )
    try:
        require_full_tab_confirmation(
            document_title=args.expected_document_title,
            output_tab=args.output_tab,
            confirmed_document_title=args.confirmed_document_title,
            confirmed_output_tab=args.confirmed_output_tab,
            input_stream=sys.stdin,
            output_stream=sys.stderr,
        )
    except WriteGuardError as exc:
        raise SystemExit(str(exc)) from exc
    creds = load_credentials(Path(args.creds), Path(args.token))
    client = GoogleDocsClient(build_docs_service(creds))
    try:
        summary = perform_write(
            client,
            document,
            document_id=args.document_id,
            expected_title=args.expected_document_title,
            input_tab=args.input_tab,
            output_tab=args.output_tab,
        )
    except WriteGuardError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
