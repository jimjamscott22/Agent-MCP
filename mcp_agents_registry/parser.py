from __future__ import annotations

import re

from .models import ParsedAgentContent
from .utils import compact_text, unique_preserving_order

HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*$")
INLINE_TAGS_RE = re.compile(r"(?im)^tags?\s*:\s*(.+)$")

CANONICAL_HEADINGS = {
    "purpose": "purpose",
    "overview": "overview",
    "stack": "stack",
    "commands": "commands",
    "setup": "setup",
    "constraints": "constraints",
    "coding rules": "coding_rules",
    "coding rule": "coding_rules",
    "rules": "coding_rules",
    "testing": "testing",
    "testing rules": "testing",
    "tests": "testing",
    "architecture": "architecture",
    "architecture notes": "architecture",
    "definition of done": "definition_of_done",
    "done": "definition_of_done",
    "notes": "notes",
    "tags": "tags",
}


def parse_agent_markdown(raw_markdown: str) -> ParsedAgentContent:
    sections: dict[str, str] = {}
    other_sections: dict[str, str] = {}
    intro_lines: list[str] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    def flush_section() -> None:
        nonlocal current_heading, current_lines
        if current_heading is None:
            return
        content = "\n".join(current_lines).strip()
        if not content:
            current_heading = None
            current_lines = []
            return
        canonical = _canonical_heading(current_heading)
        target = sections if canonical else other_sections
        key = canonical or current_heading.strip()
        if key in target:
            target[key] = f"{target[key]}\n\n{content}"
        else:
            target[key] = content
        current_heading = None
        current_lines = []

    for line in raw_markdown.splitlines():
        match = HEADING_RE.match(line)
        if match:
            flush_section()
            current_heading = match.group(2).strip()
            continue
        if current_heading is None:
            intro_lines.append(line)
        else:
            current_lines.append(line)
    flush_section()

    summary = _extract_summary(intro_lines, sections, raw_markdown)
    tags = _extract_tags(raw_markdown, sections)
    if tags:
        sections.pop("tags", None)
    return ParsedAgentContent(
        sections=sections,
        other_sections=other_sections,
        summary=summary,
        tags=tags,
    )


def _canonical_heading(value: str) -> str | None:
    normalized = " ".join(value.lower().replace("-", " ").replace("_", " ").split())
    return CANONICAL_HEADINGS.get(normalized)


def _extract_summary(intro_lines: list[str], sections: dict[str, str], raw_markdown: str) -> str:
    candidates = [
        "\n".join(intro_lines).strip(),
        sections.get("overview", ""),
        sections.get("purpose", ""),
        raw_markdown.strip(),
    ]
    for candidate in candidates:
        paragraphs = [part.strip() for part in candidate.split("\n\n") if part.strip()]
        if paragraphs:
            return compact_text(paragraphs[0])
    return ""


def _extract_tags(raw_markdown: str, sections: dict[str, str]) -> list[str]:
    tag_values: list[str] = []
    tag_values.extend(INLINE_TAGS_RE.findall(raw_markdown))
    if "tags" in sections:
        tag_values.append(sections["tags"])
    cleaned_tags: list[str] = []
    for value in tag_values:
        for token in re.split(r"[\n,]", value):
            stripped = token.strip().lstrip("-* ").strip()
            if stripped:
                cleaned_tags.append(stripped)
    return unique_preserving_order(cleaned_tags)
