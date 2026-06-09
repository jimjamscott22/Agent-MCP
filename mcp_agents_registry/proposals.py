from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROPOSALS_VERSION = 1


@dataclass(slots=True)
class MemoryProposal:
    id: str
    target_project: str
    target_path: str
    section_heading: str
    proposed_content: str
    rationale: str
    status: str
    created_at: str
    resolved_at: str | None = None
    agent_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "target_project": self.target_project,
            "target_path": self.target_path,
            "section_heading": self.section_heading,
            "proposed_content": self.proposed_content,
            "rationale": self.rationale,
            "status": self.status,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "agent_id": self.agent_id,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MemoryProposal":
        return cls(
            id=str(payload["id"]),
            target_project=str(payload["target_project"]),
            target_path=str(payload["target_path"]),
            section_heading=str(payload["section_heading"]),
            proposed_content=str(payload["proposed_content"]),
            rationale=str(payload["rationale"]),
            status=str(payload.get("status", "pending")),
            created_at=str(payload["created_at"]),
            resolved_at=payload.get("resolved_at"),
            agent_id=str(payload.get("agent_id", "")),
        )


class ProposalStore:
    def __init__(self, proposals_path: Path | None) -> None:
        self.proposals_path = proposals_path

    def load(self) -> list[MemoryProposal]:
        if self.proposals_path is None or not self.proposals_path.exists():
            return []
        payload = json.loads(self.proposals_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Proposals file must contain a top-level mapping.")
        version = int(payload.get("version", 0))
        if version != PROPOSALS_VERSION:
            raise ValueError(f"Unsupported proposals version: {version}")
        return [MemoryProposal.from_dict(item) for item in payload.get("proposals", [])]

    def save(self, proposals: list[MemoryProposal]) -> None:
        if self.proposals_path is None:
            return
        self.proposals_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": PROPOSALS_VERSION,
            "proposals": [p.to_dict() for p in proposals],
        }
        _atomic_write_json(self.proposals_path, payload)

    def add(
        self,
        *,
        target_project: str,
        target_path: str,
        section_heading: str,
        proposed_content: str,
        rationale: str,
        agent_id: str = "",
    ) -> MemoryProposal:
        proposals = self.load()
        proposal = MemoryProposal(
            id=str(uuid.uuid4()),
            target_project=target_project,
            target_path=target_path,
            section_heading=section_heading,
            proposed_content=proposed_content,
            rationale=rationale,
            status="pending",
            created_at=datetime.now(timezone.utc).isoformat(),
            resolved_at=None,
            agent_id=agent_id,
        )
        proposals.append(proposal)
        self.save(proposals)
        return proposal

    def list(self, *, status: str | None = None) -> list[MemoryProposal]:
        proposals = self.load()
        if status is not None:
            proposals = [p for p in proposals if p.status == status]
        return proposals

    def get(self, proposal_id: str) -> MemoryProposal | None:
        for proposal in self.load():
            if proposal.id == proposal_id:
                return proposal
        return None

    def update(self, proposal_id: str, **fields: Any) -> MemoryProposal:
        proposals = self.load()
        for proposal in proposals:
            if proposal.id == proposal_id:
                for key, value in fields.items():
                    setattr(proposal, key, value)
                self.save(proposals)
                return proposal
        raise LookupError(f"Proposal not found: {proposal_id}")

    def set_status(self, proposal_id: str, status: str) -> MemoryProposal:
        resolved_at = (
            datetime.now(timezone.utc).isoformat()
            if status in ("approved", "rejected")
            else None
        )
        return self.update(proposal_id, status=status, resolved_at=resolved_at)


def _atomic_write_json(path: Path, payload: object) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    temp_path.replace(path)
