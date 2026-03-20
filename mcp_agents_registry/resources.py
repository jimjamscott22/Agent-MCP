from __future__ import annotations

from .registry import AgentsRegistry
from .utils import decode_resource_path, to_pretty_json


def projects_resource_payload(registry: AgentsRegistry) -> str:
    return to_pretty_json({"projects": registry.list_projects()})


def project_resource_payload(registry: AgentsRegistry, project_name: str) -> str:
    return to_pretty_json(registry.get_project(project_name))


def project_raw_resource_payload(registry: AgentsRegistry, project_name: str) -> str:
    return registry.get_project_record(project_name).raw_markdown


def project_effective_resource_payload(registry: AgentsRegistry, project_name: str) -> str:
    return to_pretty_json(registry.resolve_project_root(project_name))


def path_resource_payload(registry: AgentsRegistry, encoded_path: str) -> str:
    return to_pretty_json(registry.resolve_context(decode_resource_path(encoded_path)))
