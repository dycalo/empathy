"""Layered loading of side-specific knowledge files (THERAPIST.md / CLIENT.md).

Layout per tier:
  Global:   ~/.empathy/client/CLIENT.md  or  ~/.empathy/therapist/THERAPIST.md
  User:     ~/.empathy/users/<user_id>/CLIENT.md
  Dialogue: <dialogue_dir>/client/CLIENT.md
  Project:  <project_dir>/.empathy/DIALOGUE.md  (shared, not side-specific)

Merge order: global -> user -> dialogue
"""

from __future__ import annotations

from pathlib import Path

from empathy.core.models import Speaker
from empathy.extensions.config import DialogueConfig, _load_yaml

_SIDE_FILE: dict[str, str] = {
    "therapist": "THERAPIST.md",
    "client": "CLIENT.md",
}


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text().strip()


def load_side_knowledge(
    side: Speaker,
    dialogue_dir: Path | None = None,
    project_dir: Path | None = None,
    global_dir: Path | None = None,
) -> str:
    """Return merged knowledge text for *side*.

    Sources loaded (in order):
    1. Global: ``~/.empathy/<side>/<filename>``
    2. User:   ``~/.empathy/users/<user_id>/<filename>``
    3. Dialogue: ``<dialogue_dir>/<side>/<filename>``

    Returns an empty string if no files are found.
    Pass *global_dir* to override the default ``~/.empathy``.
    """
    _global = Path.home() / ".empathy" if global_dir is None else global_dir
    filename = _SIDE_FILE[side]

    layers: list[str] = []

    # 1. Global
    global_content = _read(_global / side / filename)
    if global_content:
        layers.append(f"<global_state>\n{global_content}\n</global_state>")

    # 2. User
    if dialogue_dir is not None:
        dialogue_dict = _load_yaml(dialogue_dir / "dialogue.yaml")
        dialogue_config = DialogueConfig.from_dict(dialogue_dict)
        user_id = getattr(dialogue_config, f"{side}_id", None)

        if user_id:
            user_content = _read(_global / "users" / user_id / filename)
            if user_content:
                layers.append(f"<user_state>\n{user_content}\n</user_state>")

    # 3. Dialogue
    if dialogue_dir is not None:
        dialogue_content = _read(dialogue_dir / side / filename)
        if dialogue_content:
            layers.append(f"<dialogue_state>\n{dialogue_content}\n</dialogue_state>")

    return "\n\n".join(layers)


def load_dialogue_background(project_dir: Path | None = None) -> str:
    """Return the shared DIALOGUE.md from the project tier (both sides see this)."""
    if project_dir is None:
        return ""
    return _read(project_dir / ".empathy" / "DIALOGUE.md")
