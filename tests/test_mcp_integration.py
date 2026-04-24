"""Tests for MCP integration."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from empathy.extensions.mcp import McpProvider, McpServerConfig


class TestMcpProviderIntegration:
    """Tests for MCP provider with real MCP client."""

    @pytest.fixture
    def mock_mcp_tool(self):
        """Create a mock MCP tool."""
        tool = MagicMock()
        tool.name = "get_current_time"
        tool.description = "Get the current time"
        tool.inputSchema = {
            "type": "object",
            "properties": {
                "timezone": {"type": "string", "description": "Timezone name"}
            },
        }
        return tool

    @pytest.fixture
    def mock_session(self, mock_mcp_tool):
        """Create a mock MCP session."""
        session = AsyncMock()
        session.initialize = AsyncMock()

        # Mock list_tools
        tools_result = MagicMock()
        tools_result.tools = [mock_mcp_tool]
        session.list_tools = AsyncMock(return_value=tools_result)

        # Mock call_tool
        call_result = MagicMock()
        call_result.content = "2026-04-24T10:30:00Z"
        session.call_tool = AsyncMock(return_value=call_result)

        return session

    @pytest.mark.asyncio
    async def test_initialize_server(self, mock_session, mock_mcp_tool):
        """Test initializing a single MCP server."""
        provider = McpProvider(
            servers={
                "time": McpServerConfig(
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-time"],
                )
            }
        )

        with patch("mcp.client.stdio.stdio_client") as mock_stdio:
            with patch("mcp.ClientSession") as mock_client_session:
                # Mock stdio_client context manager
                mock_stdio.return_value.__aenter__ = AsyncMock(
                    return_value=(MagicMock(), MagicMock())
                )

                # Mock ClientSession
                mock_client_session.return_value = mock_session
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)

                tools = await provider._initialize_server("time", provider.servers["time"])

                assert len(tools) == 1
                assert tools[0].name == "get_current_time"
                assert "time" in provider._sessions

    @pytest.mark.asyncio
    async def test_load_all_tools(self, mock_session, mock_mcp_tool):
        """Test loading tools from all servers."""
        provider = McpProvider(
            servers={
                "time": McpServerConfig(
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-time"],
                )
            }
        )

        with patch("mcp.client.stdio.stdio_client") as mock_stdio:
            with patch("mcp.ClientSession") as mock_client_session:
                mock_stdio.return_value.__aenter__ = AsyncMock(
                    return_value=(MagicMock(), MagicMock())
                )
                mock_client_session.return_value = mock_session
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)

                await provider._load_all_tools()

                assert provider._initialized
                assert len(provider._tools_cache) == 1
                assert provider._tools_cache[0]["name"] == "time_get_current_time"
                assert provider._tools_cache[0]["_mcp_server"] == "time"
                assert provider._tools_cache[0]["_mcp_tool_name"] == "get_current_time"

    def test_tool_params_sync(self, mock_session, mock_mcp_tool):
        """Test tool_params() synchronous wrapper."""
        provider = McpProvider(
            servers={
                "time": McpServerConfig(
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-time"],
                )
            }
        )

        with patch("mcp.client.stdio.stdio_client") as mock_stdio:
            with patch("mcp.ClientSession") as mock_client_session:
                mock_stdio.return_value.__aenter__ = AsyncMock(
                    return_value=(MagicMock(), MagicMock())
                )
                mock_client_session.return_value = mock_session
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)

                tools = provider.tool_params()

                assert len(tools) == 1
                assert tools[0]["name"] == "time_get_current_time"
                assert tools[0]["description"] == "Get the current time"

    @pytest.mark.asyncio
    async def test_invoke_tool(self, mock_session, mock_mcp_tool):
        """Test invoking an MCP tool."""
        provider = McpProvider(
            servers={
                "time": McpServerConfig(
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-time"],
                )
            }
        )

        with patch("mcp.client.stdio.stdio_client") as mock_stdio:
            with patch("mcp.ClientSession") as mock_client_session:
                mock_stdio.return_value.__aenter__ = AsyncMock(
                    return_value=(MagicMock(), MagicMock())
                )
                mock_client_session.return_value = mock_session
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)

                await provider._load_all_tools()

                result = await provider.invoke_tool(
                    "time_get_current_time",
                    {"timezone": "UTC"}
                )

                assert "2026-04-24" in result
                mock_session.call_tool.assert_called_once_with(
                    "get_current_time",
                    {"timezone": "UTC"}
                )

    @pytest.mark.asyncio
    async def test_invoke_tool_not_found(self):
        """Test invoking a non-existent tool."""
        provider = McpProvider(servers={})
        provider._initialized = True

        result = await provider.invoke_tool("nonexistent_tool", {})

        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_invoke_tool_server_not_connected(self, mock_mcp_tool):
        """Test invoking a tool when server is not connected."""
        provider = McpProvider(servers={})
        provider._initialized = True
        provider._tools_cache = [
            {
                "name": "time_get_current_time",
                "_mcp_server": "time",
                "_mcp_tool_name": "get_current_time",
            }
        ]

        result = await provider.invoke_tool("time_get_current_time", {})

        assert "not connected" in result.lower()

    @pytest.mark.asyncio
    async def test_cleanup(self, mock_session):
        """Test cleaning up MCP sessions."""
        provider = McpProvider(
            servers={
                "time": McpServerConfig(
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-time"],
                )
            }
        )

        mock_session.__aexit__ = AsyncMock()
        provider._sessions["time"] = mock_session

        await provider.cleanup()

        mock_session.__aexit__.assert_called_once()
        assert len(provider._sessions) == 0

    def test_tool_params_empty_provider(self):
        """Test tool_params() with empty provider."""
        provider = McpProvider(servers={})

        tools = provider.tool_params()

        assert tools == []

    @pytest.mark.asyncio
    async def test_initialize_server_failure(self):
        """Test handling server initialization failure."""
        provider = McpProvider(
            servers={
                "invalid": McpServerConfig(
                    command="nonexistent-command",
                    args=[],
                )
            }
        )

        with patch("mcp.client.stdio.stdio_client") as mock_stdio:
            mock_stdio.side_effect = Exception("Command not found")

            tools = await provider._initialize_server("invalid", provider.servers["invalid"])

            assert tools == []
            assert "invalid" not in provider._sessions

    @pytest.mark.asyncio
    async def test_invoke_tool_execution_failure(self, mock_session, mock_mcp_tool):
        """Test handling tool execution failure."""
        provider = McpProvider(
            servers={
                "time": McpServerConfig(
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-time"],
                )
            }
        )

        with patch("mcp.client.stdio.stdio_client") as mock_stdio:
            with patch("mcp.ClientSession") as mock_client_session:
                mock_stdio.return_value.__aenter__ = AsyncMock(
                    return_value=(MagicMock(), MagicMock())
                )
                mock_client_session.return_value = mock_session
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.call_tool = AsyncMock(side_effect=Exception("Tool error"))

                await provider._load_all_tools()

                result = await provider.invoke_tool("time_get_current_time", {})

                assert "failed" in result.lower()
