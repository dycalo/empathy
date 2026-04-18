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

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from empathy.core.models import Speaker


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

    @property
    def is_empty(self) -> bool:
        return not self.servers

    def tool_params(self) -> list[dict[str, Any]]:
        """Return tools formatted for ``anthropic.messages.create(tools=...)``.
        
        Currently returns empty as we do not have a real MCP client running
        in this codebase.
        """
        return []


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
    filtered = {
        name: config 
        for name, config in merged.items() 
        if name in enabled_mcp_servers
    }

    return McpProvider(servers=filtered)
