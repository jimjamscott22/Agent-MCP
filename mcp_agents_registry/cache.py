from __future__ import annotations

import json
from pathlib import Path

from .models import CacheEntry


class RegistryCache:
    def __init__(self, cache_path: Path | None) -> None:
        self.cache_path = cache_path

    def load(self) -> dict[str, CacheEntry]:
        if self.cache_path is None or not self.cache_path.exists():
            return {}
        payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        entries = payload.get("entries", [])
        return {
            entry["agent_file_path"]: CacheEntry.from_dict(entry)
            for entry in entries
            if "agent_file_path" in entry
        }

    def save(self, entries: dict[str, CacheEntry]) -> None:
        if self.cache_path is None:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "entries": [entry.to_dict() for entry in entries.values()],
        }
        self.cache_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
