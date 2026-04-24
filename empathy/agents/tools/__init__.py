"""Tool registry for Empathy agents.

This module provides a unified interface for all tools available to agents,
including system tools (speak, listen, record, emotion_state, memory_manage),
skills, and MCP tools.
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
    "create_listen_tool",
    "create_record_tool",
    "create_emotion_state_tool",
    "create_memory_manage_tool",
    "create_all_tools",
]


def create_speak_tool() -> BaseTool:
    """Create the speak tool (terminal tool for submitting dialogue turns)."""
    from empathy.agents.tools.speak import create_speak_tool as _create

    return _create()


def create_listen_tool(transcript_path: Path) -> BaseTool:
    """Create the listen tool (read conversation history)."""
    from empathy.agents.tools.listen import create_listen_tool as _create

    return _create(transcript_path)


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


def create_memory_manage_tool(side: Speaker, dialogue_dir: Path) -> BaseTool:
    """Create the memory_manage tool (long-term memory management)."""
    from empathy.agents.tools.memory_manage import create_memory_manage_tool as _create

    return _create(side, dialogue_dir)


def create_all_tools(
    side: Speaker,
    dialogue_dir: Path,
    transcript_path: Path,
    mcp_provider: McpProvider | None = None,
) -> list[BaseTool]:
    """Create all available tools for the given side.

    Args:
        side: Speaker side ("therapist" or "client")
        dialogue_dir: Path to dialogue directory
        transcript_path: Path to transcript.jsonl
        mcp_provider: Optional MCP provider for external tools

    Returns:
        List of LangChain tools
    """
    tools: list[BaseTool] = []

    # System tools
    tools.append(create_speak_tool())
    tools.append(create_listen_tool(transcript_path))

    # Side-specific tools
    record_tool = create_record_tool(side, dialogue_dir)
    if record_tool:
        tools.append(record_tool)

    emotion_tool = create_emotion_state_tool(side, dialogue_dir)
    if emotion_tool:
        tools.append(emotion_tool)

    # Memory tool (both sides)
    tools.append(create_memory_manage_tool(side, dialogue_dir))

    # MCP tools (if available)
    if mcp_provider and not mcp_provider.is_empty:
        from empathy.agents.tools.mcp_wrapper import create_mcp_tools

        mcp_tools = create_mcp_tools(mcp_provider)
        tools.extend(mcp_tools)

    return tools
