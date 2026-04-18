"""Main CLI entry point for empathy."""

from __future__ import annotations

import os
from pathlib import Path
from typing import cast

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from empathy.cli.config import app as config_app
from empathy.core.models import DialogueMeta, Speaker

app = typer.Typer(
    name="empathy",
    help="empathy: controllable dialogue generation for psychological research",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()

_STATUS_COLOR: dict[str, str] = {
    "active": "green",
    "waiting": "yellow",
    "ended": "dim",
}

app.add_typer(config_app, name="config", help="Manage user prototypes and skills")


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", help="Show version"),
) -> None:
    """empathy — dual-agent dialogue generation CLI."""
    if version:
        console.print(Panel("empathy v0.1.0", border_style="blue"))
        raise typer.Exit()


@app.command()
def start(
    side: str = typer.Option(..., "--side", "-s", help="therapist | client"),
    project: Path | None = typer.Option(None, "--project", "-p", help="Project dir (default: cwd)"),
    client_id: str | None = typer.Option(None, "--client-id", help="Pre-seed client config"),
    therapist_id: str | None = typer.Option(
        None, "--therapist-id", help="Pre-seed therapist config"
    ),
) -> None:
    """Start or join a dialogue session."""
    if side not in ("therapist", "client"):
        console.print("[red]--side must be 'therapist' or 'client'[/red]")
        raise typer.Exit(1)

    if not os.environ.get("EMPATHY_API_KEY"):
        console.print(
            "[red]EMPATHY_API_KEY is not set.[/red]\n"
            "[dim]Export it or add it to your shell profile.[/dim]"
        )
        raise typer.Exit(1)

    project_dir = (project or Path.cwd()).resolve()
    (project_dir / ".empathy").mkdir(parents=True, exist_ok=True)

    # --- Select or create dialogue ---
    from empathy.storage.registry import list_dialogues, update_dialogue

    dialogues = list_dialogues(project_dir)
    dialogue_dir = _pick_dialogue(
        project_dir, dialogues, side, client_id=client_id, therapist_id=therapist_id
    )
    dialogue_id = dialogue_dir.name

    # Register this side as connected; transition status if both sides joined
    fresh = list_dialogues(project_dir)
    entry = next((d for d in fresh if d.id == dialogue_id), None)
    if entry is not None:
        connected = list(entry.sides_connected)
        if side not in connected:
            connected.append(side)
        new_status: str = "active" if len(connected) >= 2 else "waiting"
        update_dialogue(project_dir, dialogue_id, sides_connected=connected, status=new_status)

    # --- Load layered config + knowledge ---
    from empathy.extensions.config import load_config
    from empathy.extensions.psych import load_dialogue_background, load_side_knowledge

    config = load_config(cast(Speaker, side), dialogue_dir=dialogue_dir)
    knowledge = load_side_knowledge(cast(Speaker, side), dialogue_dir=dialogue_dir)
    background = load_dialogue_background()
    model: str = config.get("llm", {}).get("model", "claude-haiku-4-5-20251001")

    # --- Load MCP tools ---
    from empathy.extensions.mcp import load_mcp_provider

    mcp_provider = load_mcp_provider(
        cast(Speaker, side),
        dialogue_dir=dialogue_dir,
        enabled_mcp_servers=config.get("enabled_mcp_servers", []),
    )
    if not mcp_provider.is_empty:
        console.print(
            f"[dim]Loaded {len(mcp_provider.servers)} MCP server(s): "
            f"{', '.join(mcp_provider.servers.keys())}[/dim]"
        )

    # --- Build agent ---
    from empathy.agents.client import ClientAgent
    from empathy.agents.therapist import TherapistAgent

    AgentClass = TherapistAgent if side == "therapist" else ClientAgent
    agent = AgentClass(
        knowledge=knowledge,
        dialogue_background=background,
        model=model,
        mcp_provider=mcp_provider if not mcp_provider.is_empty else None,
    )

    # --- Load skills ---
    from empathy.extensions.skills import load_skills

    skills = load_skills(cast(Speaker, side), enabled_skills=config.get("enabled_skills", []))
    if skills:
        console.print(f"[dim]Loaded {len(skills)} skill(s): {', '.join(skills)}[/dim]")

    # --- Run REPL ---
    from empathy.cli.repl import run_repl
    from empathy.modes.session import DialogueSession

    session = DialogueSession(
        dialogue_dir=dialogue_dir,
        side=side,  # type: ignore[arg-type]
        agent=agent,
    )
    run_repl(session, skills=skills)

    # Mark dialogue ended when this side exits cleanly
    update_dialogue(project_dir, dialogue_id, status="ended")


@app.command()
def run(
    dialogue: Path = typer.Argument(..., help="Path to dialogue directory"),
    turns: int = typer.Option(10, "--turns", help="Number of turns to generate"),
    model: str = typer.Option("claude-haiku-4-5-20251001", "--model", help="Model ID"),
) -> None:
    """Run a dialogue in auto mode (no human confirmation required)."""
    import os

    if not os.environ.get("EMPATHY_API_KEY"):
        console.print("[red]EMPATHY_API_KEY is not set.[/red]")
        raise typer.Exit(1)

    dialogue_dir = dialogue.resolve()
    if not dialogue_dir.exists():
        console.print(f"[red]Dialogue directory not found:[/red] {dialogue_dir}")
        raise typer.Exit(1)

    from empathy.agents.client import ClientAgent
    from empathy.agents.therapist import TherapistAgent
    from empathy.extensions.config import load_config
    from empathy.extensions.psych import load_dialogue_background, load_side_knowledge
    from empathy.modes.auto import run_auto

    config_t = load_config("therapist", dialogue_dir=dialogue_dir)
    resolved_model_t: str = config_t.get("llm", {}).get("model", model)
    config_c = load_config("client", dialogue_dir=dialogue_dir)
    resolved_model_c: str = config_c.get("llm", {}).get("model", model)

    therapist = TherapistAgent(
        model=resolved_model_t,
        knowledge=load_side_knowledge("therapist", dialogue_dir=dialogue_dir),
        dialogue_background=load_dialogue_background(),
    )
    client = ClientAgent(
        model=resolved_model_c,
        knowledge=load_side_knowledge("client", dialogue_dir=dialogue_dir),
        dialogue_background=load_dialogue_background(),
    )

    console.print(
        f"[bold]Auto mode[/bold]  dialogue=[cyan]{dialogue_dir.name}[/cyan]"
        f"  turns=[yellow]{turns}[/yellow]  model=[dim]{resolved_model_t}[/dim]"
    )

    committed = run_auto(
        therapist,
        client,
        transcript_path=dialogue_dir / "transcript.jsonl",
        drafts_path=dialogue_dir / "draft-history.jsonl",
        turns=turns,
    )

    console.print(f"[green]✓[/green] {len(committed)} turns written to transcript.")


@app.command()
def delete(
    dialogue_id: str = typer.Argument(..., help="ID of the dialogue to delete"),
    project: Path | None = typer.Option(None, "--project", "-p", help="Project dir (default: cwd)"),
    force: bool = typer.Option(
        False, "--force", "-f", help="Delete without prompting for confirmation"
    ),
) -> None:
    """Delete a dialogue from the registry and disk."""
    project_dir = (project or Path.cwd()).resolve()

    from empathy.storage.registry import delete_dialogue, list_dialogues

    dialogues = list_dialogues(project_dir)
    target = next((d for d in dialogues if d.id == dialogue_id), None)

    if not target:
        console.print(f"[red]Dialogue '{dialogue_id}' not found in registry.[/red]")
        raise typer.Exit(1)

    if not force:
        confirm = Prompt.ask(
            f"Are you sure you want to delete [cyan]{dialogue_id}[/cyan]? "
            "This action cannot be undone",
            choices=["y", "N"],
            default="N",
        )
        if confirm.lower() != "y":
            console.print("[dim]Aborted.[/dim]")
            raise typer.Exit()

    success = delete_dialogue(project_dir, dialogue_id)
    if success:
        console.print(f"[green]✓[/green] Deleted dialogue [cyan]{dialogue_id}[/cyan]")
    else:
        console.print(f"[red]Failed to delete dialogue '{dialogue_id}'.[/red]")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pick_dialogue(
    project_dir: Path,
    dialogues: list[DialogueMeta],
    side: str,
    client_id: str | None = None,
    therapist_id: str | None = None,
) -> Path:
    """Interactive dialogue selector. Returns the chosen dialogue directory."""
    from empathy.storage.registry import create_dialogue

    def _prompt_edit(dialogue_dir: Path) -> None:
        if typer.confirm(f"\nDo you want to edit the {side} context ({side.upper()}.md) now?"):
            side_md = dialogue_dir / side / f"{side.upper()}.md"
            side_md.parent.mkdir(parents=True, exist_ok=True)
            if not side_md.exists():
                side_md.write_text(f"# {dialogue_dir.name} - {side.upper()} context\n\n")
            import click

            click.edit(filename=str(side_md))

    if not dialogues:
        console.print("[dim]No existing dialogues found. Creating new one…[/dim]")
        meta, dialogue_dir = create_dialogue(
            project_dir, client_id=client_id, therapist_id=therapist_id
        )
        console.print(f"[green]✓[/green] Created [cyan]{meta.id}[/cyan]")
        _prompt_edit(dialogue_dir)
        return dialogue_dir

    console.print("\n[bold]Available dialogues:[/bold]")
    for i, d in enumerate(dialogues, 1):
        color = _STATUS_COLOR.get(d.status, "white")
        ts = d.created_at.strftime("%Y-%m-%d %H:%M")
        console.print(
            f"  [[cyan]{i}[/cyan]] {d.id}  [{color}]{d.status}[/{color}]  [dim]{ts} UTC[/dim]"
        )
    console.print("  [[cyan]n[/cyan]] New dialogue\n")

    while True:
        choice = Prompt.ask("Choice").strip().lower()
        if choice == "n":
            meta, dialogue_dir = create_dialogue(
                project_dir, client_id=client_id, therapist_id=therapist_id
            )
            console.print(f"[green]✓[/green] Created [cyan]{meta.id}[/cyan]")
            _prompt_edit(dialogue_dir)
            return dialogue_dir
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(dialogues):
                dialogue_dir = project_dir / dialogues[idx].path
                _prompt_edit(dialogue_dir)
                return dialogue_dir
        except ValueError:
            pass
        console.print("[red]Invalid choice — enter a number or 'n'.[/red]")


if __name__ == "__main__":
    app()
