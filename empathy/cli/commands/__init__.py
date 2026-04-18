"""Slash command registry for empathy REPL."""

from __future__ import annotations

from typing import TypedDict


class CommandInfo(TypedDict):
    description: str
    usage: str


COMMANDS: dict[str, CommandInfo] = {
    "done": {
        "description": "Release the floor and let the other side speak",
        "usage": "/done",
    },
    "quit": {
        "description": "Exit the session (releases floor)",
        "usage": "/quit",
    },
    "help": {
        "description": "List all available commands",
        "usage": "/help",
    },
    "status": {
        "description": "Show floor state and turn info",
        "usage": "/status",
    },
    "context": {
        "description": "Show or clear agent context. Usage: /context [show|clear]",
        "usage": "/context [show|clear]",
    },
    "agent": {
        "description": "Show agent info or switch model. Usage: /agent [info | model <id>]",
        "usage": "/agent [info | model <model-id>]",
    },
    "skills": {
        "description": "List loaded skills or reload. Usage: /skills [reload]",
        "usage": "/skills [reload]",
    },
    "session": {
        "description": "Show full session information",
        "usage": "/session",
    },
}


def get_suggestions(prefix: str) -> list[str]:
    """Return matching command triggers for a given prefix (starts with '/')."""
    if not prefix.startswith("/"):
        return []
    parts = prefix[1:].split()
    query = parts[0].lower() if parts else ""  # "" matches all commands
    return [f"/{name}" for name in COMMANDS if name.startswith(query)][:5]
