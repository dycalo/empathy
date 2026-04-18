"""Skill loading from Markdown + YAML frontmatter files.

Skills are stored ONLY in the Global tier: global_dir/<side>/skills/*.md.
All skills are loaded eagerly at session start if enabled.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import frontmatter

from empathy.core.models import Speaker


@dataclass
class Skill:
    name: str
    side: Speaker
    description: str
    source_path: Path


def _load_skill(path: Path, side: Speaker) -> Skill | None:
    """Parse a single skill Markdown file. Returns None if frontmatter is invalid."""
    try:
        post = frontmatter.load(str(path))
    except Exception:
        return None
    name: str = str(post.get("name", path.stem))
    description: str = str(post.get("description", ""))
    return Skill(
        name=name,
        side=side,
        description=description,
        source_path=path,
    )


def load_skills(
    side: Speaker,
    global_dir: Path | None = None,
    enabled_skills: list[str] | None = None,
) -> dict[str, Skill]:
    """Return skill map {name: Skill} for *side*.

    Scans the global directory, but ONLY returns skills whose name is in enabled_skills.
    If enabled_skills is None, return empty dict.
    """
    if enabled_skills is None:
        return {}

    _global = Path.home() / ".empathy" if global_dir is None else global_dir
    skills_dir = _global / "skills" / side

    if not skills_dir.exists():
        return {}

    result: dict[str, Skill] = {}
    for path in sorted(skills_dir.glob("*.md")):
        skill = _load_skill(path, side)
        if skill and skill.name in enabled_skills:
            result[skill.name] = skill

    return result


def build_skill_tool(side: Speaker, skills: dict[str, Skill]) -> dict[str, Any]:
    """Build an Anthropic Tool definition for the given skills."""
    tool_name = "apply_behavior" if side == "client" else "apply_therapy"

    skills_list = []
    for skill in skills.values():
        skills_list.append(f"- {skill.name}: {skill.description}")

    skills_text = "\n".join(skills_list)

    tool_description = f"""Use this tool to get detailed instructions for a behavior/therapy.

Available skills:
{skills_text}"""

    return {
        "name": tool_name,
        "description": tool_description,
        "input_schema": {
            "type": "object",
            "properties": {
                "skill_name": {"type": "string", "description": "The name of the skill to apply."}
            },
            "required": ["skill_name"],
        },
    }


def read_skill_body(skill: Skill) -> str:
    """Return the content body (excluding frontmatter) of the markdown file."""
    try:
        post = frontmatter.load(str(skill.source_path))
        return str(post.content).strip()
    except Exception:
        return ""
