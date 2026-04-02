from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mcp_agents_registry.config import AppConfig
from mcp_agents_registry.registry import AgentsRegistry


class InventoryAndManagedFileTests(unittest.TestCase):
    def test_inventory_crud_installations_and_queries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "AGENTS.md").write_text("# Purpose\nworkspace\n", encoding="utf-8")

            registry = AgentsRegistry(
                AppConfig(
                    roots=(root,),
                    cache_enabled=False,
                    cache_path=root / ".cache" / "registry-cache.json",
                    inventory_path=root / ".cache" / "inventory.json",
                )
            )
            registry.refresh_index()

            account = registry.create_account("acct-main", "Main Account", provider="claude")
            self.assertEqual(account["account_id"], "acct-main")

            device = registry.create_device("dev-laptop", "Laptop", platform="macos")
            self.assertEqual(device["device_id"], "dev-laptop")

            installation = registry.assign_agent_installation(
                account_id="acct-main",
                device_id="dev-laptop",
                agent_name="Claude Code",
                skills=["python", "mcp", "python"],
                notes="primary setup",
            )
            self.assertEqual(installation["skills"], ["python", "mcp"])

            by_agent = registry.where_is_agent_installed("Claude Code")
            self.assertEqual(len(by_agent["installations"]), 1)

            skills = registry.skills_for_account_device("acct-main", "dev-laptop")
            self.assertEqual(skills["skills"], ["python", "mcp"])

            coverage = registry.inventory_coverage()
            self.assertEqual(coverage["totals"]["accounts"], 1)
            self.assertEqual(coverage["totals"]["devices"], 1)
            self.assertEqual(coverage["totals"]["installations"], 1)

    def test_managed_file_read_update_and_section_upsert(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            managed_file = root / "project" / "CLAUDE.md"
            managed_file.parent.mkdir(parents=True, exist_ok=True)
            managed_file.write_text("# Overview\nInitial\n", encoding="utf-8")

            registry = AgentsRegistry(
                AppConfig(
                    roots=(root,),
                    cache_enabled=False,
                    cache_path=root / ".cache" / "registry-cache.json",
                    inventory_path=root / ".cache" / "inventory.json",
                )
            )
            registry.refresh_index()

            read_result = registry.read_managed_file(managed_file)
            self.assertIn("Initial", read_result["content"])

            updated = registry.update_managed_file(
                path=managed_file,
                content="# Overview\nUpdated content\n",
                expected_sha256=read_result["sha256"],
            )
            self.assertIn("Updated content", updated["content"])

            with_section = registry.update_managed_file_section(
                path=managed_file,
                section_heading="Commands",
                section_content="- pytest -v",
                expected_sha256=updated["sha256"],
            )
            self.assertIn("## Commands", with_section["content"])
            self.assertIn("- pytest -v", with_section["content"])

            files = registry.list_managed_files()
            self.assertEqual(len(files), 1)
            self.assertEqual(Path(files[0]["path"]).name, "CLAUDE.md")

    def test_managed_file_rejects_out_of_root_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "root"
            root.mkdir(parents=True, exist_ok=True)
            outside = Path(temp_dir) / "outside" / "AGENTS.md"
            outside.parent.mkdir(parents=True, exist_ok=True)
            outside.write_text("# Overview\noutside\n", encoding="utf-8")
            (root / "AGENTS.md").write_text("# Purpose\nroot\n", encoding="utf-8")

            registry = AgentsRegistry(
                AppConfig(
                    roots=(root,),
                    cache_enabled=False,
                    cache_path=root / ".cache" / "registry-cache.json",
                    inventory_path=root / ".cache" / "inventory.json",
                )
            )
            registry.refresh_index()

            with self.assertRaises(ValueError):
                registry.read_managed_file(outside)


if __name__ == "__main__":
    unittest.main()
