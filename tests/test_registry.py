from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mcp_agents_registry.config import AppConfig
from mcp_agents_registry.registry import AgentsRegistry


class RegistryTests(unittest.TestCase):
    def test_registry_resolves_inherited_context_with_nearest_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_agents(
                root / "AGENTS.md",
                """
# Purpose
Workspace defaults.

## Commands
- make lint
- make test

## Constraints
- Stay inside the repository.

## Definition of Done
- docs: update README when behavior changes
""",
            )
            self._write_agents(
                root / "LastSeen" / "AGENTS.md",
                """
# Purpose
LastSeen backend and frontend.

## Commands
- make test
- make api

## Coding Rules
- formatter: black
- imports: keep sorted

## Testing
- run service tests

## Definition of Done
- api: validate contract tests
""",
            )
            self._write_agents(
                root / "LastSeen" / "frontend" / "AGENTS.md",
                """
# Purpose
Frontend app.

## Commands
- npm test

## Coding Rules
- formatter: prettier

## Testing
- run frontend tests

## Definition of Done
- docs: update UI screenshots
""",
            )

            registry = AgentsRegistry(
                AppConfig(
                    roots=(root,),
                    cache_enabled=True,
                    cache_path=root / ".cache" / "registry-cache.json",
                )
            )

            refresh = registry.refresh_index()
            self.assertEqual(refresh.project_count, 3)

            resolved = registry.resolve_context(root / "LastSeen" / "frontend" / "src" / "App.tsx")

            self.assertEqual(
                [Path(path).parent.name for path in resolved["matched_agent_files"]],
                [root.name, "LastSeen", "frontend"],
            )
            self.assertEqual(resolved["merged_sections"]["purpose"], "Frontend app.")
            self.assertEqual(
                resolved["merged_sections"]["commands"],
                ["make lint", "make test", "make api", "npm test"],
            )
            self.assertEqual(
                resolved["merged_sections"]["coding_rules"],
                ["imports: keep sorted", "formatter: prettier"],
            )
            self.assertEqual(
                resolved["merged_sections"]["definition_of_done"],
                ["api: validate contract tests", "docs: update UI screenshots"],
            )

            search = registry.search_projects("frontend prettier")
            self.assertEqual(search["matches"][0]["project_name"], "frontend")

    def test_resolve_rejects_paths_outside_allowed_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_agents(root / "AGENTS.md", "# Purpose\nWorkspace")
            registry = AgentsRegistry(
                AppConfig(
                    roots=(root,),
                    cache_enabled=False,
                    cache_path=root / ".cache" / "registry-cache.json",
                )
            )
            registry.refresh_index()

            with self.assertRaises(ValueError):
                registry.resolve_context(root.parent / "outside.txt")

    @staticmethod
    def _write_agents(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.strip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
