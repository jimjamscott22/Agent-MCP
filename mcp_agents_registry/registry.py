from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from .cache import RegistryCache
from .config import AppConfig, load_config
from .models import CacheEntry, ParsedAgentContent, ProjectRecord, RefreshSummary
from .parser import parse_agent_markdown
from .resolver import ContextResolver
from .scanner import scan_agent_files
from .utils import compact_text, read_text_file


class AgentsRegistry:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.cache = RegistryCache(config.cache_path if config.cache_enabled else None)
        self.resolver = ContextResolver(config)
        self.projects: list[ProjectRecord] = []
        self.projects_by_name: dict[str, ProjectRecord] = {}

    @classmethod
    def from_config_path(cls, config_path: str | Path) -> "AgentsRegistry":
        return cls(load_config(config_path))

    def refresh_index(self) -> RefreshSummary:
        cached_entries = self.cache.load() if self.config.cache_enabled else {}
        previous_signatures = _build_previous_signatures(self.projects, cached_entries)
        discovered = scan_agent_files(self.config)

        records_without_names: list[ProjectRecord] = []
        current_cache: dict[str, CacheEntry] = {}
        added = 0
        changed = 0

        for discovered_file in discovered:
            cached = cached_entries.get(discovered_file.agent_file_path)
            use_cached = bool(
                cached
                and cached.sha256 == discovered_file.sha256
                and cached.file_size == discovered_file.file_size
                and cached.mtime == discovered_file.mtime
            )
            if use_cached:
                raw_markdown = cached.raw_markdown
                parsed_content = cached.parsed_content
            else:
                try:
                    raw_markdown = read_text_file(Path(discovered_file.agent_file_path))
                except OSError:
                    continue
                parsed_content = parse_agent_markdown(raw_markdown) if self.config.parse_sections else ParsedAgentContent(summary=compact_text(raw_markdown))

            previous_signature = previous_signatures.get(discovered_file.agent_file_path)
            if previous_signature is None:
                added += 1
            elif previous_signature != (discovered_file.sha256, discovered_file.file_size, discovered_file.mtime):
                changed += 1

            current_cache[discovered_file.agent_file_path] = CacheEntry(
                agent_file_path=discovered_file.agent_file_path,
                mtime=discovered_file.mtime,
                sha256=discovered_file.sha256,
                file_size=discovered_file.file_size,
                raw_markdown=raw_markdown,
                parsed_content=parsed_content,
            )
            records_without_names.append(
                ProjectRecord(
                    project_name="",
                    agent_file_path=discovered_file.agent_file_path,
                    project_root=discovered_file.project_root,
                    scan_root=discovered_file.scan_root,
                    relative_root_from_scan_base=discovered_file.relative_root_from_scan_base,
                    parent_project_name=None,
                    depth=discovered_file.depth,
                    raw_markdown=raw_markdown,
                    parsed_sections=parsed_content,
                    tags=parsed_content.tags,
                    summary=parsed_content.summary,
                    mtime=discovered_file.mtime,
                    sha256=discovered_file.sha256,
                    file_size=discovered_file.file_size,
                )
            )

        removed = len(set(previous_signatures) - {item.agent_file_path for item in discovered})
        named_records = _assign_project_names(records_without_names)
        _assign_relationships(named_records)
        named_records.sort(key=lambda record: (record.project_name.casefold(), record.project_root))

        self.projects = named_records
        self.projects_by_name = {project.project_name: project for project in named_records}
        if self.config.cache_enabled:
            self.cache.save(current_cache)
        return RefreshSummary(
            project_count=len(named_records),
            added=added,
            changed=changed,
            removed=removed,
        )

    def list_projects(self) -> list[dict[str, Any]]:
        return [project.to_dict() for project in self.projects]

    def get_project(self, project_name: str) -> dict[str, Any]:
        project = self.projects_by_name.get(project_name)
        if project is None:
            raise LookupError(f"Unknown project: {project_name}")
        return project.to_dict()

    def get_project_record(self, project_name: str) -> ProjectRecord:
        project = self.projects_by_name.get(project_name)
        if project is None:
            raise LookupError(f"Unknown project: {project_name}")
        return project

    def resolve_context(self, path: str | Path) -> dict[str, Any]:
        return self.resolver.resolve(path, self.projects).to_dict()

    def resolve_project_root(self, project_name: str) -> dict[str, Any]:
        project = self.get_project_record(project_name)
        return self.resolve_context(project.project_root)

    def search_projects(self, query: str) -> dict[str, Any]:
        terms = [term.casefold() for term in query.split() if term.strip()]
        if not terms:
            return {"query": query, "matches": []}

        scored: list[tuple[int, ProjectRecord]] = []
        for project in self.projects:
            score = _score_project(project, terms)
            if score > 0:
                scored.append((score, project))
        scored.sort(key=lambda item: (-item[0], item[1].project_name.casefold(), item[1].project_root))
        return {
            "query": query,
            "matches": [
                {
                    "score": score,
                    **project.to_dict(),
                }
                for score, project in scored
            ],
        }


def _build_previous_signatures(
    current_projects: list[ProjectRecord],
    cached_entries: dict[str, CacheEntry],
) -> dict[str, tuple[str, int, float]]:
    if current_projects:
        return {
            project.agent_file_path: (project.sha256, project.file_size, project.mtime)
            for project in current_projects
        }
    return {
        entry.agent_file_path: (entry.sha256, entry.file_size, entry.mtime)
        for entry in cached_entries.values()
    }


def _assign_project_names(records: list[ProjectRecord]) -> list[ProjectRecord]:
    display_candidates: dict[str, list[ProjectRecord]] = {}
    for record in records:
        display_candidates.setdefault(_base_project_name(record), []).append(record)

    named_records: list[ProjectRecord] = []
    for base_name, group in display_candidates.items():
        if len(group) == 1:
            named_records.append(replace(group[0], project_name=base_name))
            continue
        for record in group:
            suffix = record.relative_root_from_scan_base
            if suffix == ".":
                suffix = Path(record.scan_root).name
            named_records.append(replace(record, project_name=f"{base_name} [{suffix}]"))
    return named_records


def _base_project_name(record: ProjectRecord) -> str:
    project_root = Path(record.project_root)
    return project_root.name or Path(record.scan_root).name


def _assign_relationships(records: list[ProjectRecord]) -> None:
    by_root = {Path(record.project_root): record for record in records}
    for record in records:
        record.child_project_names.clear()

    for record in records:
        project_root = Path(record.project_root)
        parent_record: ProjectRecord | None = None
        for parent_root, candidate in by_root.items():
            if parent_root == project_root:
                continue
            try:
                project_root.relative_to(parent_root)
            except ValueError:
                continue
            if parent_record is None or len(parent_root.parts) > len(Path(parent_record.project_root).parts):
                parent_record = candidate
        record.parent_project_name = parent_record.project_name if parent_record else None

    by_name = {record.project_name: record for record in records}
    for record in records:
        if record.parent_project_name:
            by_name[record.parent_project_name].child_project_names.append(record.project_name)
    for record in records:
        record.child_project_names.sort(key=str.casefold)


def _score_project(project: ProjectRecord, terms: list[str]) -> int:
    fields = [
        (project.project_name.casefold(), 12),
        (project.project_root.casefold(), 8),
        (project.agent_file_path.casefold(), 8),
        (" ".join(tag.casefold() for tag in project.tags), 6),
        (project.summary.casefold(), 5),
        (project.raw_markdown.casefold(), 2),
    ]
    score = 0
    for term in terms:
        term_score = sum(weight for value, weight in fields if term in value)
        if term_score == 0:
            return 0
        score += term_score
    return score
