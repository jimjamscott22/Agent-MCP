from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any, Iterable

from .config import AppConfig
from .models import EffectiveContext, ProjectRecord, ResolutionStep
from .utils import ensure_within_roots, normalize_path


class ContextResolver:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def resolve(self, target_path: str | Path, projects: Iterable[ProjectRecord]) -> EffectiveContext:
        normalized_target = normalize_path(target_path, follow_symlinks=self.config.follow_symlinks)
        if not ensure_within_roots(normalized_target, self.config.roots):
            raise ValueError(f"Path is outside configured roots: {normalized_target}")

        matched_projects = [
            project
            for project in projects
            if _is_ancestor(Path(project.project_root), normalized_target)
        ]
        matched_projects.sort(key=lambda project: (project.depth, project.project_root))
        if not matched_projects:
            raise LookupError(f"No AGENTS.md context found for path: {normalized_target}")

        resolution_trace: list[ResolutionStep] = []
        for project in matched_projects:
            resolution_trace.append(
                ResolutionStep(
                    project_name=project.project_name,
                    agent_file_path=project.agent_file_path,
                    project_root=project.project_root,
                    action="matched",
                    detail=f"Path falls under project root {project.project_root}",
                )
            )

        merged_sections = _merge_sections(matched_projects)
        raw_combined_markdown = _combine_raw_markdown(matched_projects)
        resolution_trace.append(
            ResolutionStep(
                project_name=matched_projects[-1].project_name,
                agent_file_path=matched_projects[-1].agent_file_path,
                project_root=matched_projects[-1].project_root,
                action="merged",
                detail="Merged matched AGENTS.md files from broadest to narrowest with nearest precedence.",
            )
        )
        return EffectiveContext(
            target_path=str(normalized_target),
            matched_projects=matched_projects,
            merged_sections=merged_sections,
            raw_combined_markdown=raw_combined_markdown,
            resolution_trace=resolution_trace,
        )


def _is_ancestor(root: Path, target: Path) -> bool:
    try:
        target.relative_to(root)
        return True
    except ValueError:
        return False


def _merge_sections(projects: list[ProjectRecord]) -> dict[str, Any]:
    merged: dict[str, Any] = {
        "purpose": _nearest_scalar(projects, "purpose"),
        "overview": _nearest_scalar(projects, "overview"),
        "stack": _combine_sections(projects, "stack"),
        "commands": _combine_sections(projects, "commands"),
        "setup": _combine_sections(projects, "setup"),
        "constraints": _combine_sections(projects, "constraints"),
        "coding_rules": _merge_keyed_sections(projects, "coding_rules"),
        "testing": _combine_sections(projects, "testing"),
        "architecture": _combine_sections(projects, "architecture"),
        "definition_of_done": _merge_keyed_sections(projects, "definition_of_done"),
        "notes": _combine_sections(projects, "notes"),
    }
    merged["effective_summary"] = next(
        (project.summary for project in reversed(projects) if project.summary),
        projects[-1].summary,
    )
    merged["effective_tags"] = _combine_tags(projects)
    return {key: value for key, value in merged.items() if value not in ("", [], None)}


def _nearest_scalar(projects: list[ProjectRecord], section_name: str) -> str:
    for project in reversed(projects):
        value = project.parsed_sections.sections.get(section_name, "").strip()
        if value:
            return value
    return ""


def _combine_sections(projects: list[ProjectRecord], section_name: str) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for project in projects:
        value = project.parsed_sections.sections.get(section_name, "")
        for item in _split_section_items(value):
            key = item.casefold()
            if key in seen:
                continue
            seen.add(key)
            items.append(item)
    return items


def _merge_keyed_sections(projects: list[ProjectRecord], section_name: str) -> list[str]:
    merged: OrderedDict[str, str] = OrderedDict()
    for project in projects:
        value = project.parsed_sections.sections.get(section_name, "")
        for item in _split_section_items(value):
            key = _item_key(item)
            if key in merged:
                del merged[key]
            merged[key] = item
    return list(merged.values())


def _split_section_items(value: str) -> list[str]:
    if not value.strip():
        return []
    items: list[str] = []
    buffer: list[str] = []
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line:
            if buffer:
                items.append(" ".join(buffer).strip())
                buffer = []
            continue
        cleaned = line.lstrip("-* ").strip()
        if raw_line.lstrip().startswith(("- ", "* ")):
            if buffer:
                items.append(" ".join(buffer).strip())
                buffer = []
            items.append(cleaned)
            continue
        buffer.append(cleaned)
    if buffer:
        items.append(" ".join(buffer).strip())
    return items


def _item_key(item: str) -> str:
    if ":" in item:
        return item.split(":", 1)[0].strip().casefold()
    return item.casefold()


def _combine_tags(projects: list[ProjectRecord]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for project in projects:
        for tag in project.tags:
            key = tag.casefold()
            if key in seen:
                continue
            seen.add(key)
            merged.append(tag)
    return merged


def _combine_raw_markdown(projects: list[ProjectRecord]) -> str:
    blocks = []
    for project in projects:
        blocks.append(f"<!-- Source: {project.agent_file_path} -->\n{project.raw_markdown.strip()}")
    return "\n\n---\n\n".join(blocks)
