from __future__ import annotations

import unittest

from mcp_agents_registry.parser import parse_agent_markdown


class ParserTests(unittest.TestCase):
    def test_extracts_common_sections_summary_and_tags(self) -> None:
        raw_markdown = """
# Overview
Registry for layered repo instructions.

## Commands
- python -m unittest
- ruff check .

## Constraints
- Stay inside configured roots.

## Tags
- python
- mcp
""".strip()

        parsed = parse_agent_markdown(raw_markdown)

        self.assertEqual(parsed.sections["overview"], "Registry for layered repo instructions.")
        self.assertEqual(parsed.sections["commands"], "- python -m unittest\n- ruff check .")
        self.assertEqual(parsed.summary, "Registry for layered repo instructions.")
        self.assertEqual(parsed.tags, ["python", "mcp"])


if __name__ == "__main__":
    unittest.main()
