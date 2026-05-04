"""Memory management tool - user-level long-term memory storage backed by Neo4j."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from empathy.storage.memory_models import Memory, MemoryType
from empathy.storage.memory_repo import MemoryRepository, get_memory_repository

MemoryAction = str


class MemoryManageInput(BaseModel):
    """Input schema for memory_manage tool."""

    action: MemoryAction = Field(description="Memory operation")
    memory_type: MemoryType = Field(
        description="Type of memory: key_event, pattern, relationship, insight"
    )
    content: str | None = Field(default=None, description="Memory content")
    memory_id: str | None = Field(default=None, description="Memory ID for retrieve/update/delete")
    query: str | None = Field(default=None, description="Search query")
    importance: int = Field(default=5, ge=1, le=10, description="Memory importance (1-10)")


def create_memory_manage_tool(user_id: str | None) -> StructuredTool | None:
    """Create the memory_manage tool.

    Args:
        user_id: User identifier (from dialogue.yaml client_id/therapist_id).
            If None, the tool is not available.

    Returns:
        LangChain StructuredTool, or None if user_id is missing.
    """
    if not user_id:
        return None

    def memory_manage_func(
        action: str,
        memory_type: MemoryType,
        content: str | None = None,
        memory_id: str | None = None,
        query: str | None = None,
        importance: int = 5,
    ) -> str:
        """Manage long-term memory storage.

        All memories are stored at the user level and persist across dialogues.
        """
        repo = get_memory_repository()

        try:
            if action == "store":
                return _handle_store(repo, user_id, memory_type, content, importance)
            elif action == "retrieve":
                return _handle_retrieve(repo, user_id, memory_id)
            elif action == "search":
                return _handle_search(repo, user_id, query, memory_type)
            elif action == "update":
                return _handle_update(repo, user_id, memory_id, content)
            elif action == "delete":
                return _handle_delete(repo, user_id, memory_id)
            else:
                return f"Unknown action: {action}"
        except Exception as e:
            return f"Memory service error: {e}"

    return StructuredTool.from_function(
        func=memory_manage_func,
        name="memory_manage",
        description=(
            "Manage your long-term memory storage. Memories persist across all your dialogues. "
            "Actions: store, retrieve, search, update, delete. "
            "Types: key_event, pattern, relationship, insight."
        ),
        args_schema=MemoryManageInput,
    )


def _handle_store(
    repo: MemoryRepository,
    user_id: str,
    memory_type: MemoryType,
    content: str | None,
    importance: int,
) -> str:
    if not content:
        return "Content is required for storing a memory."

    memory = Memory(
        id=str(uuid.uuid4()),
        type=memory_type,
        content=content,
        importance=importance,
        created_at=datetime.now(UTC),
    )
    repo.store(user_id, memory)
    return f"Memory stored: {memory.id}"


def _handle_retrieve(repo: MemoryRepository, user_id: str, memory_id: str | None) -> str:
    if not memory_id:
        return "Memory ID is required for retrieval."

    memory = repo.retrieve(user_id, memory_id)
    if memory is None:
        return f"Memory not found: {memory_id}"

    return _format_memory(memory)


def _handle_search(
    repo: MemoryRepository,
    user_id: str,
    query: str | None,
    memory_type: MemoryType | None,
) -> str:
    if not query:
        return "Query is required for search."

    results = repo.search(user_id, query, memory_type=memory_type, limit=20)
    if not results:
        return "No matching memories found."

    lines = []
    for mem in results:
        preview = mem.content[:80] + "..." if len(mem.content) > 80 else mem.content
        lines.append(f"[{mem.type}] {preview} (importance: {mem.importance})")

    return "\n".join(lines)


def _handle_update(
    repo: MemoryRepository,
    user_id: str,
    memory_id: str | None,
    content: str | None,
) -> str:
    if not memory_id:
        return "Memory ID is required for update."
    if not content:
        return "Content is required for update."

    if repo.update(user_id, memory_id, content):
        return f"Memory updated: {memory_id}"
    return f"Memory not found: {memory_id}"


def _handle_delete(repo: MemoryRepository, user_id: str, memory_id: str | None) -> str:
    if not memory_id:
        return "Memory ID is required for deletion."

    if repo.delete(user_id, memory_id):
        return f"Memory deleted: {memory_id}"
    return f"Memory not found: {memory_id}"


def _format_memory(memory: Memory) -> str:
    updated = f"\nUpdated: {memory.updated_at.isoformat()}" if memory.updated_at else ""
    return (
        f"ID: {memory.id}\n"
        f"Type: {memory.type}\n"
        f"Importance: {memory.importance}/10\n"
        f"Created: {memory.created_at.isoformat()}{updated}\n"
        f"Content: {memory.content}"
    )
