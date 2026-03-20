from __future__ import annotations

import os
from typing import Any

from .prompts import build_project_prompt, build_resolve_context_prompt
from .registry import AgentsRegistry
from .resources import (
    path_resource_payload,
    project_effective_resource_payload,
    project_raw_resource_payload,
    project_resource_payload,
    projects_resource_payload,
)


def create_server(config_path: str | None = None) -> Any:
    FastMCP = _load_fastmcp()
    resolved_config_path = config_path or os.environ.get("AGENTS_REGISTRY_CONFIG", "config.yaml")
    registry = AgentsRegistry.from_config_path(resolved_config_path)
    registry.refresh_index()

    app = FastMCP(name="Agents Registry")

    @app.tool()
    def list_projects() -> dict[str, object]:
        return {"projects": registry.list_projects()}

    @app.tool()
    def get_project(project_name: str) -> dict[str, object]:
        return registry.get_project(project_name)

    @app.tool()
    def resolve_context(path: str) -> dict[str, object]:
        return registry.resolve_context(path)

    @app.tool()
    def search_projects(query: str) -> dict[str, object]:
        return registry.search_projects(query)

    @app.tool()
    def refresh_index() -> dict[str, int]:
        return registry.refresh_index().to_dict()

    @app.resource("agents://projects")
    def projects_resource() -> str:
        return projects_resource_payload(registry)

    @app.resource("agents://project/{project_name}")
    def project_resource(project_name: str) -> str:
        return project_resource_payload(registry, project_name)

    @app.resource("agents://project/{project_name}/raw")
    def project_raw_resource(project_name: str) -> str:
        return project_raw_resource_payload(registry, project_name)

    @app.resource("agents://project/{project_name}/effective")
    def project_effective_resource(project_name: str) -> str:
        return project_effective_resource_payload(registry, project_name)

    @app.resource("agents://path/{encoded_path}")
    def path_resource(encoded_path: str) -> str:
        return path_resource_payload(registry, encoded_path)

    if hasattr(app, "prompt"):
        @app.prompt()
        def explain_path_context(path: str) -> str:
            return build_resolve_context_prompt(path)

        @app.prompt()
        def summarize_project(project_name: str) -> str:
            return build_project_prompt(project_name)

    return app


def _load_fastmcp() -> type[Any]:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "The MCP Python SDK is not installed. Install project dependencies before running the server."
        ) from exc
    return FastMCP


def main() -> None:
    app = create_server()
    app.run()


if __name__ == "__main__":
    main()
