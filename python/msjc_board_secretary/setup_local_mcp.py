#!/usr/bin/env python3
"""Write a local .cursor/mcp.json that points google-docs at docs_mcp.py.

The file is gitignored. Run this once on each machine. Cursor may still
show that server disabled until it is enabled in the IDE.

An existing mcp.json is left in place unless --replace is passed. With
--replace, the current file is copied to a sibling backup before it is
rewritten.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_MCP = REPO_ROOT / "python" / "msjc_board_secretary" / "docs_mcp.py"
TARGET = REPO_ROOT / ".cursor" / "mcp.json"


def config_with_google_docs(existing: dict[str, Any], docs_mcp: Path) -> dict[str, Any]:
    servers = existing.get("mcpServers")
    if servers is None:
        servers = {}
    if not isinstance(servers, dict):
        raise SystemExit("mcp.json mcpServers is not an object")
    servers["google-docs"] = {"command": sys.executable, "args": [str(docs_mcp.resolve())]}
    existing["mcpServers"] = servers
    return existing


def backup_path(target: Path) -> Path:
    """A sibling backup that does not overwrite an existing backup."""
    backup = target.with_name(target.name + ".bak")
    if not backup.exists():
        return backup
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stamped = target.with_name(f"{target.name}.bak-{stamp}")
    if stamped.exists():
        raise SystemExit(f"Refusing to overwrite backup {stamped}")
    return stamped


def write_local_mcp(
    docs_mcp: Path = DOCS_MCP,
    target: Path = TARGET,
    *,
    overwrite: bool = False,
) -> Path:
    if not docs_mcp.is_file():
        raise SystemExit(f"Missing docs server: {docs_mcp}")
    existing: dict[str, Any] = {}
    if target.is_file():
        if not overwrite:
            raise SystemExit(
                f"{target} already exists. Refusing to overwrite it. "
                "Pass --replace to overwrite; the current file is backed up first."
            )
        try:
            loaded = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid mcp.json: {exc}") from exc
        if not isinstance(loaded, dict):
            raise SystemExit(f"{target} is not a JSON object")
        existing = loaded
        backup = backup_path(target)
        backup.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Backed up {target} to {backup}")
    config = config_with_google_docs(existing, docs_mcp)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Point local Cursor at the read-only Docs server.")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Overwrite an existing mcp.json after backing it up.",
    )
    args = parser.parse_args(argv)
    path = write_local_mcp(overwrite=args.replace)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
