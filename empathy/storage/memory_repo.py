"""Memory repository abstraction and factory.

Provides an abstract base class for memory storage backends,
an in-memory implementation for testing, and a factory function
that selects the backend based on environment configuration.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from empathy.storage.memory_models import Memory, MemoryType

logger = logging.getLogger(__name__)

_repo_instance: MemoryRepository | None = None


class MemoryRepository(ABC):
    """Abstract base class for long-term memory storage."""

    @abstractmethod
    def store(self, user_id: str, memory: Memory) -> str:
        """Store a memory. Returns the memory id."""

    @abstractmethod
    def retrieve(self, user_id: str, memory_id: str) -> Memory | None:
        """Retrieve a single memory by id."""

    @abstractmethod
    def search(
        self,
        user_id: str,
        query: str,
        memory_type: MemoryType | None = None,
        limit: int = 10,
    ) -> list[Memory]:
        """Search memories by content query."""

    @abstractmethod
    def list_by_type(self, user_id: str, memory_type: MemoryType) -> list[Memory]:
        """List all memories of a given type."""

    @abstractmethod
    def update(self, user_id: str, memory_id: str, content: str) -> bool:
        """Update memory content. Returns True if found and updated."""

    @abstractmethod
    def delete(self, user_id: str, memory_id: str) -> bool:
        """Delete a memory. Returns True if found and deleted."""

    @abstractmethod
    def list_all(self, user_id: str) -> list[Memory]:
        """List all memories for a user."""


class InMemoryMemoryRepository(MemoryRepository):
    """In-memory implementation for testing and local development."""

    def __init__(self) -> None:
        """Initialize empty memory store."""
        self._memories: dict[str, list[Memory]] = {}

    def _user_memories(self, user_id: str) -> list[Memory]:
        if user_id not in self._memories:
            self._memories[user_id] = []
        return self._memories[user_id]

    def store(self, user_id: str, memory: Memory) -> str:
        self._user_memories(user_id).append(memory)
        return memory.id

    def retrieve(self, user_id: str, memory_id: str) -> Memory | None:
        for mem in self._user_memories(user_id):
            if mem.id == memory_id:
                return mem
        return None

    def search(
        self,
        user_id: str,
        query: str,
        memory_type: MemoryType | None = None,
        limit: int = 10,
    ) -> list[Memory]:
        results = []
        for mem in self._user_memories(user_id):
            if memory_type is not None and mem.type != memory_type:
                continue
            if query.lower() in mem.content.lower():
                results.append(mem)
        return results[:limit]

    def list_by_type(self, user_id: str, memory_type: MemoryType) -> list[Memory]:
        return [
            mem for mem in self._user_memories(user_id) if mem.type == memory_type
        ]

    def update(self, user_id: str, memory_id: str, content: str) -> bool:
        for mem in self._user_memories(user_id):
            if mem.id == memory_id:
                mem.content = content
                mem.updated_at = datetime.now(UTC)
                return True
        return False

    def delete(self, user_id: str, memory_id: str) -> bool:
        user_mems = self._user_memories(user_id)
        for i, mem in enumerate(user_mems):
            if mem.id == memory_id:
                user_mems.pop(i)
                return True
        return False

    def list_all(self, user_id: str) -> list[Memory]:
        return list(self._user_memories(user_id))


def get_memory_repository() -> MemoryRepository:
    """Get the singleton memory repository instance.

    If NEO4J_URI is set, uses Neo4jMemoryRepository.
    Otherwise falls back to InMemoryMemoryRepository.
    """
    global _repo_instance
    if _repo_instance is None:
        _repo_instance = _create_default_repository()
    return _repo_instance


def set_memory_repository(repo: MemoryRepository | None) -> None:
    """Set (or reset) the global memory repository instance.

    Used by tests to inject test doubles.
    """
    global _repo_instance
    _repo_instance = repo


def _create_default_repository() -> MemoryRepository:
    uri = os.environ.get("NEO4J_URI")
    if uri:
        try:
            from empathy.storage.neo4j_repo import Neo4jMemoryRepository

            user = os.environ.get("NEO4J_USER", "neo4j")
            password = os.environ.get("NEO4J_PASSWORD", "")
            return Neo4jMemoryRepository(uri, user, password)
        except Exception:
            logger.exception("Failed to connect to Neo4j, falling back to in-memory")
            return InMemoryMemoryRepository()
    return InMemoryMemoryRepository()
