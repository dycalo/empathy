"""Data models for long-term memory storage."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

MemoryType = Literal["key_event", "pattern", "relationship", "insight"]


@dataclass
class Memory:
    """A single long-term memory entry."""

    id: str
    type: MemoryType
    content: str
    importance: int
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None
