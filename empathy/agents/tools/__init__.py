"""Tool registry for Empathy agents.

This module provides a unified interface for all tools available to agents,
including system tools (speak, record, emotion_state, memory_manage),
skills, and MCP tools.

The ToolRegistry class provides centralized tool management with support for:
- Dynamic tool registration/unregistration
- Tool filtering by side, category, and enabled status
- Tool metadata tracking
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from langchain.tools import BaseTool

    from empathy.core.models import Speaker
    from empathy.extensions.mcp import McpProvider

__all__ = [
    "create_speak_tool",
    "create_record_tool",
    "create_emotion_state_tool",
    "create_memory_manage_tool",
    "create_all_tools",
    "ToolRegistry",
    "ToolMetadata",
    "create_tool_registry",
]


# Re-export registry classes
def __getattr__(name: str) -> type:
    """Lazy import for registry classes."""
    if name in ("ToolRegistry", "ToolMetadata", "create_tool_registry"):
        from empathy.agents.tools.registry import (
            ToolMetadata,
            ToolRegistry,
            create_tool_registry,
        )

        if name == "ToolRegistry":
            return ToolRegistry
        elif name == "ToolMetadata":
            return ToolMetadata
        elif name == "create_tool_registry":
            return create_tool_registry

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def create_speak_tool() -> BaseTool:
    """Create the speak tool (terminal tool for submitting dialogue turns)."""
    from empathy.agents.tools.speak import create_speak_tool as _create

    return _create()


def create_record_tool(side: Speaker, dialogue_dir: Path) -> BaseTool | None:
    """Create the record tool (therapist only - clinical records)."""
    if side != "therapist":
        return None
    from empathy.agents.tools.record import create_record_tool as _create

    return _create(dialogue_dir)


def create_emotion_state_tool(side: Speaker, dialogue_dir: Path) -> BaseTool | None:
    """Create the emotion_state tool (client only - emotion tracking)."""
    if side != "client":
        return None
    from empathy.agents.tools.emotion_state import create_emotion_state_tool as _create

    return _create(dialogue_dir)


def create_memory_manage_tool(user_id: str | None) -> BaseTool | None:
    """Create the memory_manage tool (user-level long-term memory)."""
    from empathy.agents.tools.memory_manage import create_memory_manage_tool as _create

    return _create(user_id)


def create_all_tools(
    side: Speaker,
    user_id: str | None,
    dialogue_dir: Path,
    transcript_path: Path,
    mcp_provider: McpProvider | None = None,
) -> list[BaseTool]:
    """Create all available tools for the given side.

    Args:
        side: Speaker side ("therapist" or "client")
        user_id: User identifier for user-level tools (e.g. memory)
        dialogue_dir: Path to dialogue directory
        transcript_path: Path to transcript.jsonl
        mcp_provider: Optional MCP provider for external tools

    Returns:
        List of LangChain tools
    """
    from empathy.agents.tools.registry import create_tool_registry

    # Use the registry to create and manage tools
    registry = create_tool_registry(side, user_id, dialogue_dir, transcript_path, mcp_provider)

    # Return all enabled tools for this side
    return registry.list_tools(side=side, enabled_only=True)
