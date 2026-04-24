"""Memory management tool - long-term memory storage."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from empathy.core.models import Speaker


class MemoryManageInput(BaseModel):
    """Input schema for memory_manage tool."""

    action: Literal["store", "retrieve", "search", "update", "delete"] = Field(
        description="Memory operation"
    )
    memory_type: Literal["key_event", "pattern", "relationship", "insight"] = Field(
        description="Type of memory"
    )
    content: str | None = Field(default=None, description="Memory content")
    memory_id: str | None = Field(default=None, description="Memory ID for retrieve/update/delete")
    query: str | None = Field(default=None, description="Search query")
    importance: int = Field(default=5, ge=1, le=10, description="Memory importance (1-10)")


def create_memory_manage_tool(side: Speaker, dialogue_dir: Path) -> StructuredTool:
    """Create the memory_manage tool.

    Args:
        side: Speaker side ("therapist" or "client")
        dialogue_dir: Path to dialogue directory

    Returns:
        LangChain StructuredTool
    """

    def memory_manage_func(
        action: str,
        memory_type: str,
        content: str | None = None,
        memory_id: str | None = None,
        query: str | None = None,
        importance: int = 5,
    ) -> str:
        """Manage long-term memory storage.

        Args:
            action: Memory operation (store/retrieve/search/update/delete)
            memory_type: Type of memory
            content: Memory content
            memory_id: Memory ID
            query: Search query
            importance: Importance 1-10

        Returns:
            Result message
        """
        memory_dir = dialogue_dir / ".empathy" / side / "memories"
        type_dir = memory_dir / f"{memory_type}s"
        type_dir.mkdir(parents=True, exist_ok=True)

        index_path = memory_dir / "index.json"

        if action == "store":
            if not content:
                return "Content is required for storing a memory."

            memory = {
                "id": str(uuid.uuid4()),
                "type": memory_type,
                "content": content,
                "importance": importance,
                "created_at": datetime.now(UTC).isoformat(),
                "related_turns": [],
                "tags": [],
                "evidence": [],
            }

            # Save memory
            path = type_dir / f"{memory['id']}.json"
            path.write_text(json.dumps(memory, indent=2, ensure_ascii=False))

            # Update index
            if index_path.exists():
                index = json.loads(index_path.read_text())
            else:
                index = {"memories": []}

            index["memories"].append(
                {
                    "id": memory["id"],
                    "type": memory_type,
                    "importance": importance,
                    "created_at": memory["created_at"],
                }
            )
            index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False))

            return f"Memory stored: {memory['id']}"

        elif action == "retrieve":
            if not memory_id:
                return "Memory ID is required for retrieval."

            path = type_dir / f"{memory_id}.json"
            if not path.exists():
                return f"Memory not found: {memory_id}"

            return path.read_text()

        elif action == "search":
            if not query:
                return "Query is required for search."

            results = []
            for path in type_dir.glob("*.json"):
                mem = json.loads(path.read_text())
                if query.lower() in mem["content"].lower():
                    preview = mem["content"][:80] + "..." if len(mem["content"]) > 80 else mem["content"]
                    results.append(
                        f"[{mem['type']}] {preview} (importance: {mem['importance']})"
                    )

            return "\n".join(results) if results else "No matching memories found."

        elif action == "update":
            if not memory_id:
                return "Memory ID is required for update."
            if not content:
                return "Content is required for update."

            path = type_dir / f"{memory_id}.json"
            if not path.exists():
                return f"Memory not found: {memory_id}"

            mem = json.loads(path.read_text())
            mem["content"] = content
            mem["updated_at"] = datetime.now(UTC).isoformat()

            path.write_text(json.dumps(mem, indent=2, ensure_ascii=False))

            return f"Memory updated: {memory_id}"

        elif action == "delete":
            if not memory_id:
                return "Memory ID is required for deletion."

            path = type_dir / f"{memory_id}.json"
            if path.exists():
                path.unlink()
                return f"Memory deleted: {memory_id}"

            return f"Memory not found: {memory_id}"

        else:
            return f"Unknown action: {action}"

    return StructuredTool.from_function(
        func=memory_manage_func,
        name="memory_manage",
        description="Manage long-term memory storage",
        args_schema=MemoryManageInput,
    )
