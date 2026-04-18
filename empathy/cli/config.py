"""Config mode CLI for empathy."""

from __future__ import annotations

import os
from pathlib import Path

import click
import typer
import yaml
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    help="Manage prototypes, skills, and extensions",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


def _get_empathy_home() -> Path:
    return Path(os.path.expanduser("~/.empathy"))


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@app.command("user-list")
def user_list() -> None:
    """List all user prototypes in ~/.empathy/users/."""
    users_dir = _get_empathy_home() / "users"
    if not users_dir.exists():
        console.print("[dim]No users found (directory does not exist).[/dim]")
        return

    users = [d.name for d in users_dir.iterdir() if d.is_dir()]
    if not users:
        console.print("[dim]No users found.[/dim]")
        return

    table = Table(title="User Prototypes")
    table.add_column("User ID", style="cyan")
    table.add_column("Side", style="dim")
    table.add_column("Config", style="dim")

    for user_id in sorted(users):
        user_dir = users_dir / user_id
        side = "unknown"
        if (user_dir / "CLIENT.md").exists():
            side = "client"
        elif (user_dir / "THERAPIST.md").exists():
            side = "therapist"

        config_path = user_dir / "config.yaml"
        config_status = "present" if config_path.exists() else "missing"
        table.add_row(user_id, side, config_status)

    console.print(table)


@app.command("user-create")
def user_create(
    user_id: str = typer.Argument(..., help="The ID for the new user prototype"),
    side: str = typer.Option(..., "--side", "-s", help="client | therapist"),
) -> None:
    """Create a new user prototype."""
    if side not in ("client", "therapist"):
        console.print("[red]Error:[/red] --side must be 'client' or 'therapist'")
        raise typer.Exit(1)

    user_dir = _get_empathy_home() / "users" / user_id
    if user_dir.exists():
        console.print(f"[red]Error:[/red] User '{user_id}' already exists.")
        raise typer.Exit(1)

    user_dir.mkdir(parents=True, exist_ok=True)

    # Create Markdown file
    md_filename = f"{side.upper()}.md"
    md_path = user_dir / md_filename
    md_path.write_text(f"# {user_id}\n\nAdd your {side} background and persona details here.\n")

    # Create config.yaml
    config_path = user_dir / "config.yaml"
    initial_config = {"enabled_skills": [], "enabled_mcp_servers": []}
    with config_path.open("w") as f:
        yaml.dump(initial_config, f, default_flow_style=False)

    console.print(f"[green]✓[/green] Created user [cyan]{user_id}[/cyan]")

    # Open files for editing
    click.edit(filename=str(md_path))
    click.edit(filename=str(config_path))

    console.print(f"[dim]Finished editing user {user_id}[/dim]")


@app.command("user-edit")
def user_edit(
    user_id: str = typer.Argument(..., help="The ID of the user prototype to edit"),
    side: str = typer.Option(..., "--side", "-s", help="client | therapist"),
) -> None:
    """Edit an existing user prototype."""
    if side not in ("client", "therapist"):
        console.print("[red]Error:[/red] --side must be 'client' or 'therapist'")
        raise typer.Exit(1)

    user_dir = _get_empathy_home() / "users" / user_id
    if not user_dir.exists():
        console.print(f"[red]Error:[/red] User '{user_id}' does not exist.")
        raise typer.Exit(1)

    md_filename = f"{side.upper()}.md"
    md_path = user_dir / md_filename
    if not md_path.exists():
        console.print(f"[yellow]Warning:[/yellow] {md_filename} not found, creating it.")
        md_path.write_text(f"# {user_id}\n\nAdd your {side} background and persona details here.\n")

    config_path = user_dir / "config.yaml"
    if not config_path.exists():
        console.print("[yellow]Warning:[/yellow] config.yaml not found, creating it.")
        initial_config = {"enabled_skills": [], "enabled_mcp_servers": []}
        with config_path.open("w") as f:
            yaml.dump(initial_config, f, default_flow_style=False)

    # Open files for editing
    click.edit(filename=str(md_path))
    click.edit(filename=str(config_path))

    console.print(f"[dim]Finished editing user {user_id}[/dim]")


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

import re


def _parse_frontmatter(content: str) -> dict[str, str]:
    """Parse simple YAML frontmatter from markdown."""
    frontmatter = {}
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if match:
        yaml_content = match.group(1)
        try:
            parsed = yaml.safe_load(yaml_content)
            if isinstance(parsed, dict):
                frontmatter = parsed
        except Exception:
            pass
    return frontmatter


@app.command("skill-list")
def skill_list(side: str = typer.Option(..., "--side", "-s", help="client | therapist")) -> None:
    """List all skills for a specific side."""
    if side not in ("client", "therapist"):
        console.print("[red]Error:[/red] --side must be 'client' or 'therapist'")
        raise typer.Exit(1)

    skills_dir = _get_empathy_home() / "global" / side / "skills"
    if not skills_dir.exists():
        console.print(f"[dim]No {side} skills found (directory does not exist).[/dim]")
        return

    skills = list(skills_dir.glob("*.md"))
    if not skills:
        console.print(f"[dim]No {side} skills found.[/dim]")
        return

    table = Table(title=f"{side.capitalize()} Skills")
    table.add_column("Name", style="cyan")
    table.add_column("Title", style="green")
    table.add_column("Description", style="dim")

    for skill_path in sorted(skills):
        skill_name = skill_path.stem
        content = skill_path.read_text(encoding="utf-8")
        frontmatter = _parse_frontmatter(content)

        title = frontmatter.get("name", skill_name)
        description = frontmatter.get("description", "")

        table.add_row(skill_name, str(title), str(description))

    console.print(table)


@app.command("skill-create")
def skill_create(
    name: str = typer.Argument(..., help="The name for the new skill (filename)"),
    side: str = typer.Option(..., "--side", "-s", help="client | therapist"),
) -> None:
    """Create a new skill."""
    if side not in ("client", "therapist"):
        console.print("[red]Error:[/red] --side must be 'client' or 'therapist'")
        raise typer.Exit(1)

    skills_dir = _get_empathy_home() / "global" / side / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    skill_path = skills_dir / f"{name}.md"
    if skill_path.exists():
        console.print(f"[red]Error:[/red] Skill '{name}' already exists at {skill_path}.")
        raise typer.Exit(1)

    template = f"""---
name: {name.replace("-", " ").title()}
description: A short description of what this skill does
---

# Instructions

Define the behavior for this skill here.
"""
    skill_path.write_text(template)
    console.print(f"[green]✓[/green] Created skill [cyan]{name}[/cyan]")

    click.edit(filename=str(skill_path))
    console.print(f"[dim]Finished editing skill {name}[/dim]")


@app.command("skill-edit")
def skill_edit(
    name: str = typer.Argument(..., help="The name of the skill to edit"),
    side: str = typer.Option(..., "--side", "-s", help="client | therapist"),
) -> None:
    """Edit an existing skill."""
    if side not in ("client", "therapist"):
        console.print("[red]Error:[/red] --side must be 'client' or 'therapist'")
        raise typer.Exit(1)

    skill_path = _get_empathy_home() / "global" / side / "skills" / f"{name}.md"
    if not skill_path.exists():
        console.print(f"[red]Error:[/red] Skill '{name}' does not exist at {skill_path}.")
        raise typer.Exit(1)

    click.edit(filename=str(skill_path))
    console.print(f"[dim]Finished editing skill {name}[/dim]")
