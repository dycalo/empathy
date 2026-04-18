"""Three-tier config.yaml merge loading.

Priority (lowest → highest): global → user → dialogue.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r") as f:
        result = yaml.safe_load(f)
    return result if isinstance(result, dict) else {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Return a new dict with *override* deep-merged into *base*."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


@dataclass
class DialogueConfig:
    client_id: str | None = None
    therapist_id: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DialogueConfig:
        return cls(
            client_id=data.get("client_id"),
            therapist_id=data.get("therapist_id"),
        )


def load_config(
    side: str,
    dialogue_dir: Path | None = None,
    global_dir: Path | None = None,
) -> dict[str, Any]:
    """Load and merge config from all three tiers.

    Directory layout expected:
      ~/.empathy/config.yaml                     (global)
      ~/.empathy/users/<user_id>/config.yaml     (user)
      <dialogue_dir>/dialogue.yaml               (dialogue — wins on conflicts)

    Pass *global_dir* to override the default ``~/.empathy``.
    """
    _global = Path.home() / ".empathy" if global_dir is None else global_dir

    merged = _load_yaml(_global / "config.yaml")

    if dialogue_dir is not None:
        dialogue_dict = _load_yaml(dialogue_dir / "dialogue.yaml")
        dialogue_config = DialogueConfig.from_dict(dialogue_dict)

        user_id = getattr(dialogue_config, f"{side}_id", None)

        if user_id:
            user_config = _load_yaml(_global / "users" / user_id / "config.yaml")
            merged = _deep_merge(merged, user_config)

        merged = _deep_merge(merged, dialogue_dict)

    return merged
