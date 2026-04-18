"""Dialogue registry: manages dialogues.yaml within a project directory."""

from __future__ import annotations

import random
import string
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from empathy.core.models import DialogueMeta


def _registry_path(project_dir: Path) -> Path:
    return project_dir / ".empathy" / "dialogues.yaml"


def _load_raw(project_dir: Path) -> list[dict[str, Any]]:
    path = _registry_path(project_dir)
    if not path.exists():
        return []
    with path.open("r") as f:
        data: dict[str, Any] = yaml.safe_load(f) or {}
    entries: list[dict[str, Any]] = data.get("dialogues", [])
    # PyYAML may auto-parse ISO datetime strings; normalise to str
    for entry in entries:
        raw = entry.get("created_at")
        if isinstance(raw, datetime):
            entry["created_at"] = raw.isoformat()
    return entries


def _save(project_dir: Path, dialogues: list[DialogueMeta]) -> None:
    path = _registry_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        yaml.dump(
            {"dialogues": [d.to_dict() for d in dialogues]},
            f,
            allow_unicode=True,
            default_flow_style=False,
        )


def list_dialogues(project_dir: Path) -> list[DialogueMeta]:
    """Return all registered dialogues for the project, oldest-first."""
    return [DialogueMeta.from_dict(e) for e in _load_raw(project_dir)]


def register_dialogue(project_dir: Path, meta: DialogueMeta) -> None:
    """Append a new dialogue entry to the registry."""
    existing = list_dialogues(project_dir)
    existing.append(meta)
    _save(project_dir, existing)


def update_dialogue(project_dir: Path, dialogue_id: str, **fields: Any) -> None:
    """Update arbitrary fields on an existing dialogue registry entry."""
    dialogues = list_dialogues(project_dir)
    for d in dialogues:
        if d.id == dialogue_id:
            for key, value in fields.items():
                setattr(d, key, value)
            break
    _save(project_dir, dialogues)


def create_dialogue(project_dir: Path) -> tuple[DialogueMeta, Path]:
    """Create a new dialogue directory under ``<project_dir>/dialogues/``.

    Registers the dialogue in ``dialogues.yaml`` and returns
    ``(DialogueMeta, absolute_dialogue_dir)``.
    """
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    dialogue_id = f"session_{datetime.now(UTC).strftime('%Y%m%d')}_{suffix}"
    rel_path = f"dialogues/{dialogue_id}"
    dialogue_dir = project_dir / rel_path

    (dialogue_dir / ".empathy" / "therapist").mkdir(parents=True, exist_ok=True)
    (dialogue_dir / ".empathy" / "client").mkdir(parents=True, exist_ok=True)

    meta = DialogueMeta(
        id=dialogue_id,
        path=rel_path,
        status="waiting",
        created_at=datetime.now(UTC),
        sides_connected=[],
    )
    register_dialogue(project_dir, meta)
    return meta, dialogue_dir


def delete_dialogue(project_dir: Path, dialogue_id: str) -> bool:
    """Delete a dialogue from disk and remove it from the registry.

    Returns True if successfully deleted, False if dialogue_id was not found.
    """
    import shutil

    dialogues = list_dialogues(project_dir)
    target_meta = next((d for d in dialogues if d.id == dialogue_id), None)

    if not target_meta:
        return False

    # Remove from disk
    dialogue_dir = project_dir / target_meta.path
    if dialogue_dir.exists():
        shutil.rmtree(dialogue_dir)

    # Remove from registry
    remaining = [d for d in dialogues if d.id != dialogue_id]
    _save(project_dir, remaining)

    return True
