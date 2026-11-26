#!/usr/bin/env python3
"""Read-only Drive revision list, export, and comment dump.

Scope is drive.readonly. The token file is separate from the writer token.
Output goes under Sensitive/msjc/revisions/<docId>/, which .gitignore covers
with /Sensitive/**. Dry commands still need credentials because every
subcommand calls Drive.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "python") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "python"))

from msjc_board_secretary.auth import load_credentials  # noqa: E402

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
DEFAULT_CREDS = REPO_ROOT / "Sensitive" / "credentials.json"
DEFAULT_TOKEN = REPO_ROOT / "Sensitive" / "google" / "gdocs_token_drive_readonly.json"
DEFAULT_OUT = REPO_ROOT / "Sensitive" / "msjc" / "revisions"
REVISION_FIELDS = "id,modifiedTime,lastModifyingUser(displayName),exportLinks"
REVISION_PAGE_SIZE = 1000
COMMENT_PAGE_SIZE = 100
COMMENT_FIELDS = (
    "nextPageToken,comments(id,content,author(displayName,emailAddress),"
    "createdTime,modifiedTime,resolved,quotedFileContent,"
    "replies(id,content,author(displayName,emailAddress),createdTime,modifiedTime))"
)
EXTENSIONS = {
    "text/markdown": "md",
    "text/plain": "txt",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}
PLAIN_MIME = "text/plain"
EXPORT_ATTEMPTS = 6
DRIVE_REQUEST_RETRY_COUNT = 5
SIGN_IN_TIMEOUT_SECONDS = 300
DOC_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
REFRESH_FAILURE_MESSAGE = (
    "Drive read-only token refresh failed. reauth.py updates the writer token, "
    "not this one. Move the drive read-only token file aside and run this command "
    "again to sign in."
)


def doc_id(value: str) -> str:
    """Return the Drive file id from a Docs URL or from a raw id.

    The id must be letters, digits, underscores, and hyphens. That keeps a
    path such as ``../`` from being joined onto the output directory.
    """
    match = re.search(r"/d/([A-Za-z0-9_-]+)", value)
    found = match.group(1) if match else value.strip()
    if not found:
        raise SystemExit("Document id is empty.")
    if DOC_ID_PATTERN.fullmatch(found) is None:
        raise SystemExit(
            "Document id must contain only letters, digits, underscores, and hyphens."
        )
    return found


def _is_drive_http_error(exc: BaseException) -> bool:
    return (
        type(exc).__module__.startswith("googleapiclient")
        and type(exc).__name__ == "HttpError"
    )


def _execute(request: Any) -> dict:
    """Run a Drive request with the client's own retries.

    ``num_retries`` covers HTTP 429, 5xx, and 403 ``rateLimitExceeded`` /
    ``userRateLimitExceeded``. The client chooses the backoff.
    """
    return request.execute(num_retries=DRIVE_REQUEST_RETRY_COUNT)


def _collect_pages(
    fetch_page: Callable[[str | None], dict[str, Any]], item_key: str
) -> list[dict]:
    items: list[dict] = []
    page_token: str | None = None
    while True:
        payload = fetch_page(page_token)
        items.extend(payload.get(item_key) or [])
        page_token = payload.get("nextPageToken")
        if not page_token:
            return items


def list_revisions(drive: Any, file_id: str) -> list[dict]:
    def fetch_page(page_token: str | None) -> dict[str, Any]:
        request = drive.revisions().list(
            fileId=file_id,
            pageSize=REVISION_PAGE_SIZE,
            pageToken=page_token,
            fields=f"nextPageToken,revisions({REVISION_FIELDS})",
        )
        return _execute(request)

    return _collect_pages(fetch_page, "revisions")


def list_comments(drive: Any, file_id: str) -> list[dict]:
    def fetch_page(page_token: str | None) -> dict[str, Any]:
        request = drive.comments().list(
            fileId=file_id,
            pageSize=COMMENT_PAGE_SIZE,
            pageToken=page_token,
            fields=COMMENT_FIELDS,
        )
        return _execute(request)

    return _collect_pages(fetch_page, "comments")


def revision_stamp(modified_time: str) -> str:
    return modified_time.replace(":", "").replace("-", "")[:15]


def choose_export_mime(export_links: dict[str, str], requested_mime: str) -> str | None:
    if requested_mime in export_links:
        return requested_mime
    if PLAIN_MIME in export_links:
        return PLAIN_MIME
    return None


def export_filename(modified_time: str, revision_id: str, mime: str) -> str:
    extension = EXTENSIONS.get(mime, "bin")
    return f"{revision_stamp(modified_time)}_rev{revision_id}.{extension}"


def fetch_export(session: Any, url: str) -> Any:
    """GET an export link up to six times.

    A 429 waits 5, 10, 20, 40, then 80 seconds before the next attempt.
    The sixth 429 does not sleep.
    """
    response = session.get(url)
    for attempt in range(EXPORT_ATTEMPTS - 1):
        if response.status_code != 429:
            break
        time.sleep(5 * 2**attempt)
        response = session.get(url)
    response.raise_for_status()
    return response


def cmd_list(drive: Any, file_id: str) -> None:
    meta = _execute(drive.files().get(fileId=file_id, fields="name"))
    revisions = list_revisions(drive, file_id)
    print(f"{meta['name']}: {len(revisions)} revisions")
    for revision in revisions:
        user = revision.get("lastModifyingUser") or {}
        display_name = user.get("displayName") or "unknown"
        print(f"{revision['id']:>12}  {revision['modifiedTime']}  {display_name}")


class ExportResult:
    def __init__(
        self, written: list[Path], skipped: list[str], failed: list[str]
    ) -> None:
        self.written = written
        self.skipped = skipped
        self.failed = failed


def export_revisions(
    session: Any,
    file_id: str,
    wanted: list[str],
    mime: str,
    out_dir: Path,
    revisions: list[dict],
) -> ExportResult:
    by_id = {revision["id"]: revision for revision in revisions}
    missing = [revision_id for revision_id in wanted if revision_id not in by_id]
    if missing:
        raise SystemExit(f"Revision(s) not in the API list: {', '.join(missing)}")
    target = out_dir / file_id
    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    skipped: list[str] = []
    failed: list[str] = []
    for revision_id in wanted:
        revision = by_id[revision_id]
        chosen = choose_export_mime(revision.get("exportLinks") or {}, mime)
        if chosen is None:
            skipped.append(revision_id)
            print(f"{revision_id}: no export link", file=sys.stderr)
            continue
        if chosen != mime:
            print(
                f"{revision_id}: {mime} is not in the export links; using {chosen}.",
                file=sys.stderr,
            )
        try:
            response = fetch_export(session, revision["exportLinks"][chosen])
        except Exception as exc:  # noqa: BLE001 — one Drive HttpError must not abort the rest
            if not _is_drive_http_error(exc):
                raise
            failed.append(revision_id)
            print(f"{revision_id}: {exc}", file=sys.stderr)
            continue
        path = target / export_filename(revision["modifiedTime"], revision_id, chosen)
        path.write_bytes(response.content)
        written.append(path)
        print(f"{revision_id} -> {path}")
    return ExportResult(written, skipped, failed)


def write_comments(drive: Any, file_id: str, out_dir: Path) -> Path:
    comments = list_comments(drive, file_id)
    target = out_dir / file_id
    target.mkdir(parents=True, exist_ok=True)
    path = target / "comments.json"
    payload = {"fileId": file_id, "comments": comments}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(path)
    return path


def build_drive(creds: Any) -> Any:
    from googleapiclient.discovery import build

    return build("drive", "v3", credentials=creds, cache_discovery=False)


def authorized_session(creds: Any) -> Any:
    from google.auth.transport.requests import AuthorizedSession

    return AuthorizedSession(creds)


def load_drive_credentials(creds_path: Path, token_path: Path) -> Any:
    return load_credentials(
        creds_path,
        token_path,
        SCOPES,
        interactive=True,
        timeout_seconds=SIGN_IN_TIMEOUT_SECONDS,
        refresh_failure_message=REFRESH_FAILURE_MESSAGE,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="List, export, or dump comments for one Google Doc. Read-only."
    )
    parser.add_argument("--creds", default=str(DEFAULT_CREDS))
    parser.add_argument("--token", default=str(DEFAULT_TOKEN))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    subcommands = parser.add_subparsers(dest="command", required=True)

    list_command = subcommands.add_parser(
        "list", help="Print revision id, time, and author."
    )
    list_command.add_argument("document")

    export_command = subcommands.add_parser(
        "export", help="Write revision exports under the output directory."
    )
    export_command.add_argument("document")
    export_command.add_argument("revision_ids", nargs="*")
    export_command.add_argument("--all", action="store_true")
    export_command.add_argument(
        "--mime", default="text/markdown", choices=sorted(EXTENSIONS)
    )

    comments_command = subcommands.add_parser(
        "comments", help="Write Drive comments, including replies, as JSON."
    )
    comments_command.add_argument("document")
    return parser


def _exit_for_known_failure(exc: Exception) -> int:
    if type(exc).__name__ == "WSGITimeoutError":
        raise SystemExit(
            "No sign-in arrived. Run this command again and approve the prompt."
        ) from exc
    if _is_drive_http_error(exc):
        print(f"Drive request failed: {exc}", file=sys.stderr)
        return 1
    raise exc


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "export" and args.all and args.revision_ids:
        raise SystemExit("Pass revision ids or --all, not both.")
    if args.command == "export" and not args.all and not args.revision_ids:
        raise SystemExit("Pass revision ids or --all")
    file_id = doc_id(args.document)
    try:
        return _run(args, file_id)
    except Exception as exc:  # noqa: BLE001 — Drive HttpError and sign-in timeout exit in one line
        return _exit_for_known_failure(exc)


def _run(args: argparse.Namespace, file_id: str) -> int:
    creds = load_drive_credentials(Path(args.creds), Path(args.token))
    drive = build_drive(creds)
    out_dir = Path(args.out)
    if args.command == "list":
        cmd_list(drive, file_id)
        return 0
    if args.command == "comments":
        write_comments(drive, file_id, out_dir)
        return 0
    listed = list_revisions(drive, file_id)
    wanted = (
        [revision["id"] for revision in listed] if args.all else list(args.revision_ids)
    )
    if not wanted:
        raise SystemExit("The API list has no revisions.")
    result = export_revisions(
        authorized_session(creds),
        file_id,
        wanted,
        args.mime,
        out_dir,
        listed,
    )
    if result.skipped or result.failed:
        requested = len(wanted)
        print(
            f"Wrote {len(result.written)} of {requested} revisions; "
            f"skipped {len(result.skipped)}; failed {len(result.failed)}.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
