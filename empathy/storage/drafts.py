"""Draft-history storage: JSONL with flock for append, temp+rename for updates."""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path

from empathy.core.models import Draft, DraftOutcome


def append_draft(drafts_path: Path, draft: Draft) -> None:
    """Append a draft record to draft-history.jsonl atomically."""
    drafts_path.parent.mkdir(parents=True, exist_ok=True)
    with drafts_path.open("a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(json.dumps(draft.to_dict()) + "\n")
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def update_draft_outcome(
    drafts_path: Path,
    draft_id: str,
    outcome: DraftOutcome,
    final_content: str | None = None,
) -> None:
    """Update the outcome (and optionally final_content) of a draft in-place.

    Rewrites the entire file via temp+rename for atomicity.
    Safe because draft-history is written by a single side process.
    """
    drafts = read_drafts(drafts_path)
    for draft in drafts:
        if draft.id == draft_id:
            draft.outcome = outcome
            draft.final_content = final_content
            break

    tmp_path = drafts_path.with_suffix(".tmp")
    with tmp_path.open("w") as f:
        for draft in drafts:
            f.write(json.dumps(draft.to_dict()) + "\n")
        f.flush()
        os.fsync(f.fileno())
    tmp_path.rename(drafts_path)


def read_drafts(drafts_path: Path) -> list[Draft]:
    """Read all draft records from draft-history.jsonl in order."""
    if not drafts_path.exists():
        return []
    drafts: list[Draft] = []
    with drafts_path.open("r") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        try:
            for line in f:
                stripped = line.strip()
                if stripped:
                    drafts.append(Draft.from_dict(json.loads(stripped)))
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    return drafts
