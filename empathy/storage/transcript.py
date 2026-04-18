"""Transcript storage: append-only JSONL with exclusive flock."""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path

from empathy.core.models import Turn


def append_turn(transcript_path: Path, turn: Turn) -> None:
    """Append a committed turn to transcript.jsonl atomically."""
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    with transcript_path.open("a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(json.dumps(turn.to_dict()) + "\n")
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def read_turns(transcript_path: Path) -> list[Turn]:
    """Read all turns from transcript.jsonl in order."""
    if not transcript_path.exists():
        return []
    turns: list[Turn] = []
    with transcript_path.open("r") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        try:
            for line in f:
                stripped = line.strip()
                if stripped:
                    turns.append(Turn.from_dict(json.loads(stripped)))
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    return turns
