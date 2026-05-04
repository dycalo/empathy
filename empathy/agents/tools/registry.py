"""Tool registry for centralized tool management.

This module provides a registry system for managing all tools available to agents,
including system tools, skills, and MCP tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from langchain.tools import BaseTool

    from empathy.core.models import Speaker
    from empathy.extensions.mcp import McpProvider


@dataclass
class ToolMetadata:
    """Metadata for a registered tool."""

    name: str
    description: str
    side: Speaker | None  # None means available to both sides
    category: str  # "system", "skill", "mcp"
    enabled: bool = True


class ToolRegistry:
    """Centralized registry for managing agent tools.

    The registry maintains a collection of tools with metadata,
    supporting dynamic registration, filtering, and retrieval.
    """

    def __init__(self) -> None:
        """Initialize empty tool registry."""
        self._tools: dict[str, BaseTool] = {}
        self._metadata: dict[str, ToolMetadata] = {}

    def register(
        self,
        tool: BaseTool,
        *,
        side: Speaker | None = None,
        category: str = "system",
        enabled: bool = True,
    ) -> None:
        """Register a tool with metadata.

        Args:
            tool: LangChain tool to register
            side: Speaker side (None = both sides)
            category: Tool category ("system", "skill", "mcp")
            enabled: Whether tool is enabled
        """
        name = tool.name
        if name in self._tools:
            raise ValueError(f"Tool '{name}' is already registered")

        self._tools[name] = tool
        self._metadata[name] = ToolMetadata(
            name=name,
            description=tool.description or "",
            side=side,
            category=category,
            enabled=enabled,
        )

    def unregister(self, name: str) -> None:
        """Unregister a tool by name.

        Args:
            name: Tool name to unregister
        """
        self._tools.pop(name, None)
        self._metadata.pop(name, None)

    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)

    def get_metadata(self, name: str) -> ToolMetadata | None:
        """Get tool metadata by name.

        Args:
            name: Tool name

        Returns:
            Tool metadata or None if not found
        """
        return self._metadata.get(name)

    def list_tools(
        self,
        *,
        side: Speaker | None = None,
        category: str | None = None,
        enabled_only: bool = True,
    ) -> list[BaseTool]:
        """List tools matching filters.

        Args:
            side: Filter by speaker side (None = no filter)
            category: Filter by category (None = no filter)
            enabled_only: Only return enabled tools

        Returns:
            List of matching tools
        """
        tools = []
        for name, tool in self._tools.items():
            meta = self._metadata[name]

            # Apply filters
            if enabled_only and not meta.enabled:
                continue
            if category and meta.category != category:
                continue
            if side and meta.side and meta.side != side:
                continue

            tools.append(tool)

        return tools

    def list_metadata(
        self,
        *,
        side: Speaker | None = None,
        category: str | None = None,
        enabled_only: bool = True,
    ) -> list[ToolMetadata]:
        """List tool metadata matching filters.

        Args:
            side: Filter by speaker side (None = no filter)
            category: Filter by category (None = no filter)
            enabled_only: Only return enabled tools

        Returns:
            List of matching tool metadata
        """
        metadata = []
        for _name, meta in self._metadata.items():
            # Apply filters
            if enabled_only and not meta.enabled:
                continue
            if category and meta.category != category:
                continue
            if side and meta.side and meta.side != side:
                continue

            metadata.append(meta)

        return metadata

    def enable(self, name: str) -> None:
        """Enable a tool by name.

        Args:
            name: Tool name
        """
        if name in self._metadata:
            self._metadata[name].enabled = True

    def disable(self, name: str) -> None:
        """Disable a tool by name.

        Args:
            name: Tool name
        """
        if name in self._metadata:
            self._metadata[name].enabled = False

    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
        self._metadata.clear()

    def __len__(self) -> int:
        """Return number of registered tools."""
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        """Check if tool is registered."""
        return name in self._tools


def create_tool_registry(
    side: Speaker,
    user_id: str | None,
    dialogue_dir: Path,
    transcript_path: Path,
    mcp_provider: McpProvider | None = None,
) -> ToolRegistry:
    """Create and populate a tool registry for the given side.

    Args:
        side: Speaker side ("therapist" or "client")
        user_id: User identifier for user-level tools
        dialogue_dir: Path to dialogue directory
        transcript_path: Path to transcript.jsonl
        mcp_provider: Optional MCP provider for external tools

    Returns:
        Populated ToolRegistry instance
    """
    from empathy.agents.tools import (
        create_emotion_state_tool,
        create_memory_manage_tool,
        create_record_tool,
        create_speak_tool,
    )

    registry = ToolRegistry()

    # Register system tools (available to both sides)
    registry.register(create_speak_tool(), side=None, category="system")

    # Register side-specific tools
    record_tool = create_record_tool(side, dialogue_dir)
    if record_tool:
        registry.register(record_tool, side="therapist", category="system")

    emotion_tool = create_emotion_state_tool(side, dialogue_dir)
    if emotion_tool:
        registry.register(emotion_tool, side="client", category="system")

    # Register memory tool (both sides, user-level)
    memory_tool = create_memory_manage_tool(user_id)
    if memory_tool:
        registry.register(memory_tool, side=None, category="system")

    # Register MCP tools if available
    if mcp_provider and not mcp_provider.is_empty:
        from empathy.agents.tools.mcp_wrapper import create_mcp_tools

        mcp_tools = create_mcp_tools(mcp_provider)
        for tool in mcp_tools:
            registry.register(tool, side=None, category="mcp")

    return registry
