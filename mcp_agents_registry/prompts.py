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


def memory_curation_directive() -> str:
    return (
        "SYSTEM DIRECTIVE: When you resolve a complex bug or establish a new rule, "
        "DO NOT assume it should be saved. Ask the user: "
        "'Should I add this to the project\\'s AGENTS.md?' "
        "If the user agrees, use the `propose_registry_update` tool. "
        "Do not use direct file write tools."
    )
