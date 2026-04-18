"""Persistence for per-side conversation summaries.

A summary compresses transcript turns that have scrolled out of the active
context window so older dialogue history remains accessible without consuming
the full context budget.

File location: <dialogue_dir>/.empathy/<side>/summary.json
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


def read_summary(path: Path) -> tuple[str, int]:
    """Return (summary_text, covers_turn_count) for the saved summary.

    Returns ("", 0) when no summary file exists yet.
    """
    if not path.exists():
        return "", 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("summary", ""), int(data.get("covers_turn_count", 0))
    except Exception:
        return "", 0


def write_summary(path: Path, summary: str, covers_turn_count: int) -> None:
    """Persist a summary to disk, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "summary": summary,
                "covers_turn_count": covers_turn_count,
                "generated_at": datetime.now(UTC).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
