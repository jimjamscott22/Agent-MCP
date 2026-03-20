from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mcp_agents_registry.config import AppConfig
from mcp_agents_registry.scanner import scan_agent_files


class ScannerTests(unittest.TestCase):
    def test_scanner_finds_agents_and_skips_ignored_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "AGENTS.md").write_text("workspace instructions", encoding="utf-8")
            (root / "app").mkdir()
            (root / "app" / "agents.md").write_text("subproject instructions", encoding="utf-8")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "AGENTS.md").write_text("ignore me", encoding="utf-8")

            config = AppConfig(
                roots=(root,),
                cache_enabled=False,
                cache_path=root / ".cache" / "test-cache.json",
            )

            discovered = scan_agent_files(config)

            self.assertEqual(len(discovered), 2)
            self.assertEqual(
                {item.relative_root_from_scan_base for item in discovered},
                {".", "app"},
            )
            self.assertEqual(
                {Path(item.agent_file_path).name for item in discovered},
                {"AGENTS.md", "agents.md"},
            )


if __name__ == "__main__":
    unittest.main()
