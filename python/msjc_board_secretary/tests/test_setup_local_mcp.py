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
    def _server(self, root: Path) -> Path:
        docs_mcp = root / "docs_mcp.py"
        docs_mcp.write_text("# server\n", encoding="utf-8")
        return docs_mcp

    def test_writes_docs_server_and_keeps_other_servers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs_mcp = self._server(root)
            target = root / ".cursor" / "mcp.json"
            target.parent.mkdir()
            original = json.dumps({"mcpServers": {"other": {"command": "echo"}}})
            target.write_text(original, encoding="utf-8")
            write_local_mcp(docs_mcp=docs_mcp, target=target, overwrite=True)
            saved = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(saved["mcpServers"]["other"]["command"], "echo")
            self.assertEqual(
                saved["mcpServers"]["google-docs"],
                {"command": sys.executable, "args": [str(docs_mcp.resolve())]},
            )
            backup = target.with_name("mcp.json.bak")
            self.assertEqual(backup.read_text(encoding="utf-8"), original)
            write_local_mcp(docs_mcp=docs_mcp, target=target, overwrite=True)
            self.assertEqual(backup.read_text(encoding="utf-8"), original)
            stamped = list(target.parent.glob("mcp.json.bak-*"))
            self.assertEqual(len(stamped), 1)

    def test_refuses_to_overwrite_without_replace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs_mcp = self._server(root)
            target = root / ".cursor" / "mcp.json"
            target.parent.mkdir()
            original = '{"mcpServers": {"other": {"command": "echo"}}}\n'
            target.write_text(original, encoding="utf-8")
            with self.assertRaises(SystemExit) as caught:
                write_local_mcp(docs_mcp=docs_mcp, target=target)
            self.assertIn("--replace", str(caught.exception))
            self.assertIn("Refusing to overwrite", str(caught.exception))
            self.assertEqual(target.read_text(encoding="utf-8"), original)
            self.assertFalse(target.with_name("mcp.json.bak").exists())

    def test_new_file_does_not_need_replace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs_mcp = self._server(root)
            target = root / ".cursor" / "mcp.json"
            write_local_mcp(docs_mcp=docs_mcp, target=target)
            saved = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(saved["mcpServers"]["google-docs"]["command"], sys.executable)


if __name__ == "__main__":
    unittest.main()
