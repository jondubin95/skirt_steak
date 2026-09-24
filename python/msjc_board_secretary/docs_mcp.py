#!/usr/bin/env python3
"""Read-only local Google Docs MCP server (stdio).

Exposes read_doc only. Tab writes go through write_tab.py.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "python") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "python"))

from msjc_board_secretary.write_tab import (  # noqa: E402
    DEFAULT_CREDS,
    DEFAULT_TOKEN,
    build_docs_service,
    load_credentials,
)

PROTOCOL_VERSION = "2025-06-18"

TOOLS = [
    {
        "name": "read_doc",
        "title": "Reads a document.",
        "description": (
            "Return the Google Doc as documents.get JSON, including tabs. "
            "documentId is the Drive file id. This server does not write."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "documentId": {
                    "type": "string",
                    "description": "Required. Document id (Drive file id).",
                }
            },
            "required": ["documentId"],
            "additionalProperties": False,
        },
    }
]


def send(message: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def ok(msg_id: Any, result: dict[str, Any]) -> None:
    send({"jsonrpc": "2.0", "id": msg_id, "result": result})


def fail(msg_id: Any, code: int, message: str) -> None:
    send({"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}})


def tool_text(payload: Any, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(payload)}],
        "isError": is_error,
    }


def docs_service() -> Any:
    creds = load_credentials(DEFAULT_CREDS, DEFAULT_TOKEN)
    return build_docs_service(creds)


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name != "read_doc":
        return tool_text({"error": f"Unknown tool: {name}"}, True)
    document_id = arguments.get("documentId")
    if not document_id:
        return tool_text({"error": "documentId is required"}, True)
    doc = (
        docs_service()
        .documents()
        .get(documentId=document_id, includeTabsContent=True)
        .execute()
    )
    return tool_text(doc)


def handle(message: dict[str, Any]) -> None:
    method = message.get("method")
    msg_id = message.get("id")
    if method and msg_id is None:
        return
    params = message.get("params") or {}
    if method == "initialize":
        ok(
            msg_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "google-docs", "version": "1.0.0"},
            },
        )
        return
    if method == "tools/list":
        ok(msg_id, {"tools": TOOLS})
        return
    if method == "tools/call":
        try:
            ok(msg_id, call_tool(params.get("name", ""), params.get("arguments") or {}))
        except Exception as exc:  # noqa: BLE001 — surface API errors to the client
            ok(msg_id, tool_text({"error": str(exc)}, True))
        return
    if method == "ping":
        ok(msg_id, {})
        return
    fail(msg_id, -32601, f"Method not found: {method}")


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            fail(None, -32700, f"Parse error: {exc}")
            continue
        try:
            handle(message)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            if message.get("id") is not None:
                fail(message.get("id"), -32603, "Internal error")


if __name__ == "__main__":
    main()
