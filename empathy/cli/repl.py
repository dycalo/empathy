"""Main REPL loop for human-in-the-loop dialogue mode."""

from __future__ import annotations

from rich.console import Console

from empathy.extensions.skills import Skill
from empathy.modes.session import DialogueSession

console = Console()

_COMMANDS: dict[str, str] = {
    "/done": "Release the floor and let the other side speak",
    "/status": "Show current floor and turn state",
    "/help": "List available commands",
    "/quit": "Exit the session",
}


def run_repl(session: DialogueSession, skills: dict[str, Skill] | None = None) -> None:
    """Launch the empathy TUI."""
    from empathy.cli.tui import EmpathyApp

    app = EmpathyApp(session=session, skills=skills)
    app.run()


def _handle_command(
    cmd: str, session: DialogueSession, skills: dict[str, Skill] | None = None
) -> bool:
    """Process a /command. Returns True when the session should exit."""
    _skills = skills or {}
    if cmd in _skills:
        # Skill triggers handled before reaching here; this is a fallback.
        console.print(f"[dim]Use skill [cyan]{cmd}[/cyan] as an instruction.[/dim]")
    elif cmd == "/done":
        session.release_floor()
        console.print("[dim]Floor released.[/dim]")
    elif cmd == "/status":
        st = session.floor_status()
        console.print(st)
    elif cmd == "/help":
        for name, desc in _COMMANDS.items():
            console.print(f"  [cyan]{name:<10}[/cyan] {desc}")
    elif cmd == "/quit":
        session.release_floor()
        return True
    else:
        console.print(f"[red]Unknown command:[/red] {cmd}")
    return False
