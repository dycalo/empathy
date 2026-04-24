"""MCP tool provider for empathy agents.

Tools are configured via ``mcp.json`` files using the same
3-tier resolution as config / knowledge / skills.

The JSON format matches standard MCP configuration:
{
    "mcpServers": {
        "server_name": {
            "command": "node",
            "args": ["..."],
            "env": {"FOO": "bar"}
        }
    }
}
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from empathy.core.models import Speaker

logger = logging.getLogger(__name__)


@dataclass
class McpServerConfig:
    """A single MCP server configuration."""

    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class McpProvider:
    """Aggregated tool definitions and usage instructions for one session."""

    servers: dict[str, McpServerConfig] = field(default_factory=dict)
    instructions: str = ""
    _sessions: dict[str, Any] = field(default_factory=dict, init=False, repr=False)
    _tools_cache: list[dict[str, Any]] = field(default_factory=list, init=False, repr=False)
    _initialized: bool = field(default=False, init=False, repr=False)

    @property
    def is_empty(self) -> bool:
        return not self.servers

    async def _initialize_server(self, name: str, config: McpServerConfig) -> list[Any]:
        """Initialize a single MCP server and return its tools.

        Args:
            name: Server name
            config: Server configuration

        Returns:
            List of tool definitions from the server
        """
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            server_params = StdioServerParameters(
                command=config.command,
                args=config.args,
                env=config.env or None,
            )

            # Create stdio client
            read, write = await stdio_client(server_params).__aenter__()

            # Create session
            session = ClientSession(read, write)
            await session.__aenter__()

            # Initialize session
            await session.initialize()

            # Store session for later use
            self._sessions[name] = session

            # List tools
            tools_result = await session.list_tools()
            return tools_result.tools if hasattr(tools_result, "tools") else []

        except Exception as e:
            logger.error(f"Failed to initialize MCP server '{name}': {e}")
            return []

    async def _load_all_tools(self) -> None:
        """Load all tools from all configured MCP servers."""
        if self._initialized:
            return

        all_tools = []
        for name, config in self.servers.items():
            try:
                tools = await self._initialize_server(name, config)
                for tool in tools:
                    # Convert MCP tool to our format
                    tool_dict = {
                        "name": f"{name}_{tool.name}",
                        "description": tool.description or "",
                        "input_schema": tool.inputSchema if hasattr(tool, "inputSchema") else {},
                        "_mcp_server": name,
                        "_mcp_tool_name": tool.name,
                    }
                    all_tools.append(tool_dict)
                logger.info(f"Loaded {len(tools)} tools from MCP server '{name}'")
            except Exception as e:
                logger.error(f"Failed to load tools from MCP server '{name}': {e}")

        self._tools_cache = all_tools
        self._initialized = True

    def tool_params(self) -> list[dict[str, Any]]:
        """Return tools formatted for ``anthropic.messages.create(tools=...)``.

        Loads tools from MCP servers if not already loaded.
        """
        if not self._initialized and self.servers:
            # Run async initialization in sync context
            try:
                asyncio.run(self._load_all_tools())
            except Exception as e:
                logger.error(f"Failed to load MCP tools: {e}")
                return []

        return self._tools_cache

    async def invoke_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Invoke an MCP tool by name.

        Args:
            tool_name: Tool name (format: "server_toolname")
            arguments: Tool arguments

        Returns:
            Tool result as string
        """
        # Find tool definition
        tool_def = next((t for t in self._tools_cache if t["name"] == tool_name), None)
        if not tool_def:
            return f"Tool '{tool_name}' not found"

        server_name = tool_def["_mcp_server"]
        original_tool_name = tool_def["_mcp_tool_name"]
        session = self._sessions.get(server_name)

        if not session:
            return f"MCP server '{server_name}' not connected"

        try:
            result = await session.call_tool(original_tool_name, arguments)
            # Extract content from result
            if hasattr(result, "content"):
                if isinstance(result.content, list):
                    # Join multiple content items
                    return "\n".join(str(item) for item in result.content)
                return str(result.content)
            return str(result)
        except Exception as e:
            logger.error(f"Tool execution failed for '{tool_name}': {e}")
            return f"Tool execution failed: {e}"

    async def cleanup(self) -> None:
        """Clean up MCP sessions."""
        for name, session in self._sessions.items():
            try:
                await session.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Failed to cleanup MCP session '{name}': {e}")
        self._sessions.clear()


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _load_mcp_json(path: Path) -> dict[str, McpServerConfig]:
    """Parse one mcp.json file. Returns dict of server configs. Never raises."""
    if not path.exists():
        return {}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    servers: dict[str, McpServerConfig] = {}
    mcp_servers = raw.get("mcpServers", {})
    if not isinstance(mcp_servers, dict):
        return {}

    for name, config in mcp_servers.items():
        if not isinstance(config, dict):
            continue
        command = str(config.get("command", "")).strip()
        if not command:
            continue

        args = config.get("args", [])
        if not isinstance(args, list):
            args = []

        env = config.get("env", {})
        if not isinstance(env, dict):
            env = {}

        servers[name] = McpServerConfig(
            command=command,
            args=[str(a) for a in args],
            env={str(k): str(v) for k, v in env.items()},
        )

    return servers


def load_mcp_provider(
    side: Speaker,
    dialogue_dir: Path | None = None,
    global_dir: Path | None = None,
    enabled_mcp_servers: list[str] | None = None,
) -> McpProvider:
    """Return merged ``McpProvider`` across global / user / dialogue tiers.

    Higher-priority tiers (dialogue > user > global) override servers with
    the same name.

    If enabled_mcp_servers is None, returns an empty provider.
    Otherwise only returns servers listed in enabled_mcp_servers.
    """
    if enabled_mcp_servers is None:
        return McpProvider()

    _global = Path.home() / ".empathy" if global_dir is None else global_dir

    # 1. Global
    tiers: list[Path] = [_global / side / "mcp.json"]

    # 2. User (requires looking up user_id from dialogue.yaml)
    if dialogue_dir is not None:
        try:
            import yaml

            meta_path = dialogue_dir / "dialogue.yaml"
            if meta_path.exists():
                meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
                users = meta.get("users", {})
                user_id = users.get(side)
                if user_id:
                    tiers.append(_global / "users" / user_id / "mcp.json")
        except Exception:
            pass

    # 3. Dialogue
    if dialogue_dir is not None:
        tiers.append(dialogue_dir / side / "mcp.json")

    merged: dict[str, McpServerConfig] = {}

    for tier_file in tiers:
        servers = _load_mcp_json(tier_file)
        for name, config in servers.items():
            merged[name] = config

    # Filter by enabled
    filtered = {name: config for name, config in merged.items() if name in enabled_mcp_servers}

    return McpProvider(servers=filtered)
