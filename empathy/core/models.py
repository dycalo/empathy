"""Core data models for empathy."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal


class TurnSource(StrEnum):
    HUMAN = "human"
    AGENT_AUTO = "agent_auto"
    AGENT_ACCEPT = "agent_accept"
    AGENT_EDIT = "agent_edit"
    AGENT_REJECT = "agent_reject"


Speaker = Literal["therapist", "client"]
DraftOutcome = Literal["pending", "accepted", "edited", "rejected"]
DialogueStatus = Literal["waiting", "active", "ended"]


@dataclass
class Turn:
    id: str
    speaker: Speaker
    source: TurnSource
    content: str
    timestamp: datetime
    draft_id: str | None = None
    original_draft: str | None = None
    annotations: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        speaker: Speaker,
        source: TurnSource,
        content: str,
        draft_id: str | None = None,
        original_draft: str | None = None,
        annotations: dict[str, Any] | None = None,
    ) -> Turn:
        return cls(
            id=str(uuid.uuid4()),
            speaker=speaker,
            source=source,
            content=content,
            timestamp=datetime.now(UTC),
            draft_id=draft_id,
            original_draft=original_draft,
            annotations=annotations or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "speaker": self.speaker,
            "source": self.source.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "draft_id": self.draft_id,
            "original_draft": self.original_draft,
            "annotations": self.annotations,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Turn:
        return cls(
            id=data["id"],
            speaker=data["speaker"],
            source=TurnSource(data["source"]),
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            draft_id=data.get("draft_id"),
            original_draft=data.get("original_draft"),
            annotations=data.get("annotations", {}),
        )


@dataclass
class Draft:
    id: str
    speaker: Speaker
    content: str
    source_instruction: str
    outcome: DraftOutcome
    timestamp: datetime
    final_content: str | None = None
    hook_annotations: dict[str, Any] = field(default_factory=dict)
    # Extended fields for feedback learning and training data export
    conversation_window: dict[str, int] | None = None  # {"start_turn": 0, "end_turn": 5}
    api_usage: dict[str, int] | None = None  # {"input_tokens": 1500, "output_tokens": 150, "cached_tokens": 800, "latency_ms": 2500}
    rejection_reason: str | None = None  # Optional user-provided reason for rejection
    model: str | None = None  # Model used for generation

    @classmethod
    def create(
        cls,
        speaker: Speaker,
        content: str,
        source_instruction: str,
        hook_annotations: dict[str, Any] | None = None,
        conversation_window: dict[str, int] | None = None,
        api_usage: dict[str, int] | None = None,
        model: str | None = None,
    ) -> Draft:
        return cls(
            id=str(uuid.uuid4()),
            speaker=speaker,
            content=content,
            source_instruction=source_instruction,
            outcome="pending",
            timestamp=datetime.now(UTC),
            hook_annotations=hook_annotations or {},
            conversation_window=conversation_window,
            api_usage=api_usage,
            model=model,
        )

    def to_dict(self) -> dict[str, Any]:
        result = {
            "id": self.id,
            "speaker": self.speaker,
            "content": self.content,
            "source_instruction": self.source_instruction,
            "outcome": self.outcome,
            "timestamp": self.timestamp.isoformat(),
            "final_content": self.final_content,
            "hook_annotations": self.hook_annotations,
        }
        # Add extended fields only if present (backward compatibility)
        if self.conversation_window is not None:
            result["conversation_window"] = self.conversation_window
        if self.api_usage is not None:
            result["api_usage"] = self.api_usage
        if self.rejection_reason is not None:
            result["rejection_reason"] = self.rejection_reason
        if self.model is not None:
            result["model"] = self.model
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Draft:
        return cls(
            id=data["id"],
            speaker=data["speaker"],
            content=data["content"],
            source_instruction=data["source_instruction"],
            outcome=data["outcome"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            final_content=data.get("final_content"),
            hook_annotations=data.get("hook_annotations", {}),
            # Extended fields (backward compatible)
            conversation_window=data.get("conversation_window"),
            api_usage=data.get("api_usage"),
            rejection_reason=data.get("rejection_reason"),
            model=data.get("model"),
        )


@dataclass
class ClarificationMessage:
    """Returned by session.generate_draft() when the agent needs clarification.

    The agent chose not to call the speak tool and instead output a plain-text
    question. No draft was persisted — the controller should refine the
    instruction and regenerate.
    """

    content: str  # The agent's clarification question / meta-commentary


@dataclass
class DialogueMeta:
    """Registry entry for a dialogue."""

    id: str
    path: str  # relative to project dir
    status: DialogueStatus
    created_at: datetime
    sides_connected: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "sides_connected": self.sides_connected,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DialogueMeta:
        return cls(
            id=data["id"],
            path=data["path"],
            status=data["status"],
            created_at=datetime.fromisoformat(data["created_at"]),
            sides_connected=data.get("sides_connected", []),
        )
