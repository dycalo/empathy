"""Emotion state tool - client emotion tracking (client only)."""

from __future__ import annotations

import fcntl
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from empathy.storage.state import read_state


class EmotionStateInput(BaseModel):
    """Input schema for emotion_state tool."""

    action: Literal["update", "read", "history"] = Field(
        description="Action: update current state, read latest, or view history"
    )
    primary_emotion: str | None = Field(
        default=None, description="Primary emotion (e.g., anxious, sad, angry)"
    )
    intensity: int | None = Field(
        default=None, ge=1, le=10, description="Emotion intensity (1-10)"
    )
    triggers: list[str] | None = Field(
        default=None, description="What triggered this emotion"
    )
    physical_sensations: list[str] | None = Field(
        default=None, description="Physical sensations experienced"
    )
    thoughts: str | None = Field(
        default=None, description="Thoughts associated with this emotion"
    )


def create_emotion_state_tool(dialogue_dir: Path) -> StructuredTool:
    """Create the emotion_state tool (client only).

    Args:
        dialogue_dir: Path to dialogue directory

    Returns:
        LangChain StructuredTool
    """

    def emotion_state_func(
        action: str,
        primary_emotion: str | None = None,
        intensity: int | None = None,
        triggers: list[str] | None = None,
        physical_sensations: list[str] | None = None,
        thoughts: str | None = None,
    ) -> str:
        """Manage emotional state tracking.

        Args:
            action: Action to perform (update/read/history)
            primary_emotion: Primary emotion
            intensity: Intensity 1-10
            triggers: Emotion triggers
            physical_sensations: Physical sensations
            thoughts: Associated thoughts

        Returns:
            Result message
        """
        state_dir = dialogue_dir / ".empathy" / "client" / "emotion-states"
        state_dir.mkdir(parents=True, exist_ok=True)

        current_path = state_dir / "current.json"
        history_path = state_dir / "history.jsonl"
        state_path = dialogue_dir / ".empathy" / "state.json"

        if action == "update":
            if not primary_emotion:
                return "Primary emotion is required for updating state."
            if intensity is None:
                return "Intensity is required for updating state."

            # Get current turn number
            state = read_state(state_path)
            turn_number = state.get("turn_number", 0)

            emotion_state = {
                "timestamp": datetime.now(UTC).isoformat(),
                "turn_number": turn_number,
                "primary_emotion": primary_emotion,
                "intensity": intensity,
                "triggers": triggers or [],
                "physical_sensations": physical_sensations or [],
                "thoughts": thoughts,
                "secondary_emotions": [],
            }

            # Write current state
            current_path.write_text(json.dumps(emotion_state, indent=2, ensure_ascii=False))

            # Append to history with exclusive lock
            with history_path.open("a") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    f.write(json.dumps(emotion_state, ensure_ascii=False) + "\n")
                    f.flush()
                    os.fsync(f.fileno())
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)

            return f"Emotion state updated: {primary_emotion} (intensity: {intensity}/10)"

        elif action == "read":
            if not current_path.exists():
                return "No current emotion state recorded."

            return current_path.read_text()

        elif action == "history":
            if not history_path.exists():
                return "No emotion history available."

            states = []
            with history_path.open("r") as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                try:
                    for line in f:
                        stripped = line.strip()
                        if stripped:
                            state = json.loads(stripped)
                            thoughts_preview = (
                                state.get("thoughts", "N/A")[:50]
                                if state.get("thoughts")
                                else "N/A"
                            )
                            states.append(
                                f"[Turn {state['turn_number']}] {state['primary_emotion']} "
                                f"({state['intensity']}/10): {thoughts_preview}"
                            )
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)

            # Return last 10 states
            return "\n".join(states[-10:]) if states else "No emotion history available."

        else:
            return f"Unknown action: {action}"

    return StructuredTool.from_function(
        func=emotion_state_func,
        name="emotion_state",
        description="Track and manage emotional states (client only)",
        args_schema=EmotionStateInput,
    )
