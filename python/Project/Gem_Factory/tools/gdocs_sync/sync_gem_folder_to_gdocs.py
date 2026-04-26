from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]


@dataclass(frozen=True)
class SyncItem:
    rel_key: str
    src_path: Path
    title: str


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _get_creds(client_secrets_path: Path, token_path: Path) -> Credentials:
    creds: Optional[Credentials] = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets_path), SCOPES)
    creds = flow.run_local_server(port=0)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _iter_markdown_files(src_dir: Path) -> Iterable[Path]:
    for path in sorted(src_dir.rglob("*.md")):
        if path.is_file():
            yield path


def _rel_key(src_dir: Path, path: Path) -> str:
    return path.relative_to(src_dir).as_posix()


def _compute_title(title_prefix: str, rel_key: str) -> str:
    base = Path(rel_key).stem  # keeps ".instructions" in name; that's fine
    return f"{title_prefix}{base}"


def _get_doc_end_index(doc: Dict[str, Any]) -> int:
    # Docs API uses 1-based indexes. Body content typically ends with an endIndex.
    content = doc.get("body", {}).get("content", [])
    end_index = 1
    for element in content:
        element_end = element.get("endIndex")
        if isinstance(element_end, int):
            end_index = max(end_index, element_end)
    return end_index


def _replace_doc_text(docs_svc: Any, doc_id: str, text: str) -> None:
    doc = docs_svc.documents().get(documentId=doc_id).execute()
    end_index = _get_doc_end_index(doc)

    requests = []
    # Fresh/near-empty Google Docs often have only the implicit trailing newline.
    # Deleting range 1..1 is invalid, so only delete when there's actual content.
    if end_index > 2:
        requests.append(
            {
                "deleteContentRange": {
                    "range": {"startIndex": 1, "endIndex": end_index - 1}
                }
            }
        )
    # Ensure the doc ends with a newline so the cursor doesn't stick to last line.
    if not text.endswith("\n"):
        text = text + "\n"
    requests.append({"insertText": {"location": {"index": 1}, "text": text}})

    docs_svc.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()


def _create_doc_in_drive(drive_svc: Any, title: str, folder_id: Optional[str]) -> str:
    body: Dict[str, Any] = {
        "name": title,
        "mimeType": "application/vnd.google-apps.document",
    }
    if folder_id:
        body["parents"] = [folder_id]

    created = drive_svc.files().create(body=body, fields="id").execute()
    return created["id"]


def _build_items(src_dir: Path, title_prefix: str) -> list[SyncItem]:
    items: list[SyncItem] = []
    for path in _iter_markdown_files(src_dir):
        rel_key = _rel_key(src_dir, path)
        title = _compute_title(title_prefix=title_prefix, rel_key=rel_key)
        items.append(SyncItem(rel_key=rel_key, src_path=path, title=title))
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync local markdown files to Google Docs.")
    parser.add_argument("--src", type=Path, required=True, help="Source directory of .md files")
    parser.add_argument("--title-prefix", type=str, default="", help="Prefix for created doc titles")
    parser.add_argument(
        "--client-secrets",
        type=Path,
        required=True,
        help="OAuth client secrets JSON (Desktop app)",
    )
    parser.add_argument(
        "--token",
        type=Path,
        required=True,
        help="Token cache path (will be created/updated)",
    )
    parser.add_argument(
        "--map",
        type=Path,
        required=True,
        help="JSON mapping file: relpath -> docId (will be created/updated)",
    )
    parser.add_argument("--folder-id", type=str, default=None, help="Optional Drive folder ID")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without API writes")
    args = parser.parse_args()

    src_dir: Path = args.src
    if not src_dir.exists() or not src_dir.is_dir():
        raise SystemExit(f"--src is not a directory: {src_dir}")

    if not args.client_secrets.exists():
        raise SystemExit(f"--client-secrets not found: {args.client_secrets}")

    mapping: Dict[str, Any] = _load_json(args.map)
    file_to_doc: Dict[str, str] = dict(mapping.get("files", {}))

    items = _build_items(src_dir=src_dir, title_prefix=args.title_prefix)
    if not items:
        print(f"No .md files found under: {src_dir}")
        return 0

    if args.dry_run:
        for item in items:
            doc_id = file_to_doc.get(item.rel_key)
            action = "UPDATE" if doc_id else "CREATE"
            print(f"{action}: {item.rel_key} -> {item.title}" + (f" ({doc_id})" if doc_id else ""))
        return 0

    creds = _get_creds(client_secrets_path=args.client_secrets, token_path=args.token)
    docs_svc = build("docs", "v1", credentials=creds)
    drive_svc = build("drive", "v3", credentials=creds)

    created_count = 0
    updated_count = 0

    for item in items:
        doc_id = file_to_doc.get(item.rel_key)
        if not doc_id:
            doc_id = _create_doc_in_drive(
                drive_svc=drive_svc, title=item.title, folder_id=args.folder_id
            )
            file_to_doc[item.rel_key] = doc_id
            created_count += 1

        text = item.src_path.read_text(encoding="utf-8")
        _replace_doc_text(docs_svc=docs_svc, doc_id=doc_id, text=text)
        updated_count += 1
        print(f"SYNCED: {item.rel_key} -> {item.title} ({doc_id})")

    out = {
        "src": str(src_dir),
        "title_prefix": args.title_prefix,
        "folder_id": args.folder_id,
        "files": file_to_doc,
    }
    _save_json(args.map, out)

    print(f"Done. Created: {created_count}, Updated: {updated_count}, Map: {args.map}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
