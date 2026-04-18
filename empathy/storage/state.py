"""Floor state management: state.json with temp+rename atomicity."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from empathy.core.models import Speaker

_DEFAULTS: dict[str, Any] = {
    "turn_number": 0,
    "floor_holder": None,
    "floor_since": None,
    "last_speaker": None,
    "floor_timeout_seconds": 300,
}


def read_state(state_path: Path) -> dict[str, Any]:
    """Read state.json, returning defaults if the file does not exist."""
    if not state_path.exists():
        return dict(_DEFAULTS)
    with state_path.open("r") as f:
        data: dict[str, Any] = json.load(f)
    return data


def _write_state(state_path: Path, state: dict[str, Any]) -> None:
    """Write state atomically via temp+rename."""
    tmp_path = state_path.with_suffix(".tmp")
    with tmp_path.open("w") as f:
        json.dump(state, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    tmp_path.rename(state_path)


def acquire_floor(state_path: Path, side: Speaker) -> bool:
    """Try to acquire the floor for *side*.

    Returns True on success, False if the floor is held by the other side.
    """
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state = read_state(state_path)
    holder: str | None = state.get("floor_holder")
    if holder is not None and holder != side:
        return False
    state["floor_holder"] = side
    state["floor_since"] = time.time()
    _write_state(state_path, state)
    return True


def release_floor(state_path: Path, side: Speaker) -> None:
    """Release the floor if currently held by *side*."""
    state = read_state(state_path)
    if state.get("floor_holder") == side:
        state["floor_holder"] = None
        state["floor_since"] = None
        state["last_speaker"] = side
        state["turn_number"] = int(state.get("turn_number", 0)) + 1
        _write_state(state_path, state)


def is_floor_timed_out(state_path: Path) -> bool:
    """Return True if the current floor holder has exceeded the timeout."""
    state = read_state(state_path)
    holder: str | None = state.get("floor_holder")
    floor_since: float | None = state.get("floor_since")
    if holder is None or floor_since is None:
        return False
    timeout: int = int(state.get("floor_timeout_seconds", 300))
    return (time.time() - floor_since) > timeout
