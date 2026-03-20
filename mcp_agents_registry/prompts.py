from __future__ import annotations


def build_resolve_context_prompt(path: str) -> str:
    return (
        "Use the MCP agents registry to resolve the effective AGENTS.md context for this path: "
        f"{path}. Explain which parent and child instruction files applied and summarize the final merged rules."
    )


def build_project_prompt(project_name: str) -> str:
    return (
        "Use the MCP agents registry to inspect project instructions for "
        f"{project_name}. Summarize the project purpose, key commands, constraints, and testing guidance."
    )
