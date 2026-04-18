"""Tests for MCP configuration parsing."""

from __future__ import annotations

import json
from pathlib import Path

from empathy.extensions.mcp import load_mcp_provider

def test_load_mcp_empty(tmp_path: Path) -> None:
    provider = load_mcp_provider("therapist", global_dir=tmp_path, enabled_mcp_servers=["test"])
    assert provider.is_empty
    assert provider.servers == {}

def test_load_mcp_from_global(tmp_path: Path) -> None:
    global_dir = tmp_path / "global"
    tier_dir = global_dir / "therapist"
    tier_dir.mkdir(parents=True)
    
    config = {
        "mcpServers": {
            "test": {
                "command": "node",
                "args": ["-v"],
                "env": {"FOO": "bar"}
            }
        }
    }
    (tier_dir / "mcp.json").write_text(json.dumps(config))
    
    provider = load_mcp_provider("therapist", global_dir=global_dir, enabled_mcp_servers=["test"])
    assert not provider.is_empty
    assert "test" in provider.servers
    
    server = provider.servers["test"]
    assert server.command == "node"
    assert server.args == ["-v"]
    assert server.env == {"FOO": "bar"}

def test_load_mcp_returns_only_enabled(tmp_path: Path) -> None:
    tier_dir = tmp_path / "therapist"
    tier_dir.mkdir(parents=True)
    
    config = {
        "mcpServers": {
            "test": {"command": "node"},
            "other": {"command": "python"}
        }
    }
    (tier_dir / "mcp.json").write_text(json.dumps(config))
    
    provider = load_mcp_provider("therapist", global_dir=tmp_path, enabled_mcp_servers=["test"])
    assert "test" in provider.servers
    assert "other" not in provider.servers

def test_load_mcp_overrides(tmp_path: Path) -> None:
    global_dir = tmp_path / "global"
    dialogue_dir = tmp_path / "dialogue"
    
    (global_dir / "therapist").mkdir(parents=True)
    (dialogue_dir / "therapist").mkdir(parents=True)
    
    (global_dir / "therapist" / "mcp.json").write_text(json.dumps({
        "mcpServers": {
            "test": {"command": "node"}
        }
    }))
    
    (dialogue_dir / "therapist" / "mcp.json").write_text(json.dumps({
        "mcpServers": {
            "test": {"command": "python", "args": ["-m"]}
        }
    }))
    
    provider = load_mcp_provider(
        "therapist", 
        global_dir=global_dir, 
        dialogue_dir=dialogue_dir,
        enabled_mcp_servers=["test"]
    )
    
    # Dialogue tier should override
    server = provider.servers["test"]
    assert server.command == "python"
    assert server.args == ["-m"]
