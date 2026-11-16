#!/usr/bin/env python3
"""Write a local .cursor/mcp.json that points google-docs at docs_mcp.py.

The file is gitignored. Run this once on each machine. Cursor may still
show that server disabled until it is enabled in the IDE.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_MCP = REPO_ROOT / "python" / "msjc_board_secretary" / "docs_mcp.py"
TARGET = REPO_ROOT / ".cursor" / "mcp.json"


def google_docs_server(docs_mcp: Path) -> dict[str, Any]:
    return {"command": "python", "args": [str(docs_mcp.resolve())]}


def config_with_google_docs(existing: dict[str, Any], docs_mcp: Path) -> dict[str, Any]:
    servers = existing.get("mcpServers")
    if servers is None:
        servers = {}
    if not isinstance(servers, dict):
        raise SystemExit("mcp.json mcpServers is not an object")
    servers["google-docs"] = google_docs_server(docs_mcp)
    existing["mcpServers"] = servers
    return existing


def write_local_mcp(
    repo_root: Path = REPO_ROOT,
    docs_mcp: Path = DOCS_MCP,
    target: Path = TARGET,
) -> Path:
    if not docs_mcp.is_file():
        raise SystemExit(f"Missing docs server: {docs_mcp}")
    existing: dict[str, Any] = {}
    if target.is_file():
        try:
            loaded = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid mcp.json: {exc}") from exc
        if not isinstance(loaded, dict):
            raise SystemExit(f"{target} is not a JSON object")
        existing = loaded
    config = config_with_google_docs(existing, docs_mcp)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return target


def main() -> None:
    path = write_local_mcp()
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
