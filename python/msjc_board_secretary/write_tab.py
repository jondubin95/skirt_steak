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
from typing import Any

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
    load_minutes_document,
    validate_write_guards,
)

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]
DEFAULT_CREDS = REPO_ROOT / "Sensitive" / "credentials.json"
DEFAULT_TOKEN = REPO_ROOT / "Sensitive" / "google" / "gdocs_token.json"
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


def tab_end_index(tab: dict[str, Any]) -> int:
    content = (tab.get("documentTab") or {}).get("body", {}).get("content") or []
    if not content:
        return 2
    return int(content[-1]["endIndex"])


def load_credentials(creds_path: Path, token_path: Path) -> Any:
    """Load or refresh OAuth credentials. Does not invent a client from the environment."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not creds_path.is_file():
                raise SystemExit(f"Missing OAuth client file: {creds_path}")
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


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
            if not revision:
                raise WriteGuardError("missing document revisionId for writeControl")
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


def _load_document(path: Path) -> MinutesDocument:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid minutes JSON: {exc}") from exc
    return load_minutes_document(raw)


def _require_write_args(args: argparse.Namespace) -> None:
    missing = [
        flag
        for flag, value in (
            ("--document-id", args.document_id),
            ("--expected-document-title", args.expected_document_title),
            ("--input-tab", args.input_tab),
            ("--output-tab", args.output_tab),
        )
        if not value
    ]
    if missing:
        raise SystemExit("refusing to write without " + ", ".join(missing))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write minutes into one Docs tab.")
    parser.add_argument("--input", required=True, help="Semantic minutes JSON path.")
    parser.add_argument("--write", action="store_true", help="Mutate the output tab.")
    parser.add_argument("--document-id", default="")
    parser.add_argument("--expected-document-title", default="")
    parser.add_argument("--input-tab", default="")
    parser.add_argument("--output-tab", default="")
    parser.add_argument("--creds", default=str(DEFAULT_CREDS))
    parser.add_argument("--token", default=str(DEFAULT_TOKEN))
    args = parser.parse_args(argv)

    document = _load_document(Path(args.input))
    if not args.write:
        print(json.dumps(dry_run_summary(document), indent=2))
        return 0

    _require_write_args(args)
    source = Path(args.input)
    if not input_is_private(source):
        raise SystemExit(
            "minutes JSON must live under Sensitive/ or outside the repo before --write"
        )
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
