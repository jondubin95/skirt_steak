"""Local MCP pointer. Standard library only."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from msjc_board_secretary.setup_local_mcp import write_local_mcp  # noqa: E402


class SetupLocalMcpTests(unittest.TestCase):
    def test_writes_docs_server_and_keeps_other_servers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs_mcp = root / "docs_mcp.py"
            docs_mcp.write_text("# server\n", encoding="utf-8")
            target = root / ".cursor" / "mcp.json"
            target.parent.mkdir()
            target.write_text(
                json.dumps({"mcpServers": {"other": {"command": "echo"}}}),
                encoding="utf-8",
            )
            write_local_mcp(repo_root=root, docs_mcp=docs_mcp, target=target)
            saved = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(saved["mcpServers"]["other"]["command"], "echo")
            self.assertEqual(
                saved["mcpServers"]["google-docs"],
                {"command": "python", "args": [str(docs_mcp.resolve())]},
            )


if __name__ == "__main__":
    unittest.main()
