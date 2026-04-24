"""Listen tool - read conversation history."""

from __future__ import annotations

import fcntl
import json
from pathlib import Path
from typing import Literal

from langchain.tools import StructuredTool
from pydantic import BaseModel, Field

from empathy.core.models import Turn


class ListenInput(BaseModel):
    """Input schema for listen tool."""

    scope: Literal["recent", "all", "range", "search"] = Field(
        description="What to retrieve: recent (last N turns), all, range (specific turns), search (keyword)"
    )
    limit: int = Field(default=5, description="Number of turns for 'recent' scope")
    start_turn: int | None = Field(default=None, description="Start turn number for 'range'")
    end_turn: int | None = Field(default=None, description="End turn number for 'range'")
    keyword: str | None = Field(default=None, description="Search keyword for 'search' scope")
    speaker: Literal["therapist", "client", "both"] = Field(
        default="both", description="Filter by speaker"
    )


def create_listen_tool(transcript_path: Path) -> StructuredTool:
    """Create the listen tool.

    Args:
        transcript_path: Path to transcript.jsonl

    Returns:
        LangChain StructuredTool
    """

    def listen_func(
        scope: str,
        limit: int = 5,
        start_turn: int | None = None,
        end_turn: int | None = None,
        keyword: str | None = None,
        speaker: str = "both",
    ) -> str:
        """Read conversation history from transcript.

        Args:
            scope: What to retrieve (recent/all/range/search)
            limit: Number of turns for 'recent'
            start_turn: Start turn for 'range'
            end_turn: End turn for 'range'
            keyword: Search keyword for 'search'
            speaker: Filter by speaker (therapist/client/both)

        Returns:
            Formatted conversation history
        """
        if not transcript_path.exists():
            return "No conversation history available yet."

        # Read transcript with shared lock
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

        if not turns:
            return "No conversation history available yet."

        # Filter by speaker
        if speaker != "both":
            turns = [t for t in turns if t.speaker == speaker]

        # Apply scope
        if scope == "recent":
            selected_turns = turns[-limit:] if limit > 0 else turns
        elif scope == "all":
            selected_turns = turns
        elif scope == "range":
            start = start_turn if start_turn is not None else 0
            end = end_turn if end_turn is not None else len(turns)
            selected_turns = turns[start:end]
        elif scope == "search":
            if not keyword:
                return "Search scope requires a keyword."
            selected_turns = [
                t for t in turns if keyword.lower() in t.content.lower()
            ]
        else:
            return f"Unknown scope: {scope}"

        if not selected_turns:
            return "No turns found matching the criteria."

        # Format output
        result = []
        for i, turn in enumerate(selected_turns):
            turn_idx = turns.index(turn)
            result.append(f"[Turn {turn_idx}] {turn.speaker.upper()}: {turn.content}")

        return "\n\n".join(result)

    return StructuredTool.from_function(
        func=listen_func,
        name="listen",
        description="Read conversation history from the transcript",
        args_schema=ListenInput,
    )
